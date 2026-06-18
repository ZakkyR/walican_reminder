import json
import base64
import itsdangerous
from app.models.event import Event, EventParticipant
from app.models.notification import NotificationSetting, NotificationMode
from app.models.user import User
from app.config import settings


def _make_auth_client_for(client, user_obj):
    signer = itsdangerous.TimestampSigner(str(settings.session_secret))
    data = base64.b64encode(json.dumps({"user_id": user_obj.id}).encode())
    signed = signer.sign(data).decode()
    client.cookies.set("session", signed)
    return client


def test_save_notification_setting(auth_client, db, user):
    event = Event(name="通知テスト", created_by=user.id)
    db.add(event)
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.commit()
    db.refresh(event)

    response = auth_client.post(f"/events/{event.id}/notification", data={
        "discord_channel_id": "111222333444555666",
        "mode": "scheduled",
        "schedule_cron": "0 12 * * 1",
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    setting = db.query(NotificationSetting).filter(NotificationSetting.event_id == event.id).first()
    assert setting is not None
    assert setting.discord_channel_id == "111222333444555666"
    assert setting.mode == NotificationMode.scheduled
    assert setting.schedule_cron == "0 12 * * 1"


def test_update_notification_setting(auth_client, db, user):
    event = Event(name="通知更新テスト", created_by=user.id)
    db.add(event)
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    existing = NotificationSetting(
        event_id=event.id, discord_channel_id="000", mode=NotificationMode.scheduled
    )
    db.add(existing)
    db.commit()
    db.refresh(event)

    response = auth_client.post(f"/events/{event.id}/notification", data={
        "discord_channel_id": "999888777666555444",
        "mode": "deadline",
        "deadline_days_before": "3",
        "deadline_days_after": "7",
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    db.refresh(existing)
    assert existing.discord_channel_id == "999888777666555444"
    assert existing.mode == NotificationMode.deadline
    assert existing.deadline_days_before == 3


def test_non_creator_cannot_save_notification(client, db, user):
    other = User(discord_id="other001", discord_username="OtherUser")
    db.add(other)
    db.flush()
    event = Event(name="権限テスト", created_by=user.id)
    db.add(event)
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.add(EventParticipant(event_id=event.id, user_id=other.id))
    db.commit()
    db.refresh(event)
    db.refresh(other)

    _make_auth_client_for(client, other)
    response = client.post(f"/events/{event.id}/notification", data={
        "discord_channel_id": "999",
        "mode": "scheduled",
        "schedule_cron": "0 9 * * *",
    }, follow_redirects=False)
    assert response.status_code in (403, 404)
    assert db.query(NotificationSetting).filter(NotificationSetting.event_id == event.id).first() is None


def test_non_creator_cannot_send_now(client, db, user):
    other = User(discord_id="other002", discord_username="OtherUser2")
    db.add(other)
    db.flush()
    event = Event(name="即時通知権限テスト", created_by=user.id)
    db.add(event)
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.add(EventParticipant(event_id=event.id, user_id=other.id))
    db.add(NotificationSetting(event_id=event.id, discord_channel_id="111", mode=NotificationMode.scheduled))
    db.commit()
    db.refresh(event)
    db.refresh(other)

    _make_auth_client_for(client, other)
    response = client.post(f"/events/{event.id}/notification/send-now", follow_redirects=False)
    assert response.status_code in (403, 404)
