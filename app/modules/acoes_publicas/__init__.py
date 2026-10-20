"""Ações municipais com rascunho privado e publicação explícita."""


def register_routes(bp):
    from .routes import register_routes as register_http
    register_http(bp)
