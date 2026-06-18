import io
from app.models.event import Event, EventParticipant
from app.models.expense import Expense, ExpenseParticipant
from app.models.user import User

CSV_CONTENT = """登録日,品目名,通貨,金額,払った人,借りている人
2026/02/07,ホテル,JPY,12000,みやざき,みやざき/ムス/ゆーだい
2026/02/07,ガソリン,JPY,3000,ゆーだい,みやざき/ゆーだい
"""

BAD_CSV_CONTENT = """date,item,amount
2026/02/07,ホテル,12000
"""


def test_import_preview(auth_client, db, user):
    response = auth_client.post(
        "/events/import/preview",
        files={"file": ("payments.csv", io.BytesIO(CSV_CONTENT.encode("utf-8")), "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "みやざき" in response.text
    assert "ゆーだい" in response.text
    assert "ムス" in response.text
    assert "ホテル" in response.text


def test_import_preview_bad_csv(auth_client, db, user):
    response = auth_client.post(
        "/events/import/preview",
        files={"file": ("bad.csv", io.BytesIO(BAD_CSV_CONTENT.encode("utf-8")), "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_import_create(auth_client, db, user):
    db.add(User(discord_id="u_miyazaki", discord_username="みやざき"))
    db.commit()
    miyazaki = db.query(User).filter(User.discord_username == "みやざき").first()

    form_data = {
        "event_name": "スキー旅行",
        "rows_json": '[{"date":"2026/02/07","title":"ホテル","amount":12000,"paid_by":"みやざき","participants":["みやざき","ムス","ゆーだい"]}]',
        "csv_name_0": "みやざき",
        "mapping_0": miyazaki.id,
        "csv_name_1": "ムス",
        "mapping_1": "guest:ムス",
        "csv_name_2": "ゆーだい",
        "mapping_2": "guest:ゆーだい",
    }
    response = auth_client.post("/events/import/create", data=form_data, follow_redirects=False)
    assert response.status_code in (302, 303)

    event = db.query(Event).filter(Event.name == "スキー旅行").first()
    assert event is not None
    participants = db.query(EventParticipant).filter(EventParticipant.event_id == event.id).all()
    participant_ids = {p.user_id for p in participants}
    # creator (user), みやざき, ムス, ゆーだい
    assert user.id in participant_ids
    assert len(participants) == 4

    expense = db.query(Expense).filter(Expense.event_id == event.id, Expense.title == "ホテル").first()
    assert expense is not None
    assert int(expense.total_amount) == 12000
    assert expense.paid_by == miyazaki.id

    ep_count = db.query(ExpenseParticipant).filter(ExpenseParticipant.expense_id == expense.id).count()
    assert ep_count == 3


def test_import_create_rejects_invalid_amount(auth_client, db, user):
    db.add(User(discord_id="u_m2", discord_username="A"))
    db.commit()
    a_user = db.query(User).filter(User.discord_username == "A").first()

    form_data = {
        "event_name": "不正テスト",
        "rows_json": '[{"date":"2026/01/01","title":"悪意","amount":-9999,"paid_by":"A","participants":["A"]}]',
        "csv_name_0": "A",
        "mapping_0": a_user.id,
    }
    response = auth_client.post("/events/import/create", data=form_data, follow_redirects=False)
    assert response.status_code == 400
