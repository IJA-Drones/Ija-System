"""Ciclo editorial real e fronteira pública; somente SQLite e arquivos descartáveis."""
import io
import os
import re
import subprocess
from datetime import date, time
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask
from flask_login import LoginManager
from PIL import Image
from sqlalchemy import event
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import AcaoPublica, AcaoPublicaEvento, AcaoPublicaMidia, Equipe, OrdemServico, Prefeitura, Solicitacao, Usuario
from app.routes import bp
from app.modules.auth.routes import bp as auth_bp
from app.modules.acoes_publicas import media
from app.modules.gestao_ti.service import save_configurations
from app.shared.csrf_security import register_csrf_security

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def app(tmp_path):
    a = Flask(__name__, template_folder=str(ROOT/'app/templates'), static_folder=str(ROOT/'app/static'))
    a.config.update(TESTING=True, SECRET_KEY='isolated-action-tests-secret-key-32',
        SQLALCHEMY_DATABASE_URI='sqlite:///'+str(tmp_path/'acoes.sqlite'), SESSION_PROTECTION=None,
        ACOES_PUBLICAS_ENABLED=True, ACOES_PUBLICAS_UPLOAD_DIR=str(tmp_path/'media'),
        CSRF_PROTECTION_ENABLED=True, CENTRAL_TI_ENABLED=True, CENTRAL_TI_ENFORCE_PERMISSIONS=True)
    db.init_app(a)
    manager = LoginManager(a)
    manager.login_view = 'auth.login'
    manager.user_loader(lambda uid: db.session.get(Usuario, int(uid)))
    register_csrf_security(a)
    a.register_blueprint(auth_bp)
    a.register_blueprint(bp)
    with a.app_context():
        db.create_all()
        db.session.add_all([Prefeitura(id=1,nome='Alfa fictícia',slug='alfa'), Prefeitura(id=2,nome='Beta fictícia',slug='beta')])
        for uid,role,city,region in [(1,'covisa',1,'COVISA'),(2,'covisa',2,'COVISA'),(3,'dev',None,None),
                                     (4,'uvis',1,None),(5,'covisa',None,'COVISA'),(6,'prefeitura_admin',1,None)]:
            db.session.add(Usuario(id=uid,login=f'action{uid}',senha_hash='unused',nome_uvis=f'Conta interna {uid}',
                tipo_usuario=role,prefeitura_id=city,regiao=region))
        db.session.commit()
    with patch.object(media.skybox,'skybox_enabled',return_value=False):
        yield a
    with a.app_context():
        db.session.remove()
        db.engine.dispose()


def client(app, uid=1):
    c = app.test_client()
    if uid:
        with c.session_transaction() as session:
            session.update(_user_id=str(uid), _fresh=True, _ija_csrf='global-token', _acoes_csrf='action-token')
    return c


def payload(**changes):
    return dict(dict(acao_csrf='action-token', _csrf_token='global-token', prefeitura_id='1', demo='true',
        titulo='Mutirão fictício de prevenção', tipo='mutirao', bairro='Área demonstrativa', inicio='2026-01-10',
        fim='2026-01-10', descricao='Orientação fictícia às equipes e à comunidade.'), **changes)


def create(c, **changes):
    page = c.get('/acoes-realizadas/nova')
    assert page.status_code == 200
    identifier = re.search(r'name="request_id" value="([a-f0-9]+)"', page.text)[1]
    response = c.post('/acoes-realizadas/nova',data=payload(request_id=identifier,**changes))
    assert response.status_code == 303, response.text
    return identifier


def post(c, identifier, suffix='', **changes):
    with c.application.app_context():
        version = db.session.get(AcaoPublica,identifier).versao
    return c.post(f'/acoes-realizadas/{identifier}{suffix}',data=payload(**{'versao':str(version),**changes}))


def image():
    result = io.BytesIO()
    exif = Image.Exif()
    exif[315] = 'Identidade privada'
    Image.new('RGB',(40,30),'teal').save(result,'JPEG',exif=exif)
    result.seek(0)
    return result


def upload(c, identifier):
    response = post(c,identifier,'/midias',arquivo=(image(),'original-private.jpg'),legenda='Imagem fictícia autorizada')
    assert response.status_code == 303, response.text
    with c.application.app_context():
        return AcaoPublicaMidia.query.filter_by(acao_id=identifier).order_by(AcaoPublicaMidia.criado_em.desc()).first().id


