from unittest.mock import patch, AsyncMock, MagicMock
from app.models.user_guild import UserGuild


def _make_discord_mock(discord_user_data):
    """Return an AsyncMock for oauth.discord.get whose result has .json() set."""
    mock_get = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = discord_user_data
    mock_get.return_value = mock_resp
    return mock_get


def test_login_stores_user_guilds(client, db, user):
    guilds_payload = [
        {"id": "111222333444555666", "name": "Gaming Server"},
        {"id": "999888777666555444", "name": "Work Server"},
    ]
    token_data = {
        "access_token": "fake_token",
        "token_type": "Bearer",
        "scope": "identify guilds",
    }
    discord_user_data = {
        "id": user.discord_id,
        "username": user.discord_username,
        "avatar": None,
    }
    with patch("app.routers.auth.oauth.discord.authorize_access_token", new=AsyncMock(return_value=token_data)), \
         patch("app.routers.auth.oauth.discord.get", new=_make_discord_mock(discord_user_data)), \
         patch("app.routers.auth.get_user_guilds", return_value=guilds_payload):
        response = client.get("/auth/callback?code=fake&state=fake", follow_redirects=False)

    assert response.status_code in (302, 303, 307)
    stored = db.query(UserGuild).filter(UserGuild.user_id == user.id).all()
    assert len(stored) == 2
    guild_ids = {g.guild_id for g in stored}
    assert "111222333444555666" in guild_ids
    assert "999888777666555444" in guild_ids


def test_login_updates_existing_guilds(client, db, user):
    """Second login replaces old guild list with new one."""
    from app.models.user_guild import UserGuild
    db.add(UserGuild(user_id=user.id, guild_id="old_guild", guild_name="Old"))
    db.commit()

    guilds_payload = [{"id": "new_guild", "name": "New Server"}]
    token_data = {"access_token": "t", "token_type": "Bearer", "scope": "identify guilds"}
    discord_user_data = {"id": user.discord_id, "username": user.discord_username, "avatar": None}

    with patch("app.routers.auth.oauth.discord.authorize_access_token", new=AsyncMock(return_value=token_data)), \
         patch("app.routers.auth.oauth.discord.get", new=_make_discord_mock(discord_user_data)), \
         patch("app.routers.auth.get_user_guilds", return_value=guilds_payload):
        client.get("/auth/callback?code=fake&state=fake", follow_redirects=False)

    stored = db.query(UserGuild).filter(UserGuild.user_id == user.id).all()
    assert len(stored) == 1
    assert stored[0].guild_id == "new_guild"
