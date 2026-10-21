"""Exclusão HTTP e efeitos no consolidado; somente SQLite descartável com FKs ativas."""
import re
from unittest.mock import patch

import pytest
import sqlalchemy as sa

from app.extensions import db
from app.models import AuditoriaUsuario, Usuario
from app.modules.gestao_ti.service import save_configurations
from app.modules.vigilancia.deletion import DeletionStore
from app.modules.vigilancia.field_store import FieldConflict
from app.modules.vigilancia.field_models import CampoInspecao, CampoLoteInspecao, CampoImovel
from app.modules.vigilancia.planning_models import CampoPlanoVisita
from app.modules.vigilancia.results import ResultsStore, filters_from
from app.modules.portal_cidadao.public_risk import get_public_risk_report
from app.modules.vigilancia.sinan import MUNICIPALITIES_BY_IBGE
from werkzeug.datastructures import MultiDict

from test_vigilancia_planning import planned
from test_vigilancia_planned_csv import make_plan, visits
from test_vigilancia_field_routes import client, login, token


@pytest.fixture
def deletion(planned):
    c, store = planned
    def enable_foreign_keys(connection, record, proxy):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()
    sa.event.listen(store.engine, 'checkout', enable_foreign_keys)
    with c.application.app_context():
        for uid, role in ((901, 'dev'), (902, 'admin'), (903, 'diretor'), (904, 'prefeitura_admin')):
            db.session.add(Usuario(id=uid, login=f'exclusao-{uid}', nome_uvis=f'Conta {role}',
                senha_hash='unused', tipo_usuario=role, prefeitura_id=None if uid != 904 else 7))
        db.session.commit()
        with store.engine.connect() as conn:
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')
            assert conn.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1
    make_plan(store)
    batch = store.prepare(visits(), prefeitura=7, demo=True, actor='703', source='Arquivo A', filename='visitas.csv')
    store.confirm(batch['id'], prefeitura=7, actor='703')
    login(c, '703')
    c.get('/vigilancia/campo?demo=true')
    return c, store, batch


def selection(kind='levantamento', code='L-2026-01', **changes):
    return dict(prefeitura_id='7', demo='true', tipo=kind, codigo=code,
                origem='LIRAA' if kind == 'visita' else '', **changes)


def review(c, values=None):
    values = values or selection()
    page = c.get('/vigilancia/excluir', query_string=values)
    assert page.status_code == 200, page.text
    match = re.search(r'name="revisao" value="([a-f0-9]+)"', page.text)
    return dict(values, revisao=match[1], confirmacao='sim', _csrf_token=token(c))


def remove(c, values=None):
    return c.post('/vigilancia/excluir', data=review(c, values))


def public(store):
    return get_public_risk_report({'VIGILANCIA_MUNICIPIOS_IBGE': {'7': '2610905'},
        'VIGILANCIA_IMPORT_ENABLED': True, 'SINAN_ENABLED': False},
        MUNICIPALITIES_BY_IBGE['2610905'], MultiDict({'demo': 'true'}), engine=store.engine)


def test_single_visit_disappears_from_all_batches_maps_and_execution_but_original_csv_survives(deletion):
    c, store, batch = deletion
    other = store.prepare(visits(), prefeitura=7, demo=True, actor='703', source='Arquivo B', filename='visitas.csv')
    store.confirm(other['id'], prefeitura=7, actor='703')
    original = store.original(batch['id'], 7)
    assert len(public(store)['geografia']['features']) == 2
    form = review(c, selection('visita', 'VIS-1'))
    assert len(store.records(7, demo=True)) == 2  # GET só revisa.
    response = c.post('/vigilancia/excluir', data=form)
    assert response.status_code == 303, response.text
    assert [r['inspecao_codigo'] for r in store.records(7, demo=True)] == ['VIS-2']
    report = public(store)
    assert report['liraa']['visitas'] == 1 and len(report['geografia']['features']) == 1
    assert report['liraa']['indicadores'][0]['imoveis_positivos'] == 0
    assert store.overview(7, True, 'L-2026-01')['quarteiroes'][0]['inspecionados'] == 0
    assert store.original(batch['id'], 7) == original
    for lot in (batch, other):
        assert store.get(lot['id'], 7)['report']['exclusoes'][0]['tipo'] == 'visita'
        with pytest.raises(FieldConflict, match='exclusões'):
            store.confirm(lot['id'], prefeitura=7, actor='703')
    assert 'Carga afetada por exclusões' in c.get('/vigilancia/importacoes?lote='+batch['id']).text
    with store.connection() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(CampoLoteInspecao)) == 2
        assert conn.scalar(sa.select(sa.func.count()).select_from(CampoPlanoVisita)) == 1
        assert conn.scalar(sa.select(sa.func.count()).select_from(CampoImovel)) == 1
        event = conn.execute(sa.select(AuditoriaUsuario.__table__)).mappings().one()
        assert event['tipo_evento'] == 'EXCLUSAO' and event['prefeitura_id'] == 7
        assert event['usuario_id'] == 703 and event['detalhes']['visitas'] == 1


