from unittest.mock import patch, MagicMock
from app.services.discord_api import get_user_guilds, get_guild_members


def test_get_user_guilds_returns_guild_list():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [
        {"id": "111", "name": "Server A"},
        {"id": "222", "name": "Server B"},
    ]
    with patch("app.services.discord_api.httpx.get", return_value=mock_response):
        result = get_user_guilds("test_token")

    assert len(result) == 2
    assert result[0] == {"id": "111", "name": "Server A"}
    assert result[1] == {"id": "222", "name": "Server B"}


def test_get_guild_members_returns_member_list():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [
        {"user": {"id": "u1", "username": "Alice", "avatar": "abc123"}, "nick": None},
        {"user": {"id": "u2", "username": "Bob", "avatar": None}, "nick": "Bobby"},
    ]
    with patch("app.services.discord_api.httpx.get", return_value=mock_response):
        result = get_guild_members("guild1", "bot_token")

    assert result[0] == {
        "discord_id": "u1",
        "username": "Alice",
        "avatar_url": "https://cdn.discordapp.com/avatars/u1/abc123.png",
    }
    assert result[1]["username"] == "Bobby"
    assert result[1]["avatar_url"] is None


def test_get_guild_members_empty_on_http_error():
    import httpx
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=MagicMock(), response=MagicMock()
    )
    with patch("app.services.discord_api.httpx.get", return_value=mock_response):
        result = get_guild_members("guild1", "bot_token")
    assert result == []
