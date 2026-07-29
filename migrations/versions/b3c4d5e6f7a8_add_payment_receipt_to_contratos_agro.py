"""add payment receipt to contratos agro

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-10 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contratos_agro", schema=None) as batch_op:
        batch_op.add_column(sa.Column("comprovante_pagamento_path", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("comprovante_pagamento_nome", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("comprovante_pagamento_enviado_em", sa.DateTime(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_contratos_agro_comprovante_pagamento_enviado_em"),
            ["comprovante_pagamento_enviado_em"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("contratos_agro", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_contratos_agro_comprovante_pagamento_enviado_em"))
        batch_op.drop_column("comprovante_pagamento_enviado_em")
        batch_op.drop_column("comprovante_pagamento_nome")
        batch_op.drop_column("comprovante_pagamento_path")
