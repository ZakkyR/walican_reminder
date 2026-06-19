"""add channel info to notification setting

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = 'f4a5b6c7d8e9'
down_revision = 'e3f4a5b6c7d8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notification_settings', sa.Column('discord_guild_id', sa.String(20), nullable=True))
    op.add_column('notification_settings', sa.Column('discord_guild_name', sa.String(100), nullable=True))
    op.add_column('notification_settings', sa.Column('discord_channel_name', sa.String(100), nullable=True))


def downgrade():
    op.drop_column('notification_settings', 'discord_channel_name')
    op.drop_column('notification_settings', 'discord_guild_name')
    op.drop_column('notification_settings', 'discord_guild_id')
