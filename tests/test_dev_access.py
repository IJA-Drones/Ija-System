import unittest

from app.modules.auth.service import get_authenticated_redirect_endpoint
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

    def test_dev_login_redirects_to_dev_dashboard(self):
        self.assertEqual(
            get_authenticated_redirect_endpoint(DummyUser("dev")),
            "main.dev_dashboard",
        )


if __name__ == "__main__":
    unittest.main()
