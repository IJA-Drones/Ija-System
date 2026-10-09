"""limit user audit history to the newest 15,000 records"""

from alembic import op
import sqlalchemy as sa


revision = "5d7e9a1c3b20"
down_revision = "4c9b2f7a6d10"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    auditoria = sa.table("auditoria_usuarios", sa.column("id", sa.Integer()), sa.column("criado_em", sa.DateTime()))
    antigos = sa.select(auditoria.c.id).order_by(
        auditoria.c.criado_em.desc(), auditoria.c.id.desc()
    ).offset(15000).subquery()
    bind.execute(sa.delete(auditoria).where(auditoria.c.id.in_(sa.select(antigos.c.id))))


def downgrade():
    # Records deleted by the retention policy cannot be restored by a migration.
    pass
