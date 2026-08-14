from flask import current_app, has_app_context

from app.clients.google_maps_client import geocode_endereco_google


def clean_place_id(value):
    return str(value or "").strip() or None


def resolve_google_place_id_for_address(
    *,
    place_id=None,
    logradouro=None,
    numero=None,
    bairro=None,
    cidade=None,
    uf=None,
    cep=None,
):
    existing_place_id = clean_place_id(place_id)
    if existing_place_id:
        return existing_place_id

    if not all(str(value or "").strip() for value in (logradouro, numero, cidade, uf)):
        return None

    try:
        _lat, _lng, resolved_place_id = geocode_endereco_google(
            logradouro=logradouro,
            numero=numero,
            bairro=bairro,
            cidade=cidade,
            uf=uf,
            cep=cep,
        )
    except Exception:
        if has_app_context():
            current_app.logger.warning(
                "Nao foi possivel resolver automaticamente o Place ID da solicitacao."
            )
        return None

    return clean_place_id(resolved_place_id)
