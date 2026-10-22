"""add review_reactions table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-22 13:39:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'review_reactions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('review_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('value', sa.SmallInteger(), nullable=False),
        sa.CheckConstraint('value IN (1, -1)', name='ck_review_reactions_value'),
        sa.ForeignKeyConstraint(['review_id'], ['reviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('review_id', 'user_id', name='uq_review_reactions_review_user'),
    )
    op.create_index(op.f('ix_review_reactions_review_id'), 'review_reactions', ['review_id'], unique=False)
    op.create_index(op.f('ix_review_reactions_user_id'), 'review_reactions', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_review_reactions_user_id'), table_name='review_reactions')
    op.drop_index(op.f('ix_review_reactions_review_id'), table_name='review_reactions')
    op.drop_table('review_reactions')
