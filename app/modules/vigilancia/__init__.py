"""Prévia de vigilância, com registro HTTP carregado somente quando solicitado."""


def register_routes(bp):
    from .routes import register_routes as register_http_routes
    from .sinan_routes import register_routes as register_sinan_routes

    register_http_routes(bp)
    register_sinan_routes(bp)


__all__ = ["register_routes"]
