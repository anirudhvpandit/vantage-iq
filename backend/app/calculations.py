from decimal import Decimal


def percent_change(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return None
    return (abs(current) - abs(previous)) / abs(previous) * Decimal("100")


def operating_margin(revenue: Decimal, operating_costs: Decimal) -> Decimal | None:
    if revenue <= 0:
        return None
    return (revenue - operating_costs) / revenue * Decimal("100")


def budget_achievement(actual: Decimal, target: Decimal) -> Decimal | None:
    if target == 0:
        return None
    return actual / target * Decimal("100")
