from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass
class ParticipantInput:
    user_id: str
    custom_amount: Decimal | None


@dataclass
class ExpenseInput:
    paid_by: str
    total_amount: Decimal
    participants: list[ParticipantInput]


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def calculate_settlement(expenses: list[ExpenseInput]) -> list[tuple[str, str, Decimal]]:
    """
    支出リストから精算リストを計算する。
    返り値: [(from_user_id, to_user_id, amount), ...]
    """
    balances: dict[str, Decimal] = {}

    for expense in expenses:
        custom = [(p.user_id, p.custom_amount) for p in expense.participants if p.custom_amount is not None]
        equal_users = [p.user_id for p in expense.participants if p.custom_amount is None]

        custom_total = sum((amt for _, amt in custom), Decimal(0))
        equal_share = _round((expense.total_amount - custom_total) / len(equal_users)) if equal_users else Decimal(0)

        balances[expense.paid_by] = balances.get(expense.paid_by, Decimal(0)) + expense.total_amount

        for uid, amt in custom:
            balances[uid] = balances.get(uid, Decimal(0)) - amt
        for uid in equal_users:
            balances[uid] = balances.get(uid, Decimal(0)) - equal_share

    creditors = sorted([(uid, bal) for uid, bal in balances.items() if bal > 0], key=lambda x: x[1])
    debtors = sorted([(uid, -bal) for uid, bal in balances.items() if bal < 0], key=lambda x: x[1])

    payments = []
    while creditors and debtors:
        cred_id, cred_amt = creditors.pop()
        debt_id, debt_amt = debtors.pop()
        amount = min(cred_amt, debt_amt)
        payments.append((debt_id, cred_id, amount))
        if cred_amt > debt_amt:
            creditors.append((cred_id, cred_amt - debt_amt))
            creditors.sort(key=lambda x: x[1])
        elif debt_amt > cred_amt:
            debtors.append((debt_id, debt_amt - cred_amt))
            debtors.sort(key=lambda x: x[1])

    return payments


def apply_settlement(event_id: str, db) -> None:
    """
    event_id のイベントの全支出から精算を再計算し、
    Payment テーブルを更新する（paid 済みを保持、pending を再計算）。
    """
    # ローカルインポートで循環インポートを回避
    from sqlalchemy.orm import Session
    from app.models.expense import Expense, ExpenseParticipant
    from app.models.payment import Payment, PaymentStatus

    # イベントの全支出を取得
    expenses_db = db.query(Expense).filter(Expense.event_id == event_id).all()

    # ExpenseInput リストに変換
    expense_inputs = []
    for exp in expenses_db:
        participants = [
            ParticipantInput(
                user_id=p.user_id,
                custom_amount=p.custom_amount,
            )
            for p in exp.participants
        ]
        expense_inputs.append(ExpenseInput(
            paid_by=exp.paid_by,
            total_amount=exp.total_amount,
            participants=participants,
        ))

    # 精算計算
    settlement_results = calculate_settlement(expense_inputs)

    # paid 済みの支払いを保持
    paid_payments = (
        db.query(Payment)
        .filter(Payment.event_id == event_id, Payment.status == PaymentStatus.paid)
        .all()
    )
    paid_set = {(p.from_user_id, p.to_user_id, p.amount) for p in paid_payments}

    # pending の既存支払いを削除
    db.query(Payment).filter(
        Payment.event_id == event_id,
        Payment.status == PaymentStatus.pending,
    ).delete()

    # 新しい pending 支払いを追加（paid 済みは除く）
    for from_user_id, to_user_id, amount in settlement_results:
        # paid 済みで同一取引があれば残額を調整
        paid_amount = sum(
            p.amount for p in paid_payments
            if p.from_user_id == from_user_id and p.to_user_id == to_user_id
        )
        remaining = amount - paid_amount
        if remaining > 0:
            new_payment = Payment(
                event_id=event_id,
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                amount=remaining,
                status=PaymentStatus.pending,
            )
            db.add(new_payment)

    db.commit()
