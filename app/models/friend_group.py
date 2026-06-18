import uuid
from datetime import datetime
from sqlalchemy import String, Unicode, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class FriendGroup(Base):
    __tablename__ = "friend_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(Unicode(100))
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    members: Mapped[list["FriendGroupMember"]] = relationship("FriendGroupMember", back_populates="group", cascade="all, delete-orphan")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])


class FriendGroupMember(Base):
    __tablename__ = "friend_group_members"

    friend_group_id: Mapped[str] = mapped_column(String(36), ForeignKey("friend_groups.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)

    group: Mapped["FriendGroup"] = relationship("FriendGroup", back_populates="members")
    user: Mapped["User"] = relationship("User")
