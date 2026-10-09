"""Save role capabilities atomically, retaining independent data scopes."""

from datetime import datetime, timezone
from uuid import uuid4

from flask import current_app
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import Forbidden

from app.extensions import db
from app.models import CentralTiAuditoria, CentralTiPerfilConfiguracao, CentralTiSelecao
from app.modules.gestao_ti.catalog import AREA_CODES, CATALOG, PERMISSION_CODES, PROFILE_CODES
from app.modules.gestao_ti.current_rules import current_rules
from app.shared.access import normalize_role
from app.modules.gestao_ti.permissions import enforcement_enabled


class ConfigurationConflict(ValueError):
    pass


def can_manage_central_ti(user):
    return (
        bool(current_app.config.get("CENTRAL_TI_ENABLED", False))
        and bool(getattr(user, "is_authenticated", False))
        and normalize_role(getattr(user, "tipo_usuario", None)) in {"dev", "gestor_ti"}
    )


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _snapshot(areas=(), permissions=()):
    return {"areas": sorted(areas), "permissions": sorted(permissions)}


def _selection_snapshot(rows):
    return _snapshot(
        (row.codigo[5:] for row in rows if row.codigo.startswith("area:")),
        (row.codigo for row in rows if not row.codigo.startswith("area:")),
    )


def _initialization_query():
    return db.session.query(CentralTiAuditoria.perfil_codigo).filter(
        CentralTiAuditoria.usuario_id.is_(None),
        CentralTiAuditoria.usuario_login == "inicializacao_neon",
        CentralTiAuditoria.versao_anterior == 0,
        CentralTiAuditoria.versao_nova == 1,
    )


def load_configurations():
    profiles = {row.perfil_codigo: row for row in CentralTiPerfilConfiguracao.query.all()}
    selections = {code: [] for code in PROFILE_CODES}
    for row in CentralTiSelecao.query.all():
        if row.perfil_codigo in selections:
            selections[row.perfil_codigo].append(row)
    initialized = {
        code for (code,) in _initialization_query().all()
    }
    states = []
    for profile in CATALOG["profiles"]:
        code = profile["id"]
        row = profiles.get(code)
        snapshot = _selection_snapshot(selections[code])
        seeded_empty = (row is not None and row.versao == 1 and row.atualizado_por_id is None
                        and not selections[code] and code in initialized)
        configured = row is not None and not seeded_empty
        current = current_rules(code)
        notes = dict(current["notes"])
        if configured and enforcement_enabled() and code != "piloto_agro":
            notes.pop("agro", None)
        states.append({
            "id": code, "version": row.versao if row else 0, "configured": configured,
            "source": "saved_configuration" if configured else "current_rules",
            "current_rules": ({**snapshot, "notes": notes}
                              if configured and enforcement_enabled() else current),
            **(snapshot if configured else {"areas": current["areas"], "permissions": current["permissions"]}),
        })
    return states


def build_editor_data():
    # These old catalogue entries have no corresponding operation in the
    # application yet. Keep stored selections compatible, without advertising
    # an operation the user cannot perform.
    unavailable = ["prefeitura.equipes.exportar", "financeiro.bancos.operar", "sistema.tecnico.importar"]
    return {**CATALOG, "states": load_configurations(), "unavailable_permissions": unavailable}


def _codes(value, allowed, name):
    if not isinstance(value, list) or len(value) > len(allowed):
        raise ValueError(f"Seleção inválida de {name}.")
    if any(not isinstance(code, str) or code not in allowed for code in value):
        raise ValueError(f"Opção desconhecida em {name}.")
    if len(value) != len(set(value)):
        raise ValueError(f"Opção repetida em {name}.")
    return set(value)


