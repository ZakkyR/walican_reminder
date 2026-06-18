from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.user_guild import UserGuild
from app.models.event import EventParticipant
from app.models.friend_group import FriendGroupMember
from app.services.discord_api import get_guild_members, get_member_nick
from app.config import settings

router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory="app/templates")


@router.get("/server-members", response_class=HTMLResponse)
async def server_members(
    guild_id: str,
    request: Request,
    event_id: Optional[str] = None,
    group_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    allowed = db.query(UserGuild).filter(
        UserGuild.user_id == user.id,
        UserGuild.guild_id == guild_id,
    ).first()
    if not allowed:
        raise HTTPException(status_code=403, detail="このサーバーへのアクセス権がありません")

    members = get_guild_members(guild_id, settings.discord_bot_token)

    # Build set of already-added usernames to exclude
    excluded: set[str] = set()
    if event_id:
        eps = db.query(EventParticipant).filter(EventParticipant.event_id == event_id).all()
        excluded = {ep.user.discord_username for ep in eps}
    elif group_id:
        gms = db.query(FriendGroupMember).filter(FriendGroupMember.friend_group_id == group_id).all()
        excluded = {gm.user.discord_username for gm in gms}

    if excluded:
        members = [m for m in members if m["username"] not in excluded]

    return templates.TemplateResponse(
        request,
        "partials/server_member_list.html",
        {"members": members},
    )


@router.get("/my-nickname")
async def my_nickname(
    guild_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    allowed = db.query(UserGuild).filter(
        UserGuild.user_id == user.id,
        UserGuild.guild_id == guild_id,
    ).first()
    if not allowed:
        raise HTTPException(status_code=403)

    nick = get_member_nick(guild_id, user.discord_id, settings.discord_bot_token)
    return Response(content=nick or "", media_type="text/plain")
