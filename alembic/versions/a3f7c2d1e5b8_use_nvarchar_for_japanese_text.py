"""use nvarchar for japanese text

Revision ID: a3f7c2d1e5b8
Revises: 17bf98dc855f
Create Date: 2026-06-18 03:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a3f7c2d1e5b8'
down_revision: Union[str, None] = '17bf98dc855f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'discord_username',
                    type_=sa.Unicode(100),
                    existing_type=sa.String(100),
                    existing_nullable=False)
    op.alter_column('events', 'name',
                    type_=sa.Unicode(200),
                    existing_type=sa.String(200),
                    existing_nullable=False)
    op.alter_column('events', 'description',
                    type_=sa.Unicode(1000),
                    existing_type=sa.String(1000),
                    existing_nullable=True)
    op.alter_column('expenses', 'title',
                    type_=sa.Unicode(200),
                    existing_type=sa.String(200),
                    existing_nullable=False)
    op.alter_column('friend_groups', 'name',
                    type_=sa.Unicode(100),
                    existing_type=sa.String(100),
                    existing_nullable=False)


def downgrade() -> None:
    op.alter_column('friend_groups', 'name',
                    type_=sa.String(100),
                    existing_type=sa.Unicode(100),
                    existing_nullable=False)
    op.alter_column('expenses', 'title',
                    type_=sa.String(200),
                    existing_type=sa.Unicode(200),
                    existing_nullable=False)
    op.alter_column('events', 'description',
                    type_=sa.String(1000),
                    existing_type=sa.Unicode(1000),
                    existing_nullable=True)
    op.alter_column('events', 'name',
                    type_=sa.String(200),
                    existing_type=sa.Unicode(200),
                    existing_nullable=False)
    op.alter_column('users', 'discord_username',
                    type_=sa.String(100),
                    existing_type=sa.Unicode(100),
                    existing_nullable=False)
