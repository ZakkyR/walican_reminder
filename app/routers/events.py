import csv
import io
import json
import uuid
from datetime import date
from fastapi import APIRouter, Request, Depends, Form, HTTPException, Response, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.event import Event, EventParticipant, EventStatus
from app.models.expense import Expense, ExpenseParticipant
from app.models.friend_group import FriendGroup, FriendGroupMember
from app.models.payment import Payment, PaymentStatus
from app.models.user_guild import UserGuild
from app.models.bot_guild import BotGuild

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


@router.get("/import", response_class=HTMLResponse)
async def import_form(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "events/import.html", {"user": user})


_MAX_CSV_BYTES = 1 * 1024 * 1024  # 1 MB
_REQUIRED_COLUMNS = {"登録日", "品目名", "金額", "払った人", "借りている人"}


@router.post("/import/preview", response_class=HTMLResponse)
async def import_preview(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    raw = await file.read(_MAX_CSV_BYTES + 1)
    if len(raw) > _MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="ファイルが大きすぎます（上限1MB）")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("shift-jis")
        except UnicodeDecodeError:
            raise HTTPException(status_code=422, detail="文字コードを認識できません（UTF-8またはShift-JISのCSVを使用してください）")

    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        names: set[str] = set()
        for row in reader:
            missing = _REQUIRED_COLUMNS - set(row.keys())
            if missing:
                raise HTTPException(status_code=422, detail=f"CSVの列が不足しています: {', '.join(missing)}")
            paid_by = row["払った人"].strip()
            participants = [n.strip() for n in row["借りている人"].split("/") if n.strip()]
            rows.append({
                "date": row["登録日"],
                "title": row["品目名"].strip(),
                "amount": int(row["金額"]),
                "paid_by": paid_by,
                "participants": participants,
            })
            names.add(paid_by)
            names.update(participants)
    except HTTPException:
        raise
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=f"CSVの形式が正しくありません: {e}")

    names_indexed = list(enumerate(sorted(names)))

    # Pre-fill: CSV name that matches a registered user's username stays as-is (correct)
    # CSV name that matches no registered user also stays as-is (will become guest)
    return templates.TemplateResponse(request, "events/import_preview.html", {
        "user": user,
        "rows": rows,
        "names_indexed": names_indexed,
        "matched_names": {},  # text inputs pre-filled with CSV name by default
        "rows_json": json.dumps(rows, ensure_ascii=False),
    })


