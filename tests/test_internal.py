from unittest.mock import patch
from app.models.event import Event, EventParticipant
from app.models.notification import NotificationSetting, NotificationMode


def _setup_event_with_notification(db, user):
    event = Event(name="通知テスト", created_by=user.id)
    db.add(event)
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.flush()
    db.add(NotificationSetting(
        event_id=event.id,
        discord_channel_id="111222333444555666",
        mode=NotificationMode.scheduled,
        schedule_cron="0 0 * * *",
    ))
    db.commit()
    db.refresh(event)
    return event


def test_notify_all_requires_key(client, db, user):
    response = client.post("/internal/notify", headers={"x-internal-key": "wrong"})
    assert response.status_code == 403


def test_notify_all_missing_key(client, db, user):
    response = client.post("/internal/notify")
    assert response.status_code == 422


def test_notify_all_returns_sent_count(auth_client, db, user):
    _setup_event_with_notification(db, user)
    with patch("app.routers.internal.settings") as mock_settings, \
         patch("app.routers.internal.run_all_notifications", return_value=1) as mock_run:
        mock_settings.internal_notify_key = "secret"
        mock_settings.discord_bot_token = "bot_token"
        mock_settings.app_base_url = "https://example.com"
        response = auth_client.post(
            "/internal/notify",
            headers={"x-internal-key": "secret"},
        )
    assert response.status_code == 200
    assert response.json()["sent"] == 1


def test_notify_one_forbidden_with_wrong_key(client, db, user):
    event = Event(name="テスト", created_by=user.id)
    db.add(event)
    db.commit()
    db.refresh(event)
    response = client.post(f"/internal/notify/{event.id}", headers={"x-internal-key": "bad"})
    assert response.status_code == 403


def test_notify_one_calls_notify_event(auth_client, db, user):
    event = _setup_event_with_notification(db, user)
    with patch("app.routers.internal.settings") as mock_settings, \
         patch("app.routers.internal.notify_event", return_value=True) as mock_notify:
        mock_settings.internal_notify_key = "secret"
        mock_settings.discord_bot_token = "bot_token"
        mock_settings.app_base_url = "https://example.com"
        response = auth_client.post(
            f"/internal/notify/{event.id}",
            headers={"x-internal-key": "secret"},
        )
    assert response.status_code == 200
    assert response.json()["sent"] == 1
    mock_notify.assert_called_once()
