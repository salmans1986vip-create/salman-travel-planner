"""
مخطِّط احتياطي قائم على القواعد (بدون نموذج لغوي).

يُستخدم فقط عند تعذّر الوصول إلى خدمة النموذج (انقطاع الإنترنت، عدم وجود مفتاح،
تجاوز حد الطلبات)، حتى يبقى التطبيق قابلاً للاستخدام أثناء العرض.
الخطة الناتجة تُعلَّم بالمصدر "fallback" ويظهر للمستخدم أنها خطة مبسطة.
"""
from __future__ import annotations

from .schemas import DayPlan, PlanItem, TravelPlan, TripRequest

_SLOT_ORDER = ["صباحاً", "ظهراً", "عصراً", "مساءً"]


def build_fallback_plan(request: TripRequest, activities: list[dict], per_day: int = 3) -> TravelPlan:
    """
    خوارزمية جشعة بسيطة:
    - ترتيب الأنشطة حسب مطابقة الاهتمامات ثم الأرخص.
    - توزيعها على الأيام دون تكرار، نشاط واحد لكل فترة زمنية.
    """
    interest = set(request.interest_codes)
    pool = sorted(
        activities,
        key=lambda a: (a["category"] not in interest, a["cost_per_person"]),
    )
    used: set[int] = set()
    days: list[DayPlan] = []

    for day_no in range(1, request.days + 1):
        items: list[PlanItem] = []
        taken_slots: set[str] = set()
        for act in pool:
            if len(items) >= per_day:
                break
            if act["id"] in used or act["best_time"] in taken_slots:
                continue
            items.append(
                PlanItem(
                    activity_id=act["id"],
                    activity_name=act["name"],
                    time_slot=act["best_time"],
                    reason="مطابق لاهتماماتك" if act["category"] in interest else "نشاط متاح مناسب للوقت",
                )
            )
            used.add(act["id"])
            taken_slots.add(act["best_time"])
        if not items:  # نفدت الأنشطة: يوم حر
            break
        items.sort(key=lambda i: _SLOT_ORDER.index(i.time_slot))
        days.append(DayPlan(day_number=day_no, title=f"اليوم {day_no}", items=items))

    return TravelPlan(
        summary=f"خطة مبسطة لـ{request.days} أيام في {request.destination} أُعدّت تلقائياً دون النموذج اللغوي.",
        days=days,
        tips=["هذه خطة احتياطية؛ أعد المحاولة لاحقاً للحصول على خطة مفصلة من المساعد الذكي."],
    )
