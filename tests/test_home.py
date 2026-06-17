"""Tests for the home page (GET /)."""
import pytest
from app.models.event import Event, EventParticipant, EventStatus
from app.models.payment import Payment, PaymentStatus


def test_home_redirects_when_not_logged_in(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/login" in response.headers["location"]


def test_home_returns_200_when_logged_in(auth_client):
    response = auth_client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert "イベント一覧" in response.text


def test_home_shows_empty_state_when_no_events(auth_client):
    response = auth_client.get("/")
    assert response.status_code == 200
    assert "イベントがありません" in response.text


def test_home_shows_participated_events(auth_client, user, db):
    # Create an event where the user is a participant
    event = Event(
        name="テスト旅行",
        created_by=user.id,
        status=EventStatus.active,
    )
    db.add(event)
    db.flush()

    participant = EventParticipant(event_id=event.id, user_id=user.id)
    db.add(participant)
    db.commit()

    response = auth_client.get("/")
    assert response.status_code == 200
    assert "テスト旅行" in response.text


def test_home_shows_pending_payment_badge(auth_client, user, db):
    # Create an event with a pending payment
    event = Event(
        name="割り勘イベント",
        created_by=user.id,
        status=EventStatus.active,
    )
    db.add(event)
    db.flush()

    participant = EventParticipant(event_id=event.id, user_id=user.id)
    db.add(participant)

    payment = Payment(
        event_id=event.id,
        from_user_id=user.id,
        to_user_id=user.id,
        amount=1000,
        status=PaymentStatus.pending,
    )
    db.add(payment)
    db.commit()

    response = auth_client.get("/")
    assert response.status_code == 200
    assert "未払い" in response.text


def test_home_does_not_show_unparticipated_events(auth_client, user, db):
    # Create another user and their event (user is not a participant)
    from app.models.user import User
    other_user = User(discord_id="999999999", discord_username="OtherUser")
    db.add(other_user)
    db.flush()

    event = Event(
        name="他人のイベント",
        created_by=other_user.id,
        status=EventStatus.active,
    )
    db.add(event)
    db.commit()

    response = auth_client.get("/")
    assert response.status_code == 200
    assert "他人のイベント" not in response.text
