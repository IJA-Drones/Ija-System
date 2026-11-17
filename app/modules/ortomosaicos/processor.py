"""GeoTIFF inspection/conversion in a subprocess without a time limit."""
import json
import math
import os
import shutil
import sys
import time
import traceback
from contextlib import contextmanager, ExitStack
from xml.etree import ElementTree as ET

import rasterio
from rasterio.enums import ColorInterp, Resampling
from rasterio.io import MemoryFile
from rasterio.shutil import copy as raster_copy
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

# Bounded tuning validated against the full 17 GB raster over HTTP Range.
RASTER_THREADS = str(max(1, min(2, int(os.environ.get('ORTHOMOSAIC_RASTER_THREADS', '2')))))
RASTER_CACHE_MB = max(128, min(512, int(os.environ.get('ORTHOMOSAIC_RASTER_CACHE_MB', '512'))))

MAX_PIXELS = max(0, int(os.environ.get('ORTHOMOSAIC_MAX_PIXELS', '0')))


def inspect_raster(path):
    with rasterio.Env(GDAL_CACHEMAX=RASTER_CACHE_MB*1024*1024, GDAL_NUM_THREADS='1'):
        with rasterio.open(path, driver='GTiff') as src:
            if not src.crs:
                raise ValueError('O TIF não possui sistema de coordenadas. Exporte um GeoTIFF georreferenciado.')
            if MAX_PIXELS and src.width * src.height > MAX_PIXELS:
                raise ValueError(f'O ortomosaico excede o limite configurado de {MAX_PIXELS} pixels.')
            rgb, alpha = color_bands(src)
            if src.transform.is_identity:
                raise ValueError('O TIF não possui posicionamento geográfico válido.')
            bounds = transform_bounds(src.crs, 'EPSG:4326', *src.bounds, densify_pts=21)
            if (not all(math.isfinite(v) for v in bounds) or not -180 <= bounds[0] < bounds[2] <= 180
                    or not -85 <= bounds[1] < bounds[3] <= 85):
                raise ValueError('A extensão geográfica do arquivo não é compatível com este mapa.')
            # Decode a small window too; a TIFF header alone does not prove readable pixels.
            src.read(window=rasterio.windows.Window(0, 0, min(256, src.width), min(256, src.height)))
            return dict(largura=src.width, altura=src.height, bandas=src.count,
                        crs_origem=str(src.crs), limites=list(bounds), bandas_rgb=rgb, banda_alpha=alpha,
                        tipos_origem=list(src.dtypes), escala_rgb='uint16/257' if src.dtypes[rgb[0]-1] == 'uint16' else 'uint8')


def color_bands(src):
    colors = list(src.colorinterp)
    if any(colors.count(color) != 1 for color in (ColorInterp.red, ColorInterp.green, ColorInterp.blue)):
        raise ValueError('As bandas precisam identificar vermelho, verde e azul (RGB).')
    rgb = [colors.index(color) + 1 for color in (ColorInterp.red, ColorInterp.green, ColorInterp.blue)]
    if colors.count(ColorInterp.alpha) > 1:
        raise ValueError('O arquivo deve identificar no máximo uma banda de transparência.')
    alpha = colors.index(ColorInterp.alpha) + 1 if ColorInterp.alpha in colors else None
    if any(src.dtypes[i-1] not in ('uint8', 'uint16') for i in rgb + ([alpha] if alpha else [])):
        raise ValueError('Envie bandas RGB de 8 ou 16 bits sem sinal.')
    return rgb, alpha


@contextmanager
def display_source(src):
    """A lazy Byte RGBA view; extra bands and the original remain untouched.

    GDAL reads/scales blocks on demand. No full-size intermediate TIFF or array.
    16-bit unsigned channels use their full 0..65535 range, including alpha.
    """
    rgb, alpha = color_bands(src)
    if src.count in (3, 4) and rgb == [1, 2, 3] and alpha == (4 if src.count == 4 else None) and set(src.dtypes) == {'uint8'}:
        yield src
        return
    vrt = ET.Element('VRTDataset', rasterXSize=str(src.width), rasterYSize=str(src.height))
    ET.SubElement(vrt, 'SRS').text = src.crs.to_wkt()
    ET.SubElement(vrt, 'GeoTransform').text = ','.join(map(str, src.transform.to_gdal()))
    for index, (source_band, color) in enumerate(zip(rgb + [alpha], ('Red', 'Green', 'Blue', 'Alpha')), 1):
        band = ET.SubElement(vrt, 'VRTRasterBand', dataType='Byte', band=str(index))
        ET.SubElement(band, 'ColorInterp').text = color
        source = ET.SubElement(band, 'ComplexSource')
        ET.SubElement(source, 'SourceFilename', relativeToVRT='0').text = os.path.abspath(src.name)
        ET.SubElement(source, 'SourceBand').text = str(source_band) if source_band else f'mask,{rgb[0]}'
        ET.SubElement(source, 'ScaleOffset').text = '0'
        ET.SubElement(source, 'ScaleRatio').text = str(1/257 if source_band and src.dtypes[source_band-1] == 'uint16' else 1)
        for rect in ('SrcRect', 'DstRect'):
            ET.SubElement(source, rect, xOff='0', yOff='0', xSize=str(src.width), ySize=str(src.height))
    with MemoryFile(ET.tostring(vrt)) as memory, memory.open() as view:
        yield view


