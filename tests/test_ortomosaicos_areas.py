import importlib.util
import pytest
from rasterio.warp import transform
from sqlalchemy import create_engine, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.extensions import db
from app.models import Ortomosaico, OrtomosaicoArea, Prefeitura, Usuario
from app.modules.ortomosaicos.areas import calculate
from tests.test_ortomosaicos import ROOT, app, client
from tests.test_ortomosaicos_agua import survey, BOUNDS


def payload():
    x,y=transform('EPSG:4326','EPSG:32723',[-45.5],[-23.5])
    lon,lat=transform('EPSG:32723','EPSG:4326',[x[0],x[0]+100,x[0]+100,x[0],x[0]], [y[0],y[0],y[0]+100,y[0]+100,y[0]])
    return dict(nome='Quadra',geometria=dict(type='Polygon',coordinates=[[list(p) for p in zip(lon,lat)]]))


def test_metric_area_not_mercator():
    result=calculate(payload()|{'resultado':{'area_m2':1}}, BOUNDS)['resultado']
    assert result['area_m2']==pytest.approx(10000,abs=.01)
    assert result['area_ha']==pytest.approx(1,abs=.00001)
    assert result['perimetro_m']==pytest.approx(400,abs=.001)


@pytest.mark.parametrize('ring',[
    [[0,0],[1,0],[1,1],[0,0]],
    [[-45.5,-23.5],[-45.4,-23.4],[-45.4,-23.5],[-45.5,-23.4],[-45.5,-23.5]],
    [[-45.5,-23.5]]*4,
    [[True,-23.5],[-45.4,-23.5],[-45.4,-23.4],[True,-23.5]],
    [[float('nan'),-23.5]]*4,
    [[-45.5,-23.5],[-45.4,-23.5],[-45.4,-23.4]],
])
def test_invalid_polygons(ring):
    with pytest.raises(ValueError):
        calculate(payload()|{'geometria':{'type':'Polygon','coordinates':[ring]}},BOUNDS)


def test_save_reload_preview_and_delete(app,survey):
    c=client(app);url=f'/api/ortomosaicos/{survey}/areas';headers={'X-CSRFToken':'token'}
    preview=c.post(url+'/calcular',json=payload(),headers=headers)
    assert preview.status_code==200
    with app.app_context():assert OrtomosaicoArea.query.count()==0
    assert c.post(url,json=payload()).status_code==403
    saved=c.post(url,json=payload(),headers=headers)
    assert saved.status_code==201
    assert client(app,2).get(url).json['items']==[saved.json['item']]
    assert c.get(url).headers['Cache-Control']=='private, no-store'
    for uid in range(3,10):assert client(app,uid).get(url).status_code==403
    assert app.test_client().get(url).status_code==401
    aid=saved.json['item']['id']
    with app.app_context():
        row=db.session.get(Ortomosaico,survey);row.status='processando';db.session.commit()
    assert c.post(url,json=payload(),headers=headers).status_code==409
    with app.app_context():
        row=db.session.get(Ortomosaico,survey);row.status='pronto';db.session.commit()
    assert c.delete(f'/api/ortomosaicos/999/areas/{aid}',headers=headers).status_code==404
    assert c.delete(f'{url}/{aid}',headers=headers).status_code==204
    assert c.get(url).json['items']==[]


def test_migration_roundtrip():
    path=ROOT/'migrations/versions/c9e4a7120b65_ortomosaico_areas.py'
    spec=importlib.util.spec_from_file_location('area_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with create_engine('sqlite://').begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            assert 'ortomosaico_areas' in inspect(conn).get_table_names()
            module.downgrade()
            assert 'ortomosaico_areas' not in inspect(conn).get_table_names()


def test_dedicated_account_is_scoped_to_its_municipality(app, survey):
    with app.app_context():
        db.session.add(Prefeitura(id=2,nome='Outra prefeitura',slug='outra',ativa=True))
        db.session.add(Usuario(id=15,nome_uvis='Mapas',login='mapas',senha_hash='test',tipo_usuario='ortomosaico',prefeitura_id=1))
        other=Ortomosaico(prefeitura_id=2,usuario_id=1,nome='Outro levantamento',arquivo_nome='test.tif',original_path='private',sha256='other',tamanho_bytes=1,status='pronto',tipo='rgb',metadados={'limites':BOUNDS})
        db.session.add(other);db.session.commit();other_id=other.id
    c=client(app,15);headers={'X-CSRFToken':'token'}
    saved=c.post(f'/api/ortomosaicos/{survey}/areas',json=payload(),headers=headers)
    assert saved.status_code==201
    aid=saved.json['item']['id']
    assert c.get(f'/api/ortomosaicos/{survey}/areas').status_code==200
    assert c.get(f'/api/ortomosaicos/{other_id}/areas').status_code==404
    assert c.post(f'/api/ortomosaicos/{other_id}/areas/calcular',json=payload(),headers=headers).status_code==404
    assert c.delete(f'/api/ortomosaicos/{other_id}/areas/{aid}',headers=headers).status_code==404


def test_database_failure_rolls_back_and_returns_retryable_error(app,survey,monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    with app.app_context():
        rollback=db.session.rollback
        rolled_back=[]
        def fail():raise SQLAlchemyError('database unavailable')
        def recover():rolled_back.append(True);rollback()
        monkeypatch.setattr(db.session,'commit',fail)
        monkeypatch.setattr(db.session,'rollback',recover)
        response=client(app).post(f'/api/ortomosaicos/{survey}/areas',json=payload(),headers={'X-CSRFToken':'token'})
        assert response.status_code==503
        assert 'desenho foi mantido' in response.json['error']
        assert rolled_back==[True]


def test_area_form_owns_its_async_loading_state(app):
    page=client(app).get('/ortomosaicos').text
    assert '<form id="ortho-area-form" class="form-no-loading">' in page


def test_update_saved_area_keeps_id_and_recalculates(app,survey):
    c=client(app);headers={'X-CSRFToken':'token'};url=f'/api/ortomosaicos/{survey}/areas'
    item=c.post(url,json=payload(),headers=headers).json['item']
    target=f"{url}/{item['id']}"
    updated=c.put(target,json=payload()|{'nome':'Área revisada','resultado':{'area_m2':1}},headers=headers)
    assert updated.status_code==200
    assert updated.json['item']['id']==item['id']
    assert updated.json['item']['nome']=='Área revisada'
    assert updated.json['item']['resultado']['area_m2']==pytest.approx(10000,abs=.01)
    assert c.put(target,json=payload()|{'nome':''},headers=headers).status_code==400
    assert c.put(target,json=payload()).status_code==403
    assert c.put(f'/api/ortomosaicos/999/areas/{item["id"]}',json=payload(),headers=headers).status_code==404
    assert c.get(url).json['items'][0]['nome']=='Área revisada'
