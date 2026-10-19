"""Prévia de vigilância, com registro HTTP carregado somente quando solicitado."""


def register_routes(bp):
    from .routes import register_routes as register_http_routes
    from .sinan_routes import register_routes as register_sinan_routes
    from .field_routes import register_routes as register_field_routes
    from .hub_routes import register_routes as register_hub_routes
    from .planning_routes import register_routes as register_planning_routes
    from .agent_routes import register_routes as register_agent_routes

    register_http_routes(bp)
    register_sinan_routes(bp)
    register_field_routes(bp)
    register_hub_routes(bp)
    register_planning_routes(bp)
    register_agent_routes(bp)


__all__ = ["register_routes"]
