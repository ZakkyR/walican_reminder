from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.database import get_db
from app.routers.auth import get_current_user
from app.routers.events import _require_participant
from app.models.user import User
from app.models.payment import Payment, PaymentStatus

router = APIRouter(prefix="/events/{event_id}/payments")

@router.post("/{payment_id}/pay")
async def toggle_payment(
    event_id: str,
    payment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_participant(event_id, user, db)
    payment = db.get(Payment, payment_id)
    if not payment or payment.event_id != event_id:
        raise HTTPException(status_code=404)

    if payment.status == PaymentStatus.pending:
        payment.status = PaymentStatus.paid
        payment.paid_at = datetime.now(timezone.utc)
    else:
        payment.status = PaymentStatus.pending
        payment.paid_at = None
    db.commit()
    return RedirectResponse(f"/events/{event_id}?tab=payments", status_code=303)
