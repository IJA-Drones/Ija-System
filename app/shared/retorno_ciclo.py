import json
import os
from datetime import datetime

from flask import url_for
from sqlalchemy import false, func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Equipe, EquipePiloto, OrdemServico, OrdemServicoEquipeUvis, Solicitacao, Usuario
from app.shared.access import (
    ADMIN_PANEL_VIEW_TYPES,
    apply_prefeitura_scope,
    can_access_regiao,
    is_regional_user,
    normalize_regiao,
)


EQUIPE_OCEANO_USER_TYPE = "equipe_oceano"
RETURN_CYCLE_MAX_NODES = 80


def _parse_json_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).replace("\\", "/") for item in value if item]
    try:
        data = json.loads(value)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(item).replace("\\", "/") for item in data if item]


def _fmt_date(value):
    return value.strftime("%d/%m/%Y") if value else "-"


def _fmt_datetime(value):
    return value.strftime("%d/%m/%Y %H:%M") if value else "-"


def _status_upper(value):
    return (value or "").strip().upper()


def _uvis_scope_id(user):
    tipo = getattr(user, "tipo_usuario", None)
    if tipo == "uvis":
        return getattr(user, "id", None)
    if tipo == "equipe_uvis":
        return getattr(user, "equipe_uvis_uvis_usuario_id", None)
    return None


def _equipe_ids_for_user(user):
    tipo = getattr(user, "tipo_usuario", None)
    if tipo == EQUIPE_OCEANO_USER_TYPE:
        try:
            equipe_id = int((getattr(user, "codigo_setor", None) or "").strip())
        except (TypeError, ValueError):
            return []
        exists = db.session.query(Equipe.id).filter(Equipe.id == equipe_id, Equipe.ativa.is_(True)).first()
        return [equipe_id] if exists else []

    piloto_id = getattr(user, "piloto_id", None)
    if not piloto_id:
        return []
    return [
        equipe_id
        for (equipe_id,) in (
            db.session.query(EquipePiloto.equipe_id)
            .join(Equipe, Equipe.id == EquipePiloto.equipe_id)
            .filter(
                EquipePiloto.piloto_id == piloto_id,
                Equipe.ativa.is_(True),
            )
            .all()
        )
    ]


def apply_retorno_ciclo_access_scope(query, user):
    tipo = getattr(user, "tipo_usuario", None)
    if tipo in ADMIN_PANEL_VIEW_TYPES:
        query = apply_prefeitura_scope(query, user, Solicitacao.prefeitura_id)
        if is_regional_user(user):
            user_regiao = normalize_regiao(getattr(user, "regiao", None))
            if not user_regiao:
                return query.filter(false())
            query = query.filter(Solicitacao.usuario.has(func.upper(func.coalesce(Usuario.regiao, "")) == user_regiao))
        return query

    uvis_id = _uvis_scope_id(user)
    if uvis_id:
        return query.filter(Solicitacao.usuario_id == uvis_id)

    equipe_ids = _equipe_ids_for_user(user)
    if equipe_ids:
        return query.filter(Solicitacao.equipe_id.in_(equipe_ids))

    return query.filter(false())


def get_accessible_solicitacao_for_retorno_ciclo(user, os_id):
    query = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico),
            joinedload(Solicitacao.ordem_servico_equipe_uvis),
        )
        .filter(Solicitacao.id == os_id)
    )
    return apply_retorno_ciclo_access_scope(query, user).first()


def _find_root_id(start_id):
    current = Solicitacao.query.with_entities(Solicitacao.id, Solicitacao.origem_retorno_id).filter(Solicitacao.id == start_id).first()
    visited = set()
    while current and current.origem_retorno_id and current.id not in visited:
        visited.add(current.id)
        parent = (
            Solicitacao.query
            .with_entities(Solicitacao.id, Solicitacao.origem_retorno_id)
            .filter(Solicitacao.id == current.origem_retorno_id)
            .first()
        )
        if not parent:
            break
        current = parent
    return current.id if current else start_id


def _load_cycle_solicitacoes(user, root_id):
    ordered_ids = []
    queue = [root_id]
    visited = set()

    while queue and len(ordered_ids) < RETURN_CYCLE_MAX_NODES:
        current_id = queue.pop(0)
        if current_id in visited:
            continue
        visited.add(current_id)
        ordered_ids.append(current_id)

        children = (
            Solicitacao.query
            .with_entities(Solicitacao.id)
            .filter(Solicitacao.origem_retorno_id == current_id)
            .order_by(Solicitacao.data_agendamento.asc(), Solicitacao.id.asc())
            .all()
        )
        queue.extend(child_id for (child_id,) in children)

    if not ordered_ids:
        return []

    query = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico),
            joinedload(Solicitacao.ordem_servico_equipe_uvis),
        )
        .filter(Solicitacao.id.in_(ordered_ids))
    )
    visible = {item.id: item for item in apply_retorno_ciclo_access_scope(query, user).all()}
    return [visible[item_id] for item_id in ordered_ids if item_id in visible]


