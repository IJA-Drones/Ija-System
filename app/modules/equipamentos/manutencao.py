"""A single maintenance worksheet; draft saves never move inventory."""
from datetime import datetime, timezone
from itertools import zip_longest

from sqlalchemy import case, select, update

from app.extensions import db
from app.models import EstoquePeca, ManutencaoEquipamento, ManutencaoPecaUso
from app.shared.equipment_models import part_matches_equipment
from app.shared.maintenance_time import SAO_PAULO, to_sao_paulo
from app.shared.skybox import delete_skybox_file
from app.modules.equipamentos.service import (
    MANUTENCAO_STATUS_ALIASES, _signature_value, _upload_maintenance_images,
    get_manutencao_aberta, get_or_create_manutencao_aberta, list_imagens_manutencao,
    list_pecas_compativeis_manutencao, lock_maintenance_equipment,
)

CONDICOES_CHEGADA = {
    "com_avaria": "Com avaria", "sem_avaria_aparente": "Sem avaria aparente",
    "nao_liga": "Não liga", "funcionamento_irregular": "Funcionamento irregular", "outro": "Outra condição",
}
TIPOS_MANUTENCAO = {"corretiva": "Corretiva", "preventiva": "Preventiva"}
CONDICOES_FINAIS = {"apto": "Apto para operação", "apto_com_ressalvas": "Apto com ressalvas", "inapto": "Inapto para operação"}
TEXT_FIELDS = (
    "avarias_identificadas", "diagnostico_tecnico", "servicos_realizados", "observacoes_teste", "observacoes",
    "responsavel_manutencao", "responsavel_avaria", "piloto_responsavel_avaria",
    "condicao_chegada", "tipo_manutencao", "condicao_final",
)
MAX_ROWS = 100


def _values(data, key):
    if hasattr(data, "getlist"):
        return data.getlist(key)
    value = data.get(key, [])
    return value if isinstance(value, (list, tuple)) else [value]


def build_manutencao_form(order, data=None):
    if data is not None:
        form = {key: str(data.get(key) or "").strip() for key in TEXT_FIELDS}
        for key in ("manutencao_id", "versao", "recebido_em", "assinatura_responsavel_tecnico", "assinatura_responsavel_avaria",
                    "limpar_assinatura_tecnico", "limpar_assinatura_avaria"):
            form[key] = str(data.get(key) or "").strip()
        form["drone_testado"] = data.get("drone_testado") == "1"
        form["pecas_avariadas"] = [dict(peca_id=i, nome=n, descricao=d) for i, n, d in zip_longest(
            _values(data, "avariada_id"), _values(data, "avariada_nome"), _values(data, "avariada_descricao"), fillvalue="")]
        form["pecas_reparo"] = [dict(peca_id=i, quantidade=q, observacoes=o) for i, q, o in zip_longest(
            _values(data, "reparo_id"), _values(data, "reparo_quantidade"), _values(data, "reparo_observacoes"), fillvalue="")]
        return form
    form = {key: (getattr(order, key, None) or "") for key in TEXT_FIELDS}
    form.update(
        manutencao_id=str(order.id if order else 0), versao=str(order.versao if order else 0),
        recebido_em=to_sao_paulo(order.recebido_em).strftime("%Y-%m-%dT%H:%M") if order and order.recebido_em else "",
        drone_testado=bool(order and order.drone_testado),
        pecas_avariadas=list(order.pecas_avariadas or []) if order else [],
        pecas_reparo=list(order.pecas_reparo or []) if order else [],
    )
    for key in ("assinatura_responsavel_tecnico", "assinatura_responsavel_avaria"):
        form[key] = getattr(order, key, None) or ""
    form.update(limpar_assinatura_tecnico="0", limpar_assinatura_avaria="0")
    return form


