"""Read-only presentation of permission changes saved by the Central de TI."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import abort, current_app
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import CentralTiAuditoria
from app.modules.gestao_ti.catalog import CATALOG


BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
PER_PAGE = 25


def can_view_permission_audit(user):
    """This administrative history has a fixed identity guard, not a capability."""
    role = (getattr(user, "tipo_usuario", "") or "").strip().lower()
    return bool(getattr(user, "is_authenticated", False)) and role in {"dev", "diretor"}


def _label_catalog():
    labels = {}
    for area in CATALOG["catalog"]:
        labels[("area", area["id"])] = f"Área: {area['label']}"
        for module in area["modules"]:
            for action in module[4].split():
                code = f"{area['id']}.{module[0]}.{action}"
                action_label = CATALOG["labels"].get(action, action)
                labels[("permission", code)] = f"{area['label']} · {module[1]} · {action_label}"
    return labels


def _snapshot_codes(snapshot):
    if not isinstance(snapshot, dict):
        return set()
    codes = set()
    for key, kind in (("areas", "area"), ("permissions", "permission")):
        values = snapshot.get(key)
        if isinstance(values, list):
            codes.update((kind, value) for value in values if isinstance(value, str))
    return codes


def _selection_labels(codes, labels):
    return sorted(
        (labels.get((kind, code), f"Área: {code}" if kind == "area" else code)
         for kind, code in codes),
        key=str.casefold,
    )


def _parse_date(value, label, errors):
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except (ValueError, TypeError):
        errors.append(f"{label} inválida. Use o formato dia/mês/ano no campo de data.")
        return None


def _local_day_start(value):
    # Saved audit timestamps are naive UTC, matching Central de TI's writer.
    return datetime.combine(value, time.min, tzinfo=BRAZIL_TZ).astimezone(timezone.utc).replace(tzinfo=None)


def _filters(args):
    errors = []
    filters = {
        key: str(args.get(key) or "").strip()
        for key in ("perfil", "usuario", "data_inicio", "data_fim")
    }
    filters["perfil"] = filters["perfil"].lower()
    for key, maximum, label in (("perfil", 20, "perfil"), ("usuario", 50, "usuário")):
        if len(filters[key]) > maximum:
            filters[key] = filters[key][:maximum]
            errors.append(f"O filtro de {label} foi limitado a {maximum} caracteres.")

    inicio = _parse_date(filters["data_inicio"], "Data inicial", errors)
    fim = _parse_date(filters["data_fim"], "Data final", errors)
    if inicio is None:
        filters["data_inicio"] = ""
    if fim is None:
        filters["data_fim"] = ""
    if inicio and fim and inicio > fim:
        errors.append("A data inicial deve ser anterior ou igual à data final. O período não foi aplicado.")
        inicio = fim = None
        filters["data_inicio"] = filters["data_fim"] = ""

    fim_exclusivo = None
    if fim:
        try:
            fim_exclusivo = _local_day_start(fim + timedelta(days=1))
        except (OverflowError, ValueError):
            errors.append("Data final fora do intervalo permitido. O filtro de data final não foi aplicado.")
            filters["data_fim"] = ""
    return filters, inicio, fim_exclusivo, errors


def _entry(row, labels, profile_labels):
    before = _snapshot_codes(row.antes)
    after = _snapshot_codes(row.depois)
    created_at = row.criado_em
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return {
        "id": row.id,
        "created_at": created_at.astimezone(BRAZIL_TZ),
        "actor_login": row.usuario_login,
        "actor_id": row.usuario_id,
        "profile_label": profile_labels.get(row.perfil_codigo, row.perfil_codigo),
        "profile_code": row.perfil_codigo,
        "version_before": row.versao_anterior,
        "version_after": row.versao_nova,
        "batch": row.lote,
        "added": _selection_labels(after - before, labels),
        "removed": _selection_labels(before - after, labels),
        "first_configuration": row.versao_anterior == 0,
        "is_initialization": row.usuario_login == "inicializacao_neon" and row.usuario_id is None,
    }


def build_permission_audit_context(args):
    """Query only saved audit rows; never read or change current permissions."""
    filters, inicio, fim_exclusivo, errors = _filters(args)
    raw_page = str(args.get("page") or "1")
    try:
        if len(raw_page) > 9:
            raise ValueError
        page = int(raw_page)
        if page < 1:
            raise ValueError
    except (TypeError, ValueError):
        page = 1
        errors.append("Página inválida. Exibindo a primeira página.")

    query = CentralTiAuditoria.query
    if filters["perfil"]:
        query = query.filter(CentralTiAuditoria.perfil_codigo == filters["perfil"])
    if filters["usuario"]:
        # Escape LIKE wildcards so a login containing '%' or '_' stays literal.
        term = filters["usuario"].lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(func.lower(CentralTiAuditoria.usuario_login).like(f"%{term}%", escape="\\"))
    if inicio:
        query = query.filter(CentralTiAuditoria.criado_em >= _local_day_start(inicio))
    if fim_exclusivo:
        query = query.filter(CentralTiAuditoria.criado_em < fim_exclusivo)
    query = query.order_by(CentralTiAuditoria.criado_em.desc(), CentralTiAuditoria.id.desc())
    try:
        with db.session.no_autoflush:
            paginacao = query.paginate(page=page, per_page=PER_PAGE, max_per_page=PER_PAGE, error_out=False)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Não foi possível consultar a auditoria de permissões.")
        abort(503, description="Não foi possível consultar a auditoria. Tente novamente em instantes.")

    profile_options = [{"id": profile["id"], "name": profile["name"]} for profile in CATALOG["profiles"]]
    profile_labels = {profile["id"]: profile["name"] for profile in profile_options}
    labels = _label_catalog()
    return {
        "filters": filters,
        "entries": [_entry(row, labels, profile_labels) for row in paginacao.items],
        "paginacao": paginacao,
        "pagination_args": {key: value for key, value in filters.items() if value},
        "profile_options": profile_options,
        "filter_errors": errors,
    }
