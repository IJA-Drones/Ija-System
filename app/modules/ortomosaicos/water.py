"""Water estimates from explicit measurements; never infer depth from a DEM."""
import math

from rasterio.warp import transform
from shapely.geometry import Polygon


def number(data, key, label, maximum, optional=False, zero=False):
    value = data.get(key)
    if optional and (value is None or value == ''):
        return None
    try:
        if isinstance(value, bool):
            raise ValueError
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f'Informe {label} em números.') from None
    if not math.isfinite(result) or result > maximum or result < 0 or (not zero and result == 0):
        raise ValueError(f'{label.capitalize()} deve ser {"maior ou igual a" if zero else "maior que"} zero e até {maximum:g}.')
    return result


def geometry(data, bounds):
    raw = data.get('geometria')
    if not isinstance(raw, dict) or raw.get('type') not in {'Point', 'Polygon'}:
        raise ValueError('Marque a localização ou desenhe a área no mapa.')
    polygon = raw['type'] == 'Polygon'
    coords = raw.get('coordinates')
    if polygon:
        if not isinstance(coords, list) or len(coords) != 1:
            raise ValueError('Desenhe um único contorno, sem áreas internas.')
        points = coords[0]
        if not isinstance(points, list) or not 4 <= len(points) <= 501 or points[0] != points[-1]:
            raise ValueError('Feche o contorno com pelo menos três vértices e no máximo 500.')
    else:
        points = [coords]
    for point in points:
        if (not isinstance(point, list) or len(point) != 2 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in point) or
                not -180 <= point[0] <= 180 or not -80 <= point[1] <= 84):
            raise ValueError('Coordenadas inválidas para esta medição.')
        if not bounds or not (bounds[0] <= point[0] <= bounds[2] and bounds[1] <= point[1] <= bounds[3]):
            raise ValueError('Marque o recipiente dentro dos limites do levantamento selecionado.')
    area = None
    if polygon:
        shape = Polygon(points)
        if not shape.is_valid or shape.is_empty:
            raise ValueError('O contorno não pode cruzar a si mesmo.')
        if max(shape.bounds[2]-shape.bounds[0], shape.bounds[3]-shape.bounds[1]) > .1:
            raise ValueError('Selecione apenas a área do recipiente.')
        lon, lat = shape.centroid.coords[0]
        zone = min(60, max(1, int((lon+180)//6)+1))
        crs = f'EPSG:{(32600 if lat >= 0 else 32700)+zone}'
        x, y = transform('EPSG:4326', crs, *zip(*points))
        area = Polygon(zip(x, y)).area
        if not math.isfinite(area) or not .01 <= area <= 100000:
            raise ValueError('A área deve estar entre 0,01 e 100.000 m².')
    return {'type': raw['type'], 'coordinates': coords}, area


def calculate(data, bounds):
    if not isinstance(data, dict):
        raise ValueError('Envie os campos da estimativa.')
    method = data.get('metodo')
    if method not in {'mapa', 'retangular', 'cilindrico', 'capacidade'}:
        raise ValueError('Selecione um método de cálculo.')
    kind = data.get('tipo')
    if kind not in {'piscina', 'caixa', 'outro'}:
        raise ValueError('Selecione o tipo de recipiente.')
    origin = data.get('origem')
    if origin not in {'estimada', 'medida', 'fabricante'}:
        raise ValueError('Informe a origem das medidas.')
    name = data.get('nome', '')
    notes = data.get('observacoes', '')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
        raise ValueError('Informe um nome com até 120 caracteres.')
    if not isinstance(notes, str) or len(notes) > 1000:
        raise ValueError('As observações devem ter até 1.000 caracteres.')
    geom, map_area = geometry(data, bounds)
    params = {}
    area = None
    if method == 'capacidade':
        capacity = params['capacidade_l'] = number(data, 'capacidade_l', 'capacidade em litros', 1e9)
        fraction = params['ocupacao_pct'] = number(data, 'ocupacao_pct', 'percentual do volume ocupado', 100, optional=True, zero=True)
        volume = None if fraction is None else capacity*fraction/100
    else:
        if method == 'mapa':
            if map_area is None:
                raise ValueError('Desenhe a área interna do recipiente para calcular pelo mapa.')
            area = map_area
        elif method == 'retangular':
            length = params['comprimento_m'] = number(data, 'comprimento_m', 'comprimento interno em metros', 1000)
            width = params['largura_m'] = number(data, 'largura_m', 'largura interna em metros', 1000)
            area = length*width
        else:
            diameter = params['diametro_m'] = number(data, 'diametro_m', 'diâmetro interno em metros', 1000)
            area = math.pi*(diameter/2)**2
        depth = params['profundidade_m'] = number(data, 'profundidade_m', 'profundidade média até o nível máximo em metros', 100)
        water = params['agua_m'] = number(data, 'agua_m', 'profundidade média atual da água em metros', 100, optional=True, zero=True)
        if water is not None and water > depth:
            raise ValueError('A profundidade atual da água não pode ultrapassar a profundidade máxima.')
        capacity = area*depth*1000
        volume = None if water is None else area*water*1000
    return dict(nome=name.strip(), tipo=kind, metodo=method, origem=origin, observacoes=notes.strip(),
                geometria=geom, parametros=params,
                resultado=dict(area_m2=area, capacidade_l=capacity, agua_l=volume),
                versao_calculo=1)


def serialize(row):
    return dict(id=row.id, ortomosaico_id=row.ortomosaico_id, criado_em=row.criado_em.isoformat()+'Z', **row.dados)
