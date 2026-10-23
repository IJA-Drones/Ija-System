"""Integrações com sistemas externos (Ministério da Saúde)."""


def register_routes(bp):
    from .esus_routes import register_routes as register_esus_routes
    register_esus_routes(bp)


__all__ = ["register_routes"]
