"""Management snapshot uses persisted, scoped data and no external services."""
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import render_template
from jinja2 import ChoiceLoader, DictLoader

from app.extensions import db
from app.modules.painel_operacional.service import build_operational_overview
from tests.test_mapas_filters import HeatmapFilterTests


@pytest.fixture
def case():
    fixture = HeatmapFilterTests()
    fixture.setUp()
    yield fixture
    fixture.tearDown()


def test_overview_counts_agenda_and_week_exclude_closed_work(case):
    today = date(2026, 11, 24)
    case._new_request(status='PENDENTE', data_agendamento=today - timedelta(days=1))
    pending = case._new_request(status='PENDENTE', data_agendamento=today)
    approved = case._new_request(status='APROVADO', data_agendamento=today)
    case._new_request(status='APROVADO', data_agendamento=today + timedelta(days=6), equipe_id=case.equipe.id)
    case._new_request(status='APROVADO', data_agendamento=today + timedelta(days=7), equipe_id=case.equipe.id)
    case._new_request(status='CANCELADO', data_agendamento=today)
    case._new_request(status='NEGADO', data_agendamento=today)
    case._new_request(status='CONCLUÍDO', data_agendamento=today)
    # Responded orders are completed even if the request status has not caught up.
    answered = case._new_request(status='PENDENTE', data_agendamento=today, drone='SIM')
    from datetime import datetime
    answered.ordem_servico.respondido_em = datetime(2026, 11, 24, 10)
    db.session.commit()
    with patch('app.modules.painel_operacional.service.requests.get', side_effect=AssertionError('No network')):
        result = build_operational_overview(case.admin, today=today)
    assert result['totals'] == dict(hoje=2, em_analise=2, anteriores=1, sem_equipe=1, concluidas_mes=2)
    assert {row.id for row in result['agenda']} == {pending.id, approved.id}
    assert [day['count'] for day in result['week']] == [2, 0, 0, 0, 0, 0, 1]


def test_overview_honors_municipality_region_and_empty_scope(case):
    today = date(2026, 11, 24)
    for user in [case.uvis, case.uvis_other_region, case.uvis_other_city]:
        case._new_request(user=user, status='PENDENTE', data_agendamento=today)
    db.session.commit()
    regional = SimpleNamespace(tipo_usuario='regional', prefeitura_id=1, regiao='OESTE')
    result = build_operational_overview(regional, today=today)
    assert result['totals']['hoje'] == 1
    assert len(result['agenda']) == 1
    missing = SimpleNamespace(tipo_usuario='covisa', prefeitura_id=None)
    empty = build_operational_overview(missing, today=today)
    assert all(value == 0 for value in empty['totals'].values())
    assert empty['agenda'] == []
    assert empty['week_max'] == 1


def test_agenda_is_bounded_but_totals_are_not(case):
    today = date(2026, 11, 24)
    for _ in range(9):
        case._new_request(status='APROVADO', data_agendamento=today)
    db.session.commit()
    result = build_operational_overview(case.admin, today=today)
    assert result['totals']['hoje'] == 9
    assert len(result['agenda']) == 6
    assert result['week'][0]['count'] == 9


def test_template_renders_escaped_agenda_and_permission_filtered_shortcuts(case):
    from pathlib import Path
    case._new_request(status='APROVADO', data_agendamento=date(2026, 11, 24), logradouro='<script>alert(1)</script>', equipe_id=case.equipe.id)
    db.session.commit()
    case.app.template_folder = str(Path(__file__).resolve().parents[1] / 'app/templates')
    case.app.jinja_loader = ChoiceLoader([DictLoader({'base.html': '{% block content %}{% endblock %}{% block scripts %}{% endblock %}'}), case.app.jinja_loader])
    for endpoint in ['painel_operacional', 'api_painel_operacional_contexto', 'admin_dashboard', 'mapa_relatorio', 'listar_equipes', 'listar_equipamentos', 'veiculos_menu']:
        case.app.add_url_rule('/' + endpoint, endpoint='main.' + endpoint, view_func=lambda: '')
    with case.app.test_request_context('/'):
        html = render_template('painel_operacional.html', overview=build_operational_overview(case.admin, today=date(2026, 11, 24), agenda_team=str(case.equipe.id)), google_maps_key='', central_ti_url_allowed=lambda url, *args: 'listar_equipamentos' not in url)
    assert 'Agenda de hoje' in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert '<script>alert(1)</script>' not in html
    assert 'href="/listar_equipamentos"' not in html
    assert 'data-op-address=' in html
    assert f'<option value="{case.equipe.id}" selected>{case.equipe.nome_equipe}</option>' in html
    assert f'<span class="op-agenda-team"><i class="bi bi-people"></i> {case.equipe.nome_equipe}</span>' in html
    assert '1 solicitação hoje' in html


