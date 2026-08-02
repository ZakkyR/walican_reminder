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
    assert response.status_code in (200, 204, 302, 303)
    assert db.query(Payment).filter(Payment.event_id == event.id, Payment.status == PaymentStatus.pending).count() == 0


def test_expense_total_shown_in_page(auth_client, db, user):
    other = User(discord_id="901", discord_username="TotalOther")
    db.add(other)
    db.commit()
    db.refresh(other)
    event = _create_event_with_users(db, user, [other])
    db.add(Expense(event_id=event.id, title="食費", total_amount=Decimal(3000), paid_by=user.id))
    db.add(Expense(event_id=event.id, title="宿泊", total_amount=Decimal(7000), paid_by=user.id))
    db.commit()

    response = auth_client.get(f"/events/{event.id}?tab=expenses")
    assert response.status_code == 200
    assert "10,000" in response.text  # 合計 ¥10,000
    assert "合計" in response.text


def test_export_csv(auth_client, db, user):
    other = User(discord_id="903", discord_username="CsvOther")
    db.add(other)
    db.commit()
    db.refresh(other)
    event = _create_event_with_users(db, user, [other])
    expense = Expense(event_id=event.id, title="交通費", total_amount=Decimal(4000), paid_by=user.id)
    db.add(expense)
    db.flush()
    db.add(ExpenseParticipant(expense_id=expense.id, user_id=user.id))
    db.add(ExpenseParticipant(expense_id=expense.id, user_id=other.id))
    db.commit()

    response = auth_client.get(f"/events/{event.id}/expenses/export.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    text = response.content.decode("utf-8-sig")
    assert "タイトル" in text
    assert "交通費" in text
    assert "4000" in text
