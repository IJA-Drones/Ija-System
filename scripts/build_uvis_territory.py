"""Build the public UVIS reference from the Prefeitura's downloaded KML.

Usage: python scripts/build_uvis_territory.py SOURCE.kml
No database, geocoding or network access. Shapely is already a project dependency.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
NS = {"k": "http://www.opengis.net/kml/2.2"}
SOURCE = "https://www.google.com/maps/d/viewer?mid=1ZdzK_HpjS1xBTZbtGzHSq6y1OTzjW1XD"
COLORS = ('#2563eb','#dc2626','#059669','#9333ea','#d97706','#0891b2','#db2777',
          '#65a30d','#ea580c','#4f46e5','#0f766e','#be123c','#a16207','#0284c7',
          '#7c3aed','#15803d','#c2410c','#4338ca','#0d9488','#b91c1c','#6d28d9',
          '#0369a1','#a21caf','#4d7c0f','#b45309','#0e7490','#9f1239','#1d4ed8')


def build(source, output):
    raw = source.read_bytes()
    if len(raw) > 20_000_000 or b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ValueError("KML fora do formato esperado")
    root = ET.fromstring(raw)
    districts, groups = [], defaultdict(list)
    for place in root.findall('.//k:Placemark', NS):
        data = {item.get('name'): item.findtext('k:value', default='', namespaces=NS)
                for item in place.findall('.//k:Data', NS)}
        if not data.get('UVIS'):
            continue
        pieces = []
        for polygon in place.findall('.//k:Polygon', NS):
            def ring(path):
                text = polygon.findtext(path + '/k:LinearRing/k:coordinates', namespaces=NS)
                return [tuple(map(float, token.split(',')[:2])) for token in text.split()]
            outer = ring('k:outerBoundaryIs')
            holes = [[tuple(map(float, token.split(',')[:2])) for token in inner.findtext('k:LinearRing/k:coordinates', namespaces=NS).split()]
                     for inner in polygon.findall('k:innerBoundaryIs', NS)]
            pieces.append(Polygon(outer, holes))
        geometry = unary_union(pieces)
        if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in ('Polygon', 'MultiPolygon'):
            raise ValueError(f"Geometria inválida: {data['nm_distrit']}")
        props = dict(distrito=data['nm_distrit'], codigo_distrito=data['CodDA_PMSP'],
                     uvis=data['UVIS'], cnes=data['CNES_UVIS'], crs=data['CRS_MAIUSC'])
        districts.append(dict(type='Feature', properties=props, geometry=mapping(geometry)))
        groups[props['cnes']].append((geometry, props))
    if len(districts) != 96 or len(groups) != 28 or len({f['properties']['codigo_distrito'] for f in districts}) != 96:
        raise ValueError('A fonte deve conter 96 distritos e 28 UVIS distintas')
    metadata = dict(fonte='Prefeitura de São Paulo · COVISA · Territórios UVIS',
        url=SOURCE, atualizado_em='2026-07-27', consultado_em='2026-11-19',
        sha256_kml=sha256(raw).hexdigest(), ibge='3550308', uvis=28, distritos=96,
        descricao='Referência territorial; não define índices LIRAa nem altera atribuições de acesso.')
    uvis = []
    for color_index, (code, items) in enumerate(sorted(groups.items())):
        geom = unary_union([item[0] for item in items])
        if not geom.is_valid:
            raise ValueError(f'União inválida: {code}')
        p = items[0][1]
        anchor = geom.representative_point()
        uvis.append(dict(type='Feature', properties=dict(uvis=p['uvis'], cnes=code, crs=p['crs'],
            cor=COLORS[color_index], rotulo=[anchor.x,anchor.y],
            distritos=sorted(item[1]['distrito'] for item in items)), geometry=mapping(geom)))
    output.mkdir(parents=True, exist_ok=True)
    from shapely.geometry import shape
    ordered = sorted(districts, key=lambda f: f['properties']['codigo_distrito'])
    from shapely.geometry import box
    def display_geometry(feature):
        original = shape(feature['geometry'])
        tolerance = 0.00003
        for _ in range(6):
            reduced = original.simplify(tolerance, preserve_topology=True)
            if reduced.is_valid and reduced.hausdorff_distance(original) <= 0.000030001:
                return mapping(reduced)
            tolerance /= 2
        return mapping(original)
    municipality = unary_union([shape(f['geometry']) for f in districts])
    municipal_display = shape(display_geometry({'geometry':mapping(municipality)}))
    municipality_feature = dict(type='Feature', properties=dict(nome='São Paulo', codigo='3550308'), geometry=mapping(municipal_display))
    mask = dict(type='Feature', properties=dict(nome='Entorno de São Paulo'),
                geometry=mapping(box(-100, -60, -25, 20).difference(municipal_display)))
    region_masks = []
    for crs in sorted({f['properties']['crs'] for f in districts}):
        territory = unary_union([shape(f['geometry']) for f in districts if f['properties']['crs']==crs])
        territory = shape(display_geometry({'geometry':mapping(territory)}))
        region_masks.append((f'mascara-{crs.lower()}', [dict(type='Feature', properties=dict(crs=crs),
            geometry=mapping(box(-100,-60,-25,20).difference(territory)))]))
    uvis_masks = []
    for feature in uvis:
        props = feature['properties']
        territory = shape(display_geometry(feature))
        uvis_masks.append((f"mascara-uvis-{props['cnes']}", [dict(type='Feature',
            properties=dict(cnes=props['cnes'], uvis=props['uvis'], crs=props['crs']),
            geometry=mapping(box(-100, -60, -25, 20).difference(territory)))]))
    for name, features in [('distritos-referencia', ordered), ('distritos', ordered), ('uvis', uvis), ('municipio', [municipality_feature]), ('mascara', [mask]), *region_masks, *uvis_masks]:
        if name in ('distritos', 'uvis'):
            features = [{**feature, 'geometry': display_geometry(feature)} for feature in features]
        content = dict(type='FeatureCollection', metadata={**metadata, 'limite_bbox': list(municipality.bounds), 'simplificacao_graus': 0 if name == 'distritos-referencia' else 0.00003}, features=features)
        (output / (name + '.geojson')).write_text(json.dumps(content, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'app/static/data/uvis-sao-paulo')
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), ensure_ascii=False, indent=2))
