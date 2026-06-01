from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from io import BytesIO

import requests
from dotenv import dotenv_values
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Drones, EquipamentoAgro, Equipamentos


ALLOWED_EXTENSIONS = {"csv", "xls", "xlsx"}
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_FALLBACK_MODELS = ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _to_ascii(value):
    text = str(value or "")
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _is_ascii(value):
    return all(ord(ch) < 128 for ch in str(value or ""))


def _load_dotenv_key(key_name):
    env_path = os.path.abspath(os.path.join(current_app.root_path, "..", ".env"))
    return (dotenv_values(env_path).get(key_name) or "").strip()


def _resolve_gemini_api_key():
    candidates = [
        (os.getenv("GEMINI_API_KEY") or "").strip(),
        str(current_app.config.get("GEMINI_API_KEY") or "").strip(),
        _load_dotenv_key("GEMINI_API_KEY"),
    ]

    for candidate in candidates:
        if candidate and _is_ascii(candidate):
            return candidate

    invalid_positions = [
        index
        for index, char in enumerate(candidates[0] if candidates else "")
        if ord(char) >= 128
    ]
    if invalid_positions:
        raise RuntimeError(
            "GEMINI_API_KEY contém caracteres não ASCII nas posições: "
            + ", ".join(str(position) for position in invalid_positions)
            + ". Atualize a variável de ambiente ou o arquivo .env."
        )

    raise RuntimeError("GEMINI_API_KEY não configurada no ambiente.")


def _clean_text(value):
    if value is None:
        return None
    text = _to_ascii(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "-", "n/i", "nao informado", "não informado"}:
        return None
    return text


def _parse_float(value, default=None):
    text = _clean_text(value)
    if text is None:
        return default

    normalized = text.replace("kg", "").replace("l", "").replace("m", "").strip()
    normalized = normalized.replace(".", "").replace(",", ".") if "," in normalized else normalized

    try:
        return float(normalized)
    except (TypeError, ValueError):
        return default


def _normalize_status(value):
    status = (_clean_text(value) or "Ativo").strip().lower()
    if status in {"ativo", "operacional", "disponivel", "ok"}:
        return "Ativo"
    if status in {"manutencao", "em manutencao", "revisao"}:
        return "Manutenção"
    if status in {"inativo", "baixado", "desativado", "indisponivel"}:
        return "Inativo"
    return "Ativo"


def _build_renomacao(modelo, numero_serie, fallback_prefix="Drone"):
    modelo = _clean_text(modelo) or fallback_prefix
    serial = _clean_text(numero_serie)
    if serial:
        return f"{modelo} {serial[-4:]}"
    return f"{modelo} {uuid.uuid4().hex[:4].upper()}"


def _generate_provisional_anac(numero_serie):
    serial = _clean_text(numero_serie)
    suffix = re.sub(r"[^A-Za-z0-9_-]+", "", serial or "")
    suffix = suffix or uuid.uuid4().hex[:8].upper()
    return f"PROVISORIO-{suffix}"


def _extract_json_content(raw_content):
    text = (raw_content or "").strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        text = text.removesuffix("```").strip()
    return json.loads(text)


def _read_spreadsheet(file_storage):
    filename = (file_storage.filename or "").strip()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato inválido. Envie um arquivo .xlsx, .xls ou .csv.")

    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Dependência pandas não instalada no ambiente.") from exc

    buffer = BytesIO(file_storage.read())
    if extension == "csv":
        try:
            return pd.read_csv(buffer, sep=None, engine="python")
        except UnicodeDecodeError:
            buffer.seek(0)
            return pd.read_csv(buffer, sep=None, engine="python", encoding="latin-1")

    return pd.read_excel(buffer)


def _spreadsheet_to_text(file_storage):
    df = _read_spreadsheet(file_storage)
    if df.empty:
        raise ValueError("A planilha enviada está vazia.")
    return _to_ascii(df.to_string(index=False))


def _gemini_drone_import_schema():
    item_properties = {
        "modelo": {"type": "STRING"},
        "renomacao": {"type": "STRING"},
        "numero_serie": {"type": "STRING"},
        "status": {"type": "STRING"},
        "registro_anatel": {"type": "STRING"},
        "registro_anac": {"type": "STRING"},
        "pmd_kg": {"type": "STRING"},
        "capacidade_tanque_l": {"type": "STRING"},
        "largura_faixa_m": {"type": "STRING"},
    }
    return {
        "type": "OBJECT",
        "required": ["drones"],
        "properties": {
            "drones": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "required": list(item_properties.keys()),
                    "properties": item_properties,
                    "propertyOrdering": list(item_properties.keys()),
                },
            }
        },
        "propertyOrdering": ["drones"],
    }


