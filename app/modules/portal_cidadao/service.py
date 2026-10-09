import os
import re
import uuid
from datetime import datetime

from flask import current_app
from werkzeug.utils import secure_filename

from app import db
from app.clients.cep_client import CepLookupError, CepNotFoundError, lookup_cep
from app.clients.google_maps_client import geocode_endereco_google, reverse_geocode_lat_lng_google_details
from app.models import Denuncia, DenunciaAnexo
from app.shared.skybox import SkyboxError, skybox_enabled, upload_file_to_skybox
from app.shared.uploads import get_upload_folder


ALLOWED_MEDIA_EXTENSIONS = {"png", "jpg", "jpeg", "jfif", "webp", "heic", "mp4", "mov", "avi", "mkv", "webm"}
MAX_MEDIA_FILES = 5


class DenunciaValidationError(ValueError):
    def __init__(self, errors):
        super().__init__("Dados da denuncia invalidos.")
        self.errors = errors


def criar_denuncia(form, files, *, ip_origem=None, user_agent=None):
    data = _parse_denuncia_form(form)
    anexos = [arquivo for arquivo in files.getlist("midias") if arquivo and arquivo.filename]

    _enrich_address_from_location(data)
    if len(_digits(data.get("cep"))) == 8:
        _enrich_address_from_cep(data)
    _try_geocode_address(data)

    errors = _validate_denuncia_data(data)

    if len(anexos) > MAX_MEDIA_FILES:
        errors["midias"] = f"Envie no maximo {MAX_MEDIA_FILES} arquivos."

    for arquivo in anexos:
        if not _allowed_media_file(arquivo.filename):
            errors["midias"] = "Envie apenas imagens ou videos nos formatos permitidos."
            break

    if errors:
        raise DenunciaValidationError(errors)

    denuncia = Denuncia(
        protocolo=_generate_protocolo(),
        status=Denuncia.STATUS_RECEBIDA,
        tipo_visita=data["tipo_visita"],
        tipo_imovel=data.get("tipo_imovel") or None,
        foco=data["foco"],
        descricao=data.get("descricao") or None,
        cep=data["cep"],
        logradouro=data["logradouro"],
        numero=data["numero"],
        complemento=data.get("complemento") or None,
        bairro=data["bairro"],
        cidade=data["cidade"],
        uf=data["uf"],
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        place_id=data.get("place_id"),
        cidadao_nome=data["nome"],
        cidadao_cpf=data["cpf"],
        cidadao_rg=data["rg"],
        cidadao_telefone=data["telefone"],
        consentimento=True,
        ip_origem=ip_origem,
        user_agent=user_agent,
    )
    db.session.add(denuncia)
    db.session.flush()

    for arquivo in anexos:
        denuncia.anexos.append(_save_denuncia_media(denuncia, arquivo))

    db.session.commit()
    return denuncia


def _parse_denuncia_form(form):
    return {
        "tipo_visita": _clean(form.get("tipo_visita")),
        "tipo_imovel": _clean(form.get("tipo_imovel")),
        "foco": _clean(form.get("foco")),
        "descricao": _clean(form.get("descricao")),
        "cep": _format_cep(_digits(form.get("cep"))),
        "logradouro": _clean(form.get("logradouro")),
        "numero": _clean(form.get("numero")),
        "complemento": _clean(form.get("complemento")),
        "bairro": _clean(form.get("bairro")),
        "cidade": _clean(form.get("cidade")),
        "uf": _clean(form.get("uf")).upper() or "SP",
        "latitude": _clean(form.get("latitude")),
        "longitude": _clean(form.get("longitude")),
        "place_id": _clean(form.get("place_id")),
        "nome": _clean(form.get("nome")),
        "cpf": _format_cpf(_digits(form.get("cpf"))),
        "rg": _clean(form.get("rg")),
        "telefone": _format_phone(_digits(form.get("telefone"))),
        "consentimento": str(form.get("consentimento") or "").lower() in {"1", "true", "on", "sim"},
    }


def _validate_denuncia_data(data):
    errors = {}
    required = {
        "tipo_visita": "Escolha o tipo de ocorrencia.",
        "foco": "Escolha o que foi encontrado no local.",
        "logradouro": "Informe o logradouro.",
        "numero": "Informe o numero.",
        "bairro": "Informe o bairro.",
        "cidade": "Informe a cidade.",
        "nome": "Informe seu nome completo.",
        "cpf": "Informe um CPF valido.",
        "rg": "Informe o RG.",
        "telefone": "Informe um telefone valido.",
    }
    for field, message in required.items():
        if not data.get(field):
            errors[field] = message

    if data["tipo_visita"] == "Aedes" and not data["tipo_imovel"]:
        errors["tipo_imovel"] = "Informe o tipo de local."
    if data["cep"] and len(_digits(data["cep"])) != 8:
        errors["cep"] = "Informe um CEP com 8 digitos."
    if data["latitude"] and not _valid_coordinate(data["latitude"], -90, 90):
        errors["latitude"] = "Latitude invalida."
    if data["longitude"] and not _valid_coordinate(data["longitude"], -180, 180):
        errors["longitude"] = "Longitude invalida."
    if data["cpf"] and not _valid_cpf(_digits(data["cpf"])):
        errors["cpf"] = "Informe um CPF valido."
    if data["rg"] and len(re.sub(r"[^0-9A-Za-z]", "", data["rg"])) < 5:
        errors["rg"] = "Informe um RG valido."
    if data["telefone"] and len(_digits(data["telefone"])) not in (10, 11):
        errors["telefone"] = "Informe um telefone com DDD."
    if not data["consentimento"]:
        errors["consentimento"] = "Confirme o uso das informacoes para triagem."

    return errors


