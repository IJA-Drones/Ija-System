"""DEM -> bounded contour layer and matching JPEG, in an isolated subprocess.

Rasterio/GDAL handles masks/reprojection. ContourPy interpolates isolines on an
explicit metric grid. No bare-earth classification or vertical datum conversion.
"""
import json
import math
import sys
from pathlib import Path

import contourpy
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import calculate_default_transform, transform, transform_bounds

MAX_CELLS = 4_000_000
MAX_LEVELS = 500
MAX_FEATURES = 30_000
MAX_VERTICES = 1_000_000


def parameters(interval, resolution):
    try:
        interval, resolution = float(interval), float(resolution)
    except (TypeError, ValueError):
        raise ValueError('Informe intervalo e resolução numéricos em metros.') from None
    if not math.isfinite(interval) or not .25 <= interval <= 1000:
        raise ValueError('O intervalo deve estar entre 0,25 e 1.000 metros.')
    if not math.isfinite(resolution) or not .25 <= resolution <= 100:
        raise ValueError('A resolução de processamento deve estar entre 0,25 e 100 metros.')
    return interval, resolution


def inspect_dem(path):
    with rasterio.open(path, driver='GTiff') as src:
        if src.count != 1 or np.dtype(src.dtypes[0]).kind not in 'fiu':
            raise ValueError('Envie um DEM com uma única banda numérica de elevação, não uma imagem RGB.')
        if not src.crs or src.transform.is_identity:
            raise ValueError('O DEM precisa de sistema de coordenadas e georreferenciamento válidos.')
        unit = (src.units[0] or '').strip().lower()
        if unit and unit not in {'m', 'metre', 'meter', 'metres', 'meters', 'metro', 'metros'}:
            raise ValueError('Converta as elevações do DEM para metros antes de enviar.')
        bounds = transform_bounds(src.crs, 'EPSG:4326', *src.bounds, densify_pts=21)
        if (not all(math.isfinite(v) for v in bounds) or not -180 <= bounds[0] < bounds[2] <= 180
                or not -80 <= bounds[1] < bounds[3] <= 84):
            raise ValueError('A extensão geográfica do DEM não é válida para este visualizador.')
        src.read(1, window=rasterio.windows.Window(0, 0, min(src.width, 128), min(src.height, 128)))
        return dict(largura=src.width, altura=src.height, bandas=1, crs_origem=str(src.crs),
                    limites=list(bounds), unidade_vertical='m', unidade_informada=bool(unit))