def _validate(order, form, compatible, *, complete):
    errors = {}
    received = None
    raw = form["recebido_em"]
    if raw:
        try:
            value = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
            received = value.replace(tzinfo=SAO_PAULO).astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            errors["recebido_em"] = "Informe uma data e hora de recebimento válidas."
    for key in TEXT_FIELDS:
        limit = 120 if key.startswith("responsavel_") or key == "piloto_responsavel_avaria" else 20000
        if len(form[key]) > limit:
            errors[key] = f"Use até {limit} caracteres."
    for key, options in (("condicao_chegada", CONDICOES_CHEGADA), ("tipo_manutencao", TIPOS_MANUTENCAO), ("condicao_final", CONDICOES_FINAIS)):
        if form[key] and form[key] not in options:
            errors[key] = "Selecione uma opção válida."
    if complete:
        required = dict(recebido_em="Informe quando o equipamento foi recebido.", condicao_chegada="Informe a condição de chegada.",
            avarias_identificadas="Preencha o relato da operação.", diagnostico_tecnico="Registre o diagnóstico técnico.",
            tipo_manutencao="Selecione o tipo de manutenção.", responsavel_manutencao="Informe o responsável técnico.",
            servicos_realizados="Descreva os serviços realizados.", observacoes_teste="Registre os testes realizados ou explique por que não foram possíveis.",
            condicao_final="Informe a condição final do equipamento.")
        for key, message in required.items():
            if not form[key]:
                errors[key] = message
        if form["condicao_final"] in {"apto", "apto_com_ressalvas"} and not form["drone_testado"]:
            errors["drone_testado"] = "Confirme os testes antes de liberar o equipamento para operação."
    signatures = {}
    for field in ("assinatura_responsavel_tecnico", "assinatura_responsavel_avaria"):
        signatures[field] = _signature_value(form[field], field, errors)
    damaged, repairs, seen = [], [], set()
    for group in ("pecas_avariadas", "pecas_reparo"):
        if len(form[group]) > MAX_ROWS:
            errors[group] = f"Adicione no máximo {MAX_ROWS} peças por seção."
    for row in form["pecas_avariadas"][:MAX_ROWS]:
        raw_id = str(row["peca_id"] or "").strip()
        name, description = str(row["nome"] or "").strip(), str(row["descricao"] or "").strip()
        if not raw_id and not name and not description:
            continue
        part = compatible.get(int(raw_id)) if raw_id.isdecimal() else None
        if raw_id != "manual" and part is None:
            errors["pecas_avariadas"] = "Selecione peças avariadas compatíveis ou use 'Outra peça'."
            continue
        if part:
            name = part.modelo_peca
        if not name or not description or len(name) > 120 or len(description) > 2000:
            errors["pecas_avariadas"] = "Informe o nome da peça (até 120 caracteres) e a avaria de cada item (até 2.000 caracteres)."
            continue
        damaged.append(dict(peca_id=part.id if part else "manual", nome=name, descricao=description,
                            codigo_dji=part.codigo_dji if part else None))
    for row in form["pecas_reparo"][:MAX_ROWS]:
        raw_id = str(row["peca_id"] or "").strip()
        notes = str(row["observacoes"] or "").strip()
        if not raw_id and not notes:
            continue
        part = compatible.get(int(raw_id)) if raw_id.isdecimal() else None
        if part is None:
            errors["pecas_reparo"] = "Esta peça não está disponível para o modelo e a prefeitura deste drone."
            continue
        if part.id in seen:
            errors["pecas_reparo"] = "Selecione cada peça uma única vez e ajuste a quantidade."
        seen.add(part.id)
        try:
            quantity = int(row["quantidade"])
            if not 1 <= quantity <= 100000:
                raise ValueError
        except (TypeError, ValueError):
            errors["pecas_reparo"] = "Informe uma quantidade inteira positiva para cada peça do reparo."
            continue
        if len(notes) > 2000:
            errors["pecas_reparo"] = "Use até 2.000 caracteres nas observações de cada substituição."
        if complete and (part.status != "disponivel_manutencao" or part.quantidade < quantity):
            errors["pecas_reparo"] = f"Saldo insuficiente ou peça indisponível: {part.modelo_peca}. Quantidade disponível: {part.quantidade}."
        repairs.append(dict(peca_id=part.id, quantidade=quantity, observacoes=notes,
                            nome=part.modelo_peca, codigo_dji=part.codigo_dji or ""))
    return errors, received, damaged, repairs, signatures


