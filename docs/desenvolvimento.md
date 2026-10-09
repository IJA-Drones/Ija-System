# Desenvolvimento local

Este guia prepara uma instalação local e explica as diferenças entre testar regras com SQLite e reproduzir a aplicação com PostgreSQL. Execute os comandos na raiz do repositório. Os exemplos de shell usam macOS/Linux; no PowerShell, variáveis temporárias usam `$env:NOME = "valor"`.

## Dependências

- Python com `venv` e as bibliotecas de [requirements.txt](../requirements.txt). A suíte desta revisão foi executada no ambiente existente com Python **3.14.7**; não há arquivo de versão mínima/suportada no projeto nem matriz de compatibilidade validada.
- PostgreSQL para reproduzir banco e migrações; `psql` e `pg_dump` para administração e backup. A versão de servidor homologada ainda precisa ser registrada pela operação.
- Node para os dois testes JavaScript; a revisão usou **24.19.0**. Não há etapa npm para servir o frontend.
- Bibliotecas nativas exigidas pelo WeasyPrint no sistema operacional quando usar seus exportadores. Instalar o pacote Python não comprova que todos os PDFs renderizam.
- `ffmpeg` para conversão de vídeos; `ffprobe`, se disponível, auxilia a validação. A localização alternativa de `ffmpeg` é configurada com `FFMPEG_PATH`.

Essas versões descrevem o ambiente verificado, não uma instalação nova homologada de todas as dependências.

## Ambiente virtual e configuração

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

No Windows, ative com `.venv\Scripts\Activate.ps1` no PowerShell ou `.venv\Scripts\activate.bat` no CMD.

Se ainda não houver `.env`, copie [.env.example](../.env.example). Se já existir, compare os nomes e acrescente apenas o que faltar; não substitua as credenciais existentes pelo modelo.

```bash
cp -n .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Cole a chave gerada em `SECRET_KEY` e configure `DATABASE_URL` para um banco **local exclusivo**. O exemplo contém usuário e senha fictícios; crie o banco e o usuário com suas ferramentas PostgreSQL antes de continuar. Confira o [catálogo de configuração](configuracao.md) para recursos opcionais.

O projeto carrega `.env` na inicialização. Variáveis já exportadas no processo têm precedência sobre `load_dotenv`; confira se o terminal não conserva uma URL de outro ambiente. `Config` não define banco padrão: sem `DATABASE_URL`, a inicialização do SQLAlchemy falha.

## Preparar o banco

Antes de executar comandos, confirme host e nome do banco de destino sem expor a senha. Em uma base local preparada para o histórico do projeto:

```bash
flask --app app:create_app db heads
flask --app app:create_app db current
flask --app app:create_app db upgrade
```

O grafo atual tem um head, mas contém bases recuperadas e merges históricos. A revisão verificou o grafo, **não executou a cadeia completa em PostgreSQL vazio**. Se uma instalação nova falhar por tabela já existente, coluna ausente ou revisão desconhecida, preserve o erro e veja [migrações e recuperação](operacao.md). Não use `db stamp head` para mascarar a falha.

SQLite é usado nos testes com criação temporária dos modelos. Isso não valida as migrações PostgreSQL. `IJA_CREATE_ALL=1 python run.py` chama `db.create_all()` no banco configurado, não registra revisões Alembic e não atualiza tabelas existentes; não faz parte do procedimento normal de instalação.

**Efeito da factory:** `create_app()` também inicia o agendador de backup. Comandos Flask e scripts que usam a factory podem iniciar esse agendador no próprio processo. Não mantenha processos locais apontados para a base de produção. `APP_ENV=local` muda somente o nome do backup.

## Primeiro acesso em uma base local vazia

Não há comando dedicado de bootstrap nem credencial padrão no repositório. Se a base já contém um administrador, use o cadastro normal de usuários. Para uma base local vazia, depois de conferir o destino, abra:

```bash
flask --app app:create_app shell
```

Execute no shell Python:

```python
from getpass import getpass
from app.extensions import db
from app.models import Usuario

def criar_admin_local():
    if Usuario.query.first() is not None:
        raise RuntimeError("Use este bootstrap somente em uma base local sem usuários.")
    login = input("Login do administrador local: ").strip()
    if not login:
        raise ValueError("Informe o login.")
    senha = getpass("Senha: ")
    if not senha or senha != getpass("Confirme a senha: "):
        raise ValueError("Senha vazia ou confirmação diferente.")
    usuario = Usuario(nome_uvis="Administrador local", login=login, tipo_usuario="admin")
    usuario.set_senha(senha)
    db.session.add(usuario)
    db.session.commit()

criar_admin_local()
```

A senha passa pelo método do modelo; com os controles habilitados, a política configurada também se aplica. O exemplo cria um administrador global apenas na base local. O perfil `dev` é separado e necessário para diagnóstico e backup pela interface; não é concedido pelo exemplo.

## Iniciar a aplicação

```bash
python run.py
```

Abra **http://localhost:5002/login**. O [run.py](../run.py) usa porta **5002**, escuta em `0.0.0.0`, ativa debug por padrão e desativa o reloader. Use-o em um ambiente local confiável. Para bind apenas no loopback, use a CLI do Flask:

```bash
FLASK_DEBUG=1 flask --app app:create_app run --host 127.0.0.1 --port 5002 --no-reload
```

Na CLI, os defaults adicionais de `run.py` não se aplicam. Com `FLASK_DEBUG=0`, o Talisman força HTTPS; isso explica redirecionamento de HTTP em ambientes sem proxy TLS. Em produção, utilize o fluxo de Gunicorn descrito no [guia de operação](operacao.md).

Outros pontos de entrada: `/uvis-operacional/login`, `/agro/login` e `/portal-cidadao`. O piloto agro precisa de vínculo com um `PilotoAgro` ativo. O painel agro também depende do indicador `trabalha_agro`, conforme o perfil.

## CSS e verificação rápida

```bash
python scripts/build_css_bundle.py
python scripts/build_css_bundle.py --check
DATABASE_URL=sqlite:///:memory: python -m pytest -q
node --test tests/session_security_browser.test.cjs tests/csrf_security_browser.test.cjs
```

Edite os arquivos componentizados e [style.css](../app/static/css/style.css); o bundle é gerado. `run.py` o constrói ao iniciar e habilita atualização quando desatualizado, salvo configuração explícita em contrário.

Depois de iniciar o servidor, confira `/healthz` e `/healthz/full`, faça login com a conta local e abra uma listagem. Teste uploads, mapas e PDFs separadamente se as integrações tiverem sido configuradas. O roteiro de testes completo fica em [testes.md](testes.md).
