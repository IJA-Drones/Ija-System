import os
import sys
from pathlib import Path
from unittest.mock import patch

root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
os.chdir(root)
os.environ.update(DATABASE_URL='sqlite:///:memory:',SECRET_KEY='field-preview-local-only',FLASK_DEBUG='1',
                  VIGILANCIA_IMPORT_ENABLED='1',CENTRAL_TI_ENABLED='0',CSS_BUNDLE_AUTO_BUILD='0',
                  VIGILANCIA_STORAGE_PATH=str(root/'tmp/vigilancia/preview.sqlite'))
with patch('dotenv.load_dotenv',return_value=False),patch('apscheduler.schedulers.background.BackgroundScheduler.start'):
    from app import create_app, db
    app=create_app()
from app.models import Prefeitura, Usuario
from flask_login import login_user
from app.modules.vigilancia.field_store import FieldStore
from app.modules.vigilancia.sample import build_sample_csv
with app.app_context():
    db.create_all()
    db.session.add(Prefeitura(id=7,nome='Município demonstrativo',slug='demo'))
    user=Usuario(nome_uvis='Demonstração local',login='preview',tipo_usuario='admin',senha_hash='unused')
    db.session.add(user)
    db.session.commit()
    uid=user.id
store=FieldStore(app.config['VIGILANCIA_STORAGE_PATH'])
batch=store.prepare(build_sample_csv(7),prefeitura=7,actor=str(uid),source='Exemplo sintético da PoC',filename='exemplo.csv',demo=True)
store.confirm(batch['id'],prefeitura=7,actor=str(uid))
@app.before_request
def local_only_user():
    login_user(db.session.get(Usuario,uid))
app.run(host='127.0.0.1',port=5018,use_reloader=False)
