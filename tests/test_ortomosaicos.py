import hashlib
import importlib.util
import io
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest
import rasterio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask import Blueprint, Flask
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from sqlalchemy import create_engine, inspect, text
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import Ortomosaico, Prefeitura, Usuario
from app.modules.ortomosaicos import register_routes
from app.modules.ortomosaicos import service
from app.modules.ortomosaicos.processor import inspect_raster, convert
from app.shared import skybox
from app.shared.csrf_security import register_csrf_security

ROOT=Path(__file__).resolve().parents[1]


def tiff(crs='EPSG:4326',count=3):
    with MemoryFile() as file:
        with file.open(driver='GTiff',width=64,height=64,count=count,dtype='uint8',crs=crs,
                       transform=from_origin(-45.43,-22.41,.000001,.000001),photometric='RGB' if count>=3 else 'MINISBLACK') as dst:
            dst.write(np.full((count,64,64),150,dtype='uint8'))
        return file.read()


@pytest.fixture
def app(tmp_path,monkeypatch):
    app=Flask(__name__,template_folder=str(ROOT/'app/templates'))
    app.config.update(TESTING=True,SECRET_KEY='ortho-test-secret-fixed-long-enough-12345',
        SQLALCHEMY_DATABASE_URI='sqlite:///'+str(tmp_path/'test.sqlite'),
        ORTHOMOSAIC_BACKGROUND_ENABLED=False,ORTHOMOSAIC_MAX_UPLOAD_MB=2,CSRF_PROTECTION_ENABLED=True)
    db.init_app(app);manager=LoginManager(app)
    manager.user_loader(lambda uid:db.session.get(Usuario,int(uid)))
    bp=Blueprint('main',__name__);register_routes(bp);app.register_blueprint(bp)
    register_csrf_security(app)
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block extra_styles %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}'}),app.jinja_loader])
    with app.app_context():
        db.create_all();db.session.add(Prefeitura(id=1,nome='Teste',slug='teste',ativa=True))
        for uid,role in enumerate(['dev','diretor','admin','piloto','equipe_oceano','covisa','prefeitura_admin','gestor_ti','equipe_uvis'],1):
            db.session.add(Usuario(id=uid,nome_uvis=role,login=role,senha_hash='test',tipo_usuario=role,prefeitura_id=1))
        db.session.commit()
    files={}
    class Remote:
        def __init__(self,data,status=200,headers=None):self.data=data;self.status_code=status;self.headers=headers or {};self.closed=False
        def __enter__(self):return self
        def __exit__(self,*args):self.close()
        def close(self):self.closed=True
        def iter_content(self,chunk_size):yield self.data
    def upload(file,path):files[path]=file.stream.read();return skybox.build_skybox_marker(path)
    def remote(method,path,headers=None,**kwargs):
        if path not in files:return Remote(b'',404)
        data=files[path];total=len(data);status=200;result={}
        if headers and headers.get('Range'):
            start,end=headers['Range'][6:].split('-');start=int(start);end=int(end) if end else total-1
            data=data[start:end+1];status=206;result['Content-Range']=f'bytes {start}-{end}/{total}'
        result['Content-Length']=str(len(data))
        return Remote(data,status,result)
    monkeypatch.setattr(skybox,'skybox_enabled',lambda:True)
    monkeypatch.setattr(skybox,'upload_file_to_skybox',upload)
    monkeypatch.setattr(skybox,'delete_skybox_file',lambda path:files.pop(skybox.remote_path_from_marker(path),None))
    monkeypatch.setattr(skybox,'_request',remote)
    app.test_files=files
    yield app
    with app.app_context():db.session.remove();db.engine.dispose()


def client(app,uid=1):
    c=app.test_client()
    with c.session_transaction() as session:session['_user_id']=str(uid);session['_fresh']=True;session['_ija_csrf']='token'
    return c


def upload(c,body=None,headers=True):
    return c.post('/api/ortomosaicos',data={'nome':'Base de teste','prefeitura_id':'1','arquivo':(io.BytesIO(body if body is not None else tiff()),'base.tif')},
                  headers={'X-CSRFToken':'token'} if headers else {})


