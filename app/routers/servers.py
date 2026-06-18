from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.user_guild import UserGuild
from app.config import settings

router = APIRouter(prefix="/servers")
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def server_list(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user_guilds = db.query(UserGuild).filter(UserGuild.user_id == user.id).order_by(UserGuild.guild_name).all()
    return templates.TemplateResponse(request, "servers/index.html", {
        "user": user,
        "user_guilds": user_guilds,
        "discord_client_id": settings.discord_client_id,
    })
