from decimal import Decimal
from app.models.event import Event, EventParticipant
from app.models.expense import Expense, ExpenseParticipant
from app.models.payment import Payment, PaymentStatus
from app.models.user import User


def _create_event_with_users(db, creator, others):
    event = Event(name="精算テスト", created_by=creator.id)
    db.add(event)
    db.flush()
    for u in [creator] + others:
        db.add(EventParticipant(event_id=event.id, user_id=u.id))
    db.commit()
    db.refresh(event)
    return event


def test_add_expense_creates_payment(auth_client, db, user):
    other = User(discord_id="001", discord_username="Other1")
    db.add(other)
    db.commit()
    db.refresh(other)
    event = _create_event_with_users(db, user, [other])

    response = auth_client.post(f"/events/{event.id}/expenses", data={
        "title": "ホテル代",
        "total_amount": "10000",
        "paid_by": user.id,
        "participant_ids": [user.id, other.id],
    }, follow_redirects=False)
    assert response.status_code in (200, 302, 303)

    payments = db.query(Payment).filter(Payment.event_id == event.id).all()
    assert len(payments) == 1
    assert payments[0].from_user_id == other.id
    assert payments[0].to_user_id == user.id
    assert payments[0].amount == Decimal(5000)


def test_delete_expense_recalculates(auth_client, db, user):
    other = User(discord_id="002", discord_username="Other2")
    db.add(other)
    db.commit()
    db.refresh(other)
    event = _create_event_with_users(db, user, [other])

    expense = Expense(event_id=event.id, title="食費", total_amount=Decimal(6000), paid_by=user.id)
    db.add(expense)
    db.flush()
    db.add(ExpenseParticipant(expense_id=expense.id, user_id=user.id, custom_amount=None))
    db.add(ExpenseParticipant(expense_id=expense.id, user_id=other.id, custom_amount=None))
    db.commit()
    db.refresh(expense)

    from app.services.settlement import apply_settlement
    apply_settlement(event.id, db)
    assert db.query(Payment).filter(Payment.event_id == event.id).count() == 1

    response = auth_client.delete(f"/events/{event.id}/expenses/{expense.id}", follow_redirects=False)
    assert response.status_code in (200, 302, 303)
    assert db.query(Payment).filter(Payment.event_id == event.id, Payment.status == PaymentStatus.pending).count() == 0
