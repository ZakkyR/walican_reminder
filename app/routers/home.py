from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.payment import Payment, PaymentStatus

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.event import EventParticipant
    participated = db.query(Event).join(EventParticipant, EventParticipant.event_id == Event.id).filter(
        EventParticipant.user_id == user.id
    ).order_by(Event.created_at.desc()).all()

    events_with_stats = []
    for event in participated:
        pending_count = db.query(Payment).filter(
            Payment.event_id == event.id,
            Payment.status == PaymentStatus.pending
        ).count()
        events_with_stats.append({"event": event, "pending_count": pending_count})

    return templates.TemplateResponse(request, "home.html", {
        "user": user,
        "events_with_stats": events_with_stats,
    })
