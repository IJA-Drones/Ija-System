import unittest

from app.modules.auth.service import get_authenticated_redirect_endpoint
from app.modules.agro.service import can_access_agro_panel, can_edit_agro_panel
from app.modules.feedback.service import can_open_support_ticket
from app.modules.painel_operacional.service import can_access_operational_panel
from app.modules.usuarios.service import can_manage_admin_user
from app.shared.access import can_manage_user_work_flags, is_admin_global_user, is_covisa_user, is_dev_user


class DummyUser:
    def __init__(self, tipo_usuario, regiao=None, trabalha_agro=False):
        self.tipo_usuario = tipo_usuario
        self.regiao = regiao
        self.trabalha_agro = trabalha_agro


class DevAccessTests(unittest.TestCase):
    def test_dev_is_global_admin(self):
        user = DummyUser("dev")
        self.assertTrue(is_admin_global_user(user))
        self.assertTrue(is_dev_user(user))

    def test_admin_remains_global_admin_but_is_not_dev(self):
        user = DummyUser("admin")
        self.assertTrue(is_admin_global_user(user))
        self.assertFalse(is_dev_user(user))

    def test_director_is_global_admin_but_is_not_dev(self):
        user = DummyUser("diretor")
        self.assertTrue(is_admin_global_user(user))
        self.assertFalse(is_dev_user(user))

    def test_dev_login_redirects_to_dev_dashboard(self):
        self.assertEqual(
            get_authenticated_redirect_endpoint(DummyUser("dev")),
            "main.dev_dashboard",
        )

    def test_director_login_redirects_to_admin_dashboard(self):
        self.assertEqual(
            get_authenticated_redirect_endpoint(DummyUser("diretor")),
            "main.admin_dashboard",
        )

    def test_operational_panel_is_for_director_and_dev(self):
        self.assertTrue(can_access_operational_panel(DummyUser("diretor")))
        self.assertTrue(can_access_operational_panel(DummyUser("dev")))
        self.assertFalse(can_access_operational_panel(DummyUser("admin")))

    def test_director_management_hierarchy(self):
        self.assertFalse(can_manage_admin_user(DummyUser("admin"), DummyUser("diretor")))
        self.assertTrue(can_manage_admin_user(DummyUser("dev"), DummyUser("diretor")))
        self.assertTrue(can_manage_admin_user(DummyUser("diretor"), DummyUser("admin")))

    def test_only_director_and_dev_can_manage_work_flags(self):
        self.assertTrue(can_manage_user_work_flags(DummyUser("diretor")))
        self.assertTrue(can_manage_user_work_flags(DummyUser("dev")))
        self.assertFalse(can_manage_user_work_flags(DummyUser("admin")))

    def test_agro_panel_requires_agro_work_flag_for_admin_users(self):
        self.assertFalse(can_access_agro_panel(DummyUser("admin")))
        self.assertTrue(can_access_agro_panel(DummyUser("admin", trabalha_agro=True)))
        self.assertTrue(can_edit_agro_panel(DummyUser("operario", trabalha_agro=True)))

    def test_agro_panel_requires_agro_work_flag_for_finance_users(self):
        self.assertFalse(can_access_agro_panel(DummyUser("financeiro")))
        self.assertTrue(can_access_agro_panel(DummyUser("financeiro", trabalha_agro=True)))

    def test_covisa_can_report_bugs(self):
        user = DummyUser("visualizar", "COVISA")
        self.assertTrue(is_covisa_user(user))
        self.assertTrue(can_open_support_ticket(user))

    def test_regular_visualizer_cannot_report_bugs(self):
        user = DummyUser("visualizar", "NORTE")
        self.assertFalse(is_covisa_user(user))
        self.assertFalse(can_open_support_ticket(user))


if __name__ == "__main__":
    unittest.main()