def _extract_gemini_text(response_payload):
    try:
        parts = response_payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        prompt_feedback = response_payload.get("promptFeedback") if isinstance(response_payload, dict) else None
        raise ValueError(f"Gemini não retornou conteúdo válido. Feedback: {prompt_feedback}") from exc

    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if not text:
        raise ValueError("Gemini retornou uma resposta vazia.")
    return text


def _normalize_gemini_model_name(model):
    model = (model or "").strip()
    if model.startswith("models/"):
        model = model.removeprefix("models/")
    return model or GEMINI_MODEL


def _gemini_model_candidates():
    configured = _normalize_gemini_model_name(os.getenv("GEMINI_MODEL", GEMINI_MODEL))
    candidates = [configured]
    candidates.extend(GEMINI_FALLBACK_MODELS)

    unique = []
    for candidate in candidates:
        candidate = _normalize_gemini_model_name(candidate)
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


def _list_gemini_generate_content_models(api_key):
    try:
        response = requests.get(
            GEMINI_MODELS_URL,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    try:
        payload = response.json()
    except ValueError:
        return []

    models = []
    for model in payload.get("models", []):
        methods = model.get("supportedGenerationMethods") or []
        name = _normalize_gemini_model_name(model.get("name"))
        if name and "generateContent" in methods:
            models.append(name)
    return models


def _post_gemini_generate_content(api_key, model, payload):
    url = GEMINI_API_URL.format(model=model)
    try:
        response = requests.post(
            url,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
    except requests.RequestException as exc:
        raise RuntimeError("Falha de conexão com a API do Gemini.") from exc

    if response.status_code < 400:
        return response.json()

    try:
        error_payload = response.json()
    except ValueError:
        error_payload = {"error": {"message": response.text, "status": response.status_code}}

    error = error_payload.get("error") if isinstance(error_payload, dict) else None
    status = error.get("status") if isinstance(error, dict) else response.status_code
    message = error.get("message") if isinstance(error, dict) else response.text
    code = error.get("code") if isinstance(error, dict) else response.status_code
    raise RuntimeError(json.dumps({"status": status, "code": code, "message": message}, ensure_ascii=True))


def _call_gemini_json(system_prompt, user_prompt):
    api_key = _resolve_gemini_api_key()
    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "response_mime_type": "application/json",
            "response_schema": _gemini_drone_import_schema(),
        },
    }

    not_found_models = []
    last_error = None
    for candidate in _gemini_model_candidates():
        try:
            return _extract_gemini_text(_post_gemini_generate_content(api_key, candidate, payload))
        except RuntimeError as exc:
            last_error = exc
            try:
                error_payload = json.loads(str(exc))
            except ValueError:
                raise

            status = error_payload.get("status")
            message = error_payload.get("message") or ""
            if status == "NOT_FOUND":
                not_found_models.append(candidate)
                continue

            raise RuntimeError(f"Gemini retornou erro ({status}): {message}") from exc

    available_models = _list_gemini_generate_content_models(api_key)
    suffix = ""
    if available_models:
        suffix = " Modelos disponíveis para generateContent: " + ", ".join(available_models[:12])
    raise RuntimeError(
        "Nenhum modelo Gemini configurado foi encontrado para esta chave/API. "
        f"Testados: {', '.join(not_found_models)}.{suffix}"
    ) from last_error


def normalize_spreadsheet_with_ai(table_text, *, agro=False):
    system_prompt = (
        "Você é um normalizador determinístico de planilhas de drones para o IJA System. "
        "Converta a tabela recebida em JSON puro e válido, sem Markdown. "
        "Mapeie semanticamente colunas arbitrárias: S/N, SN, Serial, Série, Código e Chassi para numero_serie; "
        "Situação, Estado e Condição para status; Apelido, Nome, Renomeação e Identificação para renomacao; "
        "ANATEL e Homologação para registro_anatel; ANAC, SISANT e cadastro ANAC para registro_anac; "
        "PMD, peso máximo, peso de decolagem para pmd_kg; tanque, capacidade e volume para capacidade_tanque_l; "
        "faixa, largura de faixa e largura para largura_faixa_m. "
        "Preserve textos importantes, normalize números como texto simples e retorne null quando o dado não existir. "
        "Se uma linha não representar um drone/equipamento, ignore. "
        "A chave raiz deve ser drones."
    )

    user_prompt = (
        f"Tipo de frota alvo: {'Agro' if agro else 'Urbano/Prefeituras'}.\n"
        "Tabela extraída da planilha:\n"
        f"{table_text}"
    )

    content = _call_gemini_json(system_prompt, user_prompt)
    payload = _extract_json_content(content)
    drones = payload.get("drones")
    if not isinstance(drones, list):
        raise ValueError("A IA retornou um JSON sem a lista 'drones'.")
    return drones