def salvar_atendimento_manutencao(drone, data, *, user, files_data=None):
    """Claim a worksheet version, then finalize all stock movements in one commit."""
    form = build_manutencao_form(None, data)
    action = data.get("acao", "rascunho")
    if action not in {"rascunho", "concluir"}:
        return None, {"geral": "Selecione salvar rascunho ou concluir a OS."}
    complete = action == "concluir"
    try:
        order_id, version = int(form["manutencao_id"]), int(form["versao"])
        if order_id < 0 or version < 0:
            raise ValueError
    except (TypeError, ValueError):
        return None, {"conflito": "Recarregue a OS antes de salvar. Não foi possível identificar a versão do formulário."}
    lock_maintenance_equipment(drone)
    order = get_manutencao_aberta(drone, user=user)
    if not order or order.id != order_id:
        # Old equipment may be in maintenance without an associated worksheet.
        if order is None and order_id == 0 and version == 0 and drone.status in MANUTENCAO_STATUS_ALIASES:
            order = get_or_create_manutencao_aberta(drone, user=user)
            db.session.flush()
        else:
            db.session.rollback()
            return None, {"conflito": "Esta OS foi concluída ou substituída. Recarregue a página para conferir o estado atual."}
    compatible = {p.id: p for p in list_pecas_compativeis_manutencao(drone, user=user)}
    errors, received, damaged, repairs, signatures = _validate(order, form, compatible, complete=complete)
    if errors:
        db.session.rollback()
        return None, errors
    uploaded = []
    try:
        claimed = db.session.execute(update(ManutencaoEquipamento).where(
            ManutencaoEquipamento.id == order.id, ManutencaoEquipamento.status == "aberta",
            ManutencaoEquipamento.versao == version,
        ).values(versao=version + 1, atualizada_em=datetime.now(timezone.utc).replace(tzinfo=None))
            .returning(ManutencaoEquipamento.id).execution_options(synchronize_session="fetch")).scalar_one_or_none()
        if claimed is None:
            db.session.rollback()
            return None, {"conflito": "Esta OS mudou em outra aba. Recarregue a página antes de salvar suas alterações."}
        for key in TEXT_FIELDS:
            setattr(order, key, form[key] or None)
        order.recebido_em = received
        order.drone_testado = form["drone_testado"]
        order.pecas_avariadas, order.pecas_reparo = damaged, repairs
        for field, flag in (("assinatura_responsavel_tecnico", "limpar_assinatura_tecnico"), ("assinatura_responsavel_avaria", "limpar_assinatura_avaria")):
            if form[flag] == "1":
                setattr(order, field, None)
            elif signatures[field] is not None:
                setattr(order, field, signatures[field])
        if complete:
            for row in sorted(repairs, key=lambda row: row["peca_id"]):
                # Refresh under a lock: compatibility and availability may have changed since rendering.
                part = db.session.execute(select(EstoquePeca).where(EstoquePeca.id == row["peca_id"])
                    .with_for_update(of=EstoquePeca).execution_options(populate_existing=True)).unique().scalar_one()
                if part.prefeitura_id != drone.prefeitura_id or part.arquivada_em or not part_matches_equipment(part, drone):
                    raise ValueError("A compatibilidade de uma peça mudou. Confira as peças do reparo antes de concluir.")
                balance = EstoquePeca.quantidade - row["quantidade"]
                spent = db.session.execute(update(EstoquePeca).where(
                    EstoquePeca.id == part.id, EstoquePeca.quantidade >= row["quantidade"],
                    EstoquePeca.status == "disponivel_manutencao", EstoquePeca.arquivada_em.is_(None),
                    EstoquePeca.prefeitura_id == drone.prefeitura_id,
                ).values(quantidade=balance, status=case((balance == 0, "baixada"), else_=EstoquePeca.status),
                         atualizado_em=datetime.now(timezone.utc).replace(tzinfo=None))
                    .returning(EstoquePeca.id).execution_options(synchronize_session="fetch")).scalar_one_or_none()
                if spent is None:
                    raise ValueError("O saldo de uma peça mudou. Confira o estoque; nenhuma peça desta conclusão foi descontada.")
                db.session.add(ManutencaoPecaUso(prefeitura_id=drone.prefeitura_id, manutencao=order, drone_id=drone.id,
                    peca_id=part.id, usuario_id=getattr(user, "id", None), quantidade_usada=row["quantidade"],
                    criado_em=datetime.now(timezone.utc).replace(tzinfo=None),
                    observacoes=row["observacoes"] or None, nome_peca_snapshot=part.modelo_peca,
                    codigo_dji_snapshot=part.codigo_dji or "", numero_serie_snapshot=part.numero_serie or ""))
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            order.status, order.encerrada_em, order.encerrada_por_id = "encerrada", now, getattr(user, "id", None)
            order.pecas_reparo = []
            drone.status = "Inativo" if order.condicao_final == "inapto" else "Ativo"
            drone.ultima_manutencao = to_sao_paulo(now).date()
        files = files_data.getlist("imagens_ocorrido") if files_data is not None else []
        uploaded = _upload_maintenance_images(order, files)
        if uploaded:
            import json
            order.imagens_ocorrido = json.dumps(list_imagens_manutencao(order) + uploaded, ensure_ascii=False)
        db.session.commit()
        return order, {}
    except Exception:
        db.session.rollback()
        for marker in uploaded:
            try:
                delete_skybox_file(marker)
            except Exception:
                from flask import current_app
                current_app.logger.exception("Falha ao remover anexo de manutenção após rollback.")
        raise
