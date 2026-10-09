"""The Neon preparation helpers are tested using disposable SQLite only."""

import unittest
from unittest.mock import patch

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.modules.gestao_ti.catalog import CATALOG, PROFILE_CODES
from scripts.prepare_central_ti_neon import load_migration, seed_profiles, target_url


class NeonPreparationTests(unittest.TestCase):
    def test_target_requires_neon_and_ssl(self):
        for uri in (None, "postgresql://local:password@localhost/test", "postgresql://test:password@ep-example.neon.tech/neondb"):
            with self.subTest(uri=uri), patch("scripts.prepare_central_ti_neon.dotenv_values", return_value={"DATABASE_URL": uri}):
                with self.assertRaises(ValueError):
                    target_url()
        with patch("scripts.prepare_central_ti_neon.dotenv_values", return_value={"DATABASE_URL": "postgresql://test:password@ep-example.neon.tech/neondb?sslmode=require"}):
            url, fingerprint = target_url()
            self.assertEqual(url.host, "ep-example.neon.tech")
            self.assertEqual(len(fingerprint), 16)

    def test_population_is_complete_idempotent_and_preserves_existing_permissions(self):
        engine = sa.create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(sa.text("PRAGMA foreign_keys=ON"))
            connection.execute(sa.text("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, tipo_usuario TEXT)"))
            connection.execute(sa.text("INSERT INTO usuarios VALUES (1, 'dev')"))
            with Operations.context(MigrationContext.configure(connection)):
                load_migration().upgrade()
            connection.execute(sa.text("INSERT INTO central_ti_perfis_configuracoes (perfil_codigo, versao) VALUES ('dev', 2)"))
            connection.execute(sa.text("INSERT INTO central_ti_selecoes VALUES ('dev', 'area:sistema')"))
            added = seed_profiles(connection, CATALOG["profiles"])
            self.assertEqual(set(added), set(PROFILE_CODES) - {"dev"})
            self.assertEqual(set(connection.execute(sa.text("SELECT perfil_codigo FROM central_ti_perfis_configuracoes")).scalars()), set(PROFILE_CODES))
            self.assertEqual(connection.execute(sa.text("SELECT count(*) FROM central_ti_auditoria")).scalar_one(), len(added))
            self.assertEqual(seed_profiles(connection, CATALOG["profiles"]), [])
            self.assertEqual(connection.execute(sa.text("SELECT count(*) FROM central_ti_auditoria")).scalar_one(), len(added))
            self.assertEqual(connection.execute(sa.text("SELECT versao FROM central_ti_perfis_configuracoes WHERE perfil_codigo='dev'")).scalar_one(), 2)
            self.assertEqual(connection.execute(sa.text("SELECT codigo FROM central_ti_selecoes")).scalar_one(), "area:sistema")
            self.assertEqual(connection.execute(sa.text("SELECT tipo_usuario FROM usuarios")).scalar_one(), "dev")
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
