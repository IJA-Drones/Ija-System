"""Exercise resumable transfers without allocating a 16-GB request body."""
import pytest

from test_ortomosaicos import app, client, tiff
from app.models import Ortomosaico
from app.modules.ortomosaicos import uploads, service

HEADERS = {'X-CSRFToken': 'token'}


def start(c, size, **kwargs):
    return c.post('/api/ortomosaicos/uploads', json=dict(nome='Grande', prefeitura_id=1,
        filename='16gb.tif', size=size, **kwargs), headers=HEADERS)


def put(c, state, data, offset=None):
    return c.put(state['url'], data=data, content_type='application/octet-stream',
        headers={**HEADERS, 'Upload-Offset':str(state['offset'] if offset is None else offset)})


def test_receive_finalize_and_retry_are_idempotent(app):
    c=client(app); data=tiff()
    state=start(c,len(data)).json
    first=put(c,state,data[:100]).json
    # Lost HTTP response: sending the same offset twice must never append twice.
    assert put(c,state,data[:100]).status_code==409
    assert c.get(state['url']).json['offset']==100
    assert c.post(state['url'],headers=HEADERS).status_code==409
    state=put(c,first,data[100:]).json
    assert state['offset']==len(data)
    response=c.post(state['url'],headers=HEADERS)
    assert response.status_code==202 and response.json['status']=='finalizing'
    assert not app.test_files  # No lengthy Skybox PUT in the HTTP request.
    with app.app_context():
        uploads.finalize(state['id'])
        uploads.finalize(state['id'])
        assert Ortomosaico.query.count()==1
        assert next(iter(app.test_files.values()))==data
    response=c.get(state['url']).json
    assert response['status']=='complete' and response['item']['tamanho_bytes']==len(data)
    assert c.post(state['url'],headers=HEADERS).json['item']['id']==response['item']['id']
    with app.app_context():
        assert not (uploads.folder_for(state['id'])/'original.tif').exists()


def test_authorization_csrf_and_bounds(app):
    c=client(app)
    state=start(c,100).json
    assert client(app,2).get(state['url']).status_code==404
    assert client(app,3).get(state['url']).status_code==403
    assert c.put(state['url'],data=b'x',headers={'Upload-Offset':'0'}).status_code==403
    assert put(c,state,b'x',-1).status_code==409
    assert put(c,state,b'x'*101).status_code==413
    assert start(c,3*1024*1024).status_code==400
    assert start(c,10,tipo='dem').status_code==400
    assert c.get('/api/ortomosaicos/uploads/not-a-token').status_code==404
    assert c.get(state['url']).json['offset']==0


def test_16gb_offset_and_recovery_of_uncommitted_bytes(app):
    app.config['ORTHOMOSAIC_MAX_UPLOAD_MB']=0
    c=client(app); size=16*1024**3
    # This tests protocol arithmetic / sparse disk offsets, not available disk quota.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(uploads,'require_space',lambda *args:None)
        state=start(c,size).json
        with app.app_context():
            folder=uploads.folder_for(state['id'])
            manifest=uploads.read(folder)
            manifest['offset']=size-4
            uploads.write(folder,manifest)
            with (folder/'original.tif').open('r+b') as stream:
                stream.truncate(size+100)  # Simulate bytes written before a process crash.
        result=put(c,state,b'last',size-4)
        assert result.status_code==200 and result.json['offset']==size
        with (folder/'original.tif').open('rb') as stream:
            stream.seek(size-4); assert stream.read()==b'last'
        assert (folder/'original.tif').stat().st_size==size


def test_finalization_recovers_committed_row_without_duplicate(app, monkeypatch):
    c=client(app); data=tiff(); state=start(c,len(data)).json
    state=put(c,state,data).json
    c.post(state['url'],headers=HEADERS)
    original=uploads.write
    def crash_after_commit(folder, manifest):
        if manifest['status']=='complete':
            raise KeyboardInterrupt('simulate process termination after commit')
        original(folder,manifest)
    with app.app_context():
        monkeypatch.setattr(uploads,'write',crash_after_commit)
        with pytest.raises(KeyboardInterrupt):uploads.finalize(state['id'])
        monkeypatch.setattr(uploads,'write',original)
        assert Ortomosaico.query.count()==1
        monkeypatch.setattr(service,'create_upload',lambda *a,**k:pytest.fail('must reuse committed row'))
        uploads.finalize(state['id'])
    assert c.get(state['url']).json['status']=='complete'


def test_failed_storage_preserves_received_file_for_retry(app, monkeypatch):
    c=client(app); data=tiff(); state=start(c,len(data)).json
    put(c,state,data); c.post(state['url'],headers=HEADERS)
    original=service._upload
    monkeypatch.setattr(service,'_upload',lambda *a:(_ for _ in ()).throw(ValueError('Armazenamento indisponível')))
    with app.app_context():uploads.finalize(state['id'])
    assert c.get(state['url']).json['status']=='failed'
    with app.app_context():assert (uploads.folder_for(state['id'])/'original.tif').read_bytes()==data
    monkeypatch.setattr(service,'_upload',original)
    assert c.post(state['url'],headers=HEADERS).status_code==202
    with app.app_context():uploads.finalize(state['id'])
    assert c.get(state['url']).json['status']=='complete'


def test_disconnect_keeps_acknowledged_offset(app):
    c=client(app); state=start(c,100).json
    result=c.put(state['url'], data=b'partial', content_type='application/octet-stream',
        headers={**HEADERS,'Upload-Offset':'0'}, environ_overrides={'CONTENT_LENGTH':'100'})
    assert result.status_code==400
    assert c.get(state['url']).json['offset']==0
    assert put(c,state,b'x'*100).json['offset']==100
    with app.app_context():assert (uploads.folder_for(state['id'])/'original.tif').read_bytes()==b'x'*100


def test_low_disk_space_rejects_before_transfer(app, monkeypatch):
    from app.modules.ortomosaicos.storage import TemporaryStorageError
    monkeypatch.setattr(uploads,'require_space',lambda *a:(_ for _ in ()).throw(TemporaryStorageError('Espaço insuficiente')))
    assert start(client(app),100).status_code==507


def test_parallel_chunk_is_rejected_without_mutating_file(app):
    from filelock import FileLock
    c=client(app); state=start(c,100).json
    with app.app_context():folder=uploads.folder_for(state['id'])
    with FileLock(str(folder/'receive.lock')):
        assert put(c,state,b'x'*100).status_code==409
    assert c.get(state['url']).json['offset']==0


def test_upload_routes_are_registered_in_central_ti_policy(app):
    from app.modules.gestao_ti.permissions import EXCLUSIONS
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith('/api/ortomosaicos/uploads'):
            assert rule.endpoint in EXCLUSIONS
