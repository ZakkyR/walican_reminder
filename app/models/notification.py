import uuid
import enum
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, ForeignKey, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class NotificationMode(str, enum.Enum):
    scheduled = "scheduled"
    deadline = "deadline"
    from_date = "from_date"


class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), unique=True)
    discord_channel_id: Mapped[str] = mapped_column(String(20))
    mode: Mapped[NotificationMode] = mapped_column(Enum(NotificationMode, native_enum=False))
    schedule_cron: Mapped[str | None] = mapped_column(String(50), nullable=True)
    deadline_days_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadline_days_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notify_from_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notify_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    event: Mapped["Event"] = relationship("Event", back_populates="notification_setting")
