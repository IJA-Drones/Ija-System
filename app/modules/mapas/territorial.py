"""Read-only spatial reference. Geographic filters never grant account access."""
from functools import lru_cache
import json
from pathlib import Path
import unicodedata

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

DATA = Path(__file__).resolve().parents[2] / 'static/data/uvis-sao-paulo'


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').upper()) if c.isalnum())


@lru_cache(maxsize=1)
def uvis_names():
    data=json.loads((DATA/'uvis.geojson').read_text())
    return {normalized(f['properties']['uvis']):f['properties']['cnes'] for f in data['features']}


def cnes_for_name(name):
    key=normalized(name)
    if key.startswith('UVIS'):key=key[4:]
    return uvis_names().get(key)


@lru_cache(maxsize=1)
def reference():
    data = json.loads((DATA / 'distritos-referencia.geojson').read_text())
    return data, STRtree([shape(f['geometry']) for f in data['features']])


def validate_filters(crs='', cnes=''):
    data, _ = reference()
    crs = str(crs or '').strip().upper()
    cnes = str(cnes or '').strip()
    regions = {f['properties']['crs'] for f in data['features']}
    names = {normalized(r): r for r in regions}
    for prefix in ('COORDENADORIAREGIONALDESAUDE', 'COORDENADORIA', 'REGIAO', 'CRS'):
        key = normalized(crs)
        if key.startswith(prefix): key = key[len(prefix):]
        if key in names: crs = names[key]; break
    if crs and crs not in regions:
        raise ValueError('Selecione uma coordenadoria da referência territorial.')
    units = {f['properties']['cnes']: f['properties']['crs'] for f in data['features']}
    if cnes and (cnes not in units or (crs and units[cnes] != crs)):
        raise ValueError('Selecione uma UVIS vinculada à coordenadoria escolhida.')
    return crs, cnes


def locate(lat, lng):
    data, index = reference()
    return [dict(data['features'][int(i)]['properties']) for i in index.query(Point(lng, lat), predicate='intersects')]


def matches(candidates, crs='', cnes=''):
    return any((not crs or p['crs'] == crs) and (not cnes or p['cnes'] == cnes) for p in candidates)
