"""create system_logs table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-25 13:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'system_logs' not in tables:
        op.create_table(
            'system_logs',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=False),
            sa.Column('level', sa.String(length=20), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_system_logs')),
        )
        op.create_index(op.f('ix_system_logs_category'), 'system_logs', ['category'], unique=False)
        op.create_index(op.f('ix_system_logs_level'), 'system_logs', ['level'], unique=False)
        op.create_index(op.f('ix_system_logs_timestamp'), 'system_logs', ['timestamp'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_system_logs_timestamp'), table_name='system_logs')
    op.drop_index(op.f('ix_system_logs_level'), table_name='system_logs')
    op.drop_index(op.f('ix_system_logs_category'), table_name='system_logs')
    op.drop_table('system_logs')

