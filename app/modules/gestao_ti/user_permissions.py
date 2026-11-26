"""Individual access selections; never changes account identity or record scope."""
from uuid import uuid4

from flask import abort, current_app
from sqlalchemy import delete, or_, update
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import Forbidden

from app.extensions import db
from app.models import (Usuario, CentralTiUsuarioConfiguracao, CentralTiUsuarioSelecao,
                        CentralTiUsuarioAuditoria)
from app.modules.gestao_ti.catalog import CATALOG, PROFILE_CODES
from app.modules.gestao_ti.permissions import invalidate_request_permissions, profile_code
from app.modules.gestao_ti.permission_versions import submitted_permissions, stored_codes
from app.modules.gestao_ti.service import (ConfigurationConflict, _now, _selection_snapshot,
                                         can_manage_central_ti, load_configurations, validate_configurations)


def enabled():
    return bool(current_app.config.get("CENTRAL_TI_ENABLED")
                and current_app.config.get("CENTRAL_TI_USER_PERMISSIONS_ENABLED"))


def require_editor(actor):
    if not enabled():
        abort(404)
    if not can_manage_central_ti(actor):
        raise Forbidden()


def target_user(user_id):
    user = db.session.get(Usuario, user_id)
    if user is None:
        abort(404)
    # The technical recovery account remains outside the editable catalogue,
    # just as Dev is excluded from the existing profile editor.
    if profile_code(user) == "dev":
        raise Forbidden(description="A conta Dev não é editável nesta central.")
    if profile_code(user) not in PROFILE_CODES:
        raise ValueError("O tipo atual desta conta precisa ser regularizado antes de personalizar os acessos.")
    return user


def _identity(user):
    role = profile_code(user)
    labels = {item["id"]: item["name"] for item in CATALOG["profiles"]}
    return {"id": user.id, "name": user.nome_uvis or user.login, "login": user.login,
            "role": role, "role_label": labels.get(role, role),
            "prefeitura_id": user.prefeitura_id, "regiao": user.regiao or ""}


def search_users(actor, query="", page=1):
    require_editor(actor)
    if type(page) is not int or not 1 <= page <= 100000:
        raise ValueError("Página inválida.")
    if not isinstance(query, str) or len(query) > 100:
        raise ValueError("Busca inválida.")
    rows = Usuario.query.filter(Usuario.tipo_usuario != "dev")
    if query.strip():
        # Escape wildcard characters so the search is a literal name/login.
        term = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = rows.filter(or_(Usuario.nome_uvis.ilike(f"%{term}%", escape="\\"),
                               Usuario.login.ilike(f"%{term}%", escape="\\")))
    size = 30
    found = rows.order_by(Usuario.nome_uvis.asc(), Usuario.id.asc()).offset((page - 1) * size).limit(size + 1).all()
    return {"users": [_identity(user) for user in found[:size]], "page": page, "has_more": len(found) > size}


def user_configuration(actor, user_id):
    require_editor(actor)
    user = target_user(user_id)
    row = db.session.get(CentralTiUsuarioConfiguracao, user.id)
    base = next(state for state in load_configurations() if state["id"] == profile_code(user))
    if row is None:
        selection = {"areas": base["areas"], "permissions": base["permissions"]}
    else:
        selection = _selection_snapshot(CentralTiUsuarioSelecao.query.filter_by(usuario_id=user.id).all())
    return {"user": _identity(user), "version": row.versao if row else 0,
            "configured": row is not None, "source": "user_configuration" if row else base["source"],
            "nome_acesso": row.nome_acesso if row else "", **selection,
            "profile_template": {"areas": base["areas"], "permissions": base["permissions"]}}


def save_user_configuration(actor, user_id, payload, permission_schema_version=None):
    require_editor(actor)
    user = target_user(user_id)
    if not isinstance(payload, dict) or set(payload) != {"version", "areas", "permissions", "nome_acesso"}:
        raise ValueError("Formato de acesso individual inválido.")
    label = payload["nome_acesso"]
    if not isinstance(label, str) or len(label) > 80 or any(ord(char) < 32 for char in label):
        raise ValueError("Informe um nome de acesso de até 80 caracteres.")
    change = validate_configurations({"profiles": [{"id": profile_code(user),
        "version": payload["version"], "areas": payload["areas"], "permissions": payload["permissions"]}]})[0]
    # Keep the permission management capability exclusive to its existing roles.
    after = {"areas": change["areas"], "permissions": submitted_permissions(change["permissions"], permission_schema_version), "nome_acesso": label.strip()}
    expected = change["version"]
    try:
        row = db.session.get(CentralTiUsuarioConfiguracao, user.id)
        if (row.versao if row else 0) != expected:
            raise ConfigurationConflict("Os acessos deste usuário mudaram. Recarregue e revise antes de salvar.")
        before = user_configuration(actor, user.id)
        before = {key: before[key] for key in ("areas", "permissions", "nome_acesso")}
        if row is None or before != after:
            now = _now()
            if row is None:
                db.session.add(CentralTiUsuarioConfiguracao(usuario_id=user.id, versao=1,
                    nome_acesso=after["nome_acesso"], atualizado_em=now, atualizado_por_id=actor.id))
                db.session.flush()
            else:
                changed = db.session.execute(update(CentralTiUsuarioConfiguracao)
                    .where(CentralTiUsuarioConfiguracao.usuario_id == user.id,
                           CentralTiUsuarioConfiguracao.versao == expected)
                    .values(versao=expected + 1, nome_acesso=after["nome_acesso"], atualizado_em=now,
                            atualizado_por_id=actor.id).execution_options(synchronize_session=False))
                if changed.rowcount != 1:
                    raise ConfigurationConflict("Outra edição foi salva. Recarregue os acessos do usuário.")
            db.session.execute(delete(CentralTiUsuarioSelecao).where(CentralTiUsuarioSelecao.usuario_id == user.id))
            db.session.add_all([CentralTiUsuarioSelecao(usuario_id=user.id, codigo=code)
                for code in stored_codes(after["areas"], after["permissions"])])
            db.session.add(CentralTiUsuarioAuditoria(lote=str(uuid4()), usuario_alvo_id=user.id,
                usuario_id=actor.id, usuario_login=(actor.login or "")[:50],
                versao_anterior=expected, versao_nova=expected + 1, antes=before, depois=after, criado_em=now))
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ConfigurationConflict("Outra edição foi salva. Recarregue os acessos do usuário.") from exc
    except Exception:
        db.session.rollback()
        raise
    db.session.expire_all()
    invalidate_request_permissions()
    return user_configuration(actor, user.id)