def _ensure_unique_or_raise(model, field_name, value, label):
    if not value:
        return
    column = getattr(model, field_name)
    if model.query.filter(column == value).first():
        raise ValueError(f"{label} já cadastrado: {value}.")


def _validate_batch_uniques(items, *, agro=False):
    seen_series = set()
    seen_anac = set()
    for index, item in enumerate(items, start=1):
        numero_serie = _clean_text(item.get("numero_serie"))
        registro_anac = _clean_text(item.get("registro_anac"))

        if numero_serie:
            if numero_serie in seen_series:
                raise ValueError(f"Número de série duplicado na planilha: {numero_serie}.")
            seen_series.add(numero_serie)

        if not agro and registro_anac:
            if registro_anac in seen_anac:
                raise ValueError(f"Registro ANAC duplicado na planilha: {registro_anac}.")
            seen_anac.add(registro_anac)


def _create_urban_drone(item, prefeitura_id):
    modelo = _clean_text(item.get("modelo")) or "Drone sem modelo"
    numero_serie = _clean_text(item.get("numero_serie"))
    registro_anac = _clean_text(item.get("registro_anac")) or _generate_provisional_anac(numero_serie)
    registro_anatel = _clean_text(item.get("registro_anatel")) or "Não Registrado"

    _ensure_unique_or_raise(Equipamentos, "numero_serie", numero_serie, "Número de série")
    _ensure_unique_or_raise(Drones, "registro_anac", registro_anac, "Registro ANAC")

    drone = Drones(
        tipo_equipamento="drones",
        modelo=modelo,
        renomacao=_clean_text(item.get("renomacao")) or _build_renomacao(modelo, numero_serie),
        numero_serie=numero_serie,
        status=_normalize_status(item.get("status")),
        registro_anatel=registro_anatel,
        registro_anac=registro_anac,
        pmd_kg=_parse_float(item.get("pmd_kg"), default=0.0),
        prefeitura_id=prefeitura_id,
    )
    db.session.add(drone)
    return drone


def _create_agro_equipment(item, prefeitura_id):
    modelo = _clean_text(item.get("modelo")) or "Drone sem modelo"
    numero_serie = _clean_text(item.get("numero_serie"))

    _ensure_unique_or_raise(EquipamentoAgro, "numero_serie", numero_serie, "Número de série")

    equipamento = EquipamentoAgro(
        tipo="Drone",
        modelo=modelo,
        identificacao=_clean_text(item.get("renomacao")) or _build_renomacao(modelo, numero_serie),
        numero_serie=numero_serie,
        status=_normalize_status(item.get("status")),
        registro_anatel=_clean_text(item.get("registro_anatel")),
        registro_anac=_clean_text(item.get("registro_anac")),
        capacidade_tanque_l=_parse_float(item.get("capacidade_tanque_l")),
        largura_faixa_m=_parse_float(item.get("largura_faixa_m")),
        prefeitura_id=prefeitura_id,
    )
    db.session.add(equipamento)
    return equipamento


def import_drone_spreadsheet(file_storage, *, agro=False, prefeitura_id=None):
    if file_storage is None or not file_storage.filename:
        raise ValueError("Envie uma planilha para importar.")
    if prefeitura_id is None:
        raise ValueError("Informe a prefeitura relacionada à importação.")

    table_text = _spreadsheet_to_text(file_storage)
    normalized_items = normalize_spreadsheet_with_ai(table_text, agro=agro)
    normalized_items = [item for item in normalized_items if isinstance(item, dict)]
    _validate_batch_uniques(normalized_items, agro=agro)

    imported = []
    try:
        for item in normalized_items:
            has_minimum_data = _clean_text(item.get("modelo")) or _clean_text(item.get("numero_serie"))
            if not has_minimum_data:
                continue
            imported.append(
                _create_agro_equipment(item, prefeitura_id)
                if agro
                else _create_urban_drone(item, prefeitura_id)
            )

        if not imported:
            raise ValueError("Nenhum drone válido foi identificado na planilha.")

        db.session.commit()
    except (SQLAlchemyError, ValueError):
        db.session.rollback()
        raise

    return {
        "imported_count": len(imported),
        "scope": "agro" if agro else "urbano",
    }
