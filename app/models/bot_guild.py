from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class BotGuild(Base):
    __tablename__ = "bot_guilds"

    guild_id: Mapped[str] = mapped_column(String(20), primary_key=True)
