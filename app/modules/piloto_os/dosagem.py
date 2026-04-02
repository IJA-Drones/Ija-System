import json
from datetime import datetime

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import OrdemServico, Solicitacao
from app.modules.piloto_os.service import (
    PilotoOsError,
    STATUS_OS_APROVADAS_COM_ACENTO,
    STATUS_OS_CONCLUIDAS,
    _buscar_vinculo_piloto_na_equipe,
    _parse_json_object,
    _sanitize_calculo_dosagem_planejado,
)


def _fmt_number(value):
    if isinstance(value, int):
        return str(value)
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _fmt_calda(value, unidade):
    sufixo = "mL" if str(unidade).strip().lower().startswith("mili") else "L"
    return f"{_fmt_number(value)} {sufixo}"


def _fmt_tempo(value, unidade):
    sufixo = "s" if str(unidade).strip().lower().startswith("seg") else "min"
    return f"{_fmt_number(value)} {sufixo}"


_REFERENCIAS_BRUTAS = {
    "foco_aedes": {
        "label": "Foco - Aedes",
        "medida_label": "Volume util do foco (L)",
        "tipo_aplicacao": "Pulverizacao de foco (liq)",
        "regras": [
            "Direto: informe o volume util do foco em litros.",
            "Retangular: comprimento x largura x altura da agua x 1000.",
            "Circular: raio x raio x 3.14 x altura da agua x 1000.",
            "Mistura base: 500 g de BTI WDG para 10 L de agua.",
        ],
        "rows": [
            (100, 1, 20, "Militros", 5.4, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (200, 2, 40, "Militros", 10, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (250, 3, 60, "Militros", 15, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (500, 5, 100, "Militros", 30, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (1000, 10, 200, "Militros", 1, "Minutos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (2000, 20, 400, "Militros", 1, "Minutos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (3000, 30, 600, "Militros", 2, "Minutos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (4000, 40, 800, "Militros", 2, "Minutos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (5000, 50, 1, "Litros", 3, "Minutos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (7500, 75, 1.5, "Litros", 4, "Minutos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (10000, 100, 2, "Litros", 5, "Minutos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (12000, 120, 2.4, "Litros", 6, "Minutos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (15000, 150, 3, "Litros", 2, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (20000, 200, 4, "Litros", 2, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (30000, 300, 6, "Litros", 3, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (40000, 400, 8, "Litros", 4, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (50000, 500, 10, "Litros", 5, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (60000, 600, 12, "Litros", 6, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (70000, 700, 14, "Litros", 7, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (75000, 750, 15, "Litros", 8, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (80000, 800, 16, "Litros", 8, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (90000, 900, 18, "Litros", 9, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (100000, 1000, 20, "Litros", 10, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
        ],
    },
    "area_aedes": {
        "label": "Area - Aedes",
        "medida_label": "Area tratada (m2)",
        "tipo_aplicacao": "Pulverizacao de area (liq)",
        "regras": [
            "Direto: informe a area prevista em metros quadrados.",
            "Retangular: comprimento x largura.",
            "Irregular: comprimento x largura media.",
            "Mistura base: 500 g de BTI WDG para 10 L de agua.",
        ],
        "rows": [
            (100, 5, 100, "Militros", 7.5, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (200, 10, 200, "Militros", 15, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (250, 13, 260, "Militros", 19.5, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (300, 15, 300, "Militros", 22.5, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (400, 20, 400, "Militros", 30, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (500, 25, 500, "Militros", 37.5, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (600, 30, 600, "Militros", 45, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (700, 35, 700, "Militros", 52.5, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (800, 40, 800, "Militros", 60, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (900, 45, 900, "Militros", 67.5, "Segundos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (1000, 50, 1, "Litros", 1.25, "Minutos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (2000, 100, 2, "Litros", 2.5, "Minutos", "TXA8001", 2, 800, 40, 2, 2, 120),
            (3000, 150, 3, "Litros", 1.5, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (4000, 200, 4, "Litros", 2, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (5000, 250, 5, "Litros", 2.5, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (10000, 500, 10, "Litros", 5, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (15000, 750, 15, "Litros", 7.5, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (20000, 1000, 20, "Litros", 10, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (30000, 1500, 30, "Litros", 15, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (40000, 2000, 40, "Litros", 20, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (50000, 2500, 50, "Litros", 25, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (60000, 3000, 60, "Litros", 30, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (70000, 3500, 70, "Litros", 35, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (75000, 3750, 75, "Litros", 37.5, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (80000, 4000, 80, "Litros", 40, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (90000, 4500, 90, "Litros", 45, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
            (100000, 5000, 100, "Litros", 50, "Minutos", "TXA8001", 4, 2000, 100, 4, 2, 120),
        ],
    },
    "area_culex": {
        "label": "Area - Culex",
        "medida_label": "Area tratada (m2)",
        "tipo_aplicacao": "Pulverizacao de area (liq)",
        "regras": [
            "Direto: informe a area prevista em metros quadrados.",
            "Retangular: comprimento x largura.",
            "Irregular: comprimento x largura media.",
            "Corpos d'agua largos: comprimento x 10 x numero de margens.",
        ],
        "rows": [
            (100, 10, 200, "Militros", 6, "Segundos", "XR11003", 2, 2000, 100, 2, 6, 120),
            (200, 20, 400, "Militros", 12, "Segundos", "XR11003", 2, 2000, 100, 2, 6, 120),
            (250, 25, 500, "Militros", 15, "Segundos", "XR11003", 2, 2000, 100, 2, 6, 120),
            (300, 30, 600, "Militros", 18, "Segundos", "XR11003", 2, 2000, 100, 2, 6, 120),
            (400, 40, 800, "Militros", 24, "Segundos", "XR11003", 2, 2000, 100, 2, 6, 120),
            (500, 50, 1000, "Militros", 30, "Segundos", "XR11003", 2, 2000, 100, 2, 6, 120),
            (600, 60, 1200, "Militros", 36, "Segundos", "XR11003", 2, 2000, 100, 2, 6, 120),
            (700, 70, 1400, "Militros", 42, "Segundos", "XR11003", 2, 2000, 100, 2, 6, 120),
            (800, 80, 1600, "Militros", 48, "Segundos", "XR11003", 2, 2000, 100, 2, 6, 120),
            (900, 90, 1800, "Militros", 54, "Segundos", "XR11003", 2, 2000, 100, 2, 6, 120),
            (1000, 100, 2, "Litros", 1, "Minutos", "XR11003", 2, 2000, 100, 2, 6, 120),
            (2000, 200, 4, "Litros", 2, "Minutos", "XR11003", 2, 2000, 100, 2, 6, 120),
            (3000, 300, 6, "Litros", 1.3636363636363635, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (4000, 400, 8, "Litros", 1.8181818181818181, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (5000, 500, 10, "Litros", 2.272727272727273, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (10000, 1000, 20, "Litros", 4.545454545454546, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (15000, 1500, 30, "Litros", 6.818181818181818, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (20000, 2000, 40, "Litros", 9.090909090909092, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (30000, 3000, 60, "Litros", 13.636363636363637, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (40000, 4000, 80, "Litros", 18.181818181818183, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (50000, 5000, 100, "Litros", 22.727272727272727, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (60000, 6000, 120, "Litros", 27.272727272727273, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (70000, 7000, 140, "Litros", 31.818181818181817, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (75000, 7500, 150, "Litros", 34.09090909090909, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (80000, 8000, 160, "Litros", 36.36363636363637, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (90000, 9000, 180, "Litros", 40.90909090909091, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
            (100000, 10000, 200, "Litros", 45.45454545454545, "Minutos", "XR11003", 4, 4400, 220, 4, 6, 120),
        ],
    },
}


def _build_referencias_dosagem():
    referencias = []
    for key, data in _REFERENCIAS_BRUTAS.items():
        rows = []
        for row in data["rows"]:
            (
                medida,
                carga_bti_g,
                calda_valor,
                calda_unidade,
                tempo_valor,
                tempo_unidade,
                ponta,
                numero_bicos,
                vazao_bicos_ml_min,
                dose_bti_g_min,
                pressao_bar,
                faixa_aplicacao_m,
                tamanho_gotas_dmv,
            ) = row
            rows.append(
                {
                    "medida": medida,
                    "carga_bti_g": carga_bti_g,
                    "calda_label": _fmt_calda(calda_valor, calda_unidade),
                    "tempo_label": _fmt_tempo(tempo_valor, tempo_unidade),
                    "ponta": ponta,
                    "numero_bicos": numero_bicos,
                    "vazao_bicos_ml_min": vazao_bicos_ml_min,
                    "dose_bti_g_min": dose_bti_g_min,
                    "pressao_bar": pressao_bar,
                    "faixa_aplicacao_m": faixa_aplicacao_m,
                    "tamanho_gotas_dmv": tamanho_gotas_dmv,
                }
            )

        referencias.append(
            {
                "key": key,
                "label": data["label"],
                "medida_label": data["medida_label"],
                "tipo_aplicacao": data["tipo_aplicacao"],
                "regras": data["regras"],
                "rows": rows,
            }
        )
    return referencias


def _build_base_context(user):
    return {
        "mistura_padrao": "500 g de BTI WDG para 10 L de agua (ou 250 g para 5 L).",
        "piloto_nome": (
            getattr(getattr(user, "piloto", None), "nome_piloto", None)
            or getattr(user, "nome_uvis", "")
            or ""
        ),
        "referencias_dosagem": _build_referencias_dosagem(),
        "os_context": None,
        "modo_visualizacao": False,
        "calculo_dosagem_planejado": None,
        "calculo_dosagem_planejado_json": "",
    }


def _get_piloto_os_planejamento(user, os_id):
    if not getattr(user, "piloto_id", None):
        raise PilotoOsError("Piloto sem vinculo cadastrado.", "danger", redirect_endpoint="main.piloto_os")

    solicitacao = (
        Solicitacao.query
        .options(
            joinedload(Solicitacao.usuario),
            joinedload(Solicitacao.equipe),
            joinedload(Solicitacao.ordem_servico),
        )
        .get_or_404(os_id)
    )

    status_permitidos = set(STATUS_OS_APROVADAS_COM_ACENTO + STATUS_OS_CONCLUIDAS)
    if solicitacao.status not in status_permitidos:
        raise PilotoOsError(
            "Esta OS nao esta liberada para planejamento de dosagem.",
            "warning",
            redirect_endpoint="main.piloto_os",
        )

    if not solicitacao.equipe_id:
        raise PilotoOsError(
            "Esta OS nao possui equipe atribuida.",
            "danger",
            redirect_endpoint="main.piloto_os",
        )

    vinculo = _buscar_vinculo_piloto_na_equipe(user.piloto_id, solicitacao.equipe_id)
    if not vinculo:
        raise PilotoOsError(
            "Voce nao tem permissao para acessar esta OS.",
            "danger",
            redirect_endpoint="main.piloto_os",
        )

    return solicitacao


def build_piloto_dosagem_context(user, os_id=None):
    context = _build_base_context(user)
    if os_id is None:
        return context

    solicitacao = _get_piloto_os_planejamento(user, os_id)
    ordem = solicitacao.ordem_servico
    calculo_dosagem_planejado = _parse_json_object(
        getattr(ordem, "calculo_dosagem_planejado", None) if ordem else None
    )
    modo_visualizacao = (solicitacao.status or "").strip().upper() in {"CONCLUIDO", "CONCLU\u00cdDO"}

    context.update(
        {
            "os_context": {
                "id": solicitacao.id,
                "foco": solicitacao.foco or "",
                "tipo_operacao": solicitacao.tipo_operacao or "",
                "tipo_visita": solicitacao.tipo_visita or "",
                "uvis_nome": solicitacao.usuario.nome_uvis if solicitacao.usuario else "",
                "endereco": (
                    f"{solicitacao.logradouro or ''}, {solicitacao.numero or 'S/N'} - "
                    f"{solicitacao.bairro or ''} - {solicitacao.cidade or ''}/{solicitacao.uf or ''}"
                ),
                "data_agendada_label": (
                    solicitacao.data_agendamento.strftime("%d/%m/%Y")
                    if solicitacao.data_agendamento else ""
                ),
                "hora_agendada_label": (
                    solicitacao.hora_agendamento.strftime("%H:%M")
                    if solicitacao.hora_agendamento else ""
                ),
                "planejado_em_label": (
                    ordem.calculo_dosagem_planejado_em.strftime("%d/%m/%Y %H:%M")
                    if ordem and ordem.calculo_dosagem_planejado_em else "Nao salvo"
                ),
            },
            "modo_visualizacao": modo_visualizacao,
            "calculo_dosagem_planejado": calculo_dosagem_planejado,
            "calculo_dosagem_planejado_json": (
                json.dumps(calculo_dosagem_planejado, ensure_ascii=False)
                if calculo_dosagem_planejado else ""
            ),
        }
    )
    return context


def salvar_piloto_dosagem_planejada(user, os_id, raw_payload):
    solicitacao = _get_piloto_os_planejamento(user, os_id)
    if (solicitacao.status or "").strip().upper() in {"CONCLUIDO", "CONCLU\u00cdDO"}:
        raise PilotoOsError(
            "Esta OS ja foi concluida e o planejamento nao pode mais ser alterado.",
            "warning",
            redirect_endpoint="main.piloto_os_dosagem",
        )

    calculo_dosagem_planejado = _sanitize_calculo_dosagem_planejado(raw_payload)
    if not calculo_dosagem_planejado:
        raise PilotoOsError(
            "Calculo invalido. Refaça a dosagem antes de salvar o planejamento.",
            "warning",
            redirect_endpoint="main.piloto_os_dosagem",
        )

    ordem = solicitacao.ordem_servico
    if ordem is None:
        ordem = OrdemServico(
            solicitacao_id=solicitacao.id,
            equipe_id=solicitacao.equipe_id,
        )
        ordem.solicitacao = solicitacao

    if ordem.calculo_dosagem_planejado != calculo_dosagem_planejado:
        ordem.calculo_dosagem_planejado_em = datetime.now()
    elif ordem.calculo_dosagem_planejado_em is None:
        ordem.calculo_dosagem_planejado_em = datetime.now()

    ordem.calculo_dosagem_planejado = calculo_dosagem_planejado
    db.session.add(ordem)
    db.session.commit()
    return f"Planejamento de dosagem da OS #{solicitacao.id} salvo com sucesso."
