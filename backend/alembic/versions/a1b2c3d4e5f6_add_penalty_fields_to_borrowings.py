"""add penalty fields to borrowings

Revision ID: a1b2c3d4e5f6
Revises: 77534610c3c0
Create Date: 2026-10-22 12:59:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '77534610c3c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c['name'] for c in inspector.get_columns('borrowings')}

    if 'penalty_amount' not in existing_cols:
        op.add_column(
            'borrowings',
            sa.Column('penalty_amount', sa.Float(), server_default='0.0', nullable=False),
        )
    if 'is_penalty_paid' not in existing_cols:
        op.add_column(
            'borrowings',
            sa.Column('is_penalty_paid', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        )


def downgrade() -> None:
    op.drop_column('borrowings', 'is_penalty_paid')
    op.drop_column('borrowings', 'penalty_amount')

