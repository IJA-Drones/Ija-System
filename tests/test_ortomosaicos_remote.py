"""Exercise GDAL authenticated range reads against an actual local HTTP server."""
import base64
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import re
import sys
import threading
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pytest
import rasterio
import requests
from rasterio.enums import ColorInterp
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from tests.test_ortomosaicos import app, client, upload
from app.extensions import db
from app.models import Ortomosaico
from app.modules.ortomosaicos import service, bounded_process
from app.modules.ortomosaicos.remote_source import remote_source
from app.modules.ortomosaicos.storage import TemporaryStorageError
from app.shared import skybox


def rgb16():
    with MemoryFile() as file:
        with file.open(driver='GTiff',width=512,height=512,count=8,dtype='uint16',
                       crs='EPSG:31983',transform=from_origin(300000,7400000,1,1),tiled=True,
                       blockxsize=256,blockysize=256) as ds:
            ds.write(np.full((8,512,512),32896,dtype='uint16'))
            ds.colorinterp=(ColorInterp.red,ColorInterp.green,ColorInterp.blue)+(ColorInterp.undefined,)*4+(ColorInterp.alpha,)
        return file.read()


@contextmanager
def server(body, *, ranges=True):
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_HEAD(self): self.reply(False)
        def do_GET(self): self.reply(True)
        def reply(self, send_body):
            calls.append((self.command,dict(self.headers)))
            if self.headers.get('Authorization') != 'Basic '+base64.b64encode(b'mapping:secret').decode():
                self.send_error(401);return
            if self.headers.get('If-Match') not in (None,'"verified"'):
                self.send_error(412);return
            start,end=0,len(body)-1
            request_range=self.headers.get('Range')
            if request_range and ranges:
                match=re.fullmatch(r'bytes=(\d+)-(\d*)',request_range)
                if not match:self.send_error(416);return
                start=int(match[1]);end=min(int(match[2]) if match[2] else end,end)
            self.send_response(206 if request_range and ranges else 200)
            self.send_header('Content-Length',str(end-start+1))
            self.send_header('ETag','"verified"')
            if request_range and ranges:self.send_header('Content-Range',f'bytes {start}-{end}/{len(body)}')
            self.end_headers()
            if send_body:
                try:self.wfile.write(body[start:end+1])
                except (BrokenPipeError,ConnectionResetError):pass
    instance=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker=threading.Thread(target=instance.serve_forever,daemon=True);worker.start()
    try:yield f'http://127.0.0.1:{instance.server_port}/original.tif',calls
    finally:instance.shutdown();instance.server_close();worker.join()


@pytest.mark.parametrize("tipo", ["rgb", "dem"])
def test_remote_conversion_preserves_original_without_disk_copy(app,monkeypatch,tipo):
    app.config.update(ORTHOMOSAIC_MAX_UPLOAD_MB=16,ORTHOMOSAIC_REMOTE_SOURCE_MIN_MB=1)
    if tipo == 'dem':
        from tests.test_dem_contours import dem, upload as upload_dem
        body = dem() + bytes(2*1024*1024)
        oid = upload_dem(client(app),arquivo=(io.BytesIO(body),'dem.tif')).json['item']['id']
    else:
        body=rgb16()
        oid=upload(client(app),body).json['item']['id']
    previous=skybox._request
    with server(body) as (url,calls):
        def request(method,path,**kwargs):
            if path.endswith('/original.tif'):return requests.request(method,url,auth=("mapping","secret"),**kwargs)
            return previous(method,path,**kwargs)
        monkeypatch.setattr(skybox,'_request',request)
        monkeypatch.setattr(skybox,'_remote_url',lambda _:url)
        monkeypatch.setattr(skybox,'_auth',lambda:('mapping','secret'))
        run=bounded_process.run
        def inspect_run(args,environment,scratch,root,limit):
            assert args[3].startswith('/vsicurl/http://127.0.0.1:')
            assert not list(Path(scratch).glob('original.tif'))
            header=Path(environment['GDAL_HTTP_HEADER_FILE'])
            assert header.stat().st_mode & 0o777 == 0o600
            return run(args,environment,scratch,root,limit)
        monkeypatch.setattr(bounded_process,'run',inspect_run)
        with app.app_context():
            assert service.process_one(oid)
            row=db.session.get(Ortomosaico,oid)
            assert row.status=='pronto',row.erro
            assert app.test_files[skybox.remote_path_from_marker(row.original_path)]==body
            if tipo == 'dem':
                assert row.curvas_path and row.jpeg_path
            else:
                with MemoryFile(app.test_files[skybox.remote_path_from_marker(row.cog_path)]) as mem,mem.open() as ds:
                    assert ds.count==4 and ds.dtypes==('uint8',)*4
                    assert 120<=ds.read(1)[ds.height//2,ds.width//2]<=130
        ranges=[headers for _,headers in calls if 'Range' in headers]
        assert len(ranges)>1
        assert all(h.get('If-Match')=='"verified"' for h in ranges)
        assert not list(Path(app.config['ORTHOMOSAIC_TEMP_DIR']).rglob('.skybox-headers'))
        assert not list(Path(app.config['ORTHOMOSAIC_TEMP_DIR']).rglob('*.tif'))


def test_unavailable_ranges_fail_without_full_download_fallback(app,monkeypatch,tmp_path):
    body=b'original'*100
    with server(body,ranges=False) as (url,calls),app.app_context():
        monkeypatch.setattr(skybox,'_request',lambda method,path,**kw:requests.request(method,url,auth=("mapping","secret"),**kw))
        row=SimpleNamespace(original_path='skybox://original.tif',tamanho_bytes=len(body))
        with pytest.raises(ValueError,match='leitura parcial'):
            with remote_source(row,tmp_path,'"verified"'):pass
    assert not list(tmp_path.glob('.skybox-headers'))
    assert not list(tmp_path.glob('*.tif'))


def test_remote_verification_rejects_changed_original_without_disk_copy(app,monkeypatch):
    oid=upload(client(app)).json['item']['id']
    key=next(iter(app.test_files));app.test_files[key]=b'x'*len(app.test_files[key])
    with app.app_context():
        row=db.session.get(Ortomosaico,oid)
        with pytest.raises(ValueError,match='integridade'):service._download(row,None)
    assert not list(Path(app.config['ORTHOMOSAIC_TEMP_DIR']).rglob('*.tif'))


def test_budget_stops_child_before_it_can_exhaust_provider_storage(app,tmp_path):
    import os
    tmp_path = tmp_path / 'scratch'; tmp_path.mkdir()
    with app.app_context(),pytest.raises(TemporaryStorageError,match='limite seguro'):
        bounded_process.run([sys.executable,'-c',
            'import pathlib,time;pathlib.Path("'+str(tmp_path/'mapa.tif')+'").write_bytes(bytes(2*1024*1024));time.sleep(30)'],
            os.environ.copy(),str(tmp_path),tmp_path,1024*1024)

    assert (tmp_path / 'mapa.tif').stat().st_size == 2*1024*1024
