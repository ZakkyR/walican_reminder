import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.models.user import User
from app.models.event import Event, EventParticipant


def _mock_callback(client, discord_id, username, avatar=None):
    token_data = {"access_token": "fake_token", "token_type": "Bearer", "scope": "identify guilds"}
    discord_data = {"id": discord_id, "username": username, "avatar": avatar}
    mock_get = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = discord_data
    mock_get.return_value = mock_resp
    with patch("app.routers.auth.oauth.discord.authorize_access_token", new=AsyncMock(return_value=token_data)), \
         patch("app.routers.auth.oauth.discord.get", new=mock_get), \
         patch("app.routers.auth.get_user_guilds", return_value=[]):
        return client.get("/auth/callback?code=fake&state=fake", follow_redirects=False)


def test_guest_user_promoted_on_login(client, db):
    guest = User(discord_id="guest_abc123", discord_username="tanaka", is_guest=True)
    db.add(guest)
    db.commit()
    db.refresh(guest)
    guest_id = guest.id

    _mock_callback(client, discord_id="999000111", username="tanaka")

    db.expire_all()
    promoted = db.get(User, guest_id)
    assert promoted is not None
    assert promoted.discord_id == "999000111"
    assert promoted.is_guest is False
    assert db.query(User).filter(User.discord_username == "tanaka").count() == 1


def test_guest_promotion_preserves_event_participation(client, db, user):
    guest = User(discord_id="guest_def456", discord_username="tanaka", is_guest=True)
    db.add(guest)
    event = Event(name="テスト", created_by=user.id)
    db.add(event)
    db.flush()
    db.add(EventParticipant(event_id=event.id, user_id=user.id))
    db.add(EventParticipant(event_id=event.id, user_id=guest.id))
    db.commit()
    db.refresh(guest)
    guest_id = guest.id

    _mock_callback(client, discord_id="999000222", username="tanaka")

    db.expire_all()
    assert db.query(EventParticipant).filter(
        EventParticipant.event_id == event.id,
        EventParticipant.user_id == guest_id,
    ).first() is not None


def test_login_redirects_to_discord(client):
    response = client.get("/login", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "discord.com" in response.headers["location"]


def test_logout_clears_session(auth_client):
    response = auth_client.get("/logout", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/"


def test_protected_route_redirects_when_not_logged_in(client):
    response = client.get("/groups", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/login" in response.headers["location"]
