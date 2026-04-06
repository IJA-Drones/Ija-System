import os
from pathlib import Path
from uuid import uuid4

import requests
from dotenv import dotenv_values
from flask import session


ADMIN_CHATBOT_TYPES = {"admin", "operario", "visualizar", "regional"}
DEFAULT_WORKFLOW_ID = "wf_69d3b33ceac8819097db3c56fa35cdae0fa3d156a38642ad"
CHATKIT_SESSION_URL = "https://api.openai.com/v1/chatkit/sessions"


class ChatKitConfigurationError(RuntimeError):
    pass


class ChatKitRequestError(RuntimeError):
    pass


def can_access_admin_chatbot(user) -> bool:
    return getattr(user, "tipo_usuario", None) in ADMIN_CHATBOT_TYPES


def build_login_chatkit_session():
    return _build_chatkit_session(prefix="login")


def build_uvis_chatkit_session(user_identifier: str | None = None):
    return _build_chatkit_session(prefix="uvis", explicit_user=user_identifier)


def build_admin_chatkit_session(user_identifier: str | None = None):
    return _build_chatkit_session(prefix="admin", explicit_user=user_identifier)


def _build_chatkit_session(prefix: str, explicit_user: str | None = None):
    api_key = _resolve_openai_api_key()
    workflow_id = os.getenv("IJA_AGENT_WORKFLOW_ID", DEFAULT_WORKFLOW_ID)

    if not api_key:
        raise ChatKitConfigurationError(
            "ChatKit sem chave configurada. Defina `OPENAI_API_KEY` no ambiente do servidor."
        )

    if not workflow_id:
        raise ChatKitConfigurationError(
            "ChatKit sem workflow configurado. Defina `IJA_AGENT_WORKFLOW_ID` no ambiente."
        )

    user_id = explicit_user or _get_or_create_chatkit_user(prefix)
    payload = {
        "workflow": {"id": workflow_id},
        "user": user_id,
    }

    try:
        response = requests.post(
            CHATKIT_SESSION_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "OpenAI-Beta": "chatkit_beta=v1",
            },
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise ChatKitRequestError(
            "Nao foi possivel conectar a OpenAI para criar a sessao do ChatKit."
        ) from exc

    if response.status_code >= 400:
        detail = _extract_error_detail(response)
        raise ChatKitRequestError(detail or "Falha ao criar a sessao do ChatKit.")

    data = response.json()
    client_secret = data.get("client_secret")
    if not client_secret:
        raise ChatKitRequestError("A OpenAI nao retornou `client_secret` para a sessao.")

    return {
        "client_secret": client_secret,
        "session_id": data.get("id"),
        "expires_at": data.get("expires_at"),
        "user": user_id,
    }


def _get_or_create_chatkit_user(prefix: str) -> str:
    session_key = f"chatkit_user_{prefix}"
    existing = session.get(session_key)
    if existing:
        return existing

    generated = f"{prefix}_{uuid4().hex}"
    session[session_key] = generated
    session.modified = True
    return generated


def _resolve_openai_api_key() -> str | None:
    env_key = _sanitize_ascii_secret(os.getenv("OPENAI_API_KEY"))
    if env_key:
        return env_key

    dotenv_path = Path(__file__).resolve().parents[3] / ".env"
    if dotenv_path.exists():
        file_key = _sanitize_ascii_secret(dotenv_values(dotenv_path).get("OPENAI_API_KEY"))
        if file_key:
            return file_key

    return None


def _sanitize_ascii_secret(value: str | None) -> str:
    if not value:
        return ""

    cleaned = str(value).strip().replace("\r", "").replace("\n", "")
    if any(ord(ch) > 127 for ch in cleaned):
        return ""

    return cleaned


def _extract_error_detail(response) -> str:
    try:
        data = response.json()
    except Exception:
        return (response.text or "").strip()

    error = data.get("error")
    if isinstance(error, dict):
        return (error.get("message") or "").strip()

    if isinstance(data, dict):
        return (data.get("message") or "").strip()

    return ""
