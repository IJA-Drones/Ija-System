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
        'metadata': {**data['metadata'], 'recorte': 'Pernambuco continental',
            'escala': 'estado', 'descricao': 'Pernambuco continental · norte para cima · malha simplificada do IBGE. Fernando de Noronha fica fora deste recorte do CONDOMAR.'}})


@lru_cache(maxsize=1)
def _sao_paulo():
    return json.loads((Path(__file__).parent / 'data' / 'sao_paulo_ibge.geojson').read_text())


def territorial_context(ibge=None):
    """Nunca utiliza a malha de outro estado para a prefeitura selecionada."""
    if ibge and str(ibge).startswith('26'):
        return pernambuco_context(ibge)
    if ibge == '3550308':
        data = deepcopy(_sao_paulo())
        for feature in data['features']:
            feature['properties'].update(selecionado=True, condomar=False)
        data['metadata'].update(recorte='Município de São Paulo', escala='municipio',
            descricao='Município de São Paulo · norte para cima · malha simplificada do IBGE. Os contornos do levantamento vêm do planejamento.')
        return data
    return {'type': 'FeatureCollection', 'features': [], 'metadata': {
        'recorte': 'Território do levantamento', 'escala': 'levantamento',
        'descricao': 'Norte para cima · contornos do planejamento e coordenadas informadas nas visitas.'}}


def condomar_territory():
    codes = {item['ibge'] for item in MUNICIPALITIES if item['region'] == 'condomar'}
    data = _pernambuco()
    return deepcopy({'type': 'FeatureCollection', 'features': [feature for feature in data['features']
        if feature['properties']['codigo'] in codes], 'metadata': data['metadata']})


def municipality_feature(ibge):
    if ibge == '3550308':
        return deepcopy(_sao_paulo()['features'][0])
    return deepcopy(next((feature for feature in _pernambuco()['features']
        if feature['properties']['codigo'] == ibge), None))
