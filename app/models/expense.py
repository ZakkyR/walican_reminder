import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Unicode, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"))
    title: Mapped[str] = mapped_column(Unicode(200))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 0))
    paid_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    event: Mapped["Event"] = relationship("Event", back_populates="expenses")
    payer: Mapped["User"] = relationship("User", foreign_keys=[paid_by])
    participants: Mapped[list["ExpenseParticipant"]] = relationship("ExpenseParticipant", back_populates="expense", cascade="all, delete-orphan")


class ExpenseParticipant(Base):
    __tablename__ = "expense_participants"

    expense_id: Mapped[str] = mapped_column(String(36), ForeignKey("expenses.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    custom_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 0), nullable=True)

    expense: Mapped["Expense"] = relationship("Expense", back_populates="participants")
    user: Mapped["User"] = relationship("User")
