from types import SimpleNamespace

import pytest

from app.shared.solicitacao_focos import (
    build_focus_catalog, get_tipo_visita_opcoes, validate_foco_selection,
)
from app.modules.solicitacoes.service import is_solicitacao_quadra
from app.modules.admin_dashboard.service import is_solicitacao_quadra as admin_quadra
from app.modules.piloto_os.service import build_os_criadouro_context


def test_quadra_is_a_focus_and_filter_for_internal_forms():
    catalog = build_focus_catalog()
    assert get_tipo_visita_opcoes() == ['Aedes', 'Culex', 'Outro']
    assert get_tipo_visita_opcoes(False) == ['Aedes', 'Culex']
    for options in [*catalog['aedes'].values(), catalog['culex'], catalog['outro'], catalog['filtro_foco_opcoes']]:
        assert options.count('QUADRA') == 1


@pytest.mark.parametrize('visit,property_type', [('Aedes', 'Imovel Geral'), ('Aedes', 'PE Cadastrado'), ('Culex', None)])
def test_quadra_focus_keeps_the_selected_visit_and_property(visit, property_type):
    assert validate_foco_selection(visit, property_type, 'quadra') == (visit, property_type, 'QUADRA')


def test_quadra_cannot_be_submitted_as_a_visit_type():
    with pytest.raises(ValueError, match='foco da ação'):
        validate_foco_selection('Quadra', None, 'QUADRA')
    with pytest.raises(ValueError, match='foco da ação'):
        validate_foco_selection('Outro', None, 'QUADRA', allow_custom_tipo_visita=True, tipo_visita_outro='Quadra')


@pytest.mark.parametrize('visit', ['Aedes', 'Culex', 'Quadra'])
def test_os_and_admin_identify_quadra_by_focus_including_legacy_records(visit):
    request = SimpleNamespace(tipo_visita=visit, foco='QUADRA', tipo_operacao='Monitoramento')
    assert is_solicitacao_quadra(request)
    assert admin_quadra(request)
    context = build_os_criadouro_context(request, None)
    assert context['os_quadra']
    assert context['os_criadouro_value'] == ''
    assert 'QUADRA' not in context['os_criadouro_opcoes']


def test_aedes_property_requirement_is_preserved_for_quadra():
    with pytest.raises(ValueError, match='tipo de imovel'):
        validate_foco_selection('Aedes', None, 'QUADRA')
