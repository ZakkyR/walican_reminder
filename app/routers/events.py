import uuid
from datetime import date
from fastapi import APIRouter, Request, Depends, Form, HTTPException, Response
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


def _require_event_creator(event_id: str, user: User, db: Session) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404)
    if event.created_by != user.id:
        raise HTTPException(status_code=403)
    return event


@router.get("/new", response_class=HTMLResponse)
async def new_event_form(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    groups = (
        db.query(FriendGroup)
        .join(FriendGroupMember, FriendGroupMember.friend_group_id == FriendGroup.id)
        .filter(FriendGroupMember.user_id == user.id)
        .all()
    )
    all_users = db.query(User).filter(User.id != user.id).order_by(User.is_guest, User.discord_username).all()
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
    deadline = date.fromisoformat(payment_deadline) if payment_deadline else None
    event = Event(name=name, description=description, payment_deadline=deadline, created_by=user.id)
    db.add(event)

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
    is_creator = event.created_by == user.id
    return templates.TemplateResponse(request, "events/detail.html", {
        "user": user, "event": event,
        "participants": participants, "tab": tab,
        "is_creator": is_creator,
    })


@router.get("/{event_id}/edit", response_class=HTMLResponse)
async def edit_event_form(event_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = _require_event_creator(event_id, user, db)
    participants = [p.user for p in event.participants]
    return templates.TemplateResponse(request, "events/edit.html", {
        "user": user, "event": event, "participants": participants,
    })


@router.post("/{event_id}/edit")
async def update_event(
    event_id: str,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    payment_deadline: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    event = _require_event_creator(event_id, user, db)
    event.name = name
    event.description = description or None
    event.payment_deadline = date.fromisoformat(payment_deadline) if payment_deadline else None
    db.commit()
    return RedirectResponse(f"/events/{event_id}", status_code=303)


@router.post("/{event_id}/participants", response_class=HTMLResponse)
async def add_participant(
    event_id: str,
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    event = _require_event_creator(event_id, user, db)

    name = name.strip()
    if not name or len(name) > 50:
        return HTMLResponse('<p style="color:#e55;margin-top:8px;">名前は1〜50文字で入力してください。</p>', status_code=200)

    target = db.query(User).filter(User.discord_username == name, User.is_guest == False).first()  # noqa: E712
    if not target:
        target = db.query(User).filter(User.discord_username == name, User.is_guest == True).first()  # noqa: E712
    if not target:
        guest_id = f"guest_{uuid.uuid4().hex}"
        target = User(discord_id=guest_id, discord_username=name, is_guest=True)
        db.add(target)
        db.flush()

    exists = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == target.id,
    ).first()
    if exists:
        return HTMLResponse(
            f'<p style="color:#e55;margin-top:8px;">「{name}」はすでに参加者です。</p>',
            status_code=200,
        )

    db.add(EventParticipant(event_id=event_id, user_id=target.id))
    db.commit()
    return templates.TemplateResponse(
        "events/partials/event_participant_row.html",
        {"request": request, "participant": target, "event": event},
    )


@router.delete("/{event_id}/participants/{participant_user_id}")
async def remove_participant(
    event_id: str,
    participant_user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    event = _require_event_creator(event_id, user, db)
    if participant_user_id == event.created_by:
        raise HTTPException(status_code=400, detail="作成者は削除できません")
    db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == participant_user_id,
    ).delete()
    db.commit()
    return HTMLResponse("", status_code=200)


@router.delete("/{event_id}")
async def delete_event(event_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = _require_event_creator(event_id, user, db)
    db.delete(event)
    db.commit()
    response = Response(status_code=204)
    response.headers["HX-Redirect"] = "/"
    return response


@router.post("/{event_id}/complete")
async def complete_event(event_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = _require_participant(event_id, user, db)
    event.status = EventStatus.completed
    db.commit()
    return RedirectResponse(f"/events/{event_id}", status_code=303)
