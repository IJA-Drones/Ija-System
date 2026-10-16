"""Real synthetic rasters, disposable DB and mocked private object storage."""
import importlib.util
import io
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from PIL import Image
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from sqlalchemy import create_engine, text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.extensions import db
from app.models import Ortomosaico
from app.modules.ortomosaicos import service
from app.modules.ortomosaicos.dem_processor import generate, inspect_dem, parameters
from app.shared import skybox
from tests.test_ortomosaicos import app, client, tiff, ROOT


def dem(unit='metre', nodata=-9999, empty=False):
    # Planar slope: z increases 1m east per pixel. Hole remains NoData.
    a=np.tile(np.arange(64,dtype='float32'),(64,1))
    a[20:40,20:40]=nodata
    if empty:a[:]=nodata
    with MemoryFile() as mem:
        with mem.open(driver='GTiff',width=64,height=64,count=1,dtype='float32',
                      crs='EPSG:31983',transform=from_origin(300000,7400000,1,1),nodata=nodata) as dst:
            dst.write(a,1)
            if unit:dst.set_band_unit(1,unit)
        return mem.read()


def upload(c, **overrides):
    data=dict(nome='Curvas de teste',prefeitura_id='1',tipo='dem',intervalo_m='5',resolucao_m='1',elevacoes_metros='1',
              arquivo=(io.BytesIO(dem()),'dem.tif'))
    data.update(overrides)
    return c.post('/api/ortomosaicos',data=data,headers={'X-CSRFToken':'token'})


def test_planar_contours_cotas_projection_holes_and_matching_jpeg(tmp_path):
    source=tmp_path/'dem.tif';source.write_bytes(dem())
    meta=generate(source,tmp_path/'result',5,1)
    features=json.loads((tmp_path/'result/curvas.geojson').read_text())['features']
    assert meta['crs_processamento']=='EPSG:31983'
    assert meta['grade']==[64,64] and meta['resolucao_m']==1
    assert meta['curvas']==len(features)
    for f in features:
        cota=f['properties']['cota'];assert cota%5==0
        assert f['properties']['mestra']==(cota%25==0)
        points=np.array(f['geometry']['coordinates'])
        x,y=rasterio.warp.transform('EPSG:4326','EPSG:31983',points[:,0],points[:,1])
        # All isolines lie on the correct x coordinate of the planar slope.
        np.testing.assert_allclose(x,300000+.5+cota,atol=.002)
        assert not any(300020.5<px<300039.5 and 7399960.5<py<7399979.5 for px,py in zip(x,y))
    with Image.open(tmp_path/'result/curvas.jpg') as image:
        assert image.format=='JPEG' and image.size==(3080,2200)


@pytest.mark.parametrize('interval,resolution',[(0,1),('NaN',1),(1,'inf'),(-1,1),(1,0),(None,1)])
def test_invalid_processing_parameters(interval,resolution):
    with pytest.raises(ValueError):parameters(interval,resolution)


@pytest.mark.parametrize('body',[b'invalid',tiff(),dem(unit='foot')])
def test_reject_bad_dem_before_storage(app,body):
    response=upload(client(app),arquivo=(io.BytesIO(body),'dem.tif'))
    assert response.status_code==400
    assert not app.test_files


def test_empty_dem_fails_without_publishing_outputs(tmp_path):
    path=tmp_path/'empty.tif';path.write_bytes(dem(empty=True))
    with pytest.raises(ValueError,match='válidas'):generate(path,tmp_path/'out')
    assert not (tmp_path/'out/curvas.jpg').exists()


@pytest.mark.parametrize('uid',[1,2])
def test_full_dem_upload_worker_map_and_jpeg(app,uid):
    c=client(app,uid);response=upload(c);assert response.status_code==202,response.data
    oid=response.json['item']['id']
    assert c.get(f'/ortomosaicos/{oid}/curvas.jpg').status_code==404
    with app.app_context():
        assert service.process_one(oid)
        row=db.session.get(Ortomosaico,oid);assert row.tipo=='dem' and row.cog_path is None
    item=c.get(f'/api/ortomosaicos/{oid}').json['item']
    assert item['status']=='pronto' and item['arquivo_url'] is None
    assert 'skybox://' not in json.dumps(item)
    response=c.get(item['curvas_url']);assert response.status_code==200
    assert json.loads(response.data)['features']
    response=c.get(item['jpeg_url']);assert response.status_code==200
    assert response.mimetype=='image/jpeg' and response.headers['Cache-Control']=='private, no-store'
    assert 'attachment;' in response.headers['Content-Disposition']
    assert Image.open(io.BytesIO(response.data)).format=='JPEG'
    assert c.head(item['jpeg_url']).status_code==200
    assert c.get(f'/ortomosaicos/{oid}/arquivo.tif').status_code==404
    for uid in range(3,10):
        for url in (item['jpeg_url'],item['curvas_url']):
            assert client(app,uid).get(url).status_code==403
    assert app.test_client().get(item['jpeg_url']).status_code==401


