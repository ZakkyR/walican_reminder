"""add guest user support

Revision ID: b2e9f4a7c1d3
Revises: a3f7c2d1e5b8
Create Date: 2026-06-18 04:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2e9f4a7c1d3'
down_revision: Union[str, None] = 'a3f7c2d1e5b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # discord_id を長くする（guest_ プレフィックス付き UUID を格納するため）
    op.alter_column('users', 'discord_id',
                    type_=sa.String(50),
                    existing_type=sa.String(20),
                    existing_nullable=False)
    # ゲストフラグを追加
    op.add_column('users', sa.Column('is_guest', sa.Boolean(), server_default=sa.text('0'), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'is_guest')
    op.alter_column('users', 'discord_id',
                    type_=sa.String(20),
                    existing_type=sa.String(50),
                    existing_nullable=False)