def metric_crs(src, bounds):
    if src.crs.is_projected and abs(src.crs.linear_units_factor[1] - 1) < 1e-9:
        return src.crs
    lon, lat = (bounds[0]+bounds[2])/2, (bounds[1]+bounds[3])/2
    zone = min(60, max(1, int((lon+180)//6)+1))
    return rasterio.crs.CRS.from_epsg((32600 if lat >= 0 else 32700)+zone)


def generate(source, destination, interval=1, resolution=1):
    interval, resolution = parameters(interval, resolution)
    metadata = inspect_dem(source)
    with rasterio.Env(GDAL_CACHEMAX=64*1024*1024, GDAL_NUM_THREADS='1'):
        with rasterio.open(source) as src:
            crs = metric_crs(src, metadata['limites'])
            native, _, _ = calculate_default_transform(src.crs, crs, src.width, src.height, *src.bounds)
            cell = max(resolution, abs(native.a), abs(native.e))
            left, bottom, right, top = transform_bounds(src.crs, crs, *src.bounds, densify_pts=21)
            width, height = math.ceil((right-left)/cell), math.ceil((top-bottom)/cell)
            if width < 2 or height < 2:
                raise ValueError('O DEM é pequeno demais para a resolução escolhida. Use uma resolução menor.')
            if width*height > MAX_CELLS:
                suggested = math.ceil(cell*math.sqrt(width*height/MAX_CELLS)*100)/100
                raise ValueError(f'A grade excede 4 milhões de células. Use resolução de pelo menos {suggested:g} m.')
            grid = from_origin(left, top, cell, cell)
            with WarpedVRT(src, crs=crs, transform=grid, width=width, height=height,
                           dtype='float32', nodata=float('nan'), resampling=Resampling.bilinear,
                           warp_mem_limit=64) as vrt:
                z = vrt.read(1, masked=True).astype('float64')
            z = np.ma.masked_invalid(z * src.scales[0] + src.offsets[0])
    if z.count() < 4:
        raise ValueError('O DEM não possui elevações válidas suficientes.')
    low, high = float(z.min()), float(z.max())
    first, last = math.ceil(low/interval), math.floor(high/interval)
    if last-first+1 > MAX_LEVELS:
        raise ValueError('O intervalo produz mais de 500 cotas. Escolha um intervalo maior.')
    if first > last or low == high:
        raise ValueError('Não há curvas nesse intervalo. Use um intervalo menor ou outro DEM.')
    x = left + (np.arange(width)+.5)*cell
    y = top - (np.arange(height)+.5)*cell
    generator = contourpy.contour_generator(x=x, y=y, z=z, name='serial',
                                           corner_mask=False, line_type='Separate')
    features, segments, levels, masters = [], [], [], []
    vertices = 0
    for index in range(first, last+1):
        elevation = round(index*interval, 8)
        master = index % 5 == 0
        for line in generator.lines(elevation):
            if len(line) < 2:
                continue
            vertices += len(line)
            if vertices > MAX_VERTICES or len(features) >= MAX_FEATURES:
                raise ValueError('As curvas ficaram densas demais. Aumente o intervalo ou a resolução de processamento.')
            lon, lat = transform(crs, 'EPSG:4326', line[:, 0].tolist(), line[:, 1].tolist())
            coordinates = [[round(a, 8), round(b, 8)] for a, b in zip(lon, lat)]
            features.append(dict(type='Feature', properties=dict(cota=elevation, mestra=master),
                                 geometry=dict(type='LineString', coordinates=coordinates)))
            segments.append(line); levels.append(elevation); masters.append(master)
    if not features:
        raise ValueError('Nenhuma curva foi encontrada. Tente um intervalo menor.')
    out = Path(destination); out.mkdir(parents=True, exist_ok=True)
    metadata.update(intervalo_m=interval, resolucao_solicitada_m=resolution, resolucao_m=round(cell, 6),
                    crs_processamento=str(crs), elevacao_min_m=low, elevacao_max_m=high,
                    curvas=len(features), vertices=vertices, grade=[width, height],
                    metodo='Interpolação linear de isolinhas; reamostragem bilinear do DEM; sem suavização.',
                    aviso='Curvas da superfície fornecida. MDS pode incluir árvores e construções; não equivale a MDT.')
    (out/'curvas.geojson').write_text(json.dumps(dict(type='FeatureCollection', features=features),
                                               separators=(',', ':'), allow_nan=False), encoding='utf-8')
    draw_jpeg(out/'curvas.jpg', segments, levels, masters, metadata, (left, bottom, right, top))
    (out/'metadados.json').write_text(json.dumps(metadata, ensure_ascii=False), encoding='utf-8')
    return metadata


def draw_jpeg(path, segments, levels, masters, meta, bounds):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.ticker import ScalarFormatter
    fig, ax = plt.subplots(figsize=(14, 10), dpi=220)
    fig.patch.set_facecolor('#fffdf8'); ax.set_facecolor('#fffdf8')
    ax.add_collection(LineCollection(segments, colors=['#75502b' if m else '#b79b70' for m in masters],
                                    linewidths=[.8 if m else .35 for m in masters]))
    # Label selected major lines with collision filtering in map coordinates.
    left, bottom, right, top = bounds
    occupied = set()
    for line, level, master in zip(segments, levels, masters):
        if not master or np.linalg.norm(np.diff(line, axis=0), axis=1).sum() < (right-left)*.06:
            continue
        midpoint = line[len(line)//2]
        key = (int((midpoint[0]-left)/(right-left)*12), int((midpoint[1]-bottom)/(top-bottom)*10))
        if key in occupied: continue
        occupied.add(key)
        ax.text(*midpoint, f'{level:g}', fontsize=7, ha='center', va='center', color='#674322',
                bbox=dict(facecolor='#fffdf8', edgecolor='none', pad=.5))
    ax.set_xlim(left, right); ax.set_ylim(bottom, top); ax.set_aspect('equal')
    ax.grid(alpha=.18, color='#aa916c'); ax.set_xlabel('Leste (m)'); ax.set_ylabel('Norte (m)')
    formatter=ScalarFormatter(useOffset=False); formatter.set_scientific(False)
    ax.xaxis.set_major_formatter(formatter); ax.yaxis.set_major_formatter(formatter)
    ax.tick_params(labelsize=8)
    ax.set_title('CURVAS DE NÍVEL', loc='left', fontsize=21, color='#173f51', pad=24, weight='bold')
    ax.text(1, 1.025, f'Intervalo {meta["intervalo_m"]:g} m · Mestras {meta["intervalo_m"]*5:g} m',
            transform=ax.transAxes, ha='right', fontsize=10, color='#674322')
    # Scale expressed in the metric processing CRS; not Web Mercator distances.
    length = 10**math.floor(math.log10((right-left)/5))
    bx, by = left+(right-left)*.06, bottom+(top-bottom)*.06
    ax.plot([bx, bx+length], [by, by], color='#173f51', linewidth=3)
    ax.text(bx+length/2, by+(top-bottom)*.015, f'{length:g} m', ha='center', fontsize=9,
            bbox=dict(facecolor='#fffdf8', edgecolor='none', pad=2))
    ax.annotate('N', xy=(.95,.95), xytext=(.95,.84), xycoords='axes fraction', ha='center',
                arrowprops=dict(arrowstyle='->', color='#173f51'), color='#173f51', weight='bold')
    fig.text(.07,.055, f'{meta["crs_processamento"]} · Grade {meta["resolucao_m"]:g} m · Cotas em metros no referencial vertical do arquivo', fontsize=9)
    fig.text(.07,.034, 'Curvas da superfície fornecida. MDS pode incluir árvores e construções. Resolução não é precisão altimétrica.', fontsize=8, color='#665b4d')
    fig.text(.93,.02, 'IJA DRONES', ha='right', weight='bold', color='#173f51')
    fig.subplots_adjust(left=.09, right=.95, top=.88, bottom=.14)
    fig.savefig(path, format='jpeg', pil_kwargs={'quality':92}); plt.close(fig)


if __name__ == '__main__':
    try:
        result = inspect_dem(sys.argv[2]) if sys.argv[1] == 'inspect-dem' else generate(*sys.argv[2:])
        print(json.dumps({'ok':True, 'metadata':result}))
    except Exception as exc:
        print(json.dumps({'ok':False, 'error':str(exc) if isinstance(exc,ValueError) else 'Não foi possível processar o DEM. Confira se o TIFF está íntegro.'}))
        sys.exit(1)
