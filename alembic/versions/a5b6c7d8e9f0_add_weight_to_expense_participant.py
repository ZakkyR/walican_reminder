"""add weight to expense_participants

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-10-12
"""
from alembic import op
import sqlalchemy as sa

revision = 'a5b6c7d8e9f0'
down_revision = 'f4a5b6c7d8e9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('expense_participants', sa.Column('weight', sa.Numeric(6, 2), nullable=True))


def downgrade():
    op.drop_column('expense_participants', 'weight')
