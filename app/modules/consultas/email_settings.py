"""Municipal destination settings; SMTP credentials stay in the environment."""
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError

from app.extensions import db
from app.models import Prefeitura, Usuario, PrefeituraEmailConfig, ConsultaEmailEnvio, ConfiguracaoSmtp
from app.shared.access import is_admin_global_user, is_covisa_user
from app.modules.configuracoes.service import prefeitura_permitida, require_access, can_view_all_settings, can_access_settings
from app.modules.configuracoes.routes import _csrf_token, _validate_post
from . import mail
from app.shared import mail as shared_mail


def recipient_cities(user):
    query = Prefeitura.query
    if not is_admin_global_user(user):
        query = query.join(Usuario, Usuario.prefeitura_id == Prefeitura.id).filter(Usuario.id == user.id)
    return query.order_by(Prefeitura.nome)


def recipient_config(user, prefeitura_id):
    city = recipient_cities(user).filter(Prefeitura.id == prefeitura_id).first_or_404()
    setting = db.session.get(PrefeituraEmailConfig, city.id)
    return city, setting


def register_routes(bp):
    @bp.route('/configuracoes/smtp', methods=['GET', 'POST'], endpoint='configuracoes_smtp')
    @login_required
    def smtp_settings():
        if not is_admin_global_user(current_user):
            abort(403)
        row = db.session.get(ConfiguracaoSmtp, 1)
        erro = None
        if request.method == 'POST':
            _validate_post(None)
            form = request.form
            host = form.get('host', '').strip()[:200]; remetente = form.get('remetente', '').strip()[:254]
            usuario = form.get('usuario', '').strip()[:254]; senha = form.get('senha', '')
            seguranca = form.get('seguranca', 'starttls'); ativo = form.get('ativo') == 'on'
            try:
                porta = int(form.get('porta', '587'))
            except ValueError:
                porta = 0
            if not host or not shared_mail.valid_address(remetente) or not 1 <= porta <= 65535 or seguranca not in {'starttls', 'ssl'}:
                erro = 'Informe servidor, porta válida, segurança e um remetente válido.'
            else:
                if row is None:
                    row = ConfiguracaoSmtp(id=1); db.session.add(row)
                row.host, row.porta, row.seguranca, row.remetente, row.usuario, row.ativo = host, porta, seguranca, remetente, usuario or None, ativo
                if senha:
                    row.senha_cifrada = shared_mail.cifrar(senha)
                row.atualizado_por_id = current_user.id
                db.session.commit()
                flash('Servidor de e-mail salvo. Use "Enviar e-mail de teste" para confirmar.', 'success')
                return redirect(url_for('main.configuracoes_smtp'), code=303)
        conf = shared_mail.settings()
        return render_template('configuracoes_smtp.html', row=row, erro=erro, conf=conf, config_csrf_token=_csrf_token(),
                               tem_senha=bool(row and row.senha_cifrada))

    @bp.post('/configuracoes/smtp/testar', endpoint='configuracoes_smtp_testar')
    @login_required
    def smtp_test():
        if not is_admin_global_user(current_user):
            abort(403)
        _validate_post(None)
        destinatario = request.form.get('destinatario', '').strip()
        if not shared_mail.valid_address(destinatario):
            flash('Informe um e-mail de destino válido para o teste.', 'danger')
        else:
            try:
                html = shared_mail.render_html(title='Teste do servidor de e-mail', eyebrow='Configuração',
                                        intro='Este é um e-mail de teste enviado pelo IJA System. Se você o recebeu, os relatórios e alertas por e-mail estão operacionais.',
                                        lines=[('Servidor', shared_mail.settings()['host']), ('Origem', 'configuração do sistema' if shared_mail.settings()['source'] == 'sistema' else 'variáveis do ambiente')])
                shared_mail.send([destinatario], 'IJA System — teste de e-mail', 'Teste do servidor de e-mail do IJA System.', html=html)
                flash(f'E-mail de teste enviado para {destinatario}.', 'success')
            except Exception as exc:
                flash(f'Falha no envio: {str(exc)[:300]}', 'danger')
        return redirect(url_for('main.configuracoes_smtp'), code=303)

    @bp.route('/configuracoes/email/<int:prefeitura_id>', methods=['GET', 'POST'], endpoint='configuracoes_email')
    @login_required
    def settings(prefeitura_id):
        if not (can_view_all_settings(current_user) or is_covisa_user(current_user)):
            abort(403)
        city = prefeitura_permitida(current_user, prefeitura_id)
        require_access(current_user, write=request.method == 'POST')
        setting = db.session.get(PrefeituraEmailConfig, prefeitura_id)
        error, status = None, 200
        address = setting.destinatario if setting else ''
        if request.method == 'POST':
            if request.content_length and request.content_length > 4096:
                abort(413)
            _validate_post(prefeitura_id)
            address = request.form.get('destinatario', '').strip()
            try:
                # Empty explicitly disables this municipality's email destination.
                if address:
                    mail.validate_recipient(address)
                version_text = request.form.get('versao', '')
                if not version_text.isascii() or not version_text.isdecimal() or len(version_text) > 10:
                    raise ValueError('Versão inválida. Recarregue a página antes de salvar.')
                version = int(version_text)
                if version != (setting.versao if setting else 0):
                    raise StaleDataError()
                if setting is None:
                    setting = PrefeituraEmailConfig(prefeitura_id=prefeitura_id)
                    db.session.add(setting)
                setting.destinatario = address
                setting.atualizado_por_id = current_user.id
                db.session.commit()
                flash('E-mail dos relatórios atualizado para esta prefeitura.', 'success')
                return redirect(url_for('main.configuracoes_email', prefeitura_id=prefeitura_id), code=303)
            except (StaleDataError, IntegrityError):
                db.session.rollback()
                error, status = 'Outra pessoa alterou esta configuração. Recarregue antes de salvar.', 409
            except ValueError as exc:
                db.session.rollback()
                error, status = str(exc), 400
            except SQLAlchemyError:
                db.session.rollback()
                error, status = 'Não foi possível salvar. Tente novamente.', 503
        history = db.session.query(ConsultaEmailEnvio, Usuario.login).join(Usuario, Usuario.id == ConsultaEmailEnvio.usuario_id).filter(
            ConsultaEmailEnvio.prefeitura_id == prefeitura_id).order_by(ConsultaEmailEnvio.criado_em.desc()).limit(20).all()
        return render_template('configuracoes_email.html', prefeitura=city, setting=setting,
            can_configurar_email=can_access_settings(current_user, write=True),
            destinatario=address, erro=error, history=history, email_available=mail.available(),
            config_csrf_token=_csrf_token()), status
