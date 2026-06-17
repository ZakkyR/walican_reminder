from decimal import Decimal
from app.services.settlement import calculate_settlement, ExpenseInput, ParticipantInput


def test_equal_split_two_people():
    # A が 10000 円立替、A と B で均等割り → B が A に 5000 円
    expenses = [ExpenseInput(
        paid_by="A",
        total_amount=Decimal(10000),
        participants=[
            ParticipantInput(user_id="A", custom_amount=None),
            ParticipantInput(user_id="B", custom_amount=None),
        ]
    )]
    result = calculate_settlement(expenses)
    assert result == [("B", "A", Decimal(5000))]


def test_custom_amount():
    # A が 10000 円立替、A は 3000 円、B は 7000 円カスタム
    expenses = [ExpenseInput(
        paid_by="A",
        total_amount=Decimal(10000),
        participants=[
            ParticipantInput(user_id="A", custom_amount=Decimal(3000)),
            ParticipantInput(user_id="B", custom_amount=Decimal(7000)),
        ]
    )]
    result = calculate_settlement(expenses)
    assert result == [("B", "A", Decimal(7000))]


def test_mixed_split():
    # A が 9000 円立替、A はカスタム 3000 円、B と C は均等（各 3000 円）
    expenses = [ExpenseInput(
        paid_by="A",
        total_amount=Decimal(9000),
        participants=[
            ParticipantInput(user_id="A", custom_amount=Decimal(3000)),
            ParticipantInput(user_id="B", custom_amount=None),
            ParticipantInput(user_id="C", custom_amount=None),
        ]
    )]
    result = calculate_settlement(expenses)
    assert len(result) == 2
    assert ("B", "A", Decimal(3000)) in result
    assert ("C", "A", Decimal(3000)) in result


def test_multiple_expenses_minimize_transactions():
    # A が 6000 円立替（A,B,C 均等 2000 ずつ）
    # B が 3000 円立替（A,B 均等 1500 ずつ）
    # 最終: A が B に 500 円、C が A に 2000 円
    expenses = [
        ExpenseInput(
            paid_by="A",
            total_amount=Decimal(6000),
            participants=[
                ParticipantInput(user_id="A", custom_amount=None),
                ParticipantInput(user_id="B", custom_amount=None),
                ParticipantInput(user_id="C", custom_amount=None),
            ]
        ),
        ExpenseInput(
            paid_by="B",
            total_amount=Decimal(3000),
            participants=[
                ParticipantInput(user_id="A", custom_amount=None),
                ParticipantInput(user_id="B", custom_amount=None),
            ]
        ),
    ]
    result = calculate_settlement(expenses)
    # A: +6000-2000-1500 = +2500（受け取り側）
    # B: +3000-2000-1500 = -500（支払い側）
    # C: -2000（支払い側）
    # B が A に 500、C が A に 2000
    assert len(result) == 2
    assert ("B", "A", Decimal(500)) in result
    assert ("C", "A", Decimal(2000)) in result


def test_no_expenses_returns_empty():
    assert calculate_settlement([]) == []


def test_single_payer_excluded_from_participants():
    # A が 1000 円立替、参加者は B のみ → A は負担なし、B が 1000 円支払い
    expenses = [ExpenseInput(
        paid_by="A",
        total_amount=Decimal(1000),
        participants=[ParticipantInput(user_id="B", custom_amount=None)],
    )]
    result = calculate_settlement(expenses)
    assert result == [("B", "A", Decimal(1000))]