def _node_depth(item_by_id, solicitacao):
    depth = 0
    parent_id = solicitacao.origem_retorno_id
    seen = set()
    while parent_id and parent_id in item_by_id and parent_id not in seen:
        seen.add(parent_id)
        depth += 1
        parent_id = item_by_id[parent_id].origem_retorno_id
    return depth


def _detail_url_for(user, solicitacao, os_kind):
    tipo = getattr(user, "tipo_usuario", None)
    status = _status_upper(solicitacao.status)
    is_concluida = status in {"CONCLUIDO", "CONCLU\u00cdDO"}
    is_aprovada = status in {
        "APROVADO",
        "APROVADA",
        "APROVADO COM RECOMENDACOES",
        "APROVADA COM RECOMENDACOES",
        "APROVADO COM RECOMENDA\u00c7\u00d5ES",
        "APROVADA COM RECOMENDA\u00c7\u00d5ES",
    }

    if os_kind == "equipe_uvis":
        if tipo in ADMIN_PANEL_VIEW_TYPES:
            return url_for("main.admin_equipe_uvis_os_formulario_view", os_id=solicitacao.id)
        if not (is_aprovada or is_concluida):
            return ""
        if tipo == "equipe_oceano":
            return url_for("main.piloto_os_formulario_view", os_id=solicitacao.id)
        return url_for("main.equipe_uvis_os_formulario_view", os_id=solicitacao.id, voltar="historico")

    if tipo in ADMIN_PANEL_VIEW_TYPES:
        return url_for("main.admin_os_formulario_view", os_id=solicitacao.id)
    if tipo in {"uvis", "equipe_uvis"}:
        if not is_concluida:
            return ""
        return url_for("main.uvis_os_formulario_view", os_id=solicitacao.id)
    if tipo == "equipe_oceano":
        if not (is_aprovada or is_concluida):
            return ""
        return url_for("main.piloto_os_formulario_view", os_id=solicitacao.id)
    if not (is_aprovada or is_concluida):
        return ""
    return url_for("main.piloto_os_formulario_view", os_id=solicitacao.id)


def _serialize_media(solicitacao, ordem):
    principal = getattr(ordem, "imagem_principal", None) if ordem else None
    complementares = _parse_json_list(getattr(ordem, "outras_imagens", None) if ordem else None)
    video = getattr(ordem, "video", None) if ordem else None
    return {
        "principal_url": url_for("main.os_imagem_principal", os_id=solicitacao.id) if principal else "",
        "principal_nome": os.path.basename(str(principal or "").replace("\\", "/")) if principal else "",
        "complementares": [
            {
                "url": url_for("main.os_imagem_complementar", os_id=solicitacao.id, image_index=index),
                "label": f"Imagem extra {index}",
                "nome": os.path.basename(str(path or "").replace("\\", "/")),
            }
            for index, path in enumerate(complementares, start=1)
        ],
        "video_url": url_for("main.os_video", os_id=solicitacao.id) if video else "",
        "video_nome": os.path.basename(str(video or "").replace("\\", "/")) if video else "",
        "total": (1 if principal else 0) + len(complementares) + (1 if video else 0),
    }


