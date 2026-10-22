"""add cover_url to books

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-22 14:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c['name'] for c in inspector.get_columns('books')}

    if 'cover_url' not in existing_cols:
        op.add_column(
            'books',
            sa.Column('cover_url', sa.String(length=500), nullable=True),
        )


def downgrade() -> None:
    op.drop_column('books', 'cover_url')

