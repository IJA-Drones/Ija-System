"""GeoTIFF inspection/conversion in a subprocess without a time limit."""
import json
import math
import os
import sys

import rasterio
from rasterio.enums import ColorInterp, Resampling
from rasterio.shutil import copy as raster_copy
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

MAX_PIXELS = max(0, int(os.environ.get('ORTHOMOSAIC_MAX_PIXELS', '0')))


def inspect_raster(path):
    with rasterio.Env(GDAL_CACHEMAX=64*1024*1024, GDAL_NUM_THREADS='1'):
        with rasterio.open(path, driver='GTiff') as src:
            if not src.crs:
                raise ValueError('O TIF não possui sistema de coordenadas. Exporte um GeoTIFF georreferenciado.')
            if MAX_PIXELS and src.width * src.height > MAX_PIXELS:
                raise ValueError(f'O ortomosaico excede o limite configurado de {MAX_PIXELS} pixels.')
            if src.count not in (3, 4) or set(src.dtypes) != {'uint8'}:
                raise ValueError('Envie um ortomosaico RGB de 8 bits, com 3 bandas ou 4 bandas incluindo transparência.')
            if src.colorinterp[:3] != (ColorInterp.red, ColorInterp.green, ColorInterp.blue):
                raise ValueError('As bandas precisam identificar vermelho, verde e azul (RGB).')
            if src.count == 4 and src.colorinterp[3] != ColorInterp.alpha:
                raise ValueError('A quarta banda precisa representar transparência, não infravermelho ou elevação.')
            if src.transform.is_identity:
                raise ValueError('O TIF não possui posicionamento geográfico válido.')
            bounds = transform_bounds(src.crs, 'EPSG:4326', *src.bounds, densify_pts=21)
            if (not all(math.isfinite(v) for v in bounds) or not -180 <= bounds[0] < bounds[2] <= 180
                    or not -85 <= bounds[1] < bounds[3] <= 85):
                raise ValueError('A extensão geográfica do arquivo não é compatível com este mapa.')
            # Decode a small window too; a TIFF header alone does not prove readable pixels.
            src.read(window=rasterio.windows.Window(0, 0, min(256, src.width), min(256, src.height)))
            return dict(largura=src.width, altura=src.height, bandas=src.count,
                        crs_origem=str(src.crs), limites=list(bounds))


def convert(source, destination):
    metadata = inspect_raster(source)
    with rasterio.Env(GDAL_CACHEMAX=64*1024*1024, GDAL_NUM_THREADS='1'):
        with rasterio.open(source, driver='GTiff') as src:
            with WarpedVRT(src, crs='EPSG:3857', resampling=Resampling.bilinear,
                           add_alpha=src.count == 3, warp_mem_limit=64) as warped:
                if MAX_PIXELS and warped.width * warped.height > MAX_PIXELS:
                    raise ValueError('A reprojeção excede o limite de pixels permitido.')
                raster_copy(warped, destination, driver='COG', COMPRESS='DEFLATE',
                            BLOCKSIZE=256, OVERVIEWS='AUTO', RESAMPLING='BILINEAR', BIGTIFF='IF_SAFER', NUM_THREADS='1')
        with rasterio.open(destination) as result:
            metadata.update(crs_visualizacao=str(result.crs),
                            resolucao_m=round(abs(result.res[0]), 4))
    return metadata


if __name__ == '__main__':
    try:
        result = inspect_raster(sys.argv[2]) if sys.argv[1] == 'inspect' else convert(sys.argv[2], sys.argv[3])
        print(json.dumps({'ok': True, 'metadata': result}))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc) if isinstance(exc, ValueError) else 'Não foi possível ler este GeoTIFF. Verifique se o arquivo está íntegro.'}))
        sys.exit(1)