@pytest.mark.parametrize('state', ['RASCUNHO', 'LIBERADO', 'ENCERRADO'])
def test_plan_deletion_preserves_shared_territory_and_other_mode(deletion, state):
    c, store, batch = deletion
    from app.modules.vigilancia.planning_models import CampoPlano
    with store.connection(write_prefeitura=7) as conn:
        conn.execute(CampoPlano.__table__.update().where(CampoPlano.code == 'L-2026-01').values(status=state))
    # Mesmo código em outro modo e outra prefeitura não é alvo da operação.
    store.mutate(7, False, '703', 'criar', dict(plano='L-2026-01', titulo='Outro modo',
        inicio='2026-10-19', fim='2026-10-23', responsavel='Coordenação', fonte='Autorizado'))
    response = remove(c)
    assert response.status_code == 303, response.text
    overview = store.overview(7, True, 'L-2026-01')
    assert overview['plano'] is None and len(overview['territorio']) == 2
    assert store.overview(7, False, 'L-2026-01')['plano']
    assert store.records(7, demo=True) == []
    assert public(store)['geografia']['features'] == [] and not public(store)['liraa']['disponivel']
    assert store.original(batch['id'], 7)


def test_linked_block_cannot_be_deleted_until_plan_is_removed(deletion):
    c, store, _ = deletion
    values = selection('quarteirao', 'Q-1')
    page = c.get('/vigilancia/excluir', query_string=values)
    assert 'Remova os vínculos nas amostras' in page.text and 'Confirmar exclusão' not in page.text
    snapshot = DeletionStore(store.engine).preview(7, True, 'quarteirao', 'Q-1')
    response = c.post('/vigilancia/excluir', data=dict(values, revisao=snapshot['revisao'], confirmacao='sim', _csrf_token=token(c)))
    assert response.status_code == 409
    assert remove(c).status_code == 303
    assert remove(c, values).status_code == 303
    assert [r['code'] for r in store.overview(7, True)['territorio']] == ['Q-2']


def test_stale_review_rolls_back_and_pending_csv_cannot_restore_deleted_visits(deletion):
    c, store, _ = deletion
    form = review(c)
    pending = store.prepare(visits(), prefeitura=7, demo=True, actor='703', source='Pendente', filename='visitas.csv')
    # O novo lote é parte do impacto: revisão anterior não pode autorizar sua alteração.
    assert c.post('/vigilancia/excluir', data=form).status_code == 409
    assert len(store.records(7, demo=True)) == 2
    assert remove(c, selection('visita', 'VIS-1')).status_code == 303
    with pytest.raises(FieldConflict, match='exclusões'):
        store.confirm(pending['id'], prefeitura=7, actor='703')
    with pytest.raises(FieldConflict, match='afetada por exclusões'):
        store.prepare(visits(), prefeitura=7, demo=True, actor='703', source='Arquivo A', filename='visitas.csv')


@pytest.mark.parametrize('uid', ['901', '902', '703', '704'])
def test_eligible_identities_and_covisa_municipal_boundary(deletion, uid):
    c, store, _ = deletion
    login(c, uid)
    page = c.get('/vigilancia/excluir', query_string=selection())
    assert page.status_code == (403 if uid == '704' else 200)


@pytest.mark.parametrize('uid', ['903', '904', '705', '701', '706'])
def test_other_roles_are_denied_even_with_ti_delete_permission(deletion, uid):
    c, store, _ = deletion
    login(c, uid)
    with patch('app.modules.vigilancia.field_routes.can_access_endpoint', return_value=True), \
         patch('app.modules.vigilancia.field_routes.route_access', return_value=True), \
         patch('app.modules.vigilancia.access.has_permission', return_value=True):
        assert c.get('/vigilancia/excluir', query_string=selection()).status_code == 403
        assert c.post('/vigilancia/excluir', data=dict(selection(), confirmacao='sim', revisao='a'*64, _csrf_token=token(c))).status_code == 403
    assert len(store.records(7, demo=True)) == 2


def test_csrf_confirmation_scope_mode_and_duplicate_fields_are_required(deletion):
    c, store, _ = deletion
    form = review(c)
    for changes, expected in [({'_csrf_token': ''}, 403), ({'confirmacao': 'nao'}, 409),
                              ({'prefeitura_id': '8'}, 403), ({'demo': 'false'}, 409)]:
        assert c.post('/vigilancia/excluir', data={**form, **changes}).status_code == expected
    repeated = MultiDict(list(form.items()) + [('codigo', 'OUTRO')])
    assert c.post('/vigilancia/excluir', data=repeated).status_code == 409
    assert len(store.records(7, demo=True)) == 2


