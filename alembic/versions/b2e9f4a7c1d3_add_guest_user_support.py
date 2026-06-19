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
    is_sqlite = op.get_context().dialect.name == "sqlite"
    if not is_sqlite:
        # SQLite は動的型付けのため VARCHAR(20) → VARCHAR(50) は不要
        op.alter_column('users', 'discord_id',
                        type_=sa.String(50),
                        existing_type=sa.String(20),
                        existing_nullable=False)
    op.add_column('users', sa.Column('is_guest', sa.Boolean(), server_default=sa.text('0'), nullable=False))


def downgrade() -> None:
    is_sqlite = op.get_context().dialect.name == "sqlite"
    if is_sqlite:
        with op.batch_alter_table('users') as batch_op:
            batch_op.drop_column('is_guest')
    else:
        op.drop_column('users', 'is_guest')
        op.alter_column('users', 'discord_id',
                        type_=sa.String(20),
                        existing_type=sa.String(50),
                        existing_nullable=False)
