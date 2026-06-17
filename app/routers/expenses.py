from fastapi import APIRouter, Request, Depends, Form, HTTPException, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from decimal import Decimal, InvalidOperation
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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_participant(event_id, user, db)

    try:
        amount = Decimal(total_amount)
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="金額が無効です")

    expense = Expense(event_id=event_id, title=title, total_amount=amount, paid_by=paid_by)
    db.add(expense)
    db.flush()

    form_data = await request.form()
    for uid in participant_ids:
        custom_str = form_data.get(f"custom_{uid}", "")
        custom = None
        if custom_str:
            try:
                custom = Decimal(custom_str)
            except InvalidOperation:
                raise HTTPException(status_code=400, detail=f"カスタム金額が無効です: {custom_str}")
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
    response = Response(status_code=204)
    response.headers["HX-Redirect"] = f"/events/{event_id}?tab=expenses"
    return response
