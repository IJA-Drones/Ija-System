"""Corrections keep business records and their audit trail in one transaction."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from flask import Flask
from flask_login import LoginManager

from app.extensions import db
from app.models import Prefeitura, FinanceiroEmpresaPerfil, FinanceiroAgroCaixaDiario, FinanceiroAgroCaixaAjuste
from app.routes import bp
from tests.test_financeiro_central import FinanceUser


@pytest.fixture
def env():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='test-only', SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
    db.init_app(app)
    user = FinanceUser('financeiro_admin')
    manager = LoginManager(app)
    manager.user_loader(lambda uid: user)
    app.register_blueprint(bp)
    with app.app_context():
        for model in (Prefeitura, FinanceiroEmpresaPerfil, FinanceiroAgroCaixaDiario, FinanceiroAgroCaixaAjuste):
            model.__table__.create(db.engine)
        caixa = FinanceiroAgroCaixaDiario(data_caixa=date(2026, 11, 2), status='FECHADO', saldo_abertura=1300, saldo_fechamento=1600)
        seguinte = FinanceiroAgroCaixaDiario(data_caixa=date(2026, 11, 3), status='ABERTO', saldo_abertura=1600)
        db.session.add_all([caixa, seguinte]); db.session.commit()
        client = app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = '7'; session['_fresh'] = True
        with patch('app.modules.agro.routes.build_agro_caixa_diario_report', return_value={
            'total_entradas': Decimal('500'), 'total_saidas': Decimal('200')
        }):
            yield app, client, user, caixa, seguinte
        db.session.remove()


def post(env, **overrides):
    _, client, _, caixa, _ = env
    data = dict(saldo_original=str(caixa.saldo_abertura_decimal), saldo_abertura='1.280,00', motivo='Tarifa do dia anterior registrada depois.')
    data.update(overrides)
    return client.post(f'/agro/caixa/{caixa.id}/ajustar-saldo', data=data)


@pytest.mark.parametrize('status', ['ABERTO', 'FECHADO'])
def test_adjustment_keeps_status_movements_and_other_days_and_records_actor(env, status):
    _, _, _, caixa, seguinte = env
    caixa.status = status; db.session.commit()
    assert post(env).status_code == 302
    db.session.expire_all()
    assert caixa.saldo_abertura == Decimal('1280')
    assert caixa.saldo_fechamento == Decimal('1580')
    assert caixa.status == status
    assert seguinte.saldo_abertura == Decimal('1600')
    history = FinanceiroAgroCaixaAjuste.query.one()
    assert history.saldo_anterior == Decimal('1300')
    assert history.saldo_novo == Decimal('1280')
    assert history.usuario_id == 7 and history.usuario_nome == 'Equipe Financeiro'
    assert history.motivo.startswith('Tarifa') and history.criado_em
    assert post(env, saldo_abertura='-20,50').status_code == 302
    assert FinanceiroAgroCaixaAjuste.query.count() == 2
    assert caixa.saldo_fechamento == Decimal('279.50')


@pytest.mark.parametrize('role', ['financeiro', 'admin', 'diretor', 'operario'])
def test_non_master_cannot_adjust_even_with_direct_post(env, role):
    env[2].tipo_usuario = role
    assert post(env).status_code == 403
    assert env[3].saldo_abertura == Decimal('1300')
    assert FinanceiroAgroCaixaAjuste.query.count() == 0


@pytest.mark.parametrize('values', [
    {'saldo_abertura': 'NaN'}, {'saldo_abertura': 'Infinity'}, {'saldo_abertura': '10.50'},
    {'saldo_abertura': '1,234'}, {'saldo_abertura': '10000000000,00'},
    {'saldo_abertura': ''}, {'saldo_abertura': '1e5'}, {'motivo': '  '}, {'motivo': 'a'*1001},
    {'saldo_original': '1200.00'}, {'saldo_abertura': '1.300,00'},
])
def test_invalid_stale_and_unchanged_submissions_do_not_write(env, values):
    assert post(env, **values).status_code == 302
    assert env[3].saldo_abertura == Decimal('1300')
    assert FinanceiroAgroCaixaAjuste.query.count() == 0


def test_adjustment_requires_cash_operation_permission_in_configured_profile(env):
    with patch('app.modules.gestao_ti.permissions.active_configuration', return_value={
        'area:financeiro', 'financeiro.configuracoes.consultar', 'financeiro.configuracoes.configurar',
        'financeiro.contas.consultar', 'financeiro.contas.editar', 'financeiro.caixa.consultar',
    }):
        assert post(env).status_code == 403
    assert FinanceiroAgroCaixaAjuste.query.count() == 0


def test_unknown_cash_is_not_created(env):
    assert env[1].post('/agro/caixa/99999/ajustar-saldo', data={}).status_code == 404


def test_tenant_scope_rejects_another_municipality(env):
    env[2].prefeitura_id = 123
    assert post(env).status_code == 404
    assert FinanceiroAgroCaixaAjuste.query.count() == 0


def test_history_failure_rolls_back_balance(env):
    from sqlalchemy import event
    def reject(*args):
        raise RuntimeError('simulated history storage failure')
    event.listen(FinanceiroAgroCaixaAjuste, 'before_insert', reject)
    env[0].register_error_handler(RuntimeError, lambda exc: (_ for _ in ()).throw(exc))
    try:
        with pytest.raises(RuntimeError, match='history storage'):
            post(env)
        db.session.rollback()
        assert env[3].saldo_abertura == Decimal('1300')
        assert FinanceiroAgroCaixaAjuste.query.count() == 0
    finally:
        event.remove(FinanceiroAgroCaixaAjuste, 'before_insert', reject)


def test_double_submit_cannot_repeat_adjustment(env):
    original = str(env[3].saldo_abertura_decimal)
    assert post(env).status_code == 302
    assert post(env, saldo_original=original).status_code == 302
    assert FinanceiroAgroCaixaAjuste.query.count() == 1


def test_closing_overflow_rejected(env):
    assert post(env, saldo_abertura='9.999.999.999,99').status_code == 302
    assert FinanceiroAgroCaixaAjuste.query.count() == 0


def test_adjustment_requires_csrf_token_when_enabled(env):
    from app.shared.csrf_security import register_csrf_security
    app = env[0]
    app.config.update(CSRF_PROTECTION_ENABLED=True, SECRET_KEY='isolated-csrf-secret-for-adjustment-test-12345')
    register_csrf_security(app)
    with env[1].session_transaction() as session:
        session['_user_id'] = '7'; session['_fresh'] = True
        session['_ija_csrf'] = 'test-csrf'
    assert post(env).status_code == 403
    assert FinanceiroAgroCaixaAjuste.query.count() == 0
    assert post(env, _csrf_token='test-csrf').status_code == 302
    assert FinanceiroAgroCaixaAjuste.query.count() == 1
