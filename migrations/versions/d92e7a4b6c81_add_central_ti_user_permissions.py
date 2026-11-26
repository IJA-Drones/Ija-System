"""Prepare opt-in access configuration per user without altering existing grants."""
from alembic import op
import sqlalchemy as sa
import re

revision = "d92e7a4b6c81"
down_revision = "c81f0e2a4d67"
branch_labels = None
depends_on = None

EXPECTED_COLUMNS = {
    'central_ti_usuarios_configuracoes': {'usuario_id', 'nome_acesso', 'versao', 'atualizado_em', 'atualizado_por_id'},
    'central_ti_usuarios_selecoes': {'usuario_id', 'codigo'},
    'central_ti_usuarios_auditoria': {'id', 'lote', 'usuario_alvo_id', 'usuario_id', 'usuario_login', 'versao_anterior', 'versao_nova', 'antes', 'depois', 'criado_em'},
}


def _check_expression(value):
    """Compare the small CHECK grammar without erasing meaningful grouping."""
    value = re.sub(r'\s|"', '', value or '').lower()
    while value.startswith('(') and value.endswith(')'):
        depth, closing = 0, None
        for index, char in enumerate(value):
            depth += (char == '(') - (char == ')')
            if depth == 0:
                closing = index
                break
        if closing != len(value) - 1:
            break
        value = value[1:-1]
    depth = 0
    for index, char in enumerate(value):
        depth += (char == '(') - (char == ')')
        if depth < 0:
            return None
        if depth == 0 and value[index:index + 3] == 'and':
            return ('and', _check_expression(value[:index]), _check_expression(value[index + 3:]))
    match = re.fullmatch(r'([a-z_][a-z_0-9]*)(>=|>)([a-z_][a-z_0-9]*|[0-9]+)', value)
    return tuple(match.groups()) if match else None


def validate_existing_schema(connection):
    inspector = sa.inspect(connection)
    primary_keys = {'central_ti_usuarios_configuracoes': ['usuario_id'],
                    'central_ti_usuarios_selecoes': ['usuario_id', 'codigo'],
                    'central_ti_usuarios_auditoria': ['id']}
    nullable = {'atualizado_por_id', 'usuario_alvo_id'}
    strings = {'nome_acesso': 80, 'codigo': 120, 'lote': 36, 'usuario_login': 50}
    for table, names in EXPECTED_COLUMNS.items():
        columns = {item['name']: item for item in inspector.get_columns(table)}
        if set(columns) != names or inspector.get_pk_constraint(table)['constrained_columns'] != primary_keys[table]:
            raise RuntimeError('Estrutura individual da Central de TI incompatível; nenhuma correção automática foi feita.')
        for name, column in columns.items():
            expected_nullable = name in nullable or (table.endswith('auditoria') and name == 'usuario_id')
            if bool(column['nullable']) != expected_nullable:
                raise RuntimeError(f'Estrutura incompatível: {table}.{name}.')
            kind = column['type'].__visit_name__.lower()
            if name in strings:
                valid_type = kind in {'varchar', 'string'} and column['type'].length == strings[name]
            elif name in {'antes', 'depois'}:
                valid_type = kind == 'json'
            elif name in {'atualizado_em', 'criado_em'}:
                valid_type = kind in {'datetime', 'timestamp'} and not column['type'].timezone
            else:
                valid_type = kind == 'integer'
            if not valid_type:
                raise RuntimeError(f'Tipo incompatível: {table}.{name}.')
        fks = {(tuple(item['constrained_columns']), item['referred_table'], tuple(item['referred_columns']),
                item.get('options', {}).get('ondelete', '').upper()) for item in inspector.get_foreign_keys(table)}
        expected = {
            'central_ti_usuarios_configuracoes': {(('usuario_id',), 'usuarios', ('id',), 'CASCADE'), (('atualizado_por_id',), 'usuarios', ('id',), 'SET NULL')},
            'central_ti_usuarios_selecoes': {(('usuario_id',), 'central_ti_usuarios_configuracoes', ('usuario_id',), 'CASCADE')},
            'central_ti_usuarios_auditoria': {(('usuario_alvo_id',), 'usuarios', ('id',), 'SET NULL'), (('usuario_id',), 'usuarios', ('id',), 'SET NULL')},
        }[table]
        if fks != expected:
            raise RuntimeError(f'Vínculos incompatíveis: {table}.')
    for table, name, expression in [
        ('central_ti_usuarios_configuracoes', 'ck_central_ti_usuario_versao', 'versao >= 1'),
        ('central_ti_usuarios_auditoria', 'ck_central_ti_usuario_auditoria_versao', 'versao_anterior >= 0 AND versao_nova > versao_anterior'),
    ]:
        checks = {item['name']: item['sqltext'] for item in inspector.get_check_constraints(table)}
        if _check_expression(checks.get(name)) != _check_expression(expression):
            raise RuntimeError('Validação de versões incompatível na Central de TI individual.')
    indexes = {item['name']: item for item in inspector.get_indexes('central_ti_usuarios_auditoria')}
    for name, column in [('ix_central_ti_usuarios_auditoria_lote', 'lote'),
                         ('ix_central_ti_usuarios_auditoria_usuario_alvo_id', 'usuario_alvo_id')]:
        if name not in indexes or indexes[name]['column_names'] != [column] or indexes[name]['unique']:
            raise RuntimeError('Índice de auditoria incompatível na Central de TI individual.')


def upgrade():
    connection = op.get_bind()
    present = set(sa.inspect(connection).get_table_names()) & set(EXPECTED_COLUMNS)
    if present:
        if present != set(EXPECTED_COLUMNS):
            raise RuntimeError('Estrutura individual parcial; migração interrompida sem alterações.')
        validate_existing_schema(connection)
        return
    op.create_table("central_ti_usuarios_configuracoes",
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("nome_acesso", sa.String(80), nullable=False, server_default=""),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.CheckConstraint("versao >= 1", name="ck_central_ti_usuario_versao"))
    op.create_table("central_ti_usuarios_selecoes",
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("central_ti_usuarios_configuracoes.usuario_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("codigo", sa.String(120), primary_key=True))
    op.create_table("central_ti_usuarios_auditoria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lote", sa.String(36), nullable=False),
        sa.Column("usuario_alvo_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("usuario_login", sa.String(50), nullable=False),
        sa.Column("versao_anterior", sa.Integer(), nullable=False),
        sa.Column("versao_nova", sa.Integer(), nullable=False),
        sa.Column("antes", sa.JSON(), nullable=False),
        sa.Column("depois", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("versao_anterior >= 0 AND versao_nova > versao_anterior", name="ck_central_ti_usuario_auditoria_versao"))
    op.create_index("ix_central_ti_usuarios_auditoria_lote", "central_ti_usuarios_auditoria", ["lote"])
    op.create_index("ix_central_ti_usuarios_auditoria_usuario_alvo_id", "central_ti_usuarios_auditoria", ["usuario_alvo_id"])


def downgrade():
    op.drop_table("central_ti_usuarios_auditoria")
    op.drop_table("central_ti_usuarios_selecoes")
    op.drop_table("central_ti_usuarios_configuracoes")
