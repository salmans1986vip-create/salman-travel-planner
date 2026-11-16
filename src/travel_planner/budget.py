"""
حساب الميزانية برمجياً.

مبدأ مهم في المشروع: النموذج اللغوي لا يحسب الأرقام ولا يخترع الأسعار.
النموذج يختار الأنشطة فقط، ثم تُحسب التكلفة هنا من قاعدة البيانات.
"""
from __future__ import annotations

import math

from .schemas import BudgetReport, CostLine


def rooms_needed(travelers: int) -> int:
    """غرفة لكل شخصين (تقريب للأعلى)."""
    return max(1, math.ceil(travelers / 2))


def nights_for(days: int) -> int:
    """رحلة يوم واحد بلا مبيت، وإلا فعدد الليالي = الأيام - 1."""
    return max(0, days - 1)


def base_cost(destination: dict, days: int, travelers: int) -> float:
    """التكلفة الأساسية (سكن + أكل + تنقل) دون الأنشطة."""
    hotel = destination["hotel_night"] * rooms_needed(travelers) * nights_for(days)
    food = destination["food_per_person"] * travelers * days
    transport = destination["transport_per_day"] * days
    return float(hotel + food + transport)


def calculate_budget(destination: dict, days: int, travelers: int, budget: float,
                     activities: list[dict]) -> BudgetReport:
    """
    يحسب التكلفة التفصيلية للخطة.

    activities: قائمة الأنشطة المختارة (كما هي في قاعدة البيانات، بها cost_per_person).
    """
    rooms = rooms_needed(travelers)
    nights = nights_for(days)
    hotel = destination["hotel_night"] * rooms * nights
    food = destination["food_per_person"] * travelers * days
    transport = destination["transport_per_day"] * days
    acts = sum(a["cost_per_person"] for a in activities) * travelers

    lines = [
        CostLine(label=f"السكن ({nights} ليلة × {rooms} غرفة)", amount=round(hotel, 2)),
        CostLine(label=f"الوجبات ({travelers} مسافر × {days} يوم)", amount=round(food, 2)),
        CostLine(label=f"التنقل الداخلي ({days} يوم)", amount=round(transport, 2)),
        CostLine(label=f"تذاكر الأنشطة ({len(activities)} نشاط × {travelers} مسافر)", amount=round(acts, 2)),
    ]
    total = round(sum(line.amount for line in lines), 2)
    remaining = round(budget - total, 2)

    warnings: list[str] = []
    if remaining < 0:
        warnings.append(
            f"التكلفة التقديرية تتجاوز الميزانية بمقدار {abs(remaining):,.0f} ريال. "
            "يمكنك طلب خطة أوفر أو زيادة الميزانية."
        )
    elif remaining > budget * 0.4:
        warnings.append("يتبقى جزء كبير من الميزانية؛ يمكنك طلب أنشطة إضافية.")
    free = [a["name"] for a in activities if a["cost_per_person"] == 0]
    if free:
        warnings.append(f"{len(free)} من الأنشطة مجانية الدخول وفق البيانات المتاحة.")

    return BudgetReport(
        lines=lines,
        total=total,
        budget=budget,
        remaining=remaining,
        within_budget=remaining >= 0,
        warnings=warnings,
    )
