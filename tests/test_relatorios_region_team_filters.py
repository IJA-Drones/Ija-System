from datetime import date, time
from types import SimpleNamespace

from flask import Flask
from werkzeug.datastructures import MultiDict

from app import db
from app.models import Equipe, OrdemServico, Prefeitura, Solicitacao, Usuario
from app.modules.relatorios.service import (
    build_relatorios_coleta_imagens_context,
    build_relatorios_os_context,
    build_relatorios_solicitacoes_context,
)


def _make_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def _seed_relatorio_rows():
    prefeitura = Prefeitura(nome="Prefeitura Teste", slug="prefeitura-teste")
    db.session.add(prefeitura)
    db.session.flush()

    uvis_norte = Usuario(
        nome_uvis="UVIS Norte",
        regiao="NORTE",
        login="uvis_norte_rel",
        senha_hash="hash",
        tipo_usuario="uvis",
        prefeitura_id=prefeitura.id,
    )
    uvis_sul = Usuario(
        nome_uvis="UVIS Sul",
        regiao="SUL",
        login="uvis_sul_rel",
        senha_hash="hash",
        tipo_usuario="uvis",
        prefeitura_id=prefeitura.id,
    )
    equipe_norte = Equipe(
        nome_equipe="Equipe Norte",
        regiao="NORTE",
        prefeitura_id=prefeitura.id,
        ativa=True,
    )
    equipe_sul = Equipe(
        nome_equipe="Equipe Sul",
        regiao="SUL",
        prefeitura_id=prefeitura.id,
        ativa=True,
    )
    db.session.add_all([uvis_norte, uvis_sul, equipe_norte, equipe_sul])
    db.session.flush()

    solicitacao_norte = Solicitacao(
        data_agendamento=date(2026, 7, 10),
        hora_agendamento=time(9, 0),
        foco="Foco A",
        cep="01000-000",
        logradouro="Rua Norte",
        bairro="Centro",
        cidade="Sao Paulo",
        uf="SP",
        status="CONCLUIDO",
        usuario_id=uvis_norte.id,
        prefeitura_id=prefeitura.id,
        equipe_id=equipe_norte.id,
    )
    solicitacao_sul = Solicitacao(
        data_agendamento=date(2026, 7, 10),
        hora_agendamento=time(9, 0),
        foco="Foco A",
        cep="02000-000",
        logradouro="Rua Sul",
        bairro="Centro",
        cidade="Sao Paulo",
        uf="SP",
        status="CONCLUIDO",
        usuario_id=uvis_sul.id,
        prefeitura_id=prefeitura.id,
        equipe_id=equipe_sul.id,
    )
    db.session.add_all([solicitacao_norte, solicitacao_sul])
    db.session.flush()

    db.session.add_all(
        [
            OrdemServico(
                solicitacao_id=solicitacao_norte.id,
                equipe_id=equipe_norte.id,
                data_aplicacao=date(2026, 7, 11),
                larva_visualizada="SIM",
                imagem_principal="os/norte.jpg",
            ),
            OrdemServico(
                solicitacao_id=solicitacao_sul.id,
                equipe_id=equipe_sul.id,
                data_aplicacao=date(2026, 7, 11),
                larva_visualizada="NAO",
                imagem_principal="os/sul.jpg",
            ),
        ]
    )
    db.session.commit()

    admin = SimpleNamespace(tipo_usuario="prefeitura_admin", prefeitura_id=prefeitura.id)
    return admin, equipe_norte, equipe_sul


def test_relatorios_solicitacoes_filters_by_region_and_team():
    app = _make_app()
    with app.app_context():
        db.create_all()
        admin, equipe_norte, equipe_sul = _seed_relatorio_rows()

        context = build_relatorios_solicitacoes_context(
            admin,
            MultiDict(
                {
                    "mes": "7",
                    "ano": "2026",
                    "regiao": "NORTE",
                    "equipe_id": str(equipe_norte.id),
                }
            ),
        )

        assert context["total_solicitacoes"] == 1
        assert context["regiao_selecionada"] == "NORTE"
        assert context["equipe_id_selecionado"] == equipe_norte.id
        assert context["filtros_exportacao"]["equipe_id"] == equipe_norte.id
        assert equipe_sul.id not in [equipe.id for equipe in context["equipes_disponiveis"]]

        db.session.remove()
        db.drop_all()


def test_relatorios_os_filters_by_region_and_team():
    app = _make_app()
    with app.app_context():
        db.create_all()
        admin, equipe_norte, _equipe_sul = _seed_relatorio_rows()

        context = build_relatorios_os_context(
            admin,
            MultiDict(
                {
                    "mes": "7",
                    "ano": "2026",
                    "regiao": "NORTE",
                    "equipe_id": str(equipe_norte.id),
                }
            ),
        )

        assert context["total_os"] == 1
        assert context["total_larva_sim"] == 1
        assert context["regiao_selecionada"] == "NORTE"
        assert context["equipe_id_selecionado"] == equipe_norte.id
        assert context["filtros_exportacao"]["equipe_id"] == equipe_norte.id

        db.session.remove()
        db.drop_all()


def test_relatorios_coleta_imagens_filters_by_team():
    app = _make_app()
    with app.app_context():
        db.create_all()
        admin, equipe_norte, _equipe_sul = _seed_relatorio_rows()

        context = build_relatorios_coleta_imagens_context(
            admin,
            MultiDict(
                {
                    "mes": "7",
                    "ano": "2026",
                    "regiao": "NORTE",
                    "equipe_id": str(equipe_norte.id),
                }
            ),
        )

        assert context["total_levantamentos"] == 1
        assert context["regiao_selecionada"] == "NORTE"
        assert context["equipe_id_selecionado"] == equipe_norte.id
        assert context["filtros_exportacao"]["equipe_id"] == equipe_norte.id

        db.session.remove()
        db.drop_all()