def _enrich_address_from_cep(data):
    cep_digits = _digits(data["cep"])
    try:
        payload = lookup_cep(cep_digits, logger=current_app.logger)
    except CepNotFoundError as exc:
        raise DenunciaValidationError({"cep": "CEP nao encontrado."}) from exc
    except CepLookupError:
        return

    data["cep"] = payload.get("cep") or data["cep"]
    for field in ("logradouro", "bairro", "cidade", "uf"):
        if payload.get(field):
            data[field] = payload[field]


def _enrich_address_from_location(data):
    if not data.get("latitude") or not data.get("longitude"):
        return

    try:
        payload = reverse_geocode_lat_lng_google_details(
            lat=data["latitude"],
            lng=data["longitude"],
        )
    except Exception:
        current_app.logger.exception("Falha ao resolver endereco pela localizacao da denuncia cidada.")
        return

    if not payload:
        return

    for field in ("cep", "logradouro", "numero", "bairro", "cidade", "uf", "place_id"):
        if payload.get(field) and not data.get(field):
            data[field] = payload[field]


def _try_geocode_address(data):
    if not all(data.get(field) for field in ("logradouro", "numero", "cidade", "uf")):
        return

    try:
        lat, lng, place_id = geocode_endereco_google(
            logradouro=data["logradouro"],
            numero=data["numero"],
            bairro=data["bairro"],
            cidade=data["cidade"],
            uf=data["uf"],
            cep=data["cep"],
        )
    except Exception:
        current_app.logger.exception("Falha ao geocodificar denuncia cidada.")
        return

    data["latitude"] = str(lat) if lat is not None else None
    data["longitude"] = str(lng) if lng is not None else None
    data["place_id"] = place_id


def _save_denuncia_media(denuncia, arquivo):
    original_name = secure_filename(arquivo.filename or "midia")
    extension = original_name.rsplit(".", 1)[1].lower()
    stored_name = f"denuncia_{denuncia.id}_{uuid.uuid4().hex}.{extension}"
    tipo_midia = "video" if (arquivo.mimetype or "").startswith("video/") else "imagem"

    try:
        tamanho = _file_size(arquivo)
        if skybox_enabled():
            remote_path = "/".join(["denuncias", str(denuncia.id), tipo_midia, stored_name])
            arquivo_path = upload_file_to_skybox(arquivo, remote_path)
        else:
            relative_dir = os.path.join("denuncias", str(denuncia.id), tipo_midia)
            upload_dir = os.path.join(get_upload_folder(), relative_dir)
            os.makedirs(upload_dir, exist_ok=True)
            arquivo.save(os.path.join(upload_dir, stored_name))
            arquivo_path = "/".join([relative_dir.replace(os.sep, "/"), stored_name])
    except SkyboxError:
        current_app.logger.exception("Falha ao enviar midia de denuncia para o Skybox.")
        raise DenunciaValidationError({"midias": "Nao foi possivel salvar a midia enviada."})

    return DenunciaAnexo(
        arquivo_path=arquivo_path,
        arquivo_nome=original_name,
        mime_type=arquivo.mimetype,
        tamanho_bytes=tamanho,
        tipo_midia=tipo_midia,
    )


def _file_size(arquivo):
    try:
        stream = arquivo.stream
        position = stream.tell()
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(position)
        return int(size)
    except Exception:
        return None


def _generate_protocolo():
    return f"DEN-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _allowed_media_file(filename):
    return "." in str(filename or "") and filename.rsplit(".", 1)[1].lower() in ALLOWED_MEDIA_EXTENSIONS


def _clean(value):
    return " ".join(str(value or "").strip().split())


def _digits(value):
    return re.sub(r"\D", "", str(value or ""))


def _format_cep(digits):
    if len(digits) == 8:
        return f"{digits[:5]}-{digits[5:]}"
    return digits


def _format_cpf(digits):
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return digits


def _format_phone(digits):
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return digits


def _valid_coordinate(value, minimum, maximum):
    try:
        numeric = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return False
    return minimum <= numeric <= maximum


def _valid_cpf(digits):
    if len(digits) != 11 or len(set(digits)) == 1:
        return False

    for length in (9, 10):
        total = sum(int(digits[index]) * ((length + 1) - index) for index in range(length))
        check = (total * 10) % 11
        if check == 10:
            check = 0
        if check != int(digits[length]):
            return False
    return True