def validate_configurations(payload):
    if not isinstance(payload, dict) or set(payload) != {"profiles"}:
        raise ValueError("Formato de configuração inválido.")
    profiles = payload["profiles"]
    if not isinstance(profiles, list) or not 1 <= len(profiles) <= len(PROFILE_CODES):
        raise ValueError("Selecione os perfis que deseja salvar.")
    validated = []
    seen = set()
    for profile in profiles:
        if not isinstance(profile, dict) or set(profile) != {"id", "version", "areas", "permissions"}:
            raise ValueError("Formato de perfil inválido.")
        code = profile["id"]
        if not isinstance(code, str) or code not in PROFILE_CODES or code in seen:
            raise ValueError("Tipo de usuário inválido ou repetido.")
        seen.add(code)
        version = profile["version"]
        if type(version) is not int or not 0 <= version < 2147483647:
            raise ValueError("Versão de configuração inválida.")
        areas = _codes(profile["areas"], AREA_CODES, "áreas")
        permissions = _codes(profile["permissions"], PERMISSION_CODES, "permissões")
        if code not in {"dev", "gestor_ti"} and any(p.startswith("sistema.perfis.") for p in permissions):
            raise ValueError("A Central de TI é exclusiva dos perfis Dev e Gestor de TI.")
        for permission in permissions:
            area, module, action = permission.split(".")
            if area not in areas:
                raise ValueError("Habilite a área antes de selecionar suas funções.")
            if action != "consultar" and f"{area}.{module}.consultar" not in permissions:
                raise ValueError("Habilite Consultar antes das demais ações da função.")
        validated.append({"id": code, "version": version, **_snapshot(areas, permissions)})
    # A stable lock order also avoids deadlocks when two editors save several profiles.
    return sorted(validated, key=lambda profile: profile["id"])


def save_configurations(actor, payload):
    if not can_manage_central_ti(actor):
        raise Forbidden()
    changes = validate_configurations(payload)
    batch = str(uuid4())
    saved = []
    try:
        for change in changes:
            code = change["id"]
            expected = change["version"]
            profile = db.session.get(CentralTiPerfilConfiguracao, code)
            if (profile.versao if profile else 0) != expected:
                raise ConfigurationConflict("Outra edição foi salva. Recarregue a central para revisar as opções.")
            before = _selection_snapshot(CentralTiSelecao.query.filter_by(perfil_codigo=code).all())
            after = _snapshot(change["areas"], change["permissions"])
            version = expected
            # A deliberate empty save must be distinguishable from the neutral seed.
            seeded_empty = (profile is not None and expected == 1
                            and profile.atualizado_por_id is None
                            and before == _snapshot()
                            and _initialization_query().filter(CentralTiAuditoria.perfil_codigo == code).first() is not None)
            if profile is None or before != after or seeded_empty:
                version += 1
                now = _now()
                if profile is None:
                    db.session.add(CentralTiPerfilConfiguracao(
                        perfil_codigo=code, versao=version, atualizado_em=now,
                        atualizado_por_id=actor.id,
                    ))
                    # Concurrent first saves are rejected by the primary key.
                    db.session.flush()
                else:
                    result = db.session.execute(
                        update(CentralTiPerfilConfiguracao)
                        .where(CentralTiPerfilConfiguracao.perfil_codigo == code,
                               CentralTiPerfilConfiguracao.versao == expected)
                        .values(versao=version, atualizado_em=now, atualizado_por_id=actor.id)
                        .execution_options(synchronize_session=False)
                    )
                    if result.rowcount != 1:
                        raise ConfigurationConflict("Outra edição foi salva. Recarregue a central para revisar as opções.")
                db.session.execute(delete(CentralTiSelecao).where(CentralTiSelecao.perfil_codigo == code))
                db.session.add_all([
                    CentralTiSelecao(perfil_codigo=code, codigo=permission)
                    for permission in sorted([f"area:{area}" for area in after["areas"]] + after["permissions"])
                ])
                db.session.add(CentralTiAuditoria(
                    lote=batch, perfil_codigo=code, usuario_id=actor.id,
                    usuario_login=(getattr(actor, "login", "") or "")[:50],
                    versao_anterior=expected, versao_nova=version,
                    antes=before, depois=after, criado_em=now,
                ))
            saved.append({"id": code, "version": version, "configured": True,
                          "source": "saved_configuration", **after})
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ConfigurationConflict("A configuração mudou durante o salvamento. Recarregue a central.") from exc
    except Exception:
        db.session.rollback()
        raise
    return saved
