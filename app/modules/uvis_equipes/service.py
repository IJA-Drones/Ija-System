import re
import unicodedata

from sqlalchemy import func

from app.extensions import db
from app.models import EquipeUvis, Solicitacao, Usuario


MAX_MEMBROS_EQUIPE_UVIS = 5
TEAM_ACCOUNT_TYPE = "equipe_uvis"
OPERATIONAL_UVIS_ACCOUNT_NAME = "OPERACIONAL UVIS"
LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def next_team_slot(uvis_usuario_id: int, nome_equipe: str):
    usados = {
        row[0]
        for row in (
            db.session.query(EquipeUvis.ordem)
            .filter_by(uvis_usuario_id=uvis_usuario_id, nome_equipe=nome_equipe)
            .all()
        )
    }
    for slot in range(1, MAX_MEMBROS_EQUIPE_UVIS + 1):
        if slot not in usados:
            return slot
    return None


def build_uvis_teams_listing(uvis_id: int):
    membros_rows = (
        db.session.query(
            EquipeUvis.nome_equipe.label("nome_equipe"),
            func.count(EquipeUvis.id).label("total"),
        )
        .filter(EquipeUvis.uvis_usuario_id == uvis_id)
        .group_by(EquipeUvis.nome_equipe)
        .all()
    )
    membros_map = {row.nome_equipe: int(row.total) for row in membros_rows}

    contas_rows = (
        db.session.query(
            Usuario.equipe_uvis_nome.label("nome_equipe"),
            Usuario.login.label("login"),
        )
        .filter(
            Usuario.tipo_usuario == TEAM_ACCOUNT_TYPE,
            Usuario.equipe_uvis_uvis_usuario_id == uvis_id,
            Usuario.equipe_uvis_nome.isnot(None),
        )
        .all()
    )
    login_map = {row.nome_equipe: row.login for row in contas_rows if row.nome_equipe}

    equipes = []
    for nome in sorted(set(membros_map.keys()) | set(login_map.keys())):
        equipes.append(
            {
                "nome_equipe": nome,
                "total": int(membros_map.get(nome, 0)),
                "login": login_map.get(nome),
            }
        )

    return equipes


def get_team_account(uvis_id: int, nome_equipe: str):
    return (
        Usuario.query.filter(
            Usuario.tipo_usuario == TEAM_ACCOUNT_TYPE,
            Usuario.equipe_uvis_uvis_usuario_id == uvis_id,
            Usuario.equipe_uvis_nome == nome_equipe,
        )
        .first()
    )


def get_operational_uvis_account(uvis_id: int):
    account = get_team_account(uvis_id, OPERATIONAL_UVIS_ACCOUNT_NAME)
    if account:
        return account

    legacy_accounts = (
        Usuario.query.filter(
            Usuario.tipo_usuario == TEAM_ACCOUNT_TYPE,
            Usuario.equipe_uvis_uvis_usuario_id == uvis_id,
        )
        .order_by(Usuario.id.asc())
        .all()
    )
    if len(legacy_accounts) == 1:
        return legacy_accounts[0]

    return None


def get_team_members(uvis_id: int, nome_equipe: str):
    return (
        EquipeUvis.query.filter_by(uvis_usuario_id=uvis_id, nome_equipe=nome_equipe)
        .order_by(EquipeUvis.ordem.asc())
        .all()
    )


def login_in_use(login: str, exclude_user_id=None):
    if not login:
        return None

    query = Usuario.query.filter(Usuario.login == login)
    if exclude_user_id is not None:
        query = query.filter(Usuario.id != exclude_user_id)
    return query.first()


def validate_team_login(login_equipe: str, current_login=None):
    if not login_equipe:
        return "Informe o login da equipe."
    if len(login_equipe) < 4:
        return "O login deve ter pelo menos 4 caracteres."
    if len(login_equipe) > 50:
        return "O login deve ter no maximo 50 caracteres."
    if not LOGIN_PATTERN.match(login_equipe):
        return "Use apenas letras, numeros, ponto (.), hifen (-) e underscore (_)."
    if login_equipe != current_login and login_in_use(login_equipe):
        return "Este login ja esta em uso. Escolha outro."
    return None


def validate_team_password(senha: str, senha2: str, required=False):
    if required and not senha:
        return {"senha": "Informe a senha da equipe."}

    if not senha and not senha2:
        return {}

    if not senha:
        return {"senha": "Informe a senha."}
    if len(senha) < 6:
        return {"senha": "A senha deve ter pelo menos 6 caracteres."}
    if senha != senha2:
        return {"senha2": "As senhas nao conferem."}
    return {}


