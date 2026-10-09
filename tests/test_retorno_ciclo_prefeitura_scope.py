"""
Regression tests for retorno ciclo prefeitura scope access issues.

This test file validates that automatic return OS can be accessed by users
with matching prefeitura_ids, ensuring the 404 error does not reoccur.
"""

import pytest
from datetime import date, time, timedelta
from flask import Flask

from app import db
from app.models import Equipe, Usuario, Solicitacao, Prefeitura
from app.shared.access import apply_solicitacao_prefeitura_scope


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_equipe_oceano_can_access_return_os_with_matching_prefeitura_id(app):
    """
    Test that equipe_oceano users can access automatic return OS
    when both user and OS have matching prefeitura_ids.
    
    This is a regression test for the bug where all automatic return OS
    had prefeitura_id=None, causing 404 errors for equipe_oceano users.
    """
    with app.app_context():
        # Create a prefeitura
        prefeitura = Prefeitura(nome="Test Prefeitura", slug="test-prefeitura")
        db.session.add(prefeitura)
        db.session.flush()
        
        # Create equipe_oceano user with prefeitura
        user = Usuario(
            nome_uvis="Test Team",
            tipo_usuario="equipe_oceano",
            codigo_setor="1",
            login="testteam",
            senha_hash="hash",
            prefeitura_id=prefeitura.id,
        )
        db.session.add(user)
        db.session.flush()

        equipe = Equipe(nome_equipe="Equipe Teste", prefeitura_id=prefeitura.id)
        db.session.add(equipe)
        db.session.flush()
        
        # Create original OS with prefeitura
        original_os = Solicitacao(
            data_agendamento=date.today(),
            hora_agendamento=time(9, 0),
            foco="Aedes",
            tipo_operacao="Monitoramento",
            cep="00000-000",
            logradouro="Rua Teste",
            numero="100",
            bairro="Centro",
            cidade="Sao Paulo",
            uf="SP",
            usuario_id=user.id,
            prefeitura_id=prefeitura.id,
            equipe_id=equipe.id,
            status="CONCLUÍDO",
        )
        db.session.add(original_os)
        db.session.flush()
        
        # Create automatic return OS (should copy prefeitura_id)
        return_os = Solicitacao(
            data_agendamento=date.today() + timedelta(days=7),
            hora_agendamento=time(9, 0),
            foco="Aedes",
            tipo_operacao="Monitoramento",
            cep="00000-000",
            logradouro="Rua Teste",
            numero="100",
            bairro="Centro",
            cidade="Sao Paulo",
            uf="SP",
            usuario_id=user.id,
            prefeitura_id=original_os.prefeitura_id,  # Must match!
            status="PENDENTE",
            origem_retorno_id=original_os.id,
            gerada_automaticamente=True,
        )
        db.session.add(return_os)
        db.session.commit()
        
        # Test: User should be able to access the return OS
        query = db.session.query(Solicitacao).filter(Solicitacao.id == return_os.id)
        result = apply_solicitacao_prefeitura_scope(query, user).first()
        
        assert result is not None, (
            "equipe_oceano user with matching prefeitura_id should be able "
            f"to access return OS {return_os.id}"
        )
        assert result.id == return_os.id
        assert result.prefeitura_id == user.prefeitura_id


def test_automatic_return_os_inherits_prefeitura_id_from_original(app):
    """
    Test that automatically created return OS inherit the prefeitura_id
    from the original OS, not leaving it as None.
    """
    with app.app_context():
        # Create a prefeitura
        prefeitura = Prefeitura(nome="Test Prefeitura 2", slug="test-prefeitura-2")
        db.session.add(prefeitura)
        db.session.flush()
        
        # Create user
        user = Usuario(
            nome_uvis="UVIS Test",
            tipo_usuario="uvis",
            login="uvistest",
            senha_hash="hash",
            prefeitura_id=prefeitura.id,
        )
        db.session.add(user)
        db.session.flush()

        equipe = Equipe(nome_equipe="Equipe Retorno", prefeitura_id=prefeitura.id)
        db.session.add(equipe)
        db.session.flush()
        
        # Create original OS with prefeitura
        original_os = Solicitacao(
            data_agendamento=date.today(),
            hora_agendamento=time(9, 0),
            foco="Aedes",
            tipo_operacao="Monitoramento",
            cep="00000-000",
            logradouro="Rua Teste",
            numero="100",
            bairro="Centro",
            cidade="Sao Paulo",
            uf="SP",
            usuario_id=user.id,
            prefeitura_id=prefeitura.id,
            equipe_id=equipe.id,
            status="CONCLUÍDO",
            place_id="place-id-original",
        )
        db.session.add(original_os)
        db.session.commit()
        
        # Simulate creating a return OS
        from app.models import OrdemServico
        from app.modules.piloto_os.service import criar_solicitacao_retorno_monitoramento
        
        ordem = OrdemServico(
            solicitacao_id=original_os.id,
            equipe_id=equipe.id,
            identificador_os="TEST",
        )
        db.session.add(ordem)
        db.session.flush()
        
        # Create return OS
        criar_solicitacao_retorno_monitoramento(original_os, ordem)
        db.session.commit()
        
        # Verify return OS has prefeitura_id
        return_os = db.session.query(Solicitacao).filter(
            Solicitacao.origem_retorno_id == original_os.id,
            Solicitacao.gerada_automaticamente.is_(True)
        ).first()
        
        assert return_os is not None, "Return OS should be created"
        assert return_os.prefeitura_id == original_os.prefeitura_id, (
            f"Return OS prefeitura_id ({return_os.prefeitura_id}) should match "
            f"original OS prefeitura_id ({original_os.prefeitura_id})"
        )
        assert return_os.prefeitura_id is not None, (
            "Return OS prefeitura_id should never be None"
        )
        assert return_os.place_id == original_os.place_id, (
            "Return OS should inherit the Place ID from the original OS"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
