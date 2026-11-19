"""Public partner candidates and scoped, audited commercial follow-up."""
import hashlib
import re
from datetime import date, datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from flask import abort, current_app, flash, g, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from werkzeug.routing import BuildError

from app.extensions import db
from app.models import ParceiroAgro, ParceiroAgroHistorico
from app.modules.agro.service import can_access_agro_panel, can_edit_agro_panel
from app.modules.chatbot.scope import chat_key
from app.modules.chatbot.topics import normalize
from app.modules.gestao_ti.permissions import can_access_endpoint
from app.shared.access import apply_prefeitura_scope, get_user_prefeitura_id

STATUSES = {'A_ABORDAR':'A abordar', 'CONTATADO':'Contatado', 'RETORNO':'Retorno agendado',
            'NEGOCIACAO':'Em negociação', 'PARCERIA':'Parceria fechada', 'SEM_INTERESSE':'Sem interesse'}


def now():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).replace(tzinfo=None)


def allowed(endpoint, method='GET'):
    edit = endpoint in {'agro_parceiros_importar','agro_parceiro_novo','agro_parceiro_editar'}
    legacy = can_edit_agro_panel(current_user) if edit else can_access_agro_panel(current_user)
    return can_access_endpoint(current_user, 'main.' + endpoint, method, legacy=legacy)


def require(endpoint, method='GET'):
    if not allowed(endpoint, method):
        abort(403)


def scoped():
    return apply_prefeitura_scope(ParceiroAgro.query, current_user, ParceiroAgro.prefeitura_id)


def identity_key(scope, name, city):
    parts = [str(scope), re.sub(r'\W+', '', normalize(name)), re.sub(r'\W+', '', normalize(city))]
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()


def serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='ija-fly-partners-v1')


def preview(partners, sources):
    """Reviewed public results, bound to this authenticated user/access/session."""
    if not allowed('agro_parceiros_listar'):
        return None
    try:
        save_url = url_for('main.agro_parceiros_importar') if allowed('agro_parceiros_importar','POST') else None
        export_url = url_for('main.agro_parceiros_exportar_pesquisa')
        list_url = url_for('main.agro_parceiros_listar')
    except BuildError:
        return None
    rows = []
    for p in partners[:12]:
        rows.append(dict(nome=p['name'][:180], cidade=p['city'][:180], telefone=p['phone'][:100],
                         whatsapp=p['whatsapp'][:100], oportunidade=p['services'][:4000],
                         culturas=p['cultures'][:2000], abordagem=p['approach'][:4000],
                         fontes=[{'url':sources[i-1]['url'], 'title':sources[i-1].get('title','Fonte')[:300]}
                                 for i in p['source_ids'] if 1 <= i <= len(sources)]))
    if not rows:
        return None
    token = serializer().dumps({'scope':chat_key(current_user), 'rows':rows})
    return dict(token=token, rows=[{'name':r['nome'],'city':r['cidade']} for r in rows],
                save_url=save_url, export_url=export_url, list_url=list_url)


def selected_rows():
    if request.content_length and request.content_length > 128000:
        abort(413)
    raw = request.stream.read(128001)
    if len(raw) > 128000:
        abort(413)
    import json
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get('token'),str):
            raise ValueError()
        data = serializer().loads(payload['token'], max_age=86400)
        if data.get('scope') != chat_key(current_user):
            abort(403)
        ids = payload.get('selected')
        rows = data['rows']
        if (not isinstance(ids,list) or not 1 <= len(ids) <= 12
                or any(type(i) is not int or not 0 <= i < len(rows) for i in ids)):
            raise ValueError()
        return [rows[i] for i in sorted(set(ids))]
    except (ValueError, KeyError, TypeError, BadSignature, SignatureExpired):
        abort(400, description='A seleção expirou ou é inválida. Faça uma nova pesquisa e selecione os parceiros.')


def audit(partner, action, old=None, note=''):
    db.session.add(ParceiroAgroHistorico(parceiro_id=partner.id, usuario_id=current_user.id,
        autor=(getattr(current_user,'nome_uvis','') or getattr(current_user,'login','') or 'Usuário')[:180],
        acao=action, status_anterior=old, status_novo=partner.status,
        observacao=note, criado_em=now()))