@pytest.mark.parametrize('permissions', [[], ['prefeitura.vigilancia.consultar', 'prefeitura.vigilancia.editar']])
def test_dev_keeps_deletion_without_saved_grant_but_other_permissions_are_unchanged(deletion, permissions):
    from app.modules.gestao_ti.permissions import can_access_endpoint, has_permission
    c, store, _ = deletion
    c.application.config.update(CENTRAL_TI_ENABLED=True, CENTRAL_TI_ENFORCE_PERMISSIONS=True)
    with c.application.app_context():
        actor = db.session.get(Usuario, 901)
        save_configurations(actor, {'profiles': [{'id': 'dev', 'version': 0,
            'areas': ['prefeitura'] if permissions else [], 'permissions': permissions}]})
        assert has_permission(actor, 'prefeitura.vigilancia.excluir')
        assert can_access_endpoint(actor, 'main.vigilancia_excluir', 'GET')
        assert can_access_endpoint(actor, 'main.vigilancia_excluir', 'POST')
        assert has_permission(actor, 'prefeitura.vigilancia.editar') == bool(permissions)
        assert not has_permission(actor, 'prefeitura.solicitacoes.excluir')
    login(c, '901')
    if permissions:
        for url, label in [('/vigilancia/planejamento?prefeitura_id=7&demo=true', 'Excluir levantamento'),
                           ('/vigilancia/campo?prefeitura_id=7&demo=true', 'Excluir visita')]:
            page = c.get(url)
            assert page.status_code == 200 and label in page.text
    form = review(c, selection('visita', 'VIS-1'))
    assert c.post('/vigilancia/excluir', data={**form, '_csrf_token': ''}).status_code == 403
    assert c.post('/vigilancia/excluir', data={**form, 'confirmacao': 'nao'}).status_code == 409
    assert c.post('/vigilancia/excluir', data={**form, 'prefeitura_id': '8'}).status_code == 409
    assert c.post('/vigilancia/excluir', data=form).status_code == 303
    assert [row['inspecao_codigo'] for row in store.records(7, demo=True)] == ['VIS-2']
    assert c.get('/vigilancia/excluir', query_string=selection('visita', 'VIS-2')).status_code == 200
    c.application.config['VIGILANCIA_IMPORT_ENABLED'] = False
    assert c.get('/vigilancia/excluir', query_string=selection('visita', 'VIS-2')).status_code == 404


def test_ti_permission_is_required_and_role_is_rechecked_after_preview(deletion):
    c, store, _ = deletion
    form = review(c)
    c.application.config.update(CENTRAL_TI_ENABLED=True, CENTRAL_TI_ENFORCE_PERMISSIONS=True)
    with c.application.app_context():
        save_configurations(db.session.get(Usuario, 901), {'profiles':[{'id':'covisa','version':0,'areas':['prefeitura'],
            'permissions':['prefeitura.vigilancia.consultar','prefeitura.vigilancia.editar']}]})
    assert c.post('/vigilancia/excluir', data=form).status_code == 403
    with c.application.app_context():
        save_configurations(db.session.get(Usuario, 901), {'profiles':[{'id':'covisa','version':1,'areas':['prefeitura'],
            'permissions':['prefeitura.vigilancia.consultar','prefeitura.vigilancia.editar','prefeitura.vigilancia.excluir']}]})
    assert c.get('/vigilancia/excluir', query_string=selection()).status_code == 200
    with c.application.app_context():
        db.session.get(Usuario, 703).tipo_usuario = 'diretor'
        db.session.commit()
    assert c.post('/vigilancia/excluir', data=form).status_code == 403


def test_deletion_is_atomic_when_audit_write_fails(deletion):
    c, store, batch = deletion
    form = review(c)
    def fail_audit(conn, clause, *args, **kwargs):
        if getattr(clause, 'is_insert', False) and getattr(clause, 'table', None).name == 'auditoria_usuarios':
            raise sa.exc.IntegrityError('audit insert', {}, Exception('audit failure'))
    sa.event.listen(store.engine, 'before_execute', fail_audit)
    try:
        assert c.post('/vigilancia/excluir', data=form).status_code == 503
    finally:
        sa.event.remove(store.engine, 'before_execute', fail_audit)
    assert len(store.records(7, demo=True)) == 2
    assert not store.get(batch['id'], 7)['report'].get('exclusoes')
    assert store.overview(7, True, 'L-2026-01')['plano']
