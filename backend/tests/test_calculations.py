from decimal import Decimal

from app.calculations import budget_achievement, operating_margin, percent_change


def test_percent_change_uses_previous_absolute_value():
    assert percent_change(Decimal("90"), Decimal("-100")) == Decimal("-10")


def test_percent_change_returns_none_for_zero_baseline():
    assert percent_change(Decimal("15"), Decimal("0")) is None


def test_operating_margin_handles_zero_revenue():
    assert operating_margin(Decimal("0"), Decimal("100")) is None


def test_operating_margin_is_unavailable_for_net_negative_revenue():
    assert operating_margin(Decimal("-20"), Decimal("10")) is None


def test_expense_credit_is_reflected_in_operating_margin():
    assert operating_margin(Decimal("100"), Decimal("-20")) == Decimal("120.0")


def test_operating_margin_and_budget_achievement():
    assert operating_margin(Decimal("200"), Decimal("150")) == Decimal("25.00")
    assert budget_achievement(Decimal("80"), Decimal("100")) == Decimal("80")


def test_budget_achievement_handles_zero_target():
    assert budget_achievement(Decimal("80"), Decimal("0")) is None
