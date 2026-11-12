"""Four functional steps and exports at any stage, using isolated fictitious data."""
import csv
import io
import json
import zipfile
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import sqlalchemy as sa
import pytest

from app.extensions import db
from app.models import Prefeitura, Usuario
from app.modules.vigilancia.planning import PlanningStore
from app.modules.vigilancia.results import ResultsStore, filters_from
from test_vigilancia_planning import planned, client, create, change
from test_vigilancia_field_routes import login, token


FILES = Path(__file__).resolve().parents[1] / 'app/resources/treinamentos/testes'
SP_FILES = FILES.parent / 'testes-sao-paulo'


def upload(c, filename, **fields):
    fields.update(arquivo=(io.BytesIO((FILES / filename).read_bytes()), filename), _csrf_token=token(c))
    return c.post('/vigilancia/planejamento', data=fields)


def csv_rows(response):
    assert response.status_code == 200, response.text
    assert response.mimetype == 'text/csv'
    return list(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig')), delimiter=';'))


def page_links(response):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links, self.current, self.nav = [], None, ''
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'nav':
                self.nav = attrs.get('aria-label', '')
            if tag == 'a':
                self.current = dict(href=attrs.get('href'), text='', nav=self.nav, active=attrs.get('aria-current'))
        def handle_data(self, data):
            if self.current is not None:
                self.current['text'] += data
        def handle_endtag(self, tag):
            if tag == 'a' and self.current is not None:
                self.current['text'] = ' '.join(self.current['text'].split())
                self.links.append(self.current)
                self.current = None
            if tag == 'nav':
                self.nav = ''
    parser = Links()
    parser.feed(response.text)
    return parser.links


def test_normal_liraa_entry_has_four_tabs_and_opens_stratum_import(planned):
    c, planning = planned
    create(planning)
    login(c)
    entry = next(link for link in page_links(c.get('/vigilancia')) if link['text'] == 'Acessar Focal e LIRAa')
    assert parse_qs(urlsplit(entry['href']).query)['fluxo'] == ['levantamento']
    page = c.get(entry['href'])
    tabs = [link for link in page_links(page) if link['nav'] == 'Etapas do LIRAa']
    assert [tab['text'] for tab in tabs] == ['1 · Levantamento', '2 · Quarteirões', '3 · Estratos', '4 · Visitas']
    assert tabs[0]['active'] == 'page'
    assert next(link for link in page_links(page) if link['text'] == 'Ver resultados')['nav'] != 'Etapas do LIRAa'
    chooser = c.get(tabs[2]['href'])
    assert 'Selecione um levantamento em rascunho' in chooser.text
    survey = next(link for link in page_links(chooser) if link['text'] == 'L-2026-01 · Levantamento municipal')
    assert parse_qs(urlsplit(survey['href']).query)['etapa'] == ['3']
    imported = c.get(survey['href'])
    assert imported.status_code == 200
    assert 'Anexar CSV de estratos e amostra · arquivo 02' in imported.text
    assert 'id="amostra-arquivo"' in imported.text and 'Baixar CSV' in imported.text
    assert 'id="territorio"' not in imported.text and 'id="novo-levantamento"' not in imported.text
    tabs = [link for link in page_links(imported) if link['nav'] == 'Etapas do LIRAa']
    assert tabs[2]['active'] == 'page'
    for tab in tabs:
        query = parse_qs(urlsplit(tab['href']).query)
        assert query['prefeitura_id'] == ['7'] and query['demo'] == ['true']
        assert query.get('plano', query.get('levantamento')) == ['L-2026-01']
    # Old direct links also expose the same Estratos tab without a separate opt-in.
    legacy = c.get('/vigilancia/campo?demo=true&levantamento=L-2026-01')
    strata = next(link for link in page_links(legacy) if link['text'] == '3 · Estratos')
    assert 'Anexar CSV de estratos e amostra · arquivo 02' in c.get(strata['href']).text


@pytest.mark.parametrize('already_has_strata', [False, True])
def test_create_stratum_manually_without_csv_and_keep_inputs_on_error(planned, already_has_strata):
    c, planning = planned
    planning.mutate(7, True, 'a', 'criar', dict(plano='MANUAL', titulo='Cadastro manual DEMO',
        inicio='2026-11-09', fim='2026-11-13', responsavel='DEMO', fonte='Sem CSV'))
    if already_has_strata:
        planning.mutate(7, True, 'a', 'estrato', dict(plano='MANUAL', versao='1', estrato='E-ANTERIOR',
            imoveis_estrato='100', meta_estrato='5', criterio='Existente'))
    login(c)
    page = c.get('/vigilancia/planejamento?demo=true&fluxo=levantamento&etapa=3&plano=MANUAL')
    assert page.status_code == 200
    assert any(link['text'] == 'Novo estrato' and link['href'] == '#cadastrar-estrato' for link in page_links(page))
    manual = page.text.split('id="cadastrar-estrato"', 1)[1].split('</section>', 1)[0]
    assert 'id="estrato-form"' in manual and '<details' not in manual and 'type="file"' not in manual
    assert 'Salvar estrato' in manual
    common = dict(prefeitura_id='7', demo='true', fluxo='levantamento', etapa='3', acao='estrato', plano='MANUAL', _csrf_token=token(c))
    before = planning.overview(7, True, 'MANUAL')
    response = c.post('/vigilancia/planejamento', data={**common, 'versao': str(before['plano']['versao']),
        'estrato': 'E-NOVO', 'imoveis_estrato': '200', 'meta_estrato': '10', 'criterio': 'Criado à mão no sistema'})
    assert response.status_code == 303, response.text
    assert urlsplit(response.location).fragment == 'cadastrar-estrato'
    after = planning.overview(7, True, 'MANUAL')
    assert len(after['estratos']) == len(before['estratos']) + 1
    saved = next(row for row in after['estratos'] if row['code'] == 'E-NOVO')
    assert saved['imoveis'] == 200 and saved['meta'] == 10 and saved['criterio'] == 'Criado à mão no sistema'
    response = c.post('/vigilancia/planejamento', data={**common, 'versao': str(after['plano']['versao']),
        'estrato': 'E-INVALIDO', 'imoveis_estrato': '5', 'meta_estrato': '10', 'criterio': 'Preservar preenchimento'})
    assert response.status_code == 400
    manual = response.text.split('id="cadastrar-estrato"', 1)[1].split('</section>', 1)[0]
    assert 'value="E-INVALIDO"' in manual and 'value="Preservar preenchimento"' in manual
    assert planning.overview(7, True, 'MANUAL')['estratos'] == after['estratos']


def test_create_survey_then_territory_then_strata_then_visits_with_original_demo_files(planned):
    c, _ = planned
    app = c.application
    with app.app_context():
        db.session.add(Prefeitura(id=14, nome='Pesqueira DEMO', slug='pesqueira-demo'))
        db.session.add_all([
            Usuario(id=17, nome_uvis='Coordenação DEMO', login='coordenacao-demo', senha_hash='unused',
                    tipo_usuario='admin', prefeitura_id=14),
            Usuario(id=167, nome_uvis='Agente DEMO', login='agente-demo-167', senha_hash='unused',
                    tipo_usuario='agente_endemias', prefeitura_id=14),
        ])
        db.session.commit()
        planning = PlanningStore(db.engine)
    login(c, '17')
    common = dict(prefeitura_id='14', demo='true', fluxo='levantamento')
    page = c.get('/vigilancia/planejamento', query_string={**common, 'etapa': '1'})
    assert page.status_code == 200
    assert 'Levantamento LIRAa · passo 1 de 4' in page.text
    assert 'data-vigilancia-default="levantamentos"' in page.text
    assert 'id="criar-levantamento" open' in page.text
    assert 'aria-disabled="true"' not in page.text
    # Empty exports work before any step is completed.
    for kind in ('levantamentos', 'territorio', 'amostra'):
        assert csv_rows(c.get(f'/vigilancia/planejamento/exportar/{kind}.csv', query_string=common)) == []
    created = c.post('/vigilancia/planejamento', data={**common, '_csrf_token': token(c),
        'acao': 'criar', 'plano': 'teste-1', 'titulo': 'Kit DEMO', 'inicio': '2026-10-20', 'fim': '2026-10-23',
        'responsavel': 'Coordenação DEMO', 'fonte': 'Demonstração'})
    assert created.status_code == 303, created.text
    assert parse_qs(urlsplit(created.location).query)['etapa'] == ['1']
    assert urlsplit(created.location).fragment == 'levantamentos'
    page = c.get(created.location)
    assert 'data-vigilancia-default="levantamentos"' in page.text
    assert 'id="territorio"' not in page.text and 'id="amostra"' not in page.text
    assert 'teste-1 · Kit DEMO' in page.text
    next_step = next(link for link in page_links(page) if link['text'] == 'Continuar para 2 · Quarteirões')
    assert parse_qs(urlsplit(next_step['href']).query)['plano'] == ['teste-1']
    page = c.get(next_step['href'])
    assert 'data-vigilancia-default="territorio"' in page.text
    assert 'Exportar quarteirões' in page.text
    assert 'id="levantamentos"' not in page.text and 'id="amostra"' not in page.text
    assert 'Anexar CSV de quarteirões' in page.text
    assert csv_rows(c.get('/vigilancia/planejamento/exportar/levantamentos.csv', query_string=common))[0]['situacao'] == 'RASCUNHO'
    territory = upload(c, '01_Cadastro_territorial_Centro_Pesqueira_poligonos_DEMO.csv',
        **common, acao='importar_territorio', geometrias_confirmadas='sim', etapa='2', retorno_plano='teste-1')
    assert territory.status_code == 303, territory.text
    assert parse_qs(urlsplit(territory.location).query)['etapa'] == ['2']
    assert parse_qs(urlsplit(territory.location).query)['plano'] == ['teste-1']
    page = c.get(territory.location)
    assert 'data-vigilancia-default="territorio"' in page.text
    assert '3 quarteirões cadastrados' in page.text
    assert 'id="amostra"' not in page.text and 'id="novo-levantamento"' not in page.text
    assert 'Importar quarteirões e continuar' not in page.text
    next_step = next(link for link in page_links(page) if link['text'] == 'Continuar para 3 · Estratos e amostra')
    page = c.get(next_step['href'])
    assert 'data-vigilancia-default="amostra"' in page.text
    assert '<section class="vigilancia-preview-layout" id="importar-amostra">' in page.text
    assert 'Anexar CSV de estratos e amostra · arquivo 02' in page.text
    assert 'id="territorio"' not in page.text and 'id="novo-levantamento"' not in page.text
    plan = planning.overview(14, True, 'teste-1')['plano']
    sample = upload(c, '02_Amostra_Centro_Pesqueira_agente_DEMO.csv',
        **common, acao='importar_plano', etapa='3', plano='teste-1', versao=str(plan['versao']))
    assert sample.status_code == 303, sample.text
    overview = planning.overview(14, True, 'teste-1')
    assert len(overview['estratos']) == len(overview['quarteiroes']) == 3
    assert {block['agente_id'] for block in overview['quarteiroes']} == {167}
    # The sample is exportable while still in draft, before release and before visits.
    exported = csv_rows(c.get('/vigilancia/planejamento/exportar/amostra.csv', query_string={**common, 'plano': 'teste-1'}))
    assert len(exported) == 3 and {row['agente_id'] for row in exported} == {'167'}
    visits_page = c.get('/vigilancia/campo', query_string={**common, 'levantamento': 'teste-1'})
    assert visits_page.status_code == 200
    assert 'Levantamento LIRAa · passo 4 de 4' in visits_page.text
    assert 'Exportar visitas' in visits_page.text
    released = c.post('/vigilancia/planejamento', data={**common, '_csrf_token': token(c), 'acao': 'liberar',
        'plano': 'teste-1', 'versao': str(overview['plano']['versao']), 'amostra_validada': 'sim'})
    assert released.status_code == 303
    assert urlsplit(released.location).path == '/vigilancia/planejamento'
    assert parse_qs(urlsplit(released.location).query)['etapa'] == ['3']
    page = c.get(released.location)
    assert 'Coleta liberada' in page.text and 'id="amostra"' in page.text
    page = c.get(next(link['href'] for link in page_links(page) if link['text'] == 'Continuar para 4 · Visitas'))
    assert 'Selecionar quarteirão da visita' in page.text
    assert 'Anexar CSV de visitas · arquivo 03' in page.text
    imported = c.post('/vigilancia/campo', data={**common, '_csrf_token': token(c),
        'acao': 'preparar', 'fonte': 'Kit DEMO', 'levantamento_destino': 'teste-1',
        'arquivo': (io.BytesIO((FILES / '03_Visitas_LIRAa_Centro_Pesqueira_coordenadas_reais_DEMO.csv').read_bytes()), 'visitas.csv')})
    assert imported.status_code == 303, imported.text
    assert urlsplit(imported.location).path == '/vigilancia/campo'
    page = c.get(imported.location)
    assert 'Resultado da prévia' in page.text and 'Confirmar carga validada' in page.text
    batch = planning.history(14)[0]
    assert planning.records(14, demo=True) == []
    confirmed = c.post('/vigilancia/campo', data={**common, '_csrf_token': token(c), 'acao': 'confirmar', 'lote': batch['id']})
    assert confirmed.status_code == 303
    assert urlsplit(confirmed.location).path == '/vigilancia/campo'
    page = c.get(confirmed.location)
    assert 'Continuar registrando visitas' in page.text
    assert 'Levantamento LIRAa · passo 4 de 4' in page.text
    with app.app_context():
        report = ResultsStore(db.engine).report(14, True, filters_from({'levantamento': 'teste-1'}))
    assert report['atividades']['LIRAA'] == 24
    assert sum(row['imoveis_inspecionados'] for row in report['indicadores']) == 21
    assert sum(row['imoveis_positivos'] for row in report['indicadores']) == 3
    assert len(csv_rows(c.get('/vigilancia/campo/exportar.csv', query_string={**common, 'levantamento': 'teste-1'}))) == 24
    assert planning.records(14, demo=False) == []


def test_incomplete_stratum_exports_without_blocks_release_or_database_writes(planned):
    c, planning = planned
    login(c)
    planning.mutate(7, True, 'a', 'criar', dict(plano='incompleto', titulo='=1+1', inicio='2026-10-20',
        fim='2026-10-23', responsavel='Coordenação', fonte='DEMO'))
    planning.mutate(7, True, 'a', 'estrato', dict(plano='incompleto', versao='1', estrato='E-01',
        imoveis_estrato='100', meta_estrato='5', criterio='DEMO'))
    statements = []
    with c.application.app_context():
        engine = db.engine
    def observe(conn, cursor, statement, parameters, context, many):
        statements.append(statement)
    sa.event.listen(engine, 'before_cursor_execute', observe)
    try:
        data = csv_rows(c.get('/vigilancia/planejamento/exportar/amostra.csv?demo=true&plano=incompleto'))
        metadata = csv_rows(c.get('/vigilancia/planejamento/exportar/levantamentos.csv?demo=true&plano=incompleto'))
    finally:
        sa.event.remove(engine, 'before_cursor_execute', observe)
    assert len(data) == 1 and data[0]['estrato'] == 'E-01' and data[0]['quarteirao'] == ''
    assert metadata[0]['titulo'] == "'=1+1" and metadata[0]['situacao'] == 'RASCUNHO'
    assert all(statement.lstrip().upper().startswith('SELECT') for statement in statements)


def test_exports_keep_municipal_scope_demo_mode_and_missing_scope_rules(planned):
    c, planning = planned
    create(planning)
    login(c)
    for kind in ('levantamentos', 'territorio', 'amostra'):
        assert csv_rows(c.get(f'/vigilancia/planejamento/exportar/{kind}.csv?demo=true'))
        assert csv_rows(c.get(f'/vigilancia/planejamento/exportar/{kind}.csv?demo=false')) == []
        assert c.get(f'/vigilancia/planejamento/exportar/{kind}.csv?prefeitura_id=8&demo=true').status_code == 403
    login(c, 'uvis')
    assert c.get('/vigilancia/planejamento/exportar/amostra.csv?demo=true').status_code == 403
    login(c, 'global')
    assert c.get('/vigilancia/planejamento/exportar/amostra.csv?demo=true').status_code == 400


def test_failed_sample_upload_stays_with_the_survey_and_can_still_export(planned):
    c, planning = planned
    create(planning)
    login(c)
    c.get('/vigilancia/planejamento?fluxo=levantamento&etapa=3&plano=L-2026-01')
    plan = planning.overview(7, True, 'L-2026-01')['plano']
    response = c.post('/vigilancia/planejamento', data=dict(acao='importar_plano', plano='L-2026-01',
        versao=str(plan['versao']), demo='true', fluxo='levantamento', etapa='3', _csrf_token=token(c),
        arquivo=(io.BytesIO(b'cabecalho;errado\n1;2\n'), 'amostra.csv')))
    assert response.status_code == 400
    assert 'Anexar CSV de estratos e amostra · arquivo 02' in response.text
    assert 'Exportar estratos e amostra' in response.text
    assert planning.overview(7, True, 'L-2026-01')['plano']['versao'] == plan['versao']


def test_uvis_se_kit_imports_in_separate_screens_with_its_own_attachments(planned):
    c, planning = planned
    app = c.application
    # The isolated vigilance fixture omits training; its real authenticated downloads
    # are exercised for every MATERIALS entry in test_treinamentos.py.
    app.add_url_rule('/treinamentos/arquivos/<material_id>', endpoint='main.treinamentos_arquivo', view_func=lambda material_id: '')
    with app.app_context():
        db.session.add(Prefeitura(id=1, nome='Prefeitura de Sao Paulo', slug='sao-paulo-demo'))
        db.session.add(Usuario(id=55, nome_uvis='Coordenação SP DEMO', login='sp-demo', senha_hash='unused', tipo_usuario='admin', prefeitura_id=1))
        db.session.commit()
    login(c, '55')
    common = dict(prefeitura_id='1', demo='true', fluxo='levantamento')
    page = c.get('/vigilancia/planejamento', query_string={**common, 'etapa': '1'})
    assert 'id="territorio"' not in page.text and 'id="amostra"' not in page.text
    response = c.post('/vigilancia/planejamento', data={**common, '_csrf_token': token(c), 'acao': 'criar',
        'plano': 'DEMO-SP-SE-2026-11', 'titulo': 'UVIS Sé DEMO', 'inicio': '2026-11-09', 'fim': '2026-11-13', 'responsavel': 'DEMO', 'fonte': 'Kit fictício'})
    assert response.status_code == 303
    page = c.get(response.location)
    assert 'data-vigilancia-default="levantamentos"' in page.text
    assert 'id="territorio"' not in page.text
    page = c.get(next(link['href'] for link in page_links(page) if link['text'] == 'Continuar para 2 · Quarteirões'))
    assert '/treinamentos/arquivos/csv-sp-territorio' in page.text
    assert 'Baixar CSV · UVIS Sé · São Paulo' in page.text
    assert 'id="amostra"' not in page.text
    def post_file(prefix, action, **extra):
        path = next(SP_FILES.glob(prefix + '*.csv'))
        return c.post('/vigilancia/planejamento', data={**common, '_csrf_token': token(c), 'acao': action,
            'arquivo': (io.BytesIO(path.read_bytes()), path.name), **extra})
    response = post_file('01_', 'importar_territorio', etapa='2', retorno_plano='DEMO-SP-SE-2026-11', geometrias_confirmadas='sim')
    assert response.status_code == 303, response.text
    page = c.get(response.location)
    assert 'data-vigilancia-default="territorio"' in page.text
    assert '3 quarteirões cadastrados' in page.text and 'id="amostra"' not in page.text
    page = c.get(next(link['href'] for link in page_links(page) if link['text'] == 'Continuar para 3 · Estratos e amostra'))
    assert '/treinamentos/arquivos/csv-sp-amostra' in page.text
    assert 'id="territorio"' not in page.text
    response = post_file('02_', 'importar_plano', etapa='3', plano='DEMO-SP-SE-2026-11', versao='1')
    assert response.status_code == 303, response.text
    overview = planning.overview(1, True, 'DEMO-SP-SE-2026-11')
    assert {block['agente_id'] for block in overview['quarteiroes']} == {None}
    assert len(csv_rows(c.get('/vigilancia/planejamento/exportar/amostra.csv', query_string=common))) == 3
    response = c.post('/vigilancia/planejamento', data={**common, '_csrf_token': token(c), 'acao': 'liberar',
        'plano': 'DEMO-SP-SE-2026-11', 'versao': str(overview['plano']['versao']), 'amostra_validada': 'sim'})
    page = c.get(response.location)
    assert page.status_code == 200
    assert 'Coleta liberada' in page.text
    page = c.get(next(link['href'] for link in page_links(page) if link['text'] == 'Continuar para 4 · Visitas'))
    assert '/treinamentos/arquivos/csv-sp-visitas' in page.text and 'id="arquivo-csv"' in page.text
    path = next(SP_FILES.glob('03_*.csv'))
    response = c.post('/vigilancia/campo', data={**common, '_csrf_token': token(c), 'acao': 'preparar',
        'fonte': 'UVIS Sé DEMO', 'levantamento_destino': 'DEMO-SP-SE-2026-11', 'arquivo': (io.BytesIO(path.read_bytes()), path.name)})
    assert response.status_code == 303, response.text
    batch = planning.history(1)[0]
    response = c.post('/vigilancia/campo', data={**common, '_csrf_token': token(c), 'acao': 'confirmar', 'lote': batch['id']})
    assert response.status_code == 303, response.text
    with app.app_context():
        report = ResultsStore(db.engine).report(1, True, filters_from({'levantamento': 'DEMO-SP-SE-2026-11'}))
    assert report['atividades']['LIRAA'] == 24
    assert sum(row['imoveis_inspecionados'] for row in report['indicadores']) == 21
    assert sum(row['imoveis_positivos'] for row in report['indicadores']) == 3
    assert planning.records(1, demo=False) == [] and planning.records(7, demo=True) == []
    # The same confirmed imports must reach both the results and risk maps with
    # the selected municipality, never with Pernambuco as São Paulo's context.
    from test_vigilancia_risk_map import map_data
    app.config['VIGILANCIA_MUNICIPIOS_IBGE'] = {'1': '3550308'}
    query = dict(prefeitura_id='1', demo='true', levantamento='DEMO-SP-SE-2026-11')
    for endpoint in ['/vigilancia/risco', '/vigilancia/resultados']:
        page = c.get(endpoint, query_string=query)
        assert page.status_code == 200
        data = map_data(page)
        assert len(data['pontos']) == 24 and len(data['geografia']['features']) == 3
        assert data['ibge'] == '3550308'
        assert [feature['properties']['codigo'] for feature in data['contexto']['features']] == ['3550308']
        assert 'Pernambuco' not in page.text and 'CONDOMAR' not in page.text
        assert not map_data(c.get(endpoint, query_string={**query, 'demo': 'false'}))['pontos']
        assert not map_data(c.get(endpoint, query_string={**query, 'inicio': '2026-11-12'}))['pontos']


def test_sp_kit_preserves_the_four_pesqueira_layouts_and_source_records():
    from app.modules.vigilancia.sinan_import import parse_cases
    from app.modules.vigilancia.geometry import validate_polygon
    with zipfile.ZipFile(FILES.parent / 'kit-testes-sao-paulo-uvis-se-demo.zip') as archive:
        assert len([name for name in archive.namelist() if name.endswith('.csv')]) == 4
        for prefix, count in [('01_', 3), ('02_', 3), ('03_', 24), ('04_', 6)]:
            path = next(SP_FILES.glob(prefix + '*.csv'))
            original = next(FILES.glob(prefix + '*.csv'))
            rows = list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig')), delimiter=';'))
            assert rows[0] == next(csv.reader(io.StringIO(original.read_text(encoding='utf-8-sig')), delimiter=';'))
            assert len(rows) == count + 1
            assert archive.read('Sao-Paulo-UVIS-Se-DEMO/' + path.name) == path.read_bytes()
    territory = list(csv.DictReader(io.StringIO(next(SP_FILES.glob('01_*.csv')).read_text(encoding='utf-8-sig')), delimiter=';'))
    for row in territory:
        assert validate_polygon(row['geometria'])
    sources = json.loads((SP_FILES / 'FONTES_GEOGRAFICAS.json').read_text())
    assert sources['uvis'] == 'Sé' and sources['municipio_ibge'] == '3550308'
    assert {r['quadra_fiscal'] for r in sources['registros']} == {'006.014.001', '002.068.001', '002.059.001'}
    cases = parse_cases(next(SP_FILES.glob('04_*.csv')).read_bytes(), dict(disease='dengue', ibge='3550308', year=2026), True)
    assert len(cases) == 6
