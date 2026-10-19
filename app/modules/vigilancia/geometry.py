"""Validação de um contorno simples GeoJSON, sem geocodificação externa."""

import json
import math

from .field_store import FieldConflict

MAX_VERTICES = 200
EPSILON = 1e-12


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, c):
    return (abs(_cross(a, b, c)) <= EPSILON
            and min(a[0], b[0]) - EPSILON <= c[0] <= max(a[0], b[0]) + EPSILON
            and min(a[1], b[1]) - EPSILON <= c[1] <= max(a[1], b[1]) + EPSILON)


def _intersects(a, b, c, d):
    u, v, w, z = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    return ((u * v < 0 and w * z < 0)
            or _on_segment(a, b, c) or _on_segment(a, b, d)
            or _on_segment(c, d, a) or _on_segment(c, d, b))


def validate_polygon(raw):
    if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > 32768:
        raise FieldConflict("Confira o desenho da área: limite de 200 pontos.")
    try:
        geometry = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise FieldConflict("O desenho da área está incompleto. Conclua o contorno no mapa.") from exc
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        raise FieldConflict("Selecione uma área fechada no mapa.")
    rings = geometry.get("coordinates")
    if not isinstance(rings, list) or len(rings) != 1 or not isinstance(rings[0], list):
        raise FieldConflict("Use um único contorno, sem recortes internos.")
    ring = rings[0]
    if not 4 <= len(ring) <= MAX_VERTICES + 1:
        raise FieldConflict("A área deve ter entre 3 e 200 pontos e formar um contorno fechado.")
    points = []
    for pair in ring:
        if (not isinstance(pair, list) or len(pair) != 2 or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in pair)
            or not -180 <= pair[0] <= 180 or not -90 <= pair[1] <= 90):
            raise FieldConflict("O desenho contém uma coordenada inválida.")
        points.append([round(float(pair[0]), 6), round(float(pair[1]), 6)])
    if points[0] != points[-1] or len({tuple(point) for point in points[:-1]}) != len(points) - 1:
        raise FieldConflict("Feche a área sem repetir pontos do contorno.")
    if max(p[0] for p in points) - min(p[0] for p in points) > 180:
        raise FieldConflict("O contorno ultrapassa a extensão suportada. Confira o local selecionado.")
    size = len(points) - 1
    for i in range(size):
        for j in range(i + 1, size):
            if j == i + 1 or (i == 0 and j == size - 1):
                continue
            if _intersects(points[i], points[i + 1], points[j], points[j + 1]):
                raise FieldConflict("As linhas da área estão se cruzando. Ajuste os pontos do contorno.")
    area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:]))) / 2
    if area < 1e-10:
        raise FieldConflict("O contorno não forma uma área válida. Afaste ou ajuste os pontos.")
    return {"type": "Polygon", "coordinates": [points]}
