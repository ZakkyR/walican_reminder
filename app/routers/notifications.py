import logging
from datetime import date
from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)
from app.database import get_db
from app.routers.auth import get_current_user
from app.routers.events import _require_event_creator
from app.models.user import User
from app.models.notification import NotificationSetting, NotificationMode
from app.services.notifier import notify_event

router = APIRouter(prefix="/events/{event_id}/notification")


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
    _require_event_creator(event_id, user, db)
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
def send_now(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_event_creator(event_id, user, db)
    if settings.discord_bot_token and settings.app_base_url:
        try:
            notify_event(event_id, db, settings.discord_bot_token, settings.app_base_url.rstrip("/"))
        except Exception:
            logger.exception("send_now: notify_event failed for %s", event_id)
    return RedirectResponse(f"/events/{event_id}?tab=notification", status_code=303)
