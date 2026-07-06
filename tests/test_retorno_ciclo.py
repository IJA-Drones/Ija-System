import unittest
from types import SimpleNamespace

from flask import Flask

from app.routes import bp as main_bp
from app.shared.retorno_ciclo import _detail_url_for


class RetornoCicloTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(main_bp)
        self.app.secret_key = "test"
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_equipe_oceano_uses_piloto_form_for_return_cycle_nodes(self):
        user = SimpleNamespace(tipo_usuario="equipe_oceano")
        solicitacao = SimpleNamespace(id=42, status="APROVADO")

        with self.app.test_request_context('/'):
            url = _detail_url_for(user, solicitacao, "equipe_uvis")

        self.assertEqual(url, "/piloto/os/42/formulario")


if __name__ == "__main__":
    unittest.main()
