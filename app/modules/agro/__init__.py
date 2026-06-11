"""Modulo de gestao do agro."""

from app.modules.agro.routes import register_routes as register_agro_core_routes
from app.modules.agro.talent_bank_routes import register_routes as register_talent_bank_routes


def register_routes(bp):
    register_agro_core_routes(bp)
    register_talent_bank_routes(bp)


__all__ = ["register_routes"]
