import logging
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.services.notifier import notify_event, run_all_notifications

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal")


def _verify_key(x_internal_key: str = Header(...)):
    if not settings.internal_notify_key or x_internal_key != settings.internal_notify_key:
        raise HTTPException(status_code=403)


@router.post("/notify")
def notify_all(db: Session = Depends(get_db), _: None = Depends(_verify_key)):
    if not settings.discord_bot_token or not settings.app_base_url:
        raise HTTPException(status_code=500, detail="Missing configuration")
    sent = run_all_notifications(db, settings.discord_bot_token, settings.app_base_url.rstrip("/"))
    logger.info("notify_all: sent=%d", sent)
    return JSONResponse({"sent": sent})


@router.post("/notify/{event_id}")
def notify_one(event_id: str, db: Session = Depends(get_db), _: None = Depends(_verify_key)):
    if not settings.discord_bot_token or not settings.app_base_url:
        raise HTTPException(status_code=500, detail="Missing configuration")
    sent = notify_event(event_id, db, settings.discord_bot_token, settings.app_base_url.rstrip("/"))
    return JSONResponse({"sent": sent})