@router.post("/import/create")
async def import_create(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    form = await request.form()
    event_name = (form.get("event_name") or "Walicaインポート").strip()
    payment_deadline_str = form.get("payment_deadline") or None
    rows_json = form.get("rows_json", "[]")
    rows = json.loads(rows_json)

    # Rebuild name→user mapping from indexed fields (cap at 500 to prevent amplification)
    name_to_uid: dict[str, str] = {}
    for i in range(500):
        csv_name = form.get(f"csv_name_{i}")
        if csv_name is None:
            break
        # mapping_name_N is the username text the user typed (or the CSV name pre-filled)
        mapping_name = (form.get(f"mapping_name_{i}") or csv_name).strip() or csv_name

        # Look up registered user first, then guest, then create guest
        target = db.query(User).filter(User.discord_username == mapping_name, User.is_guest == False).first()  # noqa: E712
        if not target:
            target = db.query(User).filter(User.discord_username == mapping_name, User.is_guest == True).first()  # noqa: E712
        if not target:
            target = User(discord_id=f"guest_{uuid.uuid4().hex}", discord_username=mapping_name, is_guest=True)
            db.add(target)
            db.flush()
        name_to_uid[csv_name] = target.id

    # Critical: validate rows from hidden field — never trust client-submitted amounts/titles
    known_names = set(name_to_uid.keys())
    for row in rows:
        if not isinstance(row.get("amount"), int) or row["amount"] <= 0:
            raise HTTPException(status_code=400, detail="不正な金額が含まれています")
        if not isinstance(row.get("title"), str) or len(row["title"]) > 200:
            raise HTTPException(status_code=400, detail="不正な品目名が含まれています")
        if row.get("paid_by") not in known_names:
            raise HTTPException(status_code=400, detail="不正な払った人が含まれています")
        for pname in row.get("participants", []):
            if pname not in known_names:
                raise HTTPException(status_code=400, detail="不正な参加者名が含まれています")

    deadline = date.fromisoformat(payment_deadline_str) if payment_deadline_str else None
    event = Event(name=event_name, created_by=user.id, payment_deadline=deadline)
    db.add(event)
    db.flush()

    participant_ids = set(name_to_uid.values()) | {user.id}
    for uid in participant_ids:
        db.add(EventParticipant(event_id=event.id, user_id=uid))

    for row in rows:
        payer_id = name_to_uid.get(row["paid_by"])
        if not payer_id:
            continue
        expense = Expense(
            event_id=event.id,
            title=row["title"],
            total_amount=row["amount"],
            paid_by=payer_id,
        )
        db.add(expense)
        db.flush()
        for pname in row["participants"]:
            uid = name_to_uid.get(pname)
            if uid:
                db.add(ExpenseParticipant(expense_id=expense.id, user_id=uid))

    db.commit()
    from app.services.settlement import apply_settlement
    apply_settlement(event.id, db)
    return RedirectResponse(f"/events/{event.id}", status_code=303)


@router.get("/new", response_class=HTMLResponse)
async def new_event_form(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    groups = (
        db.query(FriendGroup)
        .join(FriendGroupMember, FriendGroupMember.friend_group_id == FriendGroup.id)
        .filter(FriendGroupMember.user_id == user.id)
        .all()
    )
    user_guilds = db.query(UserGuild).join(BotGuild, BotGuild.guild_id == UserGuild.guild_id).filter(UserGuild.user_id == user.id).all()
    return templates.TemplateResponse(request, "events/new.html", {
        "user": user, "groups": groups,
        "user_guilds": user_guilds,
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
    display_names = {
        ep.user_id: ep.display_name or ep.user.discord_username
        for ep in event.participants
    }
    user_guilds = db.query(UserGuild).join(BotGuild, BotGuild.guild_id == UserGuild.guild_id).filter(UserGuild.user_id == user.id).all()
    unpaid_count = sum(1 for p in event.payments if p.status == PaymentStatus.pending)
    return templates.TemplateResponse(request, "events/detail.html", {
        "user": user, "event": event,
        "participants": participants, "tab": tab,
        "is_creator": is_creator,
        "display_names": display_names,
        "user_guilds": user_guilds,
        "unpaid_count": unpaid_count,
    })


@router.get("/{event_id}/edit", response_class=HTMLResponse)
async def edit_event_form(event_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = _require_event_creator(event_id, user, db)
    participants = [p.user for p in event.participants]
    user_guilds = db.query(UserGuild).join(BotGuild, BotGuild.guild_id == UserGuild.guild_id).filter(UserGuild.user_id == user.id).all()
    my_ep = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == user.id,
    ).first()
    my_display_name = my_ep.display_name if my_ep else None
    return templates.TemplateResponse(request, "events/edit.html", {
        "user": user, "event": event, "participants": participants,
        "user_guilds": user_guilds,
        "my_display_name": my_display_name,
    })


@router.post("/{event_id}/my-display-name")
async def set_my_display_name(
    event_id: str,
    display_name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_participant(event_id, user, db)
    ep = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == user.id,
    ).first()
    if ep:
        ep.display_name = display_name.strip() or None
        db.commit()
    return RedirectResponse(f"/events/{event_id}/edit", status_code=303)


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
    if event.status == EventStatus.completed:
        return HTMLResponse('<p style="color:#e55;margin-top:8px;">完了済みイベントは編集できません。</p>', status_code=200)

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
    if event.status == EventStatus.completed:
        raise HTTPException(status_code=400, detail="完了済みイベントは編集できません")
    if participant_user_id == event.created_by:
        raise HTTPException(status_code=400, detail="作成者は削除できません")
    has_expenses = db.query(ExpenseParticipant).join(
        Expense, Expense.id == ExpenseParticipant.expense_id
    ).filter(
        Expense.event_id == event_id,
        ExpenseParticipant.user_id == participant_user_id,
    ).first()
    if has_expenses:
        raise HTTPException(status_code=400, detail="この参加者は支出に含まれているため削除できません")
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
    from datetime import datetime, timezone
    for p in event.payments:
        if p.status == PaymentStatus.pending:
            p.status = PaymentStatus.paid
            p.paid_at = datetime.now(timezone.utc)
    event.status = EventStatus.completed
    db.commit()
    return RedirectResponse(f"/events/{event_id}", status_code=303)


@router.post("/{event_id}/reopen")
async def reopen_event(event_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = _require_participant(event_id, user, db)
    event.status = EventStatus.active
    db.commit()
    return RedirectResponse(f"/events/{event_id}", status_code=303)
