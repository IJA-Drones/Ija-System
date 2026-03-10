import argparse

from app import create_app, db
from app.models import Usuario


def criar_ou_atualizar_usuario(nome: str, login: str, senha: str, tipo_usuario: str, regiao: str) -> str:
    usuario = Usuario.query.filter_by(login=login).first()

    if usuario:
        usuario.nome_uvis = nome
        usuario.regiao = regiao
        usuario.tipo_usuario = tipo_usuario
        usuario.set_senha(senha)
        return f"atualizado: {login} ({tipo_usuario})"

    novo = Usuario(
        nome_uvis=nome,
        regiao=regiao,
        login=login,
        tipo_usuario=tipo_usuario,
    )
    novo.set_senha(senha)
    db.session.add(novo)
    return f"criado: {login} ({tipo_usuario})"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cria/atualiza usuários de painel: visualizar e operario."
    )
    parser.add_argument("--regiao", default="CENTRO", help="Região padrão para os usuários.")

    parser.add_argument("--nome-visualizar", default="Usuário Visualizar")
    parser.add_argument("--login-visualizar", default="visualizar")
    parser.add_argument("--senha-visualizar", default="visualizar123")

    parser.add_argument("--nome-operario", default="Usuário Operário")
    parser.add_argument("--login-operario", default="operario")
    parser.add_argument("--senha-operario", default="operario123")

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        mensagens = [
            criar_ou_atualizar_usuario(
                nome=args.nome_visualizar,
                login=args.login_visualizar,
                senha=args.senha_visualizar,
                tipo_usuario="visualizar",
                regiao=args.regiao,
            ),
            criar_ou_atualizar_usuario(
                nome=args.nome_operario,
                login=args.login_operario,
                senha=args.senha_operario,
                tipo_usuario="operario",
                regiao=args.regiao,
            ),
        ]

        db.session.commit()

        for msg in mensagens:
            print(msg)


if __name__ == "__main__":
    main()
