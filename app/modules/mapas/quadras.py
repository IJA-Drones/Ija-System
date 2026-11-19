"""Bounded GeoSampa quadra reads. Fixed endpoint, sanitized attributes, memory cache."""
from collections import OrderedDict
from copy import deepcopy
import json
import math
import re
from threading import RLock
from time import monotonic

import requests
from shapely.geometry import shape

URL = 'https://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs'
SOURCE = 'https://metadados.geosampa.prefeitura.sp.gov.br/geonetwork/srv/api/records/4ca0d339-8510-4f4d-aac4-a5f6ee570c0b'
MAX_FEATURES = 500
MAX_BYTES = 1_500_000
_cache = OrderedDict()
_lock = RLock()


class QuadraUnavailable(Exception):
    pass


def quadra_id(value):
    value = str(value or '')
    if not re.fullmatch(r'[0-9]{1,15}', value):
        raise ValueError('Selecione uma quadra fiscal válida.')
    return value


def bounds(raw):
    try:
        values = [float(x) for x in str(raw).split(',')]
        if len(values) != 4 or any(not math.isfinite(x) for x in values): raise ValueError
        w,s,e,n = values
        if not (-46.90 <= w < e <= -46.30 and -24.10 <= s < n <= -23.25): raise ValueError
        if e-w > .08 or n-s > .08 or (e-w)*(n-s) > .0025:
            raise ValueError('Aproxime o mapa para consultar as quadras desta região.')
        return tuple(round(x, 6) for x in values)
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc) if 'Aproxime' in str(exc) else 'Selecione um recorte válido e aproximado de São Paulo.') from exc


def _clean(feature):
    p = feature.get('properties', {})
    identifier = quadra_id(p.get('cd_identificador_original_quadra_fiscal'))
    geometry = feature.get('geometry')
    if not isinstance(geometry, dict) or geometry.get('type') not in ('Polygon','MultiPolygon'):
        raise QuadraUnavailable('O GeoSampa retornou uma geometria inválida.')
    try:
        geom = shape(geometry)
        w,s,e,n = geom.bounds
        if geom.is_empty or not geom.is_valid or not (-46.95 <= w <= e <= -46.20 and -24.15 <= s <= n <= -23.15): raise ValueError
    except Exception as exc:
        raise QuadraUnavailable('Não foi possível validar o contorno da quadra.') from exc
    def text(name): return str(p.get(name) or '')[:80]
    return dict(type='Feature', id=identifier, geometry=geometry, properties=dict(
        id=identifier, setor=text('cd_setor_fiscal'), quadra=text('cd_quadra_fiscal'),
        subquadra=text('cd_subquadra_fiscal'), tipo=text('tx_tipo_quadra'), atualizado_em=text('dt_carga')))


def _download(params):
    base = dict(service='WFS', version='2.0.0', request='GetFeature', typeNames='geoportal:quadra_fiscal',
                outputFormat='application/json', srsName='EPSG:4326', count=MAX_FEATURES+1)
    try:
        with requests.get(URL, params={**base, **params}, timeout=(3.05, 15), stream=True) as response:
            response.raise_for_status()
            chunks=[]; size=0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES: raise QuadraUnavailable('Recorte extenso. Aproxime o mapa para consultar quadras.')
                chunks.append(chunk)
        data=json.loads(b''.join(chunks))
        features=data.get('features')
        if data.get('type') != 'FeatureCollection' or not isinstance(features,list): raise ValueError
        if len(features)>MAX_FEATURES: raise ValueError('Mais de 500 quadras no recorte. Aproxime o mapa; nenhuma lista parcial foi exibida.')
        result=dict(type='FeatureCollection', features=[_clean(f) for f in features],
                    metadata=dict(fonte='GeoSampa · Prefeitura de São Paulo', url=SOURCE, consulta='Área visível do mapa; referência fiscal, não quarteirão LIRAa.'))
        return result
    except QuadraUnavailable: raise
    except requests.RequestException as exc:
        raise QuadraUnavailable('GeoSampa indisponível no momento. Tente carregar as quadras novamente.') from exc
    except (ValueError,TypeError,KeyError) as exc:
        if '500 quadras' in str(exc): raise ValueError(str(exc)) from exc
        raise QuadraUnavailable('O GeoSampa não retornou uma resposta válida de quadras.') from exc


def _cached(key, load):
    with _lock:
        found=_cache.get(key)
        if found and found[0]>monotonic():
            _cache.move_to_end(key);return deepcopy(found[1])
    result=load()
    with _lock:
        _cache[key]=(monotonic()+900,result,len(json.dumps(result)));_cache.move_to_end(key)
        while len(_cache)>24 or sum(entry[2] for entry in _cache.values())>4_000_000:_cache.popitem(last=False)
    return deepcopy(result)


def list_quadras(bbox):
    frame=bounds(bbox)
    return _cached(('bbox',frame),lambda:_download({'bbox':','.join(map(str,frame))+',EPSG:4326'}))


def get_quadra(identifier):
    identifier=quadra_id(identifier)
    def load():
        data=_download({'CQL_FILTER':f'cd_identificador_original_quadra_fiscal={identifier}', 'count':2})
        if len(data['features'])!=1 or data['features'][0]['id']!=identifier:
            raise ValueError('A quadra selecionada não está disponível. Atualize a camada de quadras.')
        return data['features'][0]
    return _cached(('id',identifier),load)
