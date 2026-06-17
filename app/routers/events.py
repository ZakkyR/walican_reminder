from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.event import Event, EventParticipant, EventStatus
from app.models.friend_group import FriendGroup, FriendGroupMember

router = APIRouter(prefix="/events")
templates = Jinja2Templates(directory="app/templates")


def _require_participant(event_id: str, user: User, db: Session) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404)
    is_participant = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == user.id,
    ).first()
    if not is_participant:
        raise HTTPException(status_code=403)
    return event


@router.get("/new", response_class=HTMLResponse)
async def new_event_form(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    groups = db.query(FriendGroup).filter(FriendGroup.created_by == user.id).all()
    all_users = db.query(User).filter(User.id != user.id).all()
    return templates.TemplateResponse(request, "events/new.html", {
        "user": user, "groups": groups, "all_users": all_users,
    })


@router.post("")
async def create_event(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    payment_deadline: Optional[str] = Form(None),
    friend_group_id: Optional[str] = Form(None),
    participant_ids: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from datetime import date
    deadline = date.fromisoformat(payment_deadline) if payment_deadline else None
    event = Event(name=name, description=description, payment_deadline=deadline, created_by=user.id)
    db.add(event)
    db.flush()

    participant_set = {user.id}
    if friend_group_id:
        members = db.query(FriendGroupMember).filter(FriendGroupMember.friend_group_id == friend_group_id).all()
        participant_set.update(m.user_id for m in members)
    participant_set.update(participant_ids)

    for uid in participant_set:
        db.add(EventParticipant(event_id=event.id, user_id=uid))
    db.commit()
    return RedirectResponse(f"/events/{event.id}", status_code=303)


@router.get("/{event_id}", response_class=HTMLResponse)
async def event_detail(event_id: str, request: Request, tab: str = "expenses", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = _require_participant(event_id, user, db)
    participants = [p.user for p in event.participants]
    return templates.TemplateResponse(request, "events/detail.html", {
        "user": user, "event": event,
        "participants": participants, "tab": tab,
    })


@router.post("/{event_id}/complete")
async def complete_event(event_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = _require_participant(event_id, user, db)
    event.status = EventStatus.completed
    db.commit()
    return RedirectResponse(f"/events/{event_id}", status_code=303)