def publish(c, identifier):
    assert post(c,identifier,'/revisar').status_code == 303
    assert post(c,identifier,'/publicar',autorizado='sim').status_code == 303


def test_full_editorial_lifecycle_approved_snapshot_and_withdrawal(app):
    c, anonymous = client(app), client(app,None)
    identifier = create(c)
    media_id = upload(c,identifier)
    public_url = f'/portal-cidadao/acoes/{identifier}'
    asset = f'{public_url}/midias/{media_id}'
    assert anonymous.get(public_url).status_code == anonymous.get(asset).status_code == 404
    assert 'Prévia privada' in c.get(f'/acoes-realizadas/{identifier}/previa').text
    assert anonymous.get(f'/acoes-realizadas/{identifier}/previa').status_code == 302
    publish(c,identifier)
    public = anonymous.get(public_url)
    assert public.status_code == 200 and 'Mutirão fictício' in public.text and 'dados fictícios' in public.text
    assert 'og:image' in public.text and 'https://wa.me/?text=' in public.text
    assert 'facebook.com/sharer/sharer.php?' in public.text
    for private in ('original-private.jpg','Identidade privada','Conta interna','stored_path','origem_os_id'):
        assert private not in public.text
    asset_response = anonymous.get(asset)
    assert asset_response.status_code == 200 and 'no-store' in asset_response.headers['Cache-Control']
    clean = Image.open(io.BytesIO(asset_response.data))
    assert not clean.getexif()
    assert anonymous.get(asset,headers={'Range':'bytes=0-15'}).status_code == 206
    assert identifier not in anonymous.get('/portal-cidadao/acoes').text
    assert identifier in anonymous.get('/portal-cidadao/acoes?demo=true').text
    assert post(c,identifier,titulo='Alteração ainda privada',fim='2026-01-11').status_code == 303
    assert 'Alteração ainda privada' not in anonymous.get(public_url).text
    assert identifier not in anonymous.get('/portal-cidadao/acoes?demo=true&inicio=2026-01-11').text
    assert post(c,identifier,f'/midias/{media_id}/remover').status_code == 303
    assert anonymous.get(asset).status_code == 200  # Still part of the approved snapshot.
    second_media = upload(c,identifier)
    assert anonymous.get(f'{public_url}/midias/{second_media}').status_code == 404
    publish(c,identifier)
    assert 'Alteração ainda privada' in anonymous.get(public_url).text
    assert anonymous.get(asset).status_code == 404
    second_asset = f'{public_url}/midias/{second_media}'
    assert anonymous.get(second_asset).status_code == 200
    assert post(c,identifier,'/retirar',confirmar='sim').status_code == 303
    assert anonymous.get(public_url).status_code == anonymous.get(second_asset).status_code == 404
    with app.app_context():
        assert AcaoPublicaEvento.query.filter_by(acao_id=identifier,evento='PUBLICADA').count() == 2
        assert AcaoPublicaEvento.query.filter_by(acao_id=identifier,evento='RETIRADA').count() == 1
        assert AcaoPublicaMidia.query.filter_by(acao_id=identifier).count() == 2


def test_tenant_scope_auth_csrf_duplicate_and_version(app):
    c = client(app)
    identifier = create(c)
    assert client(app,None).get('/acoes-realizadas').status_code == 302
    assert client(app,4).get('/acoes-realizadas').status_code == 403
    assert client(app,5).get('/acoes-realizadas').status_code == 403
    assert client(app,2).get(f'/acoes-realizadas/{identifier}').status_code == 404
    assert post(client(app,2),identifier,'/revisar').status_code == 404
    assert c.get('/acoes-realizadas?prefeitura_id=2').status_code == 403
    assert post(c,identifier,acao_csrf='wrong').status_code == 403
    assert post(c,identifier,_csrf_token='wrong').status_code == 403
    assert post(c,identifier,versao='999').status_code == 409
    assert c.post('/acoes-realizadas/nova',data=payload(request_id=identifier)).status_code == 303
    duplicate = MultiDict(payload(versao='1'))
    duplicate.add('titulo','Outro título')
    assert c.post(f'/acoes-realizadas/{identifier}',data=duplicate).status_code == 400
    with app.app_context():
        assert AcaoPublica.query.count() == 1
        assert AcaoPublicaEvento.query.count() == 1


