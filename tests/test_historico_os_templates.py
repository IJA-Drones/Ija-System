from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, render_template
from jinja2 import ChoiceLoader, DictLoader


class FilterControls(HTMLParser):
    """Collect the options and submitted values from the rendered filters."""

    def __init__(self):
        super().__init__()
        self.selects = {}
        self.hidden_values = {}
        self._div_names = []
        self._select = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            self._div_names.append(attrs.get("data-name"))
        elif tag == "select":
            self._select = attrs.get("name") or next(
                (name for name in reversed(self._div_names) if name), None
            )
            self.selects[self._select] = []
        elif tag == "option" and self._select is not None:
            self.selects[self._select].append(attrs)
        elif tag == "input" and attrs.get("type") == "hidden":
            self.hidden_values.setdefault(attrs.get("name"), []).append(attrs.get("value"))

    def handle_endtag(self, tag):
        if tag == "div":
            self._div_names.pop()
        elif tag == "select":
            self._select = None


@pytest.mark.parametrize(
    "template_name",
    [
        "uvis_os_historico.html",
        "piloto_os_historico.html",
        "equipe_uvis_os_historico.html",
    ],
)
def test_history_filters_receive_catalogs_and_keep_selected_values(template_name):
    templates = Path(__file__).resolve().parents[1] / "app" / "templates"
    app = Flask(__name__, template_folder=str(templates))
    app.config["TESTING"] = True
    app.jinja_loader = ChoiceLoader(
        [DictLoader({"base.html": "{% block content %}{% endblock %}"}), app.jinja_loader]
    )
    app.jinja_env.globals["url_for"] = lambda endpoint, **values: f"/{endpoint}"

    catalogs = {
        "tipo_visita": ["Visita inicial", "Retorno"],
        "tipo_imovel": ["Residência", "Comércio"],
        "foco": ["Caixa d'água", "Recipientes & pneus", "Piscina"],
    }

    @app.context_processor
    def filter_catalogs():
        return {
            "solicitacao_tipo_visita_opcoes": catalogs["tipo_visita"],
            "solicitacao_tipo_imovel_opcoes": catalogs["tipo_imovel"],
            "solicitacao_filter_foco_opcoes": catalogs["foco"],
        }

    filters = {
        "status": "CONCLUIDAS",
        "unidade_values": [],
        "regiao": "",
        "equipe": "",
        "apoio_cet": "",
        "tipo_visita": "Retorno",
        "tipo_imovel": "Comércio",
        "foco_values": catalogs["foco"][:2],
        "protocolo": "",
        "endereco": "",
        "data_ini": "",
        "data_fim": "",
        "retorno_automatico": "",
    }
    with app.test_request_context("/"):
        rendered = render_template(
            template_name,
            filtros=filters,
            pedidos=[],
            paginacao=SimpleNamespace(total=0, pages=0),
            unidades_select=[],
            equipes_select=[],
            pagination_args={},
        )

    controls = FilterControls()
    controls.feed(rendered)
    for name, options in catalogs.items():
        assert [option["value"] for option in controls.selects[name]] == ["", *options]

    for name in ("tipo_visita", "tipo_imovel"):
        assert [
            option["value"] for option in controls.selects[name] if "selected" in option
        ] == [filters[name]]

    assert controls.hidden_values["foco"] == filters["foco_values"]
    assert [
        option["value"] for option in controls.selects["foco"] if "disabled" in option
    ] == filters["foco_values"]
