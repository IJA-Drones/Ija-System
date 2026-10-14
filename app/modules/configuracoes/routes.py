import secrets

from flask import abort, current_app, flash, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required
from requests import RequestException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError

from app.extensions import db
from app.models import PrefeituraDocumentoConfig, PrefeituraDocumentoHistorico
from app.shared.access import is_dev_user
from app.shared.csrf_security import CSRF_SESSION_KEY
from app.shared.skybox import SkyboxError, is_skybox_path, stream_skybox_file
from .service import (
    ConfigConflictError, ConfigValidationError, local_image_path, prefeitura_permitida,
    prefeituras_permitidas, require_access, save_config, snapshot,
)


def _csrf_token():
    if not session.get(CSRF_SESSION_KEY):
        session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)
    return session[CSRF_SESSION_KEY]


def _validate_post(prefeitura_id):
    expected = session.get(CSRF_SESSION_KEY)
    supplied = request.form.get("_csrf_token", "")
    if not isinstance(expected, str) or not secrets.compare_digest(expected.encode(), supplied.encode()):
        abort(403, description="Recarregue a página antes de salvar.")
    # Reject conflicting/repeated scope fields instead of silently trusting them.
    supplied_ids = request.args.getlist("prefeitura_id") + request.form.getlist("prefeitura_id")
    if any(value != str(prefeitura_id) for value in supplied_ids):
        abort(403)


def register_routes(bp):
    @bp.after_request
    def documentos_config_no_store(response):
        if (request.endpoint or "").startswith("main.configuracoes") or response.mimetype == "application/pdf":
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @bp.route("/configuracoes", endpoint="configuracoes")
    @login_required
    def configuracoes():
        require_access(current_user)
        prefeituras = prefeituras_permitidas(current_user).all()
        if not is_dev_user(current_user) and prefeituras:
            return redirect(url_for("main.configuracoes_documentos", prefeitura_id=prefeituras[0].id))
        return render_template("configuracoes_documentos.html", prefeitura=None, prefeituras=prefeituras)

    @bp.route("/configuracoes/documentos/<int:prefeitura_id>", methods=["GET", "POST"], endpoint="configuracoes_documentos")
    @login_required
    def configuracoes_documentos(prefeitura_id):
        prefeitura = prefeitura_permitida(current_user, prefeitura_id)
        erro, status = None, 200
        if request.method == "POST":
            # Limit the multipart request as well as the actual image stream.
            if request.content_length and request.content_length > 6 * 1024 * 1024:
                abort(413, description="Envie uma imagem de até 5 MB.")
            _validate_post(prefeitura_id)
            try:
                save_config(current_user, prefeitura_id, request.form, request.files.get("imagem"))
            except ConfigValidationError as exc:
                erro, status = str(exc), 400
            except (ConfigConflictError, IntegrityError, StaleDataError):
                db.session.rollback()
                erro, status = "Outra pessoa alterou esta configuração. Recarregue a página antes de salvar.", 409
            except (SkyboxError, RequestException, OSError, SQLAlchemyError):
                db.session.rollback()
                current_app.logger.exception("Falha ao salvar configuração de documentos da prefeitura %s.", prefeitura_id)
                erro, status = "Não foi possível salvar. A configuração anterior foi preservada. Tente novamente.", 503
            else:
                flash("Configurações de documentos salvas.", "success")
                return redirect(url_for("main.configuracoes_documentos", prefeitura_id=prefeitura_id), code=303)
        config = db.session.get(PrefeituraDocumentoConfig, prefeitura_id)
        form = snapshot(config)
        if status == 400:
            # Keep user edits after validation, without trusting invalid numeric values.
            for key in ("ativo", "identificar_usuario"):
                form[key] = request.form.get(key) == "1"
            for key, low, high in (("opacidade", 5, 30), ("largura_percentual", 25, 80)):
                value = request.form.get(key, "")
                if value.isdecimal() and len(value) < 4 and low <= int(value) <= high:
                    form[key] = int(value)
        return render_template(
            "configuracoes_documentos.html", prefeitura=prefeitura,
            prefeituras=prefeituras_permitidas(current_user).all() if is_dev_user(current_user) else [],
            config=config, form=form, erro=erro, config_csrf_token=_csrf_token(),
            historico=PrefeituraDocumentoHistorico.query.filter_by(prefeitura_id=prefeitura_id)
                .order_by(PrefeituraDocumentoHistorico.id.desc()).limit(20).all(),
        ), status

    @bp.route("/configuracoes/documentos/<int:prefeitura_id>/imagem", endpoint="configuracoes_documentos_imagem")
    @login_required
    def configuracoes_documentos_imagem(prefeitura_id):
        prefeitura_permitida(current_user, prefeitura_id)
        config = db.session.get(PrefeituraDocumentoConfig, prefeitura_id)
        if not config or not config.imagem_path:
            abort(404)
        try:
            if is_skybox_path(config.imagem_path):
                return stream_skybox_file(config.imagem_path)
            return send_file(local_image_path(config.imagem_path), mimetype="image/png", conditional=False)
        except FileNotFoundError:
            abort(404)
        except (SkyboxError, RequestException, OSError, ConfigValidationError):
            abort(503, description="Imagem temporariamente indisponível.")