def test_unlimited_upload_and_form(app):
    app.config['ORTHOMOSAIC_MAX_UPLOAD_MB']=0
    c=client(app)
    response=upload(c,tiff()+bytes(3*1024*1024))
    assert response.status_code==202,response.data
    html=c.get('/ortomosaicos').get_data(as_text=True)
    assert 'data-max-mb="0"' in html
    assert 'Sem limite de tamanho definido pelo sistema.' in html
    assert '200 milhões' not in html


def test_upload_larger_than_old_128mb_limit_streams_to_storage(app,tmp_path,monkeypatch):
    app.config['ORTHOMOSAIC_MAX_UPLOAD_MB']=0
    path=tmp_path/'large.tif'
    # A valid TIFF with sparse trailing padding exercises the old byte ceiling
    # without allocating the complete payload in test memory.
    with path.open('wb') as stream:
        stream.write(tiff());stream.seek(129*1024*1024);stream.write(b'\0')
    received=0
    def remote_upload(storage,remote):
        nonlocal received
        while chunk:=storage.stream.read(1024*1024):received+=len(chunk)
        return skybox.build_skybox_marker(remote)
    monkeypatch.setattr(skybox,'upload_file_to_skybox',remote_upload)
    with app.app_context(),path.open('rb') as stream:
        row=service.create_upload(FileStorage(stream=stream,filename='large.tif'),'Grande',1,1)
        assert row.tamanho_bytes==received==path.stat().st_size
        assert row.status=='pendente'


def test_pixel_ceiling_is_optional_and_passed_to_processor(app,tmp_path):
    path=tmp_path/'many_pixels.tif'
    with rasterio.open(path,'w',driver='GTiff',width=16000,height=16000,count=3,
                       dtype='uint8',crs='EPSG:4326',transform=from_origin(-45,-22,.000001,.000001),
                       photometric='RGB',tiled=True,SPARSE_OK=True):
        pass
    with app.app_context():
        app.config['ORTHOMOSAIC_MAX_PIXELS']=0
        metadata=service.raster_command('inspect',path)
        assert metadata['largura']*metadata['altura']>200_000_000
        app.config['ORTHOMOSAIC_MAX_PIXELS']=200_000_000
        with pytest.raises(ValueError,match='limite configurado'):
            service.raster_command('inspect',path)


def test_explicit_upload_limit_still_enforced(app):
    response=upload(client(app),tiff()+bytes(3*1024*1024))
    assert response.status_code==413
    assert not app.test_files


@pytest.mark.parametrize('front,legacy,expected', [
    ('front-browser-key','legacy-browser-key','front-browser-key'),
    ('','legacy-browser-key','legacy-browser-key'),
    ('','',''),
])
def test_satellite_configuration_uses_only_browser_key(app,front,legacy,expected):
    import json
    import re
    app.config.update(Maps_KEY_FRONT=front,
                      KEY_API_GOOGLE_MAPS=legacy,Maps_KEY_BACK='private-server-key')
    response=client(app).get('/ortomosaicos')
    assert response.status_code==200
    html=response.get_data(as_text=True)
    config=json.loads(re.search(r'<script id="ortho-basemap-config"[^>]*>(.*?)</script>',html).group(1))
    assert config=={'key':expected}
    assert 'private-server-key' not in html


@pytest.mark.parametrize('uid',[1,2])
def test_allowed_roles_upload_process_and_read_private_ranges(app,uid):
    c=client(app,uid);r=upload(c);assert r.status_code==202,r.data
    oid=r.json['item']['id'];assert r.json['item']['status']=='pendente'
    assert 'original_path' not in r.json['item']
    with app.app_context():
        assert service.process_one(oid)
        row=db.session.get(Ortomosaico,oid);assert row.status=='pronto'
        assert row.metadados['crs_visualizacao']=='EPSG:3857'
    r=c.get(f'/ortomosaicos/{oid}/arquivo.tif',headers={'Range':'bytes=0-15'})
    assert r.status_code==206 and len(r.data)==16
    assert r.headers['Cache-Control']=='private, no-store'
    assert r.headers['Content-Range'].startswith('bytes 0-15/')
    assert c.head(f'/ortomosaicos/{oid}/arquivo.tif').status_code==200
    assert c.get('/ortomosaicos').status_code==200