def _serialize_node(user, solicitacao, item_by_id, current_os_id, index):
    ordem = solicitacao.ordem_servico or solicitacao.ordem_servico_equipe_uvis
    os_kind = "equipe_uvis" if solicitacao.ordem_servico_equipe_uvis and not solicitacao.ordem_servico else "piloto"
    status = _status_upper(solicitacao.status)
    larva = _status_upper(getattr(ordem, "larva_visualizada", None) if ordem else None)
    retorno_flag = _status_upper(getattr(ordem, "retornar_proxima_semana_monitorar_larvas", None) if ordem else None)
    children = [item.id for item in item_by_id.values() if item.origem_retorno_id == solicitacao.id]
    is_concluida = status in {"CONCLUIDO", "CONCLU\u00cdDO"}
    is_pendente = status == "PENDENTE"
    is_retorno = bool(solicitacao.origem_retorno_id or solicitacao.gerada_automaticamente)

    color = "secondary"
    icon = "bi-circle"
    if larva == "SIM":
        color = "danger"
        icon = "bi-bug-fill"
    elif children:
        color = "info"
        icon = "bi-arrow-repeat"
    elif is_pendente:
        color = "warning"
        icon = "bi-calendar-event"
    elif is_concluida:
        color = "success"
        icon = "bi-check-circle-fill"

    badges = []
    if is_retorno:
        badges.append({"label": "Retorno automatico", "color": "warning"})
    if larva == "SIM":
        badges.append({"label": "Larva visualizada", "color": "danger"})
    if children:
        badges.append({"label": f"Gerou {len(children)} retorno(s)", "color": "info"})
    if is_concluida:
        badges.append({"label": "Concluida", "color": "success"})
    elif is_pendente:
        badges.append({"label": "Pendente", "color": "warning"})

    data_execucao = getattr(ordem, "data_aplicacao", None) if ordem else None
    if not data_execucao and ordem:
        data_execucao = getattr(ordem, "respondido_em", None)

    return {
        "id": solicitacao.id,
        "parent_id": solicitacao.origem_retorno_id,
        "depth": _node_depth(item_by_id, solicitacao),
        "index": index,
        "is_current": solicitacao.id == current_os_id,
        "is_root": not solicitacao.origem_retorno_id,
        "is_retorno": is_retorno,
        "status": solicitacao.status or "-",
        "color": color,
        "icon": icon,
        "badges": badges,
        "title": f"OS #{solicitacao.id} - {'Retorno automatico' if is_retorno else 'Visita inicial'}",
        "uvis_nome": getattr(getattr(solicitacao, "usuario", None), "nome_uvis", None) or "UVIS nao informada",
        "regiao_nome": getattr(getattr(solicitacao, "usuario", None), "regiao", None) or "Regiao nao informada",
        "endereco": (
            f"{solicitacao.logradouro or ''}, {solicitacao.numero or 'S/N'} - "
            f"{solicitacao.bairro or ''} - {solicitacao.cidade or ''}/{solicitacao.uf or ''}"
        ).strip(" -"),
        "agendamento_label": _fmt_date(solicitacao.data_agendamento),
        "execucao_label": _fmt_date(data_execucao) if not isinstance(data_execucao, datetime) else _fmt_datetime(data_execucao),
        "respondido_label": _fmt_datetime(getattr(ordem, "respondido_em", None) if ordem else None),
        "situacao": getattr(ordem, "situacao_aplicacao", None) if ordem else "",
        "larva": larva or "-",
        "retorno_flag": retorno_flag or "-",
        "observacoes": getattr(ordem, "observacoes", None) if ordem else "",
        "motivo_nao_realizacao": getattr(ordem, "motivo_nao_realizacao", None) if ordem else "",
        "tratamento_adicional": getattr(ordem, "tratamento_adicional_realizado", None) if ordem else "",
        "quantos_quais": getattr(ordem, "quantos_quais", None) if ordem else "",
        "produto_ml": getattr(ordem, "quantidade_produto_administrada_ml", None) if ordem else None,
        "identificador_os": getattr(ordem, "identificador_os", None) if ordem else "",
        "respondido_por": getattr(ordem, "respondido_por", None) if ordem else "",
        "detail_url": _detail_url_for(user, solicitacao, os_kind),
        "media": _serialize_media(solicitacao, solicitacao.ordem_servico),
    }


def build_retorno_ciclo_context(user, os_id):
    current = get_accessible_solicitacao_for_retorno_ciclo(user, os_id)
    if not current:
        return {"nodes": [], "has_cycle": False, "total_midias": 0}

    regiao = getattr(getattr(current, "usuario", None), "regiao", None)
    if not can_access_regiao(user, regiao):
        return {"nodes": [], "has_cycle": False, "total_midias": 0}

    root_id = _find_root_id(current.id)
    solicitacoes = _load_cycle_solicitacoes(user, root_id)
    item_by_id = {item.id: item for item in solicitacoes}
    nodes = [
        _serialize_node(user, item, item_by_id, current.id, index)
        for index, item in enumerate(solicitacoes, start=1)
    ]
    total_midias = sum(node["media"]["total"] for node in nodes)
    has_cycle = len(nodes) > 1 or bool(current.origem_retorno_id) or any(node["retorno_flag"] == "SIM" for node in nodes)

    return {
        "nodes": nodes,
        "has_cycle": has_cycle,
        "root_id": root_id,
        "current_id": current.id,
        "total_midias": total_midias,
        "total_retornos": max(0, len(nodes) - 1),
    }