@pytest.mark.parametrize('changes',[{'fim':'2999-01-01'}, {'inicio':'2026-01-11'}, {'tipo':'invalid'},
    {'titulo':' '}, {'descricao':'x'*5001}, {'inicio':'20260110'}])
def test_invalid_content_cannot_replace_draft(app, changes):
    c = client(app)
    identifier = create(c)
    assert post(c,identifier,**changes).status_code == 400
    with app.app_context():
        assert db.session.get(AcaoPublica,identifier).versao == 1


def test_review_lock_required_approval_and_escape(app):
    c = client(app)
    identifier = create(c,titulo='<script>alert(1)</script>')
    assert post(c,identifier,'/publicar',autorizado='sim').status_code == 400
    assert post(c,identifier,'/revisar').status_code == 303
    assert post(c,identifier,titulo='Alteração bloqueada').status_code == 400
    assert post(c,identifier,'/midias',arquivo=(image(),'private.jpg')).status_code == 400
    assert post(c,identifier,'/publicar').status_code == 400
    assert post(c,identifier,'/publicar',autorizado='sim').status_code == 303
    public = client(app,None).get(f'/portal-cidadao/acoes/{identifier}')
    assert '<script>alert(1)</script>' not in public.text
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in public.text
    assert post(c,identifier,'/retirar').status_code == 400


def configure(app, role, permissions):
    with app.app_context():
        save_configurations(db.session.get(Usuario,3), {'profiles':[{'id':role,'version':0,
            'areas':['prefeitura'],'permissions':[f'prefeitura.acoes_publicas.{p}' for p in permissions]}]})


def test_central_ti_separates_editor_publisher_and_revocation(app):
    configure(app,'uvis',['consultar','criar','editar'])
    c = client(app,4)
    identifier = create(c)
    assert post(c,identifier,'/revisar').status_code == 303
    assert post(c,identifier,'/publicar',autorizado='sim').status_code == 403
    assert post(client(app,1),identifier,'/publicar',autorizado='sim').status_code == 303
    configure(app,'covisa',[])
    assert client(app,1).get('/acoes-realizadas').status_code == 403
    assert client(app,None).get(f'/portal-cidadao/acoes/{identifier}').status_code == 200


def test_disabled_or_missing_schema_does_not_create_tables(app):
    c = client(app)
    app.config['ACOES_PUBLICAS_ENABLED'] = False
    assert c.get('/acoes-realizadas').status_code == 503
    app.config['ACOES_PUBLICAS_ENABLED'] = True
    with app.app_context():
        AcaoPublicaEvento.__table__.drop(db.engine)
    assert c.get('/acoes-realizadas').status_code == 503
    assert client(app,None).get('/portal-cidadao/acoes').status_code == 503


def test_media_validation_limits_and_storage_rollback(app):
    c = client(app)
    identifier = create(c)
    assert post(c,identifier,'/midias',arquivo=(io.BytesIO(b'<svg/>'),'fake.jpg')).status_code == 400
    assert c.post(f'/acoes-realizadas/{identifier}',data={'x':'x'*65536}).status_code == 413
    with patch.object(media,'MAX_SELECTED',1):
        upload(c,identifier)
        assert post(c,identifier,'/midias',arquivo=(image(),'extra.jpg')).status_code == 400
    with app.app_context():
        before = set(Path(app.config['ACOES_PUBLICAS_UPLOAD_DIR']).rglob('*.jpg'))
        def fail_commit(*args):
            raise RuntimeError('synthetic commit failure')
        event.listen(db.session(),'before_flush',fail_commit)
        try:
            assert post(c,identifier,'/midias',arquivo=(image(),'rollback.jpg')).status_code == 500
        finally:
            event.remove(db.session(),'before_flush',fail_commit)
        assert set(Path(app.config['ACOES_PUBLICAS_UPLOAD_DIR']).rglob('*.jpg')) == before