@pytest.mark.parametrize('uid',range(3,10))
def test_other_roles_cannot_access_any_endpoint_even_with_direct_link(app,uid):
    c=client(app,uid)
    for path in ['/ortomosaicos','/api/ortomosaicos','/api/ortomosaicos/1','/ortomosaicos/1/arquivo.tif']:
        assert c.get(path).status_code==403,path
    assert c.head('/ortomosaicos/1/arquivo.tif').status_code==403
    assert upload(c).status_code==403
    assert c.post('/api/ortomosaicos/1/reprocessar',headers={'X-CSRFToken':'token'}).status_code==403


def test_missing_login_csrf_validation_and_municipality(app):
    assert app.test_client().get('/api/ortomosaicos').status_code==401
    c=client(app)
    assert upload(c,headers=False).status_code==403
    r=c.post('/api/ortomosaicos',data={'prefeitura_id':'99'},headers={'X-CSRFToken':'token'})
    assert r.status_code==400
    assert c.get('/api/ortomosaicos?prefeitura_id=bad').status_code==400


@pytest.mark.parametrize('body',[b'not a tiff',b'',tiff(crs=None),tiff(count=1)])
def test_invalid_raster_rejected_before_remote_upload(app,body):
    r=upload(client(app),body);assert r.status_code==400,r.data
    assert not app.test_files
    with app.app_context():assert Ortomosaico.query.count()==0


def test_corrupted_remote_file_fails_then_can_retry(app):
    c=client(app);oid=upload(c).json['item']['id']
    original=next(iter(app.test_files));saved=app.test_files[original];app.test_files[original]=b'corrupt'
    with app.app_context():assert service.process_one(oid) is False
    r=c.get(f'/api/ortomosaicos/{oid}');assert r.json['item']['status']=='falha'
    app.test_files[original]=saved
    assert c.post(f'/api/ortomosaicos/{oid}/reprocessar',headers={'X-CSRFToken':'token'}).status_code==202
    with app.app_context():assert service.process_one(oid)


def test_worker_respects_active_claim_and_recovers_expired_one(app):
    oid=upload(client(app)).json['item']['id']
    with app.app_context():
        row=db.session.get(Ortomosaico,oid);row.status='processando';row.processamento_ate=service.now()+timedelta(minutes=20);db.session.commit()
        assert service.process_one(oid) is False
        row.processamento_ate=service.now()-timedelta(seconds=1);db.session.commit()
        assert service.process_one(oid)


def test_missing_raster_and_invalid_range(app):
    c=client(app);oid=upload(c).json['item']['id']
    assert c.get(f'/ortomosaicos/{oid}/arquivo.tif').status_code==404
    with app.app_context():service.process_one(oid)
    assert c.get(f'/ortomosaicos/{oid}/arquivo.tif',headers={'Range':'bytes=0-2,4-6'}).status_code==416


def test_migration_preserves_existing_records(tmp_path):
    spec=importlib.util.spec_from_file_location('ortho_migration',ROOT/'migrations/versions/c8d3e70a192f_ortomosaicos.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine('sqlite:///'+str(tmp_path/'migration.sqlite'))
    with engine.begin() as c:
        c.execute(text('CREATE TABLE usuarios (id INTEGER PRIMARY KEY)'))
        c.execute(text('CREATE TABLE prefeituras (id INTEGER PRIMARY KEY)'))
        c.execute(text('INSERT INTO prefeituras VALUES (1)'))
        with Operations.context(MigrationContext.configure(c)):
            migration.upgrade();assert inspect(c).has_table('ortomosaicos')
            assert c.execute(text('SELECT COUNT(*) FROM prefeituras')).scalar()==1
            migration.downgrade();assert not inspect(c).has_table('ortomosaicos')
    engine.dispose()
