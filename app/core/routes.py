from flask import abort, current_app
from flask_login import current_user, login_required

from app.shared.access import is_dev_user


def _dev_only():
    if not current_app.debug or not is_dev_user(current_user):
        abort(404)


def register_core_routes(bp):
    @bp.get("/sw.js", endpoint="service_worker")
    def service_worker():
        # Servido na raiz para que o escopo do service worker cubra todo o site (push em qualquer página).
        from flask import current_app, send_from_directory
        response = send_from_directory(current_app.static_folder, "sw.js", mimetype="application/javascript")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @bp.route("/sw.js")
    def serve_sw():
        return bp.send_static_file("sw.js")

    @bp.route("/forcar_erro")
    @login_required
    def forcar_erro():
        _dev_only()
        1 / 0
        return "nunca vai chegar aqui"

    @bp.route("/__test/erro/<int:code>", methods=["GET"], endpoint="test_error_code")
    @login_required
    def test_error_code(code):
        _dev_only()

        if code == 500:
            raise RuntimeError("Erro 500 forcado para teste")
        abort(code)
