import httpx

_DISCORD_API = "https://discord.com/api/v10"


def get_user_guilds(access_token: str) -> list[dict]:
    """Fetch guilds the user belongs to. Returns list of {"id": str, "name": str}."""
    resp = httpx.get(
        f"{_DISCORD_API}/users/@me/guilds",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    return [{"id": g["id"], "name": g["name"]} for g in resp.json()]


def get_guild_members(guild_id: str, bot_token: str) -> list[dict]:
    """Fetch members of a guild via Bot token.
    Requires GUILD_MEMBERS privileged intent in Discord Developer Portal.
    Returns list of:
      {"discord_id": str, "username": str, "display_name": str, "avatar_url": str | None}
    username  = global Discord username (matches discord_username in DB)
    display_name = server nickname if set, otherwise username
    Returns [] on HTTP error (e.g. 403 if intent not enabled).
    """
    try:
        resp = httpx.get(
            f"{_DISCORD_API}/guilds/{guild_id}/members",
            # Discord caps this endpoint at 1000 per page; servers with >1000 members are silently truncated.
            params={"limit": 1000},
            headers={"Authorization": f"Bot {bot_token}"},
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError:
        return []

    members = []
    for m in resp.json():
        user = m["user"]
        avatar = user.get("avatar")
        members.append({
            "discord_id": user["id"],
            "username": user["username"],
            "display_name": m.get("nick") or user["username"],
            "avatar_url": (
                f"https://cdn.discordapp.com/avatars/{user['id']}/{avatar}.png"
                if avatar else None
            ),
        })
    return members


def get_guild_channels(guild_id: str, bot_token: str) -> list[dict]:
    """Fetch text channels of a guild via Bot token.
    Returns list of {"id": str, "name": str} sorted by position.
    Returns [] on HTTP error.
    """
    try:
        resp = httpx.get(
            f"{_DISCORD_API}/guilds/{guild_id}/channels",
            headers={"Authorization": f"Bot {bot_token}"},
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError:
        return []

    text_channels = [
        {"id": ch["id"], "name": ch["name"]}
        for ch in resp.json()
        if ch["type"] == 0  # GUILD_TEXT
    ]
    text_channels.sort(key=lambda c: c["name"])
    return text_channels


def get_member_nick(guild_id: str, discord_id: str, bot_token: str) -> str | None:
    """Returns server nickname for a specific user in a guild, or None if no nick/not found."""
    try:
        resp = httpx.get(
            f"{_DISCORD_API}/guilds/{guild_id}/members/{discord_id}",
            headers={"Authorization": f"Bot {bot_token}"},
        )
        resp.raise_for_status()
        return resp.json().get("nick") or None
    except httpx.HTTPStatusError:
        return None
