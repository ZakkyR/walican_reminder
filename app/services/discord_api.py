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
    Returns list of {"discord_id": str, "username": str, "avatar_url": str | None}.
    Returns [] on HTTP error (e.g. 403 if intent not enabled).
    """
    try:
        resp = httpx.get(
            f"{_DISCORD_API}/guilds/{guild_id}/members",
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
            "username": m.get("nick") or user["username"],
            "avatar_url": (
                f"https://cdn.discordapp.com/avatars/{user['id']}/{avatar}.png"
                if avatar else None
            ),
        })
    return members
