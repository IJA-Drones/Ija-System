"""Persist polygon masks independently of raster processing; never rewrite the TIFF."""
import math

from flask import abort, current_app, jsonify, request
from flask_login import current_user
from rasterio.warp import transform
from shapely.geometry import Polygon
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import OrtomosaicoArea
from .water import serialize


def calculate(data, bounds):
    if not isinstance(data, dict):
        raise ValueError('Informe a área desenhada.')
    name = data.get('nome', '')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
        raise ValueError('Informe um nome de até 120 caracteres.')
    geometry = data.get('geometria')
    if not isinstance(geometry, dict) or geometry.get('type') != 'Polygon':
        raise ValueError('Desenhe um polígono no mapa.')
    rings = geometry.get('coordinates')
    if not isinstance(rings, list) or len(rings) != 1 or not isinstance(rings[0], list):
        raise ValueError('Use um contorno único, sem buracos.')
    ring = rings[0]
    if not 4 <= len(ring) <= 501 or ring[0] != ring[-1]:
        raise ValueError('Feche o contorno com 3 a 500 vértices.')
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        raise ValueError('O levantamento não tem limites disponíveis.')
    for point in ring:
        if (not isinstance(point, (list, tuple)) or len(point) != 2 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in point)):
            raise ValueError('Coordenadas inválidas.')
        lon, lat = point
        if not (-180 <= lon <= 180 and -80 <= lat <= 84 and
                bounds[0] <= lon <= bounds[2] and bounds[1] <= lat <= bounds[3]):
            raise ValueError('Desenhe dentro dos limites do ortomosaico.')
    polygon = Polygon(ring)
    if not polygon.is_valid or polygon.is_empty or polygon.area == 0:
        raise ValueError('O contorno não pode cruzar a si mesmo ou ter área nula.')
    if polygon.bounds[2]-polygon.bounds[0] > 3 or polygon.bounds[3]-polygon.bounds[1] > 3:
        raise ValueError('Divida esta área em recortes menores (até 3° de extensão).')
    center = polygon.centroid
    zone = min(60, max(1, int((center.x+180)//6)+1))
    crs = f'EPSG:{(32600 if center.y >= 0 else 32700)+zone}'
    x, y = transform('EPSG:4326', crs, [p[0] for p in ring], [p[1] for p in ring])
    metric = Polygon(zip(x, y))
    if not metric.is_valid or not math.isfinite(metric.area) or metric.area < .01:
        raise ValueError('Desenhe uma área de pelo menos 0,01 m².')
    return dict(nome=name.strip(), geometria=dict(type='Polygon', coordinates=[ring]),
                resultado=dict(area_m2=metric.area, area_ha=metric.area/10000,
                               perimetro_m=metric.length, crs=crs))


def register_routes(bp, restricted, get_record):
    def survey(oid):
        row = get_record(oid)
        if row.status != 'pronto' or row.tipo != 'rgb':
            abort(409, description='Selecione um ortomosaico RGB disponível.')
        return row

    def data(row):
        if request.content_length and request.content_length > 65536:
            raise ValueError('O desenho excede o tamanho permitido.')
        return calculate(request.get_json(silent=True), (row.metadados or {}).get('limites'))

    @bp.post('/api/ortomosaicos/<int:oid>/areas/calcular', endpoint='ortomosaico_area_calcular')
    @restricted
    def preview(oid):
        row = survey(oid)
        try:
            return jsonify(item=data(row))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    @bp.route('/api/ortomosaicos/<int:oid>/areas', methods=['GET', 'POST'], endpoint='ortomosaico_areas')
    @restricted
    def collection(oid):
        row = survey(oid)
        if request.method == 'GET':
            rows = OrtomosaicoArea.query.filter_by(ortomosaico_id=oid).order_by(OrtomosaicoArea.id).all()
            response = jsonify(items=[serialize(r) for r in rows])
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        try:
            values = data(row)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        area = OrtomosaicoArea(ortomosaico_id=oid, usuario_id=current_user.id, dados=values)
        db.session.add(area)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception('Falha ao salvar área do ortomosaico %s', oid)
            return jsonify(error='Não foi possível salvar a área. Verifique se a migração do banco foi aplicada e tente novamente. Seu desenho foi mantido.'), 503
        return jsonify(item=serialize(area)), 201

    @bp.route('/api/ortomosaicos/<int:oid>/areas/<int:aid>', methods=['PUT', 'DELETE'], endpoint='ortomosaico_area_item')
    @restricted
    def area_item(oid, aid):
        row = survey(oid)
        area = OrtomosaicoArea.query.filter_by(id=aid, ortomosaico_id=oid).first_or_404()
        if request.method == 'PUT':
            try:
                area.dados = data(row)
            except ValueError as exc:
                return jsonify(error=str(exc)), 400
        else:
            db.session.delete(area)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception('Falha ao alterar área %s do ortomosaico %s', aid, oid)
            return jsonify(error='Não foi possível alterar a área. Tente novamente.'), 503
        return jsonify(item=serialize(area)) if request.method == 'PUT' else ('', 204)