def save_rows(rows):
    tenant = get_user_prefeitura_id(current_user)
    created, existing = [], []
    for row in rows:
        key = identity_key(tenant, row['nome'], row['cidade'])
        partner = ParceiroAgro.query.filter_by(chave_unica=key).first()
        if partner:
            existing.append(partner.id)
            continue
        # A unique constraint also protects simultaneous imports.
        try:
            with db.session.begin_nested():
                partner = ParceiroAgro(**row, prefeitura_id=tenant, chave_unica=key,
                                      status='A_ABORDAR', criado_em=now(), atualizado_em=now())
                db.session.add(partner)
                db.session.flush()
                audit(partner, 'CADASTRO', note='Incluído para prospecção; contato ainda não realizado.')
            created.append(partner.id)
        except IntegrityError:
            partner = ParceiroAgro.query.filter_by(chave_unica=key).first()
            if not partner:
                raise
            existing.append(partner.id)
    db.session.commit()
    return created, existing


def filtered():
    q = request.args.get('q','').strip()[:200]
    status = request.args.get('status','')
    due = request.args.get('retornos') == '1'
    query = scoped()
    if q:
        pattern = '%' + q + '%'
        query = query.filter(or_(*[col.ilike(pattern) for col in (ParceiroAgro.nome, ParceiroAgro.cidade,
                              ParceiroAgro.telefone, ParceiroAgro.oportunidade, ParceiroAgro.responsavel)]))
    if status:
        if status not in STATUSES:
            abort(400)
        query = query.filter(ParceiroAgro.status == status)
    if due:
        query = query.filter(ParceiroAgro.proximo_contato <= now().date(),
                             ParceiroAgro.status.notin_(['PARCERIA','SEM_INTERESSE']))
    return query, dict(q=q, status=status, retornos='1' if due else '')


