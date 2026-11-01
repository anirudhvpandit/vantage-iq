from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Alert,
    Budget,
    Customer,
    Department,
    ExpenseTransaction,
    Organization,
    Project,
    RevenueTransaction,
)


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(Organization.id).where(Organization.is_demo.is_(True))):
        return

    organization = Organization(name="Northstar Industrial Services", currency="USD", is_demo=True)
    db.add(organization)
    db.flush()

    department_names = ["Field Services", "Engineering", "Managed Operations", "Sales"]
    departments = {
        name: Department(organization_id=organization.id, name=name)
        for name in department_names
    }
    db.add_all(departments.values())
    db.flush()

    customer_specs = [
        ("Asteron Manufacturing", "Industrial", "Active", "Jordan Lee"),
        ("Bluepeak Energy", "Energy", "Active", "Taylor Morgan"),
        ("Cedarline Foods", "Manufacturing", "Active", "Riley Chen"),
        ("Dovetail Logistics", "Logistics", "Active", "Jordan Lee"),
        ("Eastbank Utilities", "Utilities", "Active", "Taylor Morgan"),
        ("Fathom Components", "Industrial", "Active", "Riley Chen"),
        ("Granite Harbor Group", "Industrial", "Active", "Jordan Lee"),
        ("HelioWorks", "Energy", "Active", "Taylor Morgan"),
        ("Ironwood Systems", "Technology", "Active", "Riley Chen"),
        ("Juniper Materials", "Manufacturing", "Active", "Jordan Lee"),
        ("Kestrel Process Co.", "Industrial", "Active", "Taylor Morgan"),
        ("Lumen Field Partners", "Services", "At risk", "Riley Chen"),
    ]
    customers = {
        name: Customer(
            organization_id=organization.id,
            name=name,
            segment=segment,
            status=status,
            account_owner=owner,
        )
        for name, segment, status, owner in customer_specs
    }
    db.add_all(customers.values())
    db.flush()

    start_year, start_month = 2024, 11
    for offset in range(24):
        month_index = start_month - 1 + offset
        year, month = start_year + month_index // 12, month_index % 12 + 1
        month_start = date(year, month, 1)
        seasonality = Decimal("1.0") + Decimal(str(((offset % 6) - 2) * 0.025))
        for index, (customer_name, customer) in enumerate(customers.items()):
            dept_name = department_names[(index + offset) % 4]
            trend = Decimal("1.0") + Decimal(offset) * Decimal("0.012")
            base = Decimal(8500 + index * 1750) * trend * seasonality
            if customer_name == "Lumen Field Partners" and offset >= 18:
                base *= Decimal("0.72")
            amount = base.quantize(Decimal("0.01"))
            db.add(
                RevenueTransaction(
                    organization_id=organization.id,
                    customer_id=customer.id,
                    department_id=departments[dept_name].id,
                    external_id=f"demo-{year}-{month:02d}-{index:02d}",
                    transaction_date=date(year, month, min(5 + index, 26)),
                    amount=amount,
                    currency=organization.currency,
                    description="Synthetic recognized services revenue",
                    revenue_type="recognized",
                )
            )
        for index, dept_name in enumerate(department_names):
            cost = Decimal(42000 + (index * 9200) + (offset % 4) * 1700)
            if dept_name == "Engineering" and offset >= 20:
                cost *= Decimal("1.12")
            db.add(
                ExpenseTransaction(
                    organization_id=organization.id,
                    department_id=departments[dept_name].id,
                    transaction_date=date(year, month, 20),
                    amount=cost.quantize(Decimal("0.01")),
                    category=["Payroll", "Delivery", "Facilities", "Sales operations"][index],
                    description="Synthetic operating expense",
                )
            )
        for index, dept_name in enumerate(department_names):
            db.add(
                Budget(
                    organization_id=organization.id,
                    department_id=departments[dept_name].id,
                    period_start=month_start,
                    revenue_target=(Decimal(52000 + index * 2500) + Decimal(offset * 650)).quantize(Decimal("0.01")),
                    expense_budget=Decimal(65000 + index * 5000),
                )
            )

    project_specs = [
        ("Asteron line modernization", "Asteron Manufacturing", "Field Services", "In progress", 45, 54, 135000, 92000, 2026, 12, None),
        ("Bluepeak controls upgrade", "Bluepeak Energy", "Engineering", "At risk", 78, 58, 210000, 194000, 2026, 10, None),
        ("Cedarline reliability review", "Cedarline Foods", "Managed Operations", "Completed", 100, 100, 84000, 79000, 2026, 7, date(2026, 7, 24)),
        ("Eastbank site assessment", "Eastbank Utilities", "Engineering", "Planned", 12, 8, 96000, 12500, 2027, 1, None),
        ("Granite Harbor maintenance", "Granite Harbor Group", "Field Services", "In progress", 66, 70, 165000, 112000, 2026, 11, None),
        ("Lumen transition support", "Lumen Field Partners", "Managed Operations", "Completed", 100, 100, 68000, 73500, 2026, 5, date(2026, 6, 8)),
    ]
    for index, spec in enumerate(project_specs):
        name, customer_name, dept, status, planned, actual, budget, cost, end_year, end_month, actual_end = spec
        db.add(
            Project(
                organization_id=organization.id,
                customer_id=customers[customer_name].id,
                department_id=departments[dept].id,
                name=name,
                manager=["Casey Brooks", "Morgan Patel", "Alex Rivera"][index % 3],
                status=status,
                start_date=date(2026, max(1, end_month - 4), 1),
                planned_end_date=date(end_year, end_month, 25),
                actual_end_date=actual_end,
                budget=Decimal(budget),
                actual_cost=Decimal(cost),
                planned_progress=planned,
                actual_progress=actual,
            )
        )

    db.add_all(
        [
            Alert(
                organization_id=organization.id,
                title="Bluepeak controls upgrade is behind plan",
                severity="High",
                explanation="Actual progress is 20 percentage points below planned progress.",
                suggested_action="Review the remaining milestones and agree a recovery plan with the project manager.",
                detected_at=datetime(2026, 10, 28, 9, 0),
            ),
            Alert(
                organization_id=organization.id,
                title="Lumen revenue has declined",
                severity="Medium",
                explanation="Synthetic recognized revenue for this customer is lower than its prior-period level.",
                suggested_action="Review the account plan and confirm the next scheduled engagement.",
                detected_at=datetime(2026, 10, 30, 10, 0),
            ),
        ]
    )
    db.commit()
