def register_routes(bp):
    from .routes import register_routes as register
    register(bp)
