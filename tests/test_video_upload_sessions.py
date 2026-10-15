import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Blueprint, Flask
from flask_login import LoginManager, UserMixin

from app.modules.piloto_os import routes


class User(UserMixin):
    tipo_usuario = 'equipe_oceano'
    def __init__(self, uid):
        self.id = int(uid)


def make_app(path, storage=None):
    app=Flask(__name__,instance_path=str(path))
    app.config.update(TESTING=True,SECRET_KEY='upload-test-only',VIDEO_UPLOAD_TEMP_DIR=str(storage) if storage else '')
    login=LoginManager(app);login.user_loader(User)
    bp=Blueprint('main',__name__);routes.register_routes(bp);app.register_blueprint(bp)
    return app


def client(app,uid=1):
    c=app.test_client()
    with c.session_transaction() as s:s['_user_id']=str(uid);s['_fresh']=True
    return c


def create_session(app):
    with app.app_context():
        return routes._create_video_upload_session(os_id=1,user_id=1,file_name='test.mp4',
            original_name='test.mp4',content_type='video/mp4',total_bytes=6,total_chunks=2)['id']


@pytest.mark.parametrize('stage',['chunk','complete'])
def test_lost_session_is_machine_readable_and_does_not_recreate_folders(tmp_path,stage):
    app=make_app(tmp_path/'instance');c=client(app);sid=create_session(app)
    shutil.rmtree(app.instance_path)
    if stage=='chunk':r=c.put(f'/api/video-upload-sessions/{sid}/chunks/0',data=b'abc')
    else:r=c.post(f'/api/video-upload-sessions/{sid}/complete')
    assert r.status_code==404
    assert r.json['code']=='video_upload_session_missing'
    assert not Path(app.instance_path).exists()


def test_new_application_can_continue_session_on_configured_persistent_storage(tmp_path,monkeypatch):
    storage=tmp_path/'persistent'
    first=make_app(tmp_path/'old-instance',storage);sid=create_session(first)
    assert client(first).put(f'/api/video-upload-sessions/{sid}/chunks/0',data=b'abc').status_code==200
    second=make_app(tmp_path/'new-instance',storage);c=client(second)
    r=c.put(f'/api/video-upload-sessions/{sid}/chunks/1',data=b'def')
    assert r.status_code==200 and r.json['progress']==100
    assembled=[];submitted=[]
    def validate(path,name):assembled.append(Path(path).read_bytes())
    monkeypatch.setattr(routes,'_validate_uploaded_video_file',validate)
    monkeypatch.setattr(routes,'_create_video_upload_job',lambda **kwargs:'job-test')
    monkeypatch.setattr(routes,'VIDEO_BACKGROUND_UPLOAD_EXECUTOR',SimpleNamespace(submit=lambda *args:submitted.append(args)))
    r=c.post(f'/api/video-upload-sessions/{sid}/complete')
    assert r.status_code==202 and r.json['job_id']=='job-test'
    assert assembled==[b'abcdef'] and len(submitted)==1


def test_session_still_requires_owner_and_valid_chunk(tmp_path):
    app=make_app(tmp_path/'instance');sid=create_session(app)
    other=client(app,2)
    assert other.put(f'/api/video-upload-sessions/{sid}/chunks/0',data=b'abc').status_code==403
    assert other.post(f'/api/video-upload-sessions/{sid}/complete').status_code==403
    owner=client(app)
    assert owner.put(f'/api/video-upload-sessions/{sid}/chunks/2',data=b'abc').status_code==400
    assert owner.post(f'/api/video-upload-sessions/{sid}/complete').status_code==400


def test_session_disappearing_during_chunk_does_not_report_success(tmp_path,monkeypatch):
    app=make_app(tmp_path/'instance');sid=create_session(app)
    monkeypatch.setattr(routes,'_set_video_upload_session',lambda *args,**kwargs:None)
    r=client(app).put(f'/api/video-upload-sessions/{sid}/chunks/0',data=b'abc')
    assert r.status_code==404 and r.json['code']=='video_upload_session_missing'