def workbook(rows):
    """Application XLSX exporter; keep external text literal, including = formulas."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    book = Workbook()
    sheet = book.active
    sheet.title = 'Parceiros'
    columns = [('nome','Parceiro'),('cidade','Cidade/UF'),('telefone','Telefone'),('whatsapp','WhatsApp'),
               ('oportunidade','Oportunidade / serviços possíveis'),('culturas','Culturas'),
               ('abordagem','Abordagem sugerida'),('status','Situação'),('responsavel','Responsável'),
               ('ultimo_contato','Último contato'),('proximo_contato','Próximo contato'),('fontes','Fontes')]
    sheet.append([label for _,label in columns])
    for item in rows:
        values = dict(item)
        values['status'] = STATUSES.get(values.get('status','A_ABORDAR'),'A abordar')
        values['fontes'] = '\n'.join(s['url'] for s in values.get('fontes',[]))
        sheet.append([values.get(key) or '' for key,_ in columns])
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value,str):
                cell.data_type = 's'
            cell.alignment = Alignment(vertical='top', wrap_text=True)
            if isinstance(cell.value,(date,datetime)):
                cell.number_format = 'dd/mm/yyyy hh:mm' if isinstance(cell.value,datetime) else 'dd/mm/yyyy'
    for cell in sheet[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid',fgColor='174D3C')
    for i,(key,_) in enumerate(columns,1):
        sheet.column_dimensions[get_column_letter(i)].width = 55 if key in {'oportunidade','abordagem','fontes'} else 25
    sheet.freeze_panes = 'A2'
    sheet.auto_filter.ref = sheet.dimensions
    stream = BytesIO()
    book.save(stream)
    stream.seek(0)
    return stream


def download(rows):
    response = send_file(workbook(rows), as_attachment=True,
                         download_name='parceiros-ija-fly.xlsx',
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response.headers['Cache-Control'] = 'private, no-store'
    return response


def register_routes(bp):
    @bp.get('/agro/parceiros', endpoint='agro_parceiros_listar')
    @login_required
    def listing():
        require('agro_parceiros_listar')
        query, filters = filtered()
        page = request.args.get('page',1,type=int)
        pagination = query.order_by(ParceiroAgro.atualizado_em.desc(),ParceiroAgro.id.desc()).paginate(page=max(page or 1,1),per_page=30,error_out=False)
        return render_template('agro_parceiros.html', pagination=pagination, filters=filters,
                               statuses=STATUSES, can_create=allowed('agro_parceiro_novo'),
                               today=now().date())

    @bp.post('/agro/parceiros/importar-pesquisa', endpoint='agro_parceiros_importar')
    @login_required
    def import_search():
        require('agro_parceiros_importar','POST')
        created, existing = save_rows(selected_rows())
        return jsonify(created=len(created), existing=len(existing), url=url_for('main.agro_parceiros_listar'),
                       message=f'{len(created)} parceiro(s) salvo(s). {len(existing)} já estavam cadastrados; acompanhamento preservado.')

    @bp.post('/agro/parceiros/exportar-pesquisa', endpoint='agro_parceiros_exportar_pesquisa')
    @login_required
    def export_search():
        require('agro_parceiros_exportar_pesquisa','POST')
        return download(selected_rows())

    @bp.get('/agro/parceiros/excel', endpoint='agro_parceiros_exportar')
    @login_required
    def export_saved():
        require('agro_parceiros_exportar')
        query, _ = filtered()
        rows = query.order_by(ParceiroAgro.nome).limit(5001).all()
        if len(rows)>5000:
            abort(400, description='Filtre a lista para exportar até 5.000 parceiros por arquivo.')
        return download([{c.name:getattr(row,c.name) for c in ParceiroAgro.__table__.columns} for row in rows])

    @bp.route('/agro/parceiros/novo',methods=['GET','POST'],endpoint='agro_parceiro_novo')
    @login_required
    def create():
        require('agro_parceiro_novo',request.method)
        if request.method == 'POST':
            values = form_values()
            values.update(fontes=[], culturas='', abordagem='')
            created, existing = save_rows([values])
            flash('Parceiro cadastrado.' if created else 'Esta unidade já está cadastrada.','success')
            return redirect(url_for('main.agro_parceiro_detalhe',partner_id=(created or existing)[0]))
        return render_template('agro_parceiro.html',partner=None,statuses=STATUSES,editable=True)

    @bp.get('/agro/parceiros/<int:partner_id>',endpoint='agro_parceiro_detalhe')
    @login_required
    def detail(partner_id):
        require('agro_parceiro_detalhe')
        partner = scoped().filter_by(id=partner_id).first_or_404()
        return render_template('agro_parceiro.html',partner=partner,statuses=STATUSES,
                               editable=allowed('agro_parceiro_editar','POST'))

    @bp.post('/agro/parceiros/<int:partner_id>/atualizar',endpoint='agro_parceiro_editar')
    @login_required
    def edit(partner_id):
        require('agro_parceiro_editar','POST')
        partner = scoped().filter_by(id=partner_id).first_or_404()
        values = form_values()
        status = request.form.get('status')
        if status not in STATUSES:
            abort(400)
        try:
            version = int(request.form.get('versao',''))
            next_date = date.fromisoformat(request.form['proximo_contato']) if request.form.get('proximo_contato') else None
        except ValueError:
            abort(400)
        if status == 'RETORNO' and not next_date:
            abort(400, description='Informe a data do próximo contato para agendar um retorno.')
        responsible = request.form.get('responsavel','').strip()
        note = request.form.get('observacao','').strip()
        if len(responsible)>180 or len(note)>4000:
            abort(400)
        old_status = partner.status
        contact = request.form.get('contato_realizado') == '1' or (status == 'CONTATADO' and old_status != status)
        changes = [key for key,value in values.items() if getattr(partner,key) != value]
        values.update(status=status, responsavel=responsible, proximo_contato=next_date,
                      ultimo_contato=now() if contact else partner.ultimo_contato,
                      chave_unica=identity_key(partner.prefeitura_id,values['nome'],values['cidade']),
                      versao=version+1, atualizado_em=now())
        try:
            count = db.session.execute(update(ParceiroAgro).where(ParceiroAgro.id==partner.id,
                ParceiroAgro.versao==version).values(**values).execution_options(synchronize_session=False)).rowcount
            if count != 1:
                db.session.rollback()
                abort(409,description='Outra pessoa atualizou este parceiro. Recarregue antes de salvar.')
            db.session.refresh(partner)
            audit(partner, 'CONTATO' if contact else 'ATUALIZACAO', old_status,
                  note + ('\nCampos corrigidos: '+', '.join(changes) if changes else ''))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409,description='Já existe um parceiro com esse nome e cidade.')
        flash('Acompanhamento salvo.','success')
        return redirect(url_for('main.agro_parceiro_detalhe',partner_id=partner.id))


def form_values():
    fields = {'nome':180,'cidade':180,'telefone':100,'whatsapp':100,'oportunidade':4000}
    result = {key:request.form.get(key,'').strip() for key in fields}
    if not result['nome'] or not result['cidade'] or any(len(result[k])>limit for k,limit in fields.items()):
        abort(400,description='Informe nome e cidade e respeite o tamanho dos campos.')
    return result
