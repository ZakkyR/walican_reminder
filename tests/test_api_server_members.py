from unittest.mock import patch
from app.models.user_guild import UserGuild


def test_server_members_returns_member_list(auth_client, db, user):
    db.add(UserGuild(user_id=user.id, guild_id="guild123", guild_name="Test Server"))
    db.commit()

    members = [
        {"discord_id": "u1", "username": "Alice", "display_name": "Alice", "avatar_url": None},
        {"discord_id": "u2", "username": "Bob", "display_name": "Bobby", "avatar_url": "https://cdn.discordapp.com/avatars/u2/x.png"},
    ]
    with patch("app.routers.api.get_guild_members", return_value=members):
        response = auth_client.get("/api/server-members?guild_id=guild123")

    assert response.status_code == 200
    assert "Alice" in response.text
    assert "Bob" in response.text


def test_server_members_rejects_non_member_guild(auth_client, db, user):
    response = auth_client.get("/api/server-members?guild_id=not_my_guild")
    assert response.status_code == 403
