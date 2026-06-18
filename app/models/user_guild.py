from sqlalchemy import String, Unicode, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class UserGuild(Base):
    __tablename__ = "user_guilds"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    guild_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    guild_name: Mapped[str] = mapped_column(Unicode(100))

    user: Mapped["User"] = relationship("User")
