from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from app.config import settings
from app.database import get_db
from app.models.user import User

router = APIRouter()

oauth = OAuth()
oauth.register(
    name="discord",
    client_id=settings.discord_client_id,
    client_secret=settings.discord_client_secret,
    authorize_url="https://discord.com/api/oauth2/authorize",
    access_token_url="https://discord.com/api/oauth2/token",
    api_base_url="https://discord.com/api/v10/",
    client_kwargs={"scope": "identify"},
)


@router.get("/login")
async def login(request: Request):
    return await oauth.discord.authorize_redirect(request, settings.discord_redirect_uri)


@router.get("/auth/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.discord.authorize_access_token(request)
    discord_user = await oauth.discord.get("users/@me", token=token)
    data = discord_user.json()

    user = db.query(User).filter(User.discord_id == data["id"]).first()
    if not user:
        user = User(
            discord_id=data["id"],
            discord_username=data["username"],
            discord_avatar_url=(
                f"https://cdn.discordapp.com/avatars/{data['id']}/{data.get('avatar')}.png"
                if data.get("avatar")
                else None
            ),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.discord_username = data["username"]
        db.commit()

    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency that returns the current authenticated user.

    Raises HTTPException(307) redirecting to /login if not authenticated.
    Routes using this dependency should handle Union[User, RedirectResponse]
    or catch the redirect via exception handlers.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=307,
            headers={"location": "/login"},
        )
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(
            status_code=307,
            headers={"location": "/login"},
        )
    return user