def test_dem_validation_and_csrf(app):
    c=client(app)
    assert upload(c,elevacoes_metros='0').status_code==400
    assert upload(c,intervalo_m='NaN').status_code==400
    assert upload(c,tipo='unknown').status_code==400
    assert c.post('/api/ortomosaicos',data={'tipo':'dem'}).status_code==403
    assert not app.test_files


def test_worker_cleans_partial_pair_and_allows_retry(app,monkeypatch):
    c=client(app);oid=upload(c).json['item']['id']
    original_upload=service._upload
    def fail_jpeg(path,remote):
        if str(path).endswith('.jpg'):raise RuntimeError('injected storage failure')
        return original_upload(path,remote)
    monkeypatch.setattr(service,'_upload',fail_jpeg)
    with app.app_context():assert not service.process_one(oid)
    assert len(app.test_files)==1  # Only original; never expose half a result.
    assert c.get(f'/ortomosaicos/{oid}/curvas.geojson').status_code==404
    monkeypatch.setattr(service,'_upload',original_upload)
    assert c.post(f'/api/ortomosaicos/{oid}/reprocessar',headers={'X-CSRFToken':'token'}).status_code==202
    with app.app_context():assert service.process_one(oid)


def test_access_check_applies_to_both_outputs(app,monkeypatch):
    from app.modules.ortomosaicos import routes
    c=client(app);oid=upload(c).json['item']['id']
    with app.app_context():assert service.process_one(oid)
    monkeypatch.setattr(routes,'can_access_prefeitura',lambda *_:False)
    assert c.get(f'/ortomosaicos/{oid}/curvas.geojson').status_code==404
    assert c.get(f'/ortomosaicos/{oid}/curvas.jpg').status_code==404


def test_dem_migration_preserves_rgb_record(tmp_path):
    def load(name):
        path=next((ROOT/'migrations/versions').glob(name+'*'))
        spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    original=load('c8d3e70a192f');migration=load('d9e4f81b203a')
    engine=create_engine('sqlite:///'+str(tmp_path/'migration.db'))
    with engine.begin() as c, Operations.context(MigrationContext.configure(c)):
        c.execute(text('CREATE TABLE usuarios (id INTEGER PRIMARY KEY)'))
        c.execute(text('CREATE TABLE prefeituras (id INTEGER PRIMARY KEY)'))
        original.upgrade()
        c.execute(text("INSERT INTO ortomosaicos (id,prefeitura_id,nome,arquivo_nome,original_path,sha256,tamanho_bytes,status,criado_em,atualizado_em) VALUES (1,1,'RGB','base.tif','skybox://original','abc',100,'pronto',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        migration.upgrade()
        assert c.execute(text('SELECT tipo FROM ortomosaicos WHERE id=1')).scalar()=='rgb'
        migration.downgrade()
        assert c.execute(text('SELECT nome FROM ortomosaicos WHERE id=1')).scalar()=='RGB'
    engine.dispose()


def test_retry_can_change_grid_without_reuploading_original(app):
    c=client(app);oid=upload(c).json['item']['id']
    with app.app_context():
        row=db.session.get(Ortomosaico,oid);row.status='falha';db.session.commit()
    url=f'/api/ortomosaicos/{oid}/reprocessar'
    headers={'X-CSRFToken':'token'}
    assert c.post(url,json={'resolucao_m':'nan'},headers=headers).status_code==400
    assert c.post(url,json=['bad'],headers=headers).status_code==400
    response=c.post(url,json={'resolucao_m':2,'intervalo_m':10},headers=headers)
    assert response.status_code==202
    assert response.json['item']['intervalo_m']==10 and response.json['item']['resolucao_m']==2
    assert len(app.test_files)==1
    with app.app_context():assert service.process_one(oid)
    assert c.post(url,json={'resolucao_m':3},headers=headers).status_code==409
