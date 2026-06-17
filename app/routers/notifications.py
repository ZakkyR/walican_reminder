from datetime import date
import httpx
from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from app.config import settings
from app.database import get_db
from app.routers.auth import get_current_user
from app.routers.events import _require_participant
from app.models.user import User
from app.models.notification import NotificationSetting, NotificationMode

router = APIRouter(prefix="/events/{event_id}/notification")
templates = Jinja2Templates(directory="app/templates")


@router.post("")
async def save_notification(
    event_id: str,
    discord_channel_id: str = Form(...),
    mode: str = Form(...),
    schedule_cron: Optional[str] = Form(None),
    deadline_days_before: Optional[int] = Form(None),
    deadline_days_after: Optional[int] = Form(None),
    notify_from_date: Optional[str] = Form(None),
    notify_interval_days: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_participant(event_id, user, db)
    setting = db.query(NotificationSetting).filter(NotificationSetting.event_id == event_id).first()
    if not setting:
        setting = NotificationSetting(event_id=event_id)
        db.add(setting)

    setting.discord_channel_id = discord_channel_id
    setting.mode = NotificationMode(mode)
    setting.schedule_cron = schedule_cron or None
    setting.deadline_days_before = deadline_days_before
    setting.deadline_days_after = deadline_days_after
    setting.notify_from_date = date.fromisoformat(notify_from_date) if notify_from_date else None
    setting.notify_interval_days = notify_interval_days
    db.commit()
    return RedirectResponse(f"/events/{event_id}?tab=notification", status_code=303)


@router.post("/send-now")
async def send_now(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_participant(event_id, user, db)
    if settings.functions_url and settings.functions_key:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.functions_url}/api/notify/{event_id}",
                headers={"x-functions-key": settings.functions_key},
                timeout=10,
            )
    return RedirectResponse(f"/events/{event_id}?tab=notification", status_code=303)