def slug_upper(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""

    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.upper()
    text = text.replace("/", "-").replace("\\", "-").replace("_", "-")
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^A-Z0-9-]", "", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def first_nonempty(*values) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def user_display_base_name(user) -> str:
    direto = first_nonempty(
        getattr(user, "nome_uvis", None),
        getattr(user, "nome", None),
        getattr(user, "name", None),
        getattr(user, "nome_completo", None),
        getattr(user, "username", None),
    )

    if not direto:
        usuario = getattr(user, "usuario", None)
        if usuario is not None:
            direto = first_nonempty(
                getattr(usuario, "nome_uvis", None),
                getattr(usuario, "nome", None),
                getattr(usuario, "name", None),
                getattr(usuario, "nome_completo", None),
            )

    if not direto:
        email = getattr(user, "email", None)
        if email and "@" in str(email):
            direto = str(email).split("@", 1)[0]

    if not direto:
        direto = "SEM-NOME"

    direto = re.sub(r"^\\s*UVIS\\s*[-:\\s]*", "", str(direto).strip(), flags=re.IGNORECASE).strip()
    return direto or "SEM-NOME"


def next_team_name_for_user(user) -> str:
    nome_uvis = slug_upper(user_display_base_name(user)) or "SEM-NOME"
    prefixo = f"UVIS-{nome_uvis}-"

    rows = (
        db.session.query(EquipeUvis.nome_equipe)
        .filter(EquipeUvis.uvis_usuario_id == user.id)
        .distinct()
        .all()
    )
    existentes = [row[0] for row in rows if row and row[0]]

    maior = 0
    pattern = re.compile(rf"^{re.escape(prefixo)}(\d+)$", re.IGNORECASE)
    for nome in existentes:
        match = pattern.match(nome.strip())
        if not match:
            continue
        try:
            valor = int(match.group(1))
        except ValueError:
            continue
        if valor > maior:
            maior = valor

    return f"{prefixo}{maior + 1}"


def suggested_team_login(nome_equipe: str) -> str:
    return f"EQUIPE-{slug_upper(nome_equipe)}"[:50]


def create_team_account(user, nome_equipe: str, login_equipe: str, senha: str):
    usuario_equipe = Usuario(
        nome_uvis=nome_equipe,
        regiao=user.regiao,
        codigo_setor=user.codigo_setor,
        login=login_equipe,
        tipo_usuario=TEAM_ACCOUNT_TYPE,
        piloto_id=None,
        equipe_uvis_uvis_usuario_id=user.id,
        equipe_uvis_nome=nome_equipe,
    )
    usuario_equipe.set_senha(senha)
    db.session.add(usuario_equipe)
    return usuario_equipe


def upsert_operational_uvis_account(user, login_operacional: str, senha: str):
    account = get_operational_uvis_account(user.id)
    if account is None:
        account = Usuario(
            nome_uvis=f"Operacional - {user.nome_uvis}",
            regiao=user.regiao,
            codigo_setor=user.codigo_setor,
            login=login_operacional,
            tipo_usuario=TEAM_ACCOUNT_TYPE,
            piloto_id=None,
            prefeitura_id=getattr(user, "prefeitura_id", None),
            equipe_uvis_uvis_usuario_id=user.id,
            equipe_uvis_nome=OPERATIONAL_UVIS_ACCOUNT_NAME,
        )
        db.session.add(account)
    else:
        account.nome_uvis = f"Operacional - {user.nome_uvis}"
        account.regiao = user.regiao
        account.codigo_setor = user.codigo_setor
        account.prefeitura_id = getattr(user, "prefeitura_id", None)
        account.login = login_operacional
        account.equipe_uvis_nome = OPERATIONAL_UVIS_ACCOUNT_NAME

    if senha:
        account.set_senha(senha)

    return account


def team_exists_for_user(uvis_id: int, nome_equipe: str):
    return (
        db.session.query(EquipeUvis.id)
        .filter(EquipeUvis.uvis_usuario_id == uvis_id)
        .filter(EquipeUvis.nome_equipe == nome_equipe)
        .first()
    )


def assign_team_to_solicitacao(solicitacao_id: int, nome_equipe: str):
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    solicitacao.equipe_uvis_nome = nome_equipe
    return solicitacao


def build_admin_uvis_teams_listing():
    rows = (
        db.session.query(
            Usuario.id.label("uvis_id"),
            Usuario.nome_uvis.label("uvis_nome"),
            EquipeUvis.nome_equipe.label("nome_equipe"),
            func.count(EquipeUvis.id).label("total"),
        )
        .join(Usuario, Usuario.id == EquipeUvis.uvis_usuario_id)
        .filter(Usuario.tipo_usuario == "uvis")
        .group_by(Usuario.id, Usuario.nome_uvis, EquipeUvis.nome_equipe)
        .order_by(Usuario.nome_uvis.asc(), EquipeUvis.nome_equipe.asc())
        .all()
    )

    return [
        {
            "uvis_id": int(row.uvis_id),
            "uvis_nome": row.uvis_nome or "",
            "nome_equipe": row.nome_equipe,
            "total": int(row.total),
        }
        for row in rows
    ]
