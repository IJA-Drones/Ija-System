from pathlib import Path
import sys
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
import app.models
from app.modules.vigilancia.field_models import FIELD_TABLES
from alembic.autogenerate import render_python_code
from alembic.operations import ops
from alembic.migration import MigrationContext
ctx=MigrationContext.configure(dialect_name='postgresql')
up=[]
for table in FIELD_TABLES:
    up.append(ops.CreateTableOp.from_table(table))
    up.extend(ops.CreateIndexOp.from_index(index) for index in table.indexes)
down=[ops.DropTableOp(table.name) for table in reversed(FIELD_TABLES)]
header='''"""Persistência Focal/LIRAa no banco do IJA.

Revision ID: a41c9e7f26b0
Revises: d9e4f81b203a
"""
from alembic import op
import sqlalchemy as sa

revision = "a41c9e7f26b0"
down_revision = "d9e4f81b203a"
branch_labels = None
depends_on = None

'''
text=header+'def upgrade():\n'+render_python_code(ops.UpgradeOps(up),migration_context=ctx)+'\n\n\ndef downgrade():\n'+render_python_code(ops.DowngradeOps(down),migration_context=ctx)+'\n'
path=root/'migrations/versions/a41c9e7f26b0_vigilancia_campo.py'
path.write_text(text,encoding='utf-8')
print(path)
