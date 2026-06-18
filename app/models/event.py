import uuid
import enum
from datetime import datetime, date
from sqlalchemy import String, Unicode, DateTime, Date, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class EventStatus(str, enum.Enum):
    active = "active"
    completed = "completed"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(Unicode(200))
    description: Mapped[str | None] = mapped_column(Unicode(1000), nullable=True)
    payment_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus, native_enum=False), default=EventStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    participants: Mapped[list["EventParticipant"]] = relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="event", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="event", cascade="all, delete-orphan")
    notification_setting: Mapped["NotificationSetting | None"] = relationship("NotificationSetting", back_populates="event", uselist=False)

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = str(uuid.uuid4())
        super().__init__(**kwargs)


class EventParticipant(Base):
    __tablename__ = "event_participants"

    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(Unicode(100), nullable=True)

    event: Mapped["Event"] = relationship("Event", back_populates="participants")
    user: Mapped["User"] = relationship("User")
