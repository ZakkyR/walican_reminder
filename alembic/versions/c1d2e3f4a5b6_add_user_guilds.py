"""add user_guilds table

Revision ID: c1d2e3f4a5b6
Revises: b2e9f4a7c1d3
Create Date: 2026-06-18 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'b2e9f4a7c1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_guilds',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('guild_id', sa.String(20), primary_key=True),
        sa.Column('guild_name', sa.Unicode(100), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('user_guilds')
