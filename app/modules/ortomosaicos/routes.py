import re
from functools import wraps

import click
from flask import Response, abort, current_app, jsonify, render_template, request, stream_with_context
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Ortomosaico, Prefeitura
from app.shared import skybox
from app.shared.access import can_access_prefeitura, normalize_role
from . import service


def restricted(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        # Deliberately fixed: Central TI must not grant this feature to other roles.
        if normalize_role(current_user.tipo_usuario) not in {'dev', 'diretor'}:
            abort(403)
        return fn(*args, **kwargs)
    return wrapped


def get_record(oid):
    row = db.session.get(Ortomosaico, oid)
    if not row or not can_access_prefeitura(current_user, row.prefeitura_id):
        abort(404)
    return row


def register_routes(bp):
    @bp.get('/ortomosaicos', endpoint='ortomosaicos')
    @restricted
    def index():
        return render_template('ortomosaicos.html', prefeituras=Prefeitura.query.filter_by(ativa=True).order_by(Prefeitura.nome).all(),
                               limite_mb=service.max_bytes() // (1024*1024),
                               limite_pixels=max(0, int(current_app.config.get('ORTHOMOSAIC_MAX_PIXELS', 0))),
                               ortho_google_key=(current_app.config.get('Maps_KEY_FRONT')
                                                 or current_app.config.get('KEY_API_GOOGLE_MAPS') or ''))

    @bp.get('/api/ortomosaicos', endpoint='ortomosaicos_listar')
    @restricted
    def listing():
        query = Ortomosaico.query
        value = request.args.get('prefeitura_id', '')
        if value:
            try:
                prefeitura_id = int(value)
            except ValueError:
                return jsonify(error='Prefeitura inválida.'), 400
            if not can_access_prefeitura(current_user, prefeitura_id):
                abort(403)
            query = query.filter_by(prefeitura_id=prefeitura_id)
        rows = query.order_by(Ortomosaico.criado_em.desc()).limit(100).all()
        return jsonify(items=[service.serialize(row) for row in rows if can_access_prefeitura(current_user, row.prefeitura_id)])

    @bp.post('/api/ortomosaicos', endpoint='ortomosaico_upload')
    @restricted
    def upload():
        if service.max_bytes() and request.content_length and request.content_length > service.max_bytes()+1024*1024:
            return jsonify(error='O arquivo excede o tamanho permitido.'), 413
        try:
            pid = int(request.form.get('prefeitura_id', ''))
            prefeitura = db.session.get(Prefeitura, pid)
            if not prefeitura or not prefeitura.ativa or not can_access_prefeitura(current_user, pid):
                return jsonify(error='Selecione uma prefeitura válida.'), 400
            file = request.files.get('arquivo')
            if not file:
                return jsonify(error='Selecione o arquivo TIF.'), 400
            if request.form.get('tipo') == 'dem' and request.form.get('elevacoes_metros') != '1':
                return jsonify(error='Confirme que as elevações do DEM estão em metros.'), 400
            row = service.create_upload(file, request.form.get('nome'), pid, current_user.id,
                tipo=request.form.get('tipo', 'rgb'), interval=request.form.get('intervalo_m'),
                resolution=request.form.get('resolucao_m'))
            payload = service.serialize(row)
            service.dispatch(row.id)
            return jsonify(item=payload), 202
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Falha no envio do ortomosaico.')
            return jsonify(error='Não foi possível concluir o envio. Confira a conexão com o armazenamento e tente novamente.'), 503

    @bp.get('/api/ortomosaicos/<int:oid>', endpoint='ortomosaico_status')
    @restricted
    def status(oid):
        row = get_record(oid)
        payload = service.serialize(row)
        if row.status in {'pendente', 'processando'}:
            service.dispatch(oid)
        return jsonify(item=payload)

    @bp.post('/api/ortomosaicos/<int:oid>/reprocessar', endpoint='ortomosaico_retry')
    @restricted
    def retry(oid):
        row = get_record(oid)
        if row.status != 'falha':
            return jsonify(error='Este ortomosaico não está aguardando uma nova tentativa.'), 409
        if row.tipo == 'dem':
            from .dem_processor import parameters
            values = request.get_json(silent=True) or {}
            if not isinstance(values, dict):
                return jsonify(error='Parâmetros inválidos.'), 400
            try:
                row.intervalo_m, row.resolucao_m = parameters(values.get('intervalo_m', row.intervalo_m),
                                                            values.get('resolucao_m', row.resolucao_m))
            except ValueError as exc:
                return jsonify(error=str(exc)), 400
        row.status = 'pendente'; row.erro = None; row.atualizado_em = service.now()
        db.session.commit(); service.dispatch(oid)
        return jsonify(item=service.serialize(row)), 202

    @bp.route('/ortomosaicos/<int:oid>/arquivo.tif', methods=['GET', 'HEAD'], endpoint='ortomosaico_arquivo')
    @restricted
    def data(oid):
        row = get_record(oid)
        if row.status != 'pronto' or not row.cog_path:
            abort(404)
        header = request.headers.get('Range')
        if header and not re.fullmatch(r'bytes=\d+-\d*', header):
            return Response(status=416)
        # Never expose remote credentials or publish a Skybox URL to the browser.
        upstream = skybox._request(request.method, skybox.remote_path_from_marker(row.cog_path),
                                  headers={'Range': header} if header else {}, stream=True)
        if upstream.status_code not in (200, 206, 416) or (header and upstream.status_code == 200):
            upstream.close()
            return jsonify(error='Não foi possível carregar esta parte do mapa.'), 502
        headers = {k: upstream.headers[k] for k in ('Content-Length','Content-Range','ETag','Last-Modified') if k in upstream.headers}
        headers.update({'Content-Type':'image/tiff', 'Accept-Ranges':'bytes', 'Cache-Control':'private, no-store',
                        'X-Content-Type-Options':'nosniff'})
        if request.method == 'HEAD' or upstream.status_code == 416:
            upstream.close()
            return Response(status=upstream.status_code, headers=headers)
        def stream():
            try:
                yield from upstream.iter_content(256*1024)
            finally:
                upstream.close()
        result = Response(stream_with_context(stream()), status=upstream.status_code, headers=headers)
        result.call_on_close(upstream.close)
        return result

    def contour_output(oid, field, mime, attachment):
        row = get_record(oid)
        marker = getattr(row, field)
        if row.tipo != 'dem' or row.status != 'pronto' or not marker:
            abort(404)
        upstream = skybox._request(request.method, skybox.remote_path_from_marker(marker), stream=True)
        if upstream.status_code != 200:
            upstream.close()
            return jsonify(error='Não foi possível recuperar o resultado. Tente novamente.'), 502
        headers = {'Content-Type':mime, 'Cache-Control':'private, no-store',
                   'X-Content-Type-Options':'nosniff'}
        if 'Content-Length' in upstream.headers:
            headers['Content-Length'] = upstream.headers['Content-Length']
        if attachment:
            headers['Content-Disposition'] = f'attachment; filename="curvas-nivel-{oid}.jpg"'
        if request.method == 'HEAD':
            upstream.close()
            return Response(headers=headers)
        def stream():
            try:
                yield from upstream.iter_content(256*1024)
            finally:
                upstream.close()
        response = Response(stream_with_context(stream()), headers=headers)
        response.call_on_close(upstream.close)
        return response

    @bp.route('/ortomosaicos/<int:oid>/curvas.geojson', methods=['GET', 'HEAD'], endpoint='ortomosaico_curvas')
    @restricted
    def curves(oid):
        return contour_output(oid, 'curvas_path', 'application/geo+json', False)

    @bp.route('/ortomosaicos/<int:oid>/curvas.jpg', methods=['GET', 'HEAD'], endpoint='ortomosaico_jpeg')
    @restricted
    def jpeg(oid):
        return contour_output(oid, 'jpeg_path', 'image/jpeg', True)

    @bp.cli.command('processar-ortomosaicos')
    @click.option('--limite', default=5, type=click.IntRange(1, 100))
    def process_pending(limite):
        """Resume durable jobs, also suitable for an external worker/scheduler."""
        ids = [r.id for r in Ortomosaico.query.filter(service.eligible()).order_by(Ortomosaico.id).limit(limite)]
        for oid in ids:
            click.echo(f'{oid}: {"pronto" if service.process_one(oid) else "não concluído"}')