def _compact_retorno_node(node):
    return {
        "id": node["id"],
        "label": f"OS #{node['id']}",
        "color": node["color"],
        "icon": node["icon"],
        "is_current": node["is_current"],
        "is_retorno": node["is_retorno"],
        "status": node["status"],
        "detail_url": node["detail_url"],
        "larva": node["larva"],
        "retorno_flag": node["retorno_flag"],
    }


def _build_retorno_ciclo_summary(context):
    nodes = context.get("nodes") or []
    if not context.get("has_cycle") or not nodes:
        return None

    current_node = next((node for node in nodes if node.get("is_current")), nodes[0])
    gerou_retorno = any(
        str(badge.get("label", "")).startswith("Gerou")
        for badge in current_node.get("badges", [])
    )
    next_pending = next(
        (
            node for node in nodes
            if node["id"] != current_node["id"]
            and _status_upper(node.get("status")) in {"PENDENTE", "APROVADO", "APROVADA"}
        ),
        None,
    )
    larva_nodes = [node for node in nodes if _status_upper(node.get("larva")) == "SIM"]
    retorno_solicitado = _status_upper(current_node.get("retorno_flag")) == "SIM"

    return {
        "has_cycle": True,
        "root_id": context.get("root_id"),
        "current_id": context.get("current_id"),
        "total_etapas": len(nodes),
        "total_retornos": context.get("total_retornos", 0),
        "total_midias": context.get("total_midias", 0),
        "is_retorno": bool(current_node.get("is_retorno")),
        "gerou_retorno": gerou_retorno,
        "retorno_solicitado": retorno_solicitado,
        "larvas": len(larva_nodes),
        "next_pending": _compact_retorno_node(next_pending) if next_pending else None,
        "nodes": [_compact_retorno_node(node) for node in nodes[:6]],
        "hidden_nodes": max(0, len(nodes) - 6),
    }


def _retorno_ciclo_candidate_ids(solicitacoes):
    solicitacao_ids = [
        solicitacao.id
        for solicitacao in solicitacoes
        if getattr(solicitacao, "id", None)
    ]
    if not solicitacao_ids:
        return set()

    parent_query = (
        db.session.query(Solicitacao.origem_retorno_id.label("solicitacao_id"))
        .filter(Solicitacao.origem_retorno_id.in_(solicitacao_ids))
    )
    piloto_retorno_query = (
        db.session.query(OrdemServico.solicitacao_id.label("solicitacao_id"))
        .filter(
            OrdemServico.solicitacao_id.in_(solicitacao_ids),
            func.upper(func.trim(func.coalesce(OrdemServico.retornar_proxima_semana_monitorar_larvas, ""))) == "SIM",
        )
    )
    equipe_uvis_retorno_query = (
        db.session.query(OrdemServicoEquipeUvis.solicitacao_id.label("solicitacao_id"))
        .filter(
            OrdemServicoEquipeUvis.solicitacao_id.in_(solicitacao_ids),
            func.upper(
                func.trim(func.coalesce(OrdemServicoEquipeUvis.retornar_proxima_semana_monitorar_larvas, ""))
            ) == "SIM",
        )
    )
    candidate_ids = {
        row.solicitacao_id
        for row in parent_query.union(piloto_retorno_query, equipe_uvis_retorno_query).all()
        if row.solicitacao_id is not None
    }
    candidate_ids.update(
        solicitacao.id
        for solicitacao in solicitacoes
        if getattr(solicitacao, "origem_retorno_id", None)
        or getattr(solicitacao, "gerada_automaticamente", False)
    )
    return candidate_ids


def _retorno_context_for_current(context, os_id):
    if context.get("current_id") == os_id:
        return context

    adjusted = dict(context)
    adjusted["current_id"] = os_id
    adjusted["nodes"] = [
        {**node, "is_current": node.get("id") == os_id}
        for node in context.get("nodes") or []
    ]
    return adjusted


def build_retorno_ciclo_summaries(user, solicitacoes):
    solicitacoes = list(solicitacoes or [])
    summaries = {}
    context_by_node = {}
    candidate_ids = _retorno_ciclo_candidate_ids(solicitacoes)

    for solicitacao in solicitacoes:
        os_id = getattr(solicitacao, "id", None)
        if not os_id or os_id not in candidate_ids:
            continue

        context = context_by_node.get(os_id)
        if context is None:
            context = build_retorno_ciclo_context(user, os_id)
            context_by_node[os_id] = context
            for node in context.get("nodes") or []:
                node_id = node.get("id")
                if node_id is not None:
                    context_by_node[node_id] = context

        summary = _build_retorno_ciclo_summary(_retorno_context_for_current(context, os_id))
        if summary:
            summaries[os_id] = summary

    return summaries
