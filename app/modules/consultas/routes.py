from functools import wraps
import smtplib
import threading
from uuid import UUID
from flask import abort, current_app, jsonify, render_template, request, send_file
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from app.extensions import db
from app.models import ConsultaSalva, ConsultaEmailEnvio
from app.modules.gestao_ti.permissions import route_access
from app.modules.relatorios.service import can_access_relatorios_menu
from . import service, exporters, mail
from .email_settings import recipient_cities, recipient_config


PDF_SLOT = threading.BoundedSemaphore(1)

def build_pdf(result):
    if not PDF_SLOT.acquire(blocking=False):
        raise service.QueryError("Há um PDF sendo gerado. Aguarde e tente novamente.")
    try: return exporters.pdf(result, current_user)
    finally: PDF_SLOT.release()

def guarded(fn):
    @wraps(fn)
    @login_required
    def run(*args, **kwargs):
        if not route_access(current_user, can_access_relatorios_menu(current_user)): abort(403)
        if request.content_length and request.content_length > 32768:
            return jsonify(error='A definição da consulta é muito extensa.'), 413
        try: return fn(*args, **kwargs)
        except service.QueryError as exc:
            db.session.rollback(); return jsonify(error=str(exc)), 400
        except StaleDataError:
            db.session.rollback(); return jsonify(error='Esta consulta foi alterada em outra aba. Recarregue o catálogo.'),409
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception('Falha na consulta personalizada.')
            return jsonify(error='A consulta não foi concluída. Tente restringir os filtros ou executar novamente.'),503
    return run


def body():
    data=request.get_json(silent=True)
    if not isinstance(data,dict): raise service.QueryError('Informe uma definição de consulta válida.')
    return data


def owned():
    return ConsultaSalva.query.filter_by(usuario_id=current_user.id, prefeitura_id=current_user.prefeitura_id)


def register_routes(bp):
    @bp.get('/relatorios/consultas', endpoint='consultas')
    @guarded
    def page():
        return render_template('consultas.html', catalog=service.catalog(), facets=service.facets(current_user),
            email_available=mail.available(), prefeituras=recipient_cities(current_user).all())

    @bp.get('/relatorios/consultas/email-destino', endpoint='consultas_email_destino')
    @guarded
    def email_destination():
        city, setting = recipient_config(current_user, request.args.get('prefeitura_id', type=int))
        if not setting or not setting.destinatario:
            return jsonify(error='Cadastre o e-mail em Configurações → E-mail dos relatórios desta prefeitura.'), 400
        return jsonify(prefeitura_id=city.id, prefeitura=city.nome, destinatario=setting.destinatario, versao=setting.versao)

    @bp.post('/relatorios/consultas/executar', endpoint='consultas_executar')
    @guarded
    def execute(): return jsonify(service.execute(current_user,body()))

    @bp.route('/relatorios/consultas/catalogo', methods=['GET','POST'], endpoint='consultas_catalogo')
    @guarded
    def definitions():
        if request.method=='GET':
            return jsonify(items=[dict(id=r.id, nome=r.nome, versao=r.versao, definicao=r.definicao) for r in owned().order_by(ConsultaSalva.nome).all()])
        data=body();spec=service.validate(data.get('definicao'))
        name=str(data.get('nome','')).strip()
        if not name or len(name)>100: raise service.QueryError('Nome da consulta: de 1 a 100 caracteres.')
        if data.get('id'):
            row=owned().filter_by(id=data['id']).first_or_404()
            if data.get('versao')!=row.versao: return jsonify(error='Consulta alterada em outra aba. Recarregue o catálogo.'),409
            row.nome=name;row.definicao=spec
        else:
            if owned().count()>=100: raise service.QueryError('Seu catálogo atingiu 100 consultas. Exclua uma antes de cadastrar outra.')
            row=ConsultaSalva(usuario_id=current_user.id,prefeitura_id=current_user.prefeitura_id,nome=name,definicao=spec)
            db.session.add(row)
        db.session.commit();return jsonify(id=row.id,versao=row.versao)

    @bp.delete('/relatorios/consultas/catalogo/<int:query_id>',endpoint='consultas_excluir')
    @guarded
    def delete(query_id):
        row=owned().filter_by(id=query_id).first_or_404();db.session.delete(row);db.session.commit();return jsonify(success=True)

    @bp.post('/relatorios/consultas/exportar/<formato>',endpoint='consultas_exportar')
    @guarded
    def export(formato):
        if formato not in {'pdf','excel'}:abort(404)
        result=service.execute(current_user,body())
        if formato=='excel':return send_file(exporters.excel(result),as_attachment=True,download_name='consulta.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        return send_file(build_pdf(result),as_attachment=True,download_name='consulta.pdf',mimetype='application/pdf')

    @bp.post('/relatorios/consultas/email',endpoint='consultas_email')
    @guarded
    def email():
        data=body()
        if not mail.available():return jsonify(error='Envio por e-mail ainda não configurado. Use PDF ou Excel.'),503
        try:
            request_id = str(UUID(data.get('envio_id', '')))
        except (ValueError, TypeError, AttributeError):
            raise service.QueryError('Identificador do envio inválido. Abra a confirmação novamente.')
        previous = db.session.get(ConsultaEmailEnvio, request_id)
        if previous:
            if previous.usuario_id != current_user.id: abort(404)
            return jsonify(error='Este envio já foi registrado. Confira o recebimento e o histórico antes de iniciar outro.'), 409
        if type(data.get('prefeitura_id')) is not int: raise service.QueryError('Selecione uma prefeitura para enviar.')
        city, setting = recipient_config(current_user, data['prefeitura_id'])
        if not setting or not setting.destinatario:
            raise service.QueryError('Cadastre o destinatário nas configurações desta prefeitura.')
        if data.get('destinatario') != setting.destinatario or data.get('versao') != setting.versao:
            return jsonify(error='O destinatário foi alterado. Abra a confirmação novamente.'),409
        result=service.execute(current_user,data.get('definicao'))
        if str(city.id) != result['spec']['filters'].get('prefeitura'):
            raise service.QueryError('Selecione a prefeitura nos filtros antes de enviar.')
        if any(pid != city.id for pid in result['prefeitura_ids']): abort(403)
        entry = ConsultaEmailEnvio(id=request_id, prefeitura_id=city.id, usuario_id=current_user.id,
            destinatario=setting.destinatario, estado='preparando')
        db.session.add(entry)
        try: db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify(error='Este envio já foi iniciado. Confira o histórico.'),409
        try:
            content = build_pdf(result).getvalue()
            if len(content) > 10*1024*1024: raise service.QueryError('O PDF excede 10 MB. Restrinja os filtros.')
        except Exception:
            entry.estado='falha';db.session.commit()
            raise
        entry.estado='enviando';db.session.commit()
        try:mail.send_report(entry.destinatario,content)
        except (ValueError,OSError,smtplib.SMTPException):
            entry.estado='incerto';db.session.commit()
            current_app.logger.warning('Não foi possível confirmar o envio SMTP da consulta.')
            return jsonify(error='Não foi possível confirmar o envio. Confira o recebimento antes de tentar novamente.'),502
        entry.estado='aceito'
        try: db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception('SMTP aceitou o PDF, mas a confirmação não foi gravada no histórico.')
            return jsonify(error='O servidor de e-mail aceitou o PDF, mas o histórico não foi atualizado. Confira o recebimento antes de repetir.'),502
        return jsonify(success=True,message='Relatório aceito pelo servidor de e-mail para entrega.')
