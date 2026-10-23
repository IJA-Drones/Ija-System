"""Fluxo HTTP real com templates, SQLite descartável, CSRF e escopo municipal."""

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Blueprint, Flask
from flask_login import LoginManager, UserMixin
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

from app.extensions import db
from app.models import Prefeitura
from app.modules.vigilancia import register_routes
from app.modules.vigilancia import field_routes
from app.modules.vigilancia.field_store import FieldStore
from app.modules.vigilancia.field_models import FIELD_TABLES
from app.modules.vigilancia.sample import build_sample_csv
from app.shared.csrf_security import CSRF_SESSION_KEY, register_csrf_security


@pytest.fixture
def client(tmp_path):
    root=Path(__file__).resolve().parents[1]
    app=Flask(__name__,static_folder=str(root/'app/static'))
    app.config.update(TESTING=True,SECRET_KEY="test-only-local-key",VIGILANCIA_IMPORT_ENABLED=True,
                      SQLALCHEMY_DATABASE_URI='sqlite:///' + str(tmp_path/'campo.sqlite'),
                      CENTRAL_TI_ENABLED=False,SESSION_PROTECTION=None)
    db.init_app(app)
    class User(UserMixin):
        def __init__(self,uid):
            self.id=uid
            self.tipo_usuario="admin" if uid=="global" else "prefeitura_admin" if uid in {"a","b","other"} else "uvis"
            self.prefeitura_id=8 if uid=="b" else None if uid=="unbound" else 7
    manager=LoginManager(app)
    manager.login_view="login"
    manager.user_loader(User)
    app.add_url_rule('/login',endpoint='login',view_func=lambda:'login')
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block extra_styles %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}'}),FileSystemLoader(str(root/'app/templates'))])
    register_csrf_security(app)
    bp=Blueprint('main',__name__)
    register_routes(bp)
    from app.modules.treinamentos.routes import register_routes as register_training_routes
    register_training_routes(bp)
    app.register_blueprint(bp)
    with app.app_context():
        Prefeitura.__table__.create(db.engine)
        for table in FIELD_TABLES:
            table.create(db.engine)
        db.session.add_all([Prefeitura(id=7,nome='Sete',slug='sete'),Prefeitura(id=8,nome='Oito',slug='oito')])
        db.session.commit()
    return app.test_client()


def login(client,user='a'):
    with client.session_transaction() as session:
        session['_user_id']=user
        session['_fresh']=True


def token(client):
    with client.session_transaction() as session:
        return session.get(CSRF_SESSION_KEY,'')


def prepare(client,**changes):
    data=dict(acao='preparar',fonte='Amostra fictícia',demo='true',_csrf_token=token(client),
              arquivo=(io.BytesIO(build_sample_csv(7)),'amostra.csv'))
    data.update(changes)
    return client.post('/vigilancia/importacoes',data=data)


def confirm(client,batch_id,**changes):
    return client.post('/vigilancia/importacoes',data=dict(acao='confirmar',lote=batch_id,_csrf_token=token(client),**changes))


def store(client):
    with client.application.app_context():
        return FieldStore(db.engine)


def test_full_prepare_confirm_reopen_and_original(client):
    login(client)
    page=client.get('/vigilancia/importacoes')
    assert page.status_code==200 and 'Importar visitas' in page.text
    assert page.headers['Cache-Control']=='private, no-store'
    response=prepare(client)
    assert response.status_code==303
    page=client.get(response.location)
    assert '33,33%' in page.text and 'Confirmar carga validada' in page.text
    batch=store(client).history(7)[0]
    assert batch['status']=='VALIDADO'
    response=confirm(client,batch['id'])
    assert response.status_code==303
    page=client.get(response.location)
    assert 'Carga concluída: 5 inspeções novas e 0 já existentes' in page.text
    assert 'somente este lote' in page.text
    assert client.get(f"/vigilancia/importacoes/{batch['id']}/origem.csv").data==build_sample_csv(7)
    assert len(store(client).history(7))==1
    assert prepare(client).status_code==303
    assert len(store(client).history(7))==1


def test_feature_flag_role_auth_and_csrf(client):
    assert client.get('/vigilancia/importacoes').status_code==302
    login(client,'uvis')
    assert client.get('/vigilancia/importacoes').status_code==403
    login(client)
    client.get('/vigilancia/importacoes')
    assert prepare(client,_csrf_token='wrong').status_code==403
    assert store(client).history(7)==[]
    client.application.config['VIGILANCIA_IMPORT_ENABLED']=False
    assert client.get('/vigilancia/importacoes').status_code==404


