import math


AREAS_GEOFENCING = [
    {"nome": "Aeroporto de Congonhas (CGH)", "lat": -23.6273, "lng": -46.6565, "raio": 5400},
    {"nome": "Aeroporto Campo de Marte (RTE)", "lat": -23.5092, "lng": -46.6377, "raio": 5400},
    {"nome": "Aeroporto de Guarulhos (GRU)", "lat": -23.4356, "lng": -46.4731, "raio": 9000},
    {"nome": "Aeroporto de Viracopos (VCP)", "lat": -23.0069, "lng": -47.1344, "raio": 9000},
    {"nome": "Zona de Helipontos (Av. Paulista)", "lat": -23.5615, "lng": -46.6559, "raio": 2000},
    {"nome": "Base Aerea de Santos", "lat": -23.9275, "lng": -46.2975, "raio": 5400},
]


def calcular_distancia(lat1, lon1, lat2, lon2):
    raio_terra_metros = 6371000

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return raio_terra_metros * c


def detectar_area_restrita(latitude, longitude):
    if latitude is None or longitude is None:
        return False

    for area in AREAS_GEOFENCING:
        distancia = calcular_distancia(latitude, longitude, area["lat"], area["lng"])
        if distancia < area["raio"]:
            return True

    return False
