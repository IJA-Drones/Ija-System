"""Survey layers as GeoJSON or zipped Shapefile, always WGS 84 (EPSG:4326)."""
import io
import zipfile

import shapefile

WGS84_PRJ = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
             'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')
CURVE_FIELDS = [('cota', 'N', 14, 3), ('mestra', 'L', 1, 0)]
WATER_FIELDS = [('id', 'N', 10, 0), ('nome', 'C', 120, 0), ('tipo', 'C', 20, 0), ('metodo', 'C', 20, 0),
                ('origem', 'C', 20, 0), ('area_m2', 'N', 18, 3), ('capac_l', 'N', 18, 1),
                ('agua_l', 'N', 18, 1), ('obs', 'C', 254, 0), ('criado_em', 'C', 32, 0)]
SHAPE_TYPES = {'Point': (shapefile.POINT, 'pontos'), 'LineString': (shapefile.POLYLINE, 'linhas'),
               'Polygon': (shapefile.POLYGON, 'areas')}


def water_features(records):
    features = []
    for record in records:
        data, result = record.dados, record.dados.get('resultado') or {}
        features.append(dict(type='Feature', geometry=data['geometria'], properties=dict(
            id=record.id, nome=data.get('nome'), tipo=data.get('tipo'), metodo=data.get('metodo'),
            origem=data.get('origem'), area_m2=result.get('area_m2'), capac_l=result.get('capacidade_l'),
            agua_l=result.get('agua_l'), obs=(data.get('observacoes') or '')[:254],
            criado_em=record.criado_em.isoformat() + 'Z')))
    return features


def shapefile_zip(features, fields, name):
    """One .shp per geometry type: a Shapefile cannot mix points and polygons."""
    groups = {}
    for feature in features:
        groups.setdefault(feature['geometry']['type'], []).append(feature)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for kind, items in groups.items():
            shape_type, suffix = SHAPE_TYPES[kind]
            base = name if len(groups) == 1 else f'{name}-{suffix}'
            shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
            with shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shape_type, encoding='utf-8') as writer:
                for field in fields:
                    writer.field(*field)
                for feature in items:
                    writer.shape(feature['geometry'])
                    writer.record(*[feature['properties'].get(field[0]) for field in fields])
            for extension, data in (('shp', shp.getvalue()), ('shx', shx.getvalue()), ('dbf', dbf.getvalue()),
                                    ('prj', WGS84_PRJ), ('cpg', 'UTF-8')):
                archive.writestr(f'{base}.{extension}', data)
    return output.getvalue()
