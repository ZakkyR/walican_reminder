from decimal import Decimal
from app.models.event import Event, EventParticipant
from app.models.expense import Expense, ExpenseParticipant
from app.models.payment import Payment
from app.models.user import User


def _setup(db, user):
    other = User(discord_id="edit001", discord_username="EditUser")
    db.add(other)
    event = Event(name="支出編集テスト", created_by=user.id)
    db.add(event)
    db.flush()
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.add(EventParticipant(event_id=event.id, user_id=other.id))
    expense = Expense(event_id=event.id, title="食費", total_amount=Decimal(6000), paid_by=user.id)
    db.add(expense)
    db.flush()
    db.add(ExpenseParticipant(expense_id=expense.id, user_id=user.id))
    db.add(ExpenseParticipant(expense_id=expense.id, user_id=other.id))
    db.commit()
    db.refresh(event)
    db.refresh(expense)
    db.refresh(other)
    return event, expense, other


def test_edit_form_returns_200(auth_client, db, user):
    event, expense, _ = _setup(db, user)
    response = auth_client.get(f"/events/{event.id}/expenses/{expense.id}/edit-form")
    assert response.status_code == 200
    assert "食費" in response.text
    assert "6000" in response.text


def test_edit_expense_updates_title_and_amount(auth_client, db, user):
    event, expense, other = _setup(db, user)

    response = auth_client.post(f"/events/{event.id}/expenses/{expense.id}/edit", data={
        "title": "ホテル代",
        "total_amount": "12000",
        "paid_by": user.id,
        "participant_ids": [user.id, other.id],
    }, follow_redirects=False)
    assert response.status_code in (302, 303)

    db.refresh(expense)
    assert expense.title == "ホテル代"
    assert expense.total_amount == Decimal(12000)


def test_edit_expense_recalculates_payment(auth_client, db, user):
    event, expense, other = _setup(db, user)

    from app.services.settlement import apply_settlement
    apply_settlement(event.id, db)
    before = db.query(Payment).filter(Payment.event_id == event.id).first()
    assert before.amount == Decimal(3000)

    auth_client.post(f"/events/{event.id}/expenses/{expense.id}/edit", data={
        "title": "食費",
        "total_amount": "10000",
        "paid_by": user.id,
        "participant_ids": [user.id, other.id],
    }, follow_redirects=False)

    payment = db.query(Payment).filter(Payment.event_id == event.id).first()
    assert payment.amount == Decimal(5000)


def test_edit_expense_with_custom_amount(auth_client, db, user):
    event, expense, other = _setup(db, user)

    auth_client.post(f"/events/{event.id}/expenses/{expense.id}/edit", data={
        "title": "食費",
        "total_amount": "9000",
        "paid_by": user.id,
        "participant_ids": [user.id, other.id],
        f"custom_{other.id}": "3000",
    }, follow_redirects=False)

    db.refresh(expense)
    ep = db.query(ExpenseParticipant).filter(
        ExpenseParticipant.expense_id == expense.id,
        ExpenseParticipant.user_id == other.id,
    ).first()
    assert ep.custom_amount == Decimal(3000)
