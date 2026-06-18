from unittest.mock import patch
from app.models.user_guild import UserGuild


FAKE_CHANNELS = [
    {"id": "111", "name": "general", "position": 0},
    {"id": "222", "name": "bot-commands", "position": 1},
]


def _add_guild(db, user, guild_id="999888777"):
    db.add(UserGuild(user_id=user.id, guild_id=guild_id, guild_name="テストサーバー"))
    db.commit()
    return guild_id


def test_channels_returns_list(auth_client, db, user):
    guild_id = _add_guild(db, user)
    with patch("app.routers.api.get_guild_channels", return_value=FAKE_CHANNELS):
        response = auth_client.get(f"/api/channels?guild_id={guild_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "111"
    assert data[0]["name"] == "general"


def test_channels_forbidden_for_unjoined_guild(auth_client, db, user):
    with patch("app.routers.api.get_guild_channels", return_value=FAKE_CHANNELS):
        response = auth_client.get("/api/channels?guild_id=000000000")
    assert response.status_code == 403


def test_channels_requires_auth(client, db):
    with patch("app.routers.api.get_guild_channels", return_value=FAKE_CHANNELS):
        response = client.get("/api/channels?guild_id=999888777", follow_redirects=False)
    assert response.status_code in (302, 303, 307, 401, 403)
