from decimal import Decimal
from app.models.event import Event, EventParticipant
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.models.expense import Expense, ExpenseParticipant


def _create_event_with_users(db, creator, others):
    event = Event(name="精算テスト", created_by=creator.id)
    db.add(event)
    db.flush()
    for u in [creator] + others:
        db.add(EventParticipant(event_id=event.id, user_id=u.id))
    db.commit()
    db.refresh(event)
    return event

def test_mark_payment_as_paid(auth_client, db, user):
    other = User(discord_id="010", discord_username="Payer")
    db.add(other)
    event = Event(name="精算テスト", created_by=user.id)
    db.add(event)
    db.flush()
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.add(EventParticipant(event_id=event.id, user_id=other.id))
    payment = Payment(event_id=event.id, from_user_id=other.id, to_user_id=user.id, amount=Decimal(5000))
    db.add(payment)
    db.commit()
    db.refresh(payment)

    response = auth_client.post(f"/events/{event.id}/payments/{payment.id}/pay", follow_redirects=False)
    assert response.status_code in (200, 302, 303)
    db.refresh(payment)
    assert payment.status == PaymentStatus.paid
    assert payment.paid_at is not None

def test_unmark_payment(auth_client, db, user):
    from datetime import datetime, timezone
    other = User(discord_id="011", discord_username="Payer2")
    db.add(other)
    event = Event(name="精算テスト2", created_by=user.id)
    db.add(event)
    db.flush()
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.add(EventParticipant(event_id=event.id, user_id=other.id))
    payment = Payment(event_id=event.id, from_user_id=other.id, to_user_id=user.id,
                      amount=Decimal(3000), status=PaymentStatus.paid, paid_at=datetime.now(timezone.utc))
    db.add(payment)
    db.commit()
    db.refresh(payment)

    response = auth_client.post(f"/events/{event.id}/payments/{payment.id}/pay", follow_redirects=False)
    assert response.status_code in (200, 302, 303)
    db.refresh(payment)
    assert payment.status == PaymentStatus.pending
    assert payment.paid_at is None

def test_paid_at_shown_when_paid(auth_client, db, user):
    from datetime import datetime, timezone
    other = User(discord_id="902", discord_username="PaidAtOther")
    db.add(other)
    db.commit()
    db.refresh(other)
    event = _create_event_with_users(db, user, [other])
    expense = Expense(event_id=event.id, title="テスト", total_amount=Decimal(2000), paid_by=user.id)
    db.add(expense)
    db.flush()
    db.add(ExpenseParticipant(expense_id=expense.id, user_id=user.id))
    db.add(ExpenseParticipant(expense_id=expense.id, user_id=other.id))
    db.commit()
    from app.services.settlement import apply_settlement
    apply_settlement(event.id, db)
    payment = db.query(Payment).filter(Payment.event_id == event.id).first()
    payment.status = PaymentStatus.paid
    payment.paid_at = datetime(2026, 6, 21, 0, 0, 0, tzinfo=timezone.utc)
    db.commit()

    response = auth_client.get(f"/events/{event.id}?tab=payments")
    assert response.status_code == 200
    assert "2026-06-21" in response.text or "06/21" in response.text or "精算日" in response.text
