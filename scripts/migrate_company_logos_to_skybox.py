"""Run after e2b431cc9f70 and before f2c531cc9f71, with the server stopped.

Each original blob remains in the database until upload and byte verification
succeed. Each company commits separately so interrupted runs can be resumed.
"""
from hashlib import sha256
from flask import current_app
from sqlalchemy import inspect, text
from app.extensions import db
from app.modules.financeiro.logos import upload_company_logo
from app.shared.skybox import stream_skybox_file


def migrate_company_logos():
    columns = {column["name"] for column in inspect(db.engine).get_columns("financeiro_empresa_perfis")}
    if "logo" not in columns:
        return 0
    if "logo_path" not in columns:
        raise RuntimeError("Aplique primeiro a migração e2b431cc9f70.")
    slugs = db.session.execute(text("SELECT empresa_slug FROM financeiro_empresa_perfis WHERE logo IS NOT NULL")).scalars().all()
    db.session.rollback()
    migrated = 0
    for slug in slugs:
        try:
            suffix = " FOR UPDATE" if db.engine.dialect.name == "postgresql" else ""
            row = db.session.execute(text("SELECT logo, logo_path FROM financeiro_empresa_perfis WHERE empresa_slug = :slug" + suffix), {"slug": slug}).mappings().one()
            if row["logo"] is None:
                db.session.rollback()
                continue
            if row["logo_path"]:
                raise RuntimeError("A empresa já possui caminho e imagem legada; revise antes de continuar.")
            original = bytes(row["logo"])
            path = upload_company_logo(slug, original)
            with current_app.test_request_context():
                response = stream_skybox_file(path)
                try:
                    digest = sha256()
                    for chunk in response.response:
                        digest.update(chunk)
                    if response.status_code != 200 or digest.digest() != sha256(original).digest():
                        raise RuntimeError("A verificação da logo no Skybox falhou; original preservado.")
                finally:
                    response.close()
            db.session.execute(text("UPDATE financeiro_empresa_perfis SET logo_path = :path, logo = NULL, tem_logo = TRUE WHERE empresa_slug = :slug"), {"path": path, "slug": slug})
            db.session.commit()
            migrated += 1
        except Exception:
            db.session.rollback()
            # Keep a verified remote copy even if a DB commit outcome is uncertain.
            # No original data is removed unless its transaction commits.
            raise
    return migrated


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        print(f"Logos transferidas e verificadas: {migrate_company_logos()}")
