import numpy as np
import pytest
import rasterio
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin
from app.modules.ortomosaicos.processor import inspect_raster, display_source, convert


def source_file(path, alpha=True):
    with rasterio.open(path,'w',driver='GTiff',width=64,height=64,count=8 if alpha else 6,
            dtype='uint16',crs='EPSG:3857',transform=from_origin(100,100,1,1)) as dst:
        data=np.full((dst.count,64,64),60000,dtype='uint16')
        data[0]=2570;data[1]=25700;data[2]=51400
        if alpha:
            data[7]=65535;data[7,:,:16]=0;data[7,:,16:32]=32896
        dst.write(data)
        dst.colorinterp=tuple([ColorInterp.red,ColorInterp.green,ColorInterp.blue]+[ColorInterp.undefined]*(dst.count-3-(1 if alpha else 0))+([ColorInterp.alpha] if alpha else []))


@pytest.mark.parametrize('alpha',[True,False])
def test_multiband_uint16_selects_rgb_scales_and_preserves_alpha(tmp_path,alpha):
    original=tmp_path/'original.tif';result=tmp_path/'mapa.tif'
    source_file(original,alpha)
    before=original.read_bytes()
    metadata=inspect_raster(original)
    assert metadata['bandas_rgb']==[1,2,3]
    assert metadata['banda_alpha']==(8 if alpha else None)
    with rasterio.open(original) as src, display_source(src) as view:
        assert view.count==4 and set(view.dtypes)=={'uint8'}
        data=view.read()
        assert tuple(data[:3,40,40])==(10,100,200)
        if alpha:
            assert data[3,40,0]==0 and data[3,40,20]==128 and data[3,40,40]==255
        else:assert np.all(data[3]==255)
    convert(original,result)
    with rasterio.open(result) as dst:
        assert dst.count==4 and set(dst.dtypes)=={'uint8'}
        assert tuple(dst.read()[:3,40,40])==(10,100,200)
        assert dst.colorinterp[-1]==ColorInterp.alpha
        if alpha:assert dst.read(4)[40,0]==0
    assert original.read_bytes()==before


def test_unidentified_multispectral_bands_still_rejected(tmp_path):
    path=tmp_path/'unknown.tif';source_file(path)
    with rasterio.open(path,'r+') as dst:dst.colorinterp=(ColorInterp.undefined,)*8
    with pytest.raises(ValueError,match='identificar'):inspect_raster(path)
