from decimal import Decimal
from app.models.event import Event, EventParticipant
from app.models.payment import Payment, PaymentStatus
from app.models.user import User

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
    from datetime import datetime
    other = User(discord_id="011", discord_username="Payer2")
    db.add(other)
    event = Event(name="精算テスト2", created_by=user.id)
    db.add(event)
    db.flush()
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.add(EventParticipant(event_id=event.id, user_id=other.id))
    payment = Payment(event_id=event.id, from_user_id=other.id, to_user_id=user.id,
                      amount=Decimal(3000), status=PaymentStatus.paid, paid_at=datetime.utcnow())
    db.add(payment)
    db.commit()
    db.refresh(payment)

    response = auth_client.post(f"/events/{event.id}/payments/{payment.id}/pay", follow_redirects=False)
    assert response.status_code in (200, 302, 303)
    db.refresh(payment)
    assert payment.status == PaymentStatus.pending
    assert payment.paid_at is None