@contextmanager
def warped_source(source):
    with rasterio.open(source, driver='GTiff') as original, display_source(original) as src:
        with WarpedVRT(src, crs='EPSG:3857', resampling=Resampling.bilinear,
                       add_alpha=src.count == 3, warp_mem_limit=64) as warped:
            yield warped


def check_conversion_space(warped, destination):
    if MAX_PIXELS and warped.width * warped.height > MAX_PIXELS:
        raise ValueError('A reprojeção excede o limite de pixels permitido.')
    required = warped.width * warped.height * warped.count * 3 + 256 * 1024 * 1024
    job_limit = int(os.environ.get('ORTHOMOSAIC_JOB_MAX_BYTES', '0'))
    if job_limit and required > job_limit:
        raise ValueError('A conversão exige mais espaço que o limite seguro do processamento. O original permanece no Skybox; configure um disco de trabalho maior.')
    if shutil.disk_usage(os.path.dirname(os.path.abspath(destination))).free < required:
        raise ValueError('Espaço insuficiente na pasta de trabalho para gerar o ortomosaico e seus níveis de zoom. Libere espaço no servidor e tente novamente.')


def remote_display_copy(source, destination):
    """Stage only display pixels, retrying an interrupted window, not the whole map.

    Closing the source on failure evicts its HTTP cache (NON_CACHED), so a short
    response cannot poison retries. If-Match still pins every read to the verified
    original. Completed output windows survive transient source-read failures.
    """
    stage = str(destination) + '.display.tif'
    try:
        with ExitStack() as inputs:
            for attempt in range(4):
                try:
                    warped = inputs.enter_context(warped_source(source))
                    break
                except rasterio.errors.RasterioError:
                    inputs.close()
                    if attempt == 3:
                        raise
                    time.sleep(2 ** attempt)
            check_conversion_space(warped, destination)
            profile = dict(driver='GTiff', width=warped.width, height=warped.height,
                           count=warped.count, dtype='uint8', crs=warped.crs,
                           transform=warped.transform, tiled=True, blockxsize=512,
                           blockysize=512, compress='DEFLATE', BIGTIFF='IF_SAFER')
            with rasterio.open(stage, 'w', **profile) as output:
                output.colorinterp = warped.colorinterp
                total = math.ceil(warped.width/512) * math.ceil(warped.height/512)
                last_progress = 0
                for completed, (_, window) in enumerate(output.block_windows(1), 1):
                    for attempt in range(4):
                        try:
                            if warped is None:
                                warped = inputs.enter_context(warped_source(source))
                            pixels = warped.read(window=window)
                            break
                        except rasterio.errors.RasterioError:
                            inputs.close()
                            warped = None
                            if attempt == 3:
                                raise
                            print(f'ortho_stage retry x={int(window.col_off)} y={int(window.row_off)} attempt={attempt+1}', file=sys.stderr, flush=True)
                            time.sleep(2 ** attempt)
                    output.write(pixels, window=window)
                    if time.monotonic() - last_progress >= 30 or completed == total:
                        print(f'ortho_stage pixels windows={completed} total={total}', file=sys.stderr, flush=True)
                        last_progress = time.monotonic()
        print('ortho_stage overviews', file=sys.stderr, flush=True)
        raster_copy(stage, destination, driver='COG', COMPRESS='DEFLATE', BLOCKSIZE=256,
                    OVERVIEWS='AUTO', RESAMPLING='BILINEAR', BIGTIFF='IF_SAFER', NUM_THREADS=RASTER_THREADS)
    finally:
        if os.path.exists(stage):
            os.unlink(stage)


def convert(source, destination):
    remote = str(source).startswith('/vsicurl/')
    settings = {'CPL_VSIL_CURL_NON_CACHED': str(source)} if remote else {}
    # Remote decoding must stay sequential: threaded GTiff reads fragment HTTP
    # ranges. Apply parallel compression only to the completed local stage.
    with rasterio.Env(GDAL_CACHEMAX=RASTER_CACHE_MB*1024*1024,
                      GDAL_NUM_THREADS='1' if remote else RASTER_THREADS, **settings):
        for attempt in range(4 if remote else 1):
            try:
                metadata = inspect_raster(source)
                break
            except rasterio.errors.RasterioError:
                if not remote or attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        if remote:
            remote_display_copy(source, destination)
        else:
            with warped_source(source) as warped:
                check_conversion_space(warped, destination)
                raster_copy(warped, destination, driver='COG', COMPRESS='DEFLATE',
                            BLOCKSIZE=256, OVERVIEWS='AUTO', RESAMPLING='BILINEAR', BIGTIFF='IF_SAFER', NUM_THREADS=RASTER_THREADS)
        with rasterio.open(destination) as result:
            metadata.update(crs_visualizacao=str(result.crs), resolucao_m=round(abs(result.res[0]), 4))
    return metadata


if __name__ == '__main__':
    try:
        result = inspect_raster(sys.argv[2]) if sys.argv[1] == 'inspect' else convert(sys.argv[2], sys.argv[3])
        print(json.dumps({'ok': True, 'metadata': result}))
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        message = ('A leitura remota do GeoTIFF falhou durante a conversão. O original permanece salvo no Skybox.'
                   if sys.argv[2].startswith('/vsicurl/') else
                   'Não foi possível ler este GeoTIFF. Verifique se o arquivo está íntegro.')
        print(json.dumps({'ok': False, 'error': str(exc) if isinstance(exc, ValueError) else message}))
        sys.exit(1)
