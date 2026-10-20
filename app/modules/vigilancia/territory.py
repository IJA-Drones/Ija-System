"""Malha pública preservada do IBGE; consulta local, sem banco ou rede."""

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from .sinan import MUNICIPALITIES


@lru_cache(maxsize=1)
def _pernambuco():
    return json.loads((Path(__file__).parent / 'data' / 'pernambuco_ibge.geojson').read_text())


def pernambuco_context(ibge=None):
    data = _pernambuco()
    codes = {item['ibge'] for item in MUNICIPALITIES if item['region'] == 'condomar'}
    # A base preserva Fernando de Noronha. O enquadramento deste painel é o
    # continente, onde estão os municípios do CONDOMAR.
    features = [{**feature, 'properties': {**feature['properties'],
        'condomar': feature['properties']['codigo'] in codes,
        'selecionado': feature['properties']['codigo'] == ibge}}
        for feature in data['features'] if feature['properties']['codigo'] != '2605459']
    return deepcopy({'type': 'FeatureCollection', 'features': features,
        'metadata': {**data['metadata'], 'recorte': 'Pernambuco continental'}})


def condomar_territory():
    codes = {item['ibge'] for item in MUNICIPALITIES if item['region'] == 'condomar'}
    data = _pernambuco()
    return deepcopy({'type': 'FeatureCollection', 'features': [feature for feature in data['features']
        if feature['properties']['codigo'] in codes], 'metadata': data['metadata']})


def municipality_feature(ibge):
    return deepcopy(next((feature for feature in _pernambuco()['features']
        if feature['properties']['codigo'] == ibge), None))
