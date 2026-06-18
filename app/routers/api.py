from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.user_guild import UserGuild
from app.services.discord_api import get_guild_members
from app.config import settings

router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory="app/templates")


@router.get("/server-members", response_class=HTMLResponse)
async def server_members(
    guild_id: str,
    request: Request,
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
    return templates.TemplateResponse(
        request,
        "partials/server_member_list.html",
        {"members": members},
    )
