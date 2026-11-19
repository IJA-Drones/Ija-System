import json

import pytest

from scripts.cleanup_pesqueira_poc import (
    REQUEST_NOTE, deletion_order, identifier, key_predicate, restore_sql, validate_rows,
)


def test_closed_poc_city_is_not_reintroduced_by_environment_or_old_public_link():
    from app.modules.portal_cidadao.municipalities import public_health_municipality
    from werkzeug.datastructures import MultiDict
    config = dict(PORTAL_EXCLUDED_MUNICIPALITIES=("2610905",),
                  INFODENGUE_GEOCODE="2610905", INFODENGUE_CITY="Pesqueira")
    city, options, api_config = public_health_municipality(config, MultiDict({"municipio": "2610905"}))
    assert city["ibge"] == api_config["INFODENGUE_GEOCODE"] == "3550308"
    assert all(option["ibge"] != "2610905" for option in options)


def test_never_expands_cleanup_into_other_municipalities_or_users():
    with pytest.raises(ValueError, match="outro município"):
        validate_rows("ordens_servico", [{"prefeitura_id": 1, "id": 99}])
    with pytest.raises(ValueError, match="não autorizada"):
        validate_rows("usuarios", [{"prefeitura_id": 14, "id": 167}])
    with pytest.raises(ValueError, match="não autorizada"):
        validate_rows("auditoria_usuarios", [{"prefeitura_id": 14, "id": 1}])


def test_request_must_have_both_demo_protocol_and_fictional_execution_marker():
    demo = {"prefeitura_id": 14, "protocolo": "DEMO-CONSULTA-PESQ-202610-001", "observacao": REQUEST_NOTE}
    validate_rows("solicitacoes", [demo])
    with pytest.raises(ValueError, match="não é da demonstração"):
        validate_rows("solicitacoes", [{**demo, "observacao": "Atendimento executado"}])


def test_real_public_sinan_is_always_protected():
    with pytest.raises(ValueError, match="públicas reais"):
        validate_rows("vigilancia_sinan_lotes", [{"ibge": "2610905", "demo": False, "kind": "datasus"}])
    validate_rows("vigilancia_sinan_lotes", [{"ibge": "2610905", "demo": True, "kind": "csv"}])


def test_unmarked_complaint_requires_specific_confirmation_and_correct_scope():
    row = {"id": 28, "prefeitura_id": 14}
    with pytest.raises(ValueError, match="sem confirmação"):
        validate_rows("denuncias", [row])
    validate_rows("denuncias", [row], confirmed_complaint=True)
    with pytest.raises(ValueError, match="outro município"):
        validate_rows("denuncias", [{**row, "prefeitura_id": 1}], confirmed_complaint=True)


def test_foreign_key_expansion_does_not_silently_take_a_real_publication():
    with pytest.raises(ValueError, match="sem identificação demonstrativa"):
        validate_rows("acoes_publicas", [{"prefeitura_id": 14, "demo": False, "titulo": "Atividade real"}])
    with pytest.raises(ValueError, match="sem origem demonstrativa"):
        validate_rows("vigilancia_campo_planos", [{"prefeitura": 14, "demo": False, "fonte": "Levantamento oficial"}])


def test_delete_order_and_restore_follow_actual_row_dependencies():
    parent = {"id": 1}
    child = {"id": 2, "parent_id": 1}
    selected = {"parent": {(1,): (parent, json.dumps(parent))}, "child": {(2,): (child, json.dumps(child))}}
    fks = [{"parent": "parent", "child": "child", "parent_columns": ["id"], "child_columns": ["parent_id"]}]
    order = deletion_order(selected, fks)
    assert order == ["child", "parent"]
    sql = restore_sql({name: [row[1] for row in rows.values()] for name, rows in selected.items()}, order, '{"ativa":true}').decode()
    assert sql.index('INSERT INTO public."parent"') < sql.index('INSERT INTO public."child"')
    assert "SET ativa=TRUE WHERE id=14 AND slug='pesqueira'" in sql
    parent["child_id"] = 2
    with pytest.raises(ValueError, match="cíclica"):
        deletion_order(selected, fks + [{"parent": "child", "child": "parent", "parent_columns": ["id"], "child_columns": ["child_id"]}])


def test_keys_are_bound_and_names_cannot_inject_sql():
    where, params = key_predicate(["code"], [("quote' ; DROP TABLE usuarios; --",)])
    assert "DROP" not in where
    assert params["k0_0"] == "quote' ; DROP TABLE usuarios; --"
    with pytest.raises(ValueError):
        identifier('usuarios; DELETE FROM prefeituras')
