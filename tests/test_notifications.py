from app.models.event import Event, EventParticipant
from app.models.notification import NotificationSetting, NotificationMode


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
