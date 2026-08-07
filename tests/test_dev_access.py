import unittest

from app.modules.auth.service import get_authenticated_redirect_endpoint
from app.modules.painel_operacional.service import can_access_operational_panel
from app.modules.usuarios.service import can_manage_admin_user
from app.shared.access import is_admin_global_user, is_dev_user


class DummyUser:
    def __init__(self, tipo_usuario):
        self.tipo_usuario = tipo_usuario


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


if __name__ == "__main__":
    unittest.main()
