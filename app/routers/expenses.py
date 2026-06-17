from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from decimal import Decimal
from typing import Optional
from app.database import get_db
from app.routers.auth import get_current_user
from app.routers.events import _require_participant
from app.models.user import User
from app.models.expense import Expense, ExpenseParticipant
from app.services.settlement import apply_settlement

router = APIRouter(prefix="/events/{event_id}/expenses")
templates = Jinja2Templates(directory="app/templates")


@router.post("")
async def add_expense(
    event_id: str,
    request: Request,
    title: str = Form(...),
    total_amount: str = Form(...),
    paid_by: str = Form(...),
    participant_ids: list[str] = Form(...),
    custom_amounts: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_participant(event_id, user, db)
    expense = Expense(
        event_id=event_id,
        title=title,
        total_amount=Decimal(total_amount),
        paid_by=paid_by,
    )
    db.add(expense)
    db.flush()

    for i, uid in enumerate(participant_ids):
        custom = Decimal(custom_amounts[i]) if i < len(custom_amounts) and custom_amounts[i] else None
        db.add(ExpenseParticipant(expense_id=expense.id, user_id=uid, custom_amount=custom))

    db.commit()
    apply_settlement(event_id, db)
    return RedirectResponse(f"/events/{event_id}?tab=expenses", status_code=303)


@router.delete("/{expense_id}")
async def delete_expense(
    event_id: str,
    expense_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_participant(event_id, user, db)
    expense = db.get(Expense, expense_id)
    if not expense or expense.event_id != event_id:
        raise HTTPException(status_code=404)
    db.delete(expense)
    db.commit()
    apply_settlement(event_id, db)
    return RedirectResponse(f"/events/{event_id}?tab=expenses", status_code=303)
