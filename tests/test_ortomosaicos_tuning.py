"""Keep remote TIFF decoding single-threaded even when local compression scales."""
from contextlib import contextmanager
from types import SimpleNamespace

import rasterio
from app.modules.ortomosaicos import processor


def test_remote_conversion_keeps_decoding_sequential(monkeypatch, tmp_path):
    monkeypatch.setattr(processor, 'RASTER_THREADS', '2')
    monkeypatch.setattr(processor, 'RASTER_CACHE_MB', 512)
    monkeypatch.setattr(processor, 'inspect_raster', lambda source: {})
    observed = []

    def copy(source, destination):
        observed.append(rasterio.env.getenv())

    @contextmanager
    def result(*args, **kwargs):
        yield SimpleNamespace(crs='EPSG:3857', res=(1, 1))

    monkeypatch.setattr(processor, 'remote_display_copy', copy)
    monkeypatch.setattr(processor.rasterio, 'open', result)
    processor.convert('/vsicurl/http://localhost/original.tif', tmp_path/'map.tif')
    assert observed[0]['GDAL_NUM_THREADS'] == '1'
    assert observed[0]['GDAL_CACHEMAX'] == 512*1024*1024
