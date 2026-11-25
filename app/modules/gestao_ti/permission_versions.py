"""Preserve the former vehicle bundle until a selection is edited explicitly.

The marker is internal selection metadata, never a permission offered to clients.
Legacy clients keep bundle semantics; current editors submit the schema version.
No business data, schema migration, or automatic permission rewrite is needed.
"""
PERMISSION_SCHEMA_VERSION = 'vehicles-v1'
VEHICLE_MARKER = 'schema:vehicles-v1'
VEHICLE_BASE = 'prefeitura.veiculos.consultar'
VEHICLE_DETAILS = frozenset({
    'prefeitura.rastreamento_veiculos.consultar',
    'prefeitura.limpezas_veiculos.consultar',
    'prefeitura.alertas_limpeza_veiculos.consultar',
})


def effective_codes(codes):
    result = set(codes)
    if VEHICLE_BASE in result and VEHICLE_MARKER not in result:
        result.update(VEHICLE_DETAILS)
    result.discard(VEHICLE_MARKER)
    return result


def submitted_permissions(permissions, schema_version=None):
    if schema_version not in (None, PERMISSION_SCHEMA_VERSION):
        raise ValueError('O catálogo de permissões mudou. Recarregue a central antes de salvar.')
    result = set(permissions)
    if schema_version != PERMISSION_SCHEMA_VERSION and VEHICLE_BASE in result:
        result.update(VEHICLE_DETAILS)
    return sorted(result)


def stored_codes(areas, permissions):
    result = set(permissions) | {f'area:{area}' for area in areas}
    if VEHICLE_BASE in result:
        result.add(VEHICLE_MARKER)
    return sorted(result)