def test_source_os_is_explicit_copied_and_scoped(app, tmp_path):
    original = tmp_path/'operational.jpg'
    original.write_bytes(image().getvalue())
    with app.app_context():
        db.session.add(Equipe(id=1,nome_equipe='Equipe fictícia',prefeitura_id=1))
        row = Solicitacao(id=123,prefeitura_id=1,data_agendamento=date(2026,1,10),hora_agendamento=time(9),
            foco='Teste',cep='00000-000',logradouro='Endereço privado',bairro='Área fictícia',cidade='Alfa',uf='SP',
            usuario_id=1,status='CONCLUIDO',observacao='Detalhes internos não publicáveis')
        db.session.add(row)
        db.session.add(OrdemServico(solicitacao_id=123,equipe_id=1,imagem_principal=str(original),outras_imagens='[]'))
        db.session.commit()
    c = client(app)
    assert c.get('/acoes-realizadas/nova?os_id=123').status_code == 200
    assert client(app,2).get('/acoes-realizadas/nova?os_id=123').status_code == 404
    identifier = create(c,os_id='123',demo='false')
    with app.app_context():
        assert AcaoPublicaMidia.query.count() == 0
        assert db.session.get(AcaoPublica,identifier).descricao != 'Detalhes internos não publicáveis'
    with patch('app.modules.piloto_os.routes._send_os_media',side_effect=lambda _:app.response_class(original.read_bytes())):
        assert post(c,identifier,'/midias',source_key='principal').status_code == 303
    with app.app_context():
        copied = AcaoPublicaMidia.query.first()
        assert copied.stored_path != str(original)
        assert Path(copied.stored_path).read_bytes() != original.read_bytes()
        row = db.session.get(Solicitacao,123)
        row.status = 'REABERTO'
        db.session.commit()
    assert c.get(f'/acoes-realizadas/{identifier}').status_code == 200
    publish(c,identifier)
    public = client(app,None).get(f'/portal-cidadao/acoes/{identifier}')
    assert public.status_code == 200
    assert 'Endereço privado' not in public.text and '123' not in public.text


def test_inactive_municipality_hides_page_and_media(app):
    c = client(app)
    identifier = create(c)
    mid = upload(c,identifier)
    publish(c,identifier)
    with app.app_context():
        db.session.get(Prefeitura,1).ativa = False
        db.session.commit()
    anon = client(app,None)
    assert anon.get(f'/portal-cidadao/acoes/{identifier}').status_code == 404
    assert anon.get(f'/portal-cidadao/acoes/{identifier}/midias/{mid}').status_code == 404


def test_video_requires_processing_and_never_passes_original(app):
    c = client(app)
    identifier = create(c)
    with patch.object(media.shutil,'which',return_value=None), patch.dict('os.environ',{'FFMPEG_PATH':''}):
        app.config['FFMPEG_PATH'] = ''
        response = post(c,identifier,'/midias',arquivo=(io.BytesIO(b'\x00\x00\x00\x18ftypisom' + b'private-metadata'),'video.mp4'))
        assert response.status_code == 400 and 'FFmpeg' in response.text
    with app.app_context():
        assert AcaoPublicaMidia.query.count() == 0


@pytest.mark.skipif(not os.getenv('IJA_TEST_FFMPEG_PATH'),reason='FFmpeg de teste não configurado')
def test_real_mp4_removes_location_metadata_and_supports_ranges(app, tmp_path):
    executable = os.environ['IJA_TEST_FFMPEG_PATH']
    source = tmp_path/'source.mp4'
    subprocess.run([executable,'-v','error','-f','lavfi','-i','color=c=teal:s=160x120:d=1',
        '-c:v','libx264','-pix_fmt','yuv420p','-metadata','location=+23.1234-046.5678/',
        '-metadata','title=PRIVATE-VIDEO-TITLE',str(source)],check=True,capture_output=True,timeout=25)
    app.config['FFMPEG_PATH'] = executable
    c = client(app)
    identifier = create(c)
    assert post(c,identifier,'/midias',arquivo=(io.BytesIO(source.read_bytes()),'private-video.mp4')).status_code == 303
    with app.app_context():
        item = AcaoPublicaMidia.query.one()
        target, media_id = item.stored_path, item.id
    metadata = subprocess.run([executable,'-v','error','-i',target,'-f','ffmetadata','-'],
        check=True,capture_output=True,timeout=25).stdout
    assert b'location' not in metadata and b'PRIVATE-VIDEO-TITLE' not in metadata
    publish(c,identifier)
    response = client(app,None).get(f'/portal-cidadao/acoes/{identifier}/midias/{media_id}',headers={'Range':'bytes=0-99'})
    assert response.status_code == 206 and response.mimetype == 'video/mp4'
    assert len(response.data) == 100
