from flask import abort, current_app
from flask_login import login_required


def _dev_only():
    if not current_app.debug:
        abort(404)


def register_core_routes(bp):
    @bp.route("/sw.js")
    def serve_sw():
        return bp.send_static_file("sw.js")

    @bp.route("/forcar_erro")
    def forcar_erro():
        1 / 0
        return "nunca vai chegar aqui"

    @bp.route("/__test/erro/<int:code>", methods=["GET"], endpoint="test_error_code")
    @login_required
    def test_error_code(code):
        _dev_only()

        if code == 500:
            raise RuntimeError("Erro 500 forcado para teste")
        abort(code)