def test_scope_tampering_cross_municipality_and_actor(client):
    login(client)
    client.get('/vigilancia/importacoes')
    assert prepare(client,prefeitura_id='8').status_code==403
    assert prepare(client).status_code==303
    batch=store(client).history(7)[0]
    login(client,'b')
    assert client.get(f"/vigilancia/importacoes?lote={batch['id']}").status_code==404
    assert client.get(f"/vigilancia/importacoes/{batch['id']}/origem.csv").status_code==404
    assert confirm(client,batch['id']).status_code!=303
    login(client,'other')
    assert client.get(f"/vigilancia/importacoes?lote={batch['id']}").status_code==200
    assert confirm(client,batch['id']).status_code!=303
    assert store(client).get(batch['id'],7)['status']=='VALIDADO'


def test_global_requires_existing_scope_and_municipal_cannot_override_sample(client):
    login(client,'global')
    client.get('/vigilancia/importacoes')
    assert prepare(client).status_code==400
    assert prepare(client,prefeitura_id='999').status_code==400
    assert prepare(client,prefeitura_id='7').status_code==303
    login(client)
    assert client.get('/vigilancia/importacoes/modelo.csv?prefeitura_id=8').status_code==403
    assert client.get('/vigilancia/importacoes/modelo.csv').data==build_sample_csv(7)


def test_import_filters_list_real_prefeituras_and_keep_sample_ids(client):
    login(client, 'global')
    response = client.get('/vigilancia/importacoes?prefeitura_id=7')
    assert response.status_code == 200
    assert '<select class="form-select" id="historico-prefeitura" name="prefeitura_id" required>' in response.text
    assert '<select class="form-select" id="prefeitura-id" name="prefeitura_id" required' in response.text
    assert '<option value="7" selected>Sete</option>' in response.text
    assert '>Oito</option>' in response.text
    assert 'municipio_id' in response.text
    assert client.get('/vigilancia/importacoes?prefeitura_id=2').status_code == 400
    assert client.get('/vigilancia/importacoes/modelo.csv?prefeitura_id=7').data == build_sample_csv(7)


def test_invalid_and_authorized_mode_and_xss(client):
    login(client)
    client.get('/vigilancia/importacoes')
    assert prepare(client,demo='false').status_code==400
    assert prepare(client,demo='nonsense').status_code==400
    response=prepare(client,fonte='<script>alert(1)</script>')
    assert response.status_code==303
    page=client.get(response.location)
    assert '<script>alert(1)</script>' not in page.text
    assert '&lt;script&gt;' in page.text
    invalid=build_sample_csv(7).replace(b'2026-01-10',b'invalid',1)
    response=prepare(client,arquivo=(io.BytesIO(invalid),'invalid.csv'))
    page=client.get(response.location)
    assert 'REJEITADO' in page.text and 'Confirmar carga validada' not in page.text


def test_body_limit_before_middleware_and_upload_extension(client):
    login(client)
    client.get('/vigilancia/importacoes')
    assert client.post('/vigilancia/importacoes',data=b'x'*(1024*1024+65537)).status_code==413
    assert prepare(client,arquivo=(io.BytesIO(build_sample_csv(7)),'bad.exe')).status_code==400


def test_delegated_user_without_municipality_never_gets_global_scope(client):
    login(client,'unbound')
    with patch.object(field_routes,'route_access',return_value=True),patch.object(field_routes,'can_access_endpoint',return_value=True):
        assert client.get('/vigilancia/importacoes?prefeitura_id=7').status_code==403


def test_post_and_export_require_consult_as_well_as_action(client):
    login(client)
    client.get('/vigilancia/importacoes')
    with patch.object(field_routes,'can_access_endpoint',return_value=False):
        assert prepare(client).status_code==403
        assert client.get('/vigilancia/importacoes/unknown/origem.csv').status_code==403


def test_shared_csrf_enabled_and_rejected_missing_token(client):
    client.application.config['CSRF_PROTECTION_ENABLED']=True
    login(client)
    client.get('/vigilancia/importacoes')
    assert prepare(client,_csrf_token='').status_code==403
    assert prepare(client).status_code==303
