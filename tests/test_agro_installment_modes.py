from contextlib import ExitStack
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from app.extensions import db
from app.models import FinanceiroAgroEntrada, FinanceiroAgroSaida
from app.modules.agro import routes
from tests import test_financeiro_central as finance_fixture


@pytest.fixture
def env():
    case = finance_fixture.FinanceiroCentralTests(); case.setUp(); case.login('financeiro_admin')
    with case.app.app_context(), ExitStack() as stack:
        for model in (FinanceiroAgroEntrada, FinanceiroAgroSaida):
            model.__table__.create(db.engine)
        for name in ('build_clientes_agro_query', 'build_fornecedores_agro_query', 'build_bancos_agro_query'):
            stack.enter_context(patch.object(routes, name, return_value=MagicMock(all=lambda: [])))
        for name in ('_get_cliente_agro', '_get_fornecedor_agro', '_get_banco_agro'):
            stack.enter_context(patch.object(routes, name, return_value=SimpleNamespace(id=None, nome='Exemplo')))
        stack.enter_context(patch.object(routes, '_enforce_agro_caixa_open_or_redirect', return_value=None))
        stack.enter_context(patch.object(routes, 'can_user_write_agro_finance_competencia', return_value=True))
        stack.enter_context(patch.object(routes, '_ensure_financeiro_agro_categoria_subcategoria'))
        stack.enter_context(patch.object(routes, 'recalculate_bancos_agro'))
        for kind in ('entrada', 'saida'):
            stack.enter_context(patch.object(routes, f'_build_financeiro_agro_{kind}_form_context', side_effect=lambda **kw: kw))
        renderer = stack.enter_context(patch.object(routes, 'render_template', return_value='form-with-errors'))
        yield case, renderer
        db.session.remove()
    case.doCleanups()


def data(mode='dividir', count='12', amount='120,00'):
    return dict(modo_parcelamento=mode, quantidade_parcelas=count, valor=amount, cliente_nome='Exemplo',
                fornecedor_agro_id='1', banco_agro_id='1', tipo_saida='DESPESA', descricao='Previsão mensal',
                categoria='Administrativo', subcategoria='Internet', status='PENDENTE', data_vencimento='2030-01-31')


@pytest.mark.parametrize('kind,model', [('entradas', FinanceiroAgroEntrada), ('saidas', FinanceiroAgroSaida)])
@pytest.mark.parametrize('mode,expected', [('dividir', Decimal('10')), ('repetir', Decimal('120')), (None, Decimal('10'))])
def test_actual_creation_values_and_months(env, kind, model, mode, expected):
    payload = data(mode)
    if mode is None: payload.pop('modo_parcelamento')
    response = env[0].client.post(f'/agro/financeiro/{kind}/cadastrar', data=payload)
    assert response.status_code == 302
    rows = db.session.query(model.valor, model.data_vencimento, model.parcela_numero, model.parcela_total, model.grupo_lancamento, model.status).order_by(model.parcela_numero).all()
    assert len(rows) == 12
    assert [r.valor for r in rows] == [expected] * 12
    assert sum(r.valor for r in rows) == expected * 12
    assert rows[1].data_vencimento == date(2030, 2, 28)
    assert rows[2].data_vencimento == date(2030, 3, 31)
    assert [r.parcela_numero for r in rows] == list(range(1,13))
    assert all(r.parcela_total == 12 and r.status == 'PENDENTE' for r in rows)
    assert len({r.grupo_lancamento for r in rows}) == 1 and rows[0].grupo_lancamento


@pytest.mark.parametrize('kind,model', [('entradas', FinanceiroAgroEntrada), ('saidas', FinanceiroAgroSaida)])
@pytest.mark.parametrize('changes', [{'modo_parcelamento':'outro'}, {'valor':'NaN'}, {'quantidade_parcelas':'121'}, {'data_vencimento':''}, {'descricao':''}])
def test_errors_preserve_selection_and_create_nothing(env, kind, model, changes):
    payload=data('repetir');payload.update(changes)
    assert env[0].client.post(f'/agro/financeiro/{kind}/cadastrar',data=payload).status_code == 200
    assert db.session.query(model.id).count() == 0
    args = env[1].call_args.kwargs
    assert args['errors']
    assert args['form']['modo_parcelamento'] == payload['modo_parcelamento']
    assert args['form']['quantidade_parcelas'] == payload['quantidade_parcelas']


def test_cent_rounding_and_single_installment():
    assert routes._split_agro_installment_values(Decimal('100'),3) == [Decimal('33.34'),Decimal('33.33'),Decimal('33.33')]
    assert routes._split_agro_installment_values(Decimal('10.99'),6,'repetir') == [Decimal('10.99')]*6
    for mode in ('dividir','repetir'):
        assert routes._split_agro_installment_values(Decimal('120'),1,mode) == [Decimal('120')]


@pytest.mark.parametrize('kind,model', [('entradas', FinanceiroAgroEntrada), ('saidas', FinanceiroAgroSaida)])
def test_repeat_keeps_competence_blocks(env,kind,model):
    with patch.object(routes,'can_user_write_agro_finance_competencia',return_value=False):
        assert env[0].client.post(f'/agro/financeiro/{kind}/cadastrar', data=data('repetir')).status_code == 200
    assert db.session.query(model.id).count() == 0
    assert 'data_vencimento' in env[1].call_args.kwargs['errors']
