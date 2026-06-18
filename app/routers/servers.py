from urllib.parse import quote
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.user_guild import UserGuild
from app.models.bot_guild import BotGuild
from app.config import settings

router = APIRouter(prefix="/servers")
templates = Jinja2Templates(directory="app/templates")

# Derive bot invite callback URI from the existing redirect URI config.
# e.g. "https://xxx.azurewebsites.net/auth/callback" → "https://xxx.azurewebsites.net/servers/callback"
_callback_uri = settings.discord_redirect_uri.replace("/auth/callback", "/servers/callback")
_callback_uri_encoded = quote(_callback_uri, safe="")


@router.get("", response_class=HTMLResponse)
async def server_list(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user_guilds = db.query(UserGuild).filter(UserGuild.user_id == user.id).order_by(UserGuild.guild_name).all()
    bot_guild_ids = {r.guild_id for r in db.query(BotGuild).all()}
    return templates.TemplateResponse(request, "servers/index.html", {
        "user": user,
        "user_guilds": user_guilds,
        "bot_guild_ids": bot_guild_ids,
        "discord_client_id": settings.discord_client_id,
        "callback_uri_encoded": _callback_uri_encoded,
    })


@router.get("/callback")
async def bot_invite_callback(
    guild_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if guild_id:
        existing = db.get(BotGuild, guild_id)
        if not existing:
            db.add(BotGuild(guild_id=guild_id))
            db.commit()
    return RedirectResponse("/servers", status_code=302)