def test_agenda_filter_shows_team_names_and_filters_week_without_changing_global_totals(case):
    from app.models import Equipe
    today = date(2026, 11, 24)
    other = Equipe(nome_equipe='Equipe Leste', prefeitura_id=1)
    db.session.add(other)
    db.session.flush()
    assigned = case._new_request(status='APROVADO', data_agendamento=today, equipe_id=case.equipe.id)
    case._new_request(status='APROVADO', data_agendamento=today, equipe_id=other.id)
    case._new_request(status='APROVADO', data_agendamento=today)
    case._new_request(status='APROVADO', data_agendamento=today + timedelta(days=1), equipe_id=case.equipe.id)
    db.session.commit()

    general = build_operational_overview(case.admin, today=today)
    selected = build_operational_overview(case.admin, today=today, agenda_team=str(case.equipe.id))
    assert selected['totals'] == general['totals']
    assert selected['agenda_total'] == 1
    assert [row.id for row in selected['agenda']] == [assigned.id]
    assert selected['agenda'][0].equipe_nome == case.equipe.nome_equipe
    assert selected['agenda_label'] == case.equipe.nome_equipe
    assert selected['agenda_team'] == str(case.equipe.id)
    assert [day['count'] for day in selected['week']] == [1, 1, 0, 0, 0, 0, 0]
    assert {team.id for team in selected['agenda_teams']} == {case.equipe.id, other.id}


def test_agenda_filter_without_team_and_team_with_no_work_today(case):
    today = date(2026, 11, 24)
    unassigned = case._new_request(status='PENDENTE', data_agendamento=today)
    case._new_request(status='APROVADO', data_agendamento=today + timedelta(days=1), equipe_id=case.equipe.id)
    db.session.commit()
    result = build_operational_overview(case.admin, today=today, agenda_team='sem_equipe')
    assert [row.id for row in result['agenda']] == [unassigned.id]
    assert result['agenda_total'] == 1
    assert result['agenda_label'] == 'Sem equipe definida'
    assert result['agenda'][0].equipe_nome is None
    empty = build_operational_overview(case.admin, today=today, agenda_team=case.equipe.id)
    assert empty['agenda_total'] == 0
    assert empty['agenda'] == []
    assert empty['week'][1]['count'] == 1


def test_team_options_and_filter_cannot_reveal_requests_outside_scope(case):
    from app.models import Equipe
    today = date(2026, 11, 24)
    foreign_team = Equipe(nome_equipe='Equipe de outra prefeitura', prefeitura_id=2)
    db.session.add(foreign_team)
    db.session.flush()
    case._new_request(user=case.uvis_other_city, status='APROVADO', data_agendamento=today, equipe_id=foreign_team.id)
    case._new_request(status='APROVADO', data_agendamento=today, equipe_id=case.equipe.id)
    db.session.commit()
    result = build_operational_overview(case.uvis, today=today)
    assert {team.id for team in result['agenda_teams']} == {case.equipe.id}
    for value in [str(foreign_team.id), '999999', '<script>', '-1']:
        with pytest.raises(ValueError, match='Equipe indisponível'):
            build_operational_overview(case.uvis, today=today, agenda_team=value)


def test_page_accepts_legacy_overview_during_template_reload_and_new_team_filter(case):
    """An old running service can render a newly reloaded template without a 500."""
    from pathlib import Path
    from flask import Blueprint
    from app.modules.painel_operacional import routes

    today = date(2026, 11, 24)
    for _ in range(9):
        case._new_request(status='APROVADO', data_agendamento=today, equipe_id=case.equipe.id)
    db.session.commit()
    legacy = build_operational_overview(case.admin, today=today)
    for key in ['agenda_total', 'agenda_team', 'agenda_teams', 'agenda_label']:
        legacy.pop(key)
    legacy['agenda'] = [SimpleNamespace(**{key: value for key, value in row._mapping.items() if key != 'equipe_nome'}) for row in legacy['agenda']]

    case.app.template_folder = str(Path(__file__).resolve().parents[1] / 'app/templates')
    case.app.jinja_loader = ChoiceLoader([DictLoader({'base.html': '{% block content %}{% endblock %}{% block scripts %}{% endblock %}'}), case.app.jinja_loader])
    bp = Blueprint('main', __name__)
    routes.register_routes(bp)
    case.app.register_blueprint(bp)
    for endpoint in ['admin_dashboard', 'mapa_relatorio', 'listar_equipes', 'listar_equipamentos', 'veiculos_menu']:
        case.app.add_url_rule('/' + endpoint, endpoint='main.' + endpoint, view_func=lambda: '')

    with patch.object(routes, 'route_access', return_value=True), patch.object(routes, 'build_operational_overview', return_value=legacy):
        response = case.app.test_client().get('/diretor/painel-operacional')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Exibindo as primeiras 6 de 9 solicitações' in html
    assert 'Todas as equipes · 9 solicitações hoje' in html
    assert 'id="opAgendaTeam"' not in html  # No filter that an old service cannot apply.
    assert f'Equipe #{case.equipe.id}' in html

    def current_overview(user, *, agenda_team):
        return build_operational_overview(user, today=today, agenda_team=agenda_team)

    with patch.object(routes, 'route_access', return_value=True), patch.object(routes, 'build_operational_overview', side_effect=current_overview):
        response = case.app.test_client().get(f'/diretor/painel-operacional?equipe_agenda={case.equipe.id}')
        invalid = case.app.test_client().get('/diretor/painel-operacional?equipe_agenda=999999')
    assert response.status_code == 200
    assert f'<option value="{case.equipe.id}" selected>' in response.get_data(as_text=True)
    assert case.equipe.nome_equipe in response.get_data(as_text=True)
    assert invalid.status_code == 400
