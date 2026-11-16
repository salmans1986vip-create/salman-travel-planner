"""
التحقق من المدخلات ومن مخرجات النموذج.

1) validate_request: يتحقق من طلب المستخدم قبل أي استدعاء للنموذج.
2) validate_plan:    يتحقق من خطة النموذج مقابل الطلب وقاعدة البيانات
                     (عدد الأيام، أرقام الأنشطة، التكرار، الحد اليومي)
                     حتى لا تُعرض أنشطة مختلقة.
"""
from __future__ import annotations

from pydantic import ValidationError

from .budget import base_cost
from .config import Settings
from .database import Database
from .exceptions import InvalidInputError
from .schemas import TravelPlan, TripRequest

_FIELD_NAMES = {
    "destination": "الوجهة",
    "days": "عدد الأيام",
    "travelers": "عدد المسافرين",
    "budget": "الميزانية",
    "interests": "الاهتمامات",
    "notes": "الملاحظات",
}


def validate_request(raw: dict, db: Database, settings: Settings) -> tuple[TripRequest, list[str]]:
    """
    يرجع (الطلب بعد التحقق، قائمة تحذيرات).
    يرفع InvalidInputError برسالة عربية تجمع كل الأخطاء.
    """
    errors: list[str] = []

    # تحويل الأنواع بأمان (قد تصل كنصوص من واجهة أو ملف)
    for key, caster in (("days", int), ("travelers", int), ("budget", float)):
        if key in raw:
            try:
                raw[key] = caster(raw[key])
            except (TypeError, ValueError):
                errors.append(f"{_FIELD_NAMES[key]}: يجب أن يكون رقماً.")

    if errors:
        raise InvalidInputError("\n".join(errors))

    try:
        request = TripRequest(**raw)
    except ValidationError as exc:
        for err in exc.errors():
            field = _FIELD_NAMES.get(str(err["loc"][0]) if err["loc"] else "", "حقل")
            errors.append(f"{field}: {err['msg']}")
        raise InvalidInputError("\n".join(errors)) from exc

    # قواعد العمل الإضافية
    if not settings.min_days <= request.days <= settings.max_days:
        errors.append(f"عدد الأيام يجب أن يكون بين {settings.min_days} و{settings.max_days}.")
    if not settings.min_travelers <= request.travelers <= settings.max_travelers:
        errors.append(f"عدد المسافرين يجب أن يكون بين {settings.min_travelers} و{settings.max_travelers}.")
    if not settings.min_budget <= request.budget <= settings.max_budget:
        errors.append(f"الميزانية يجب أن تكون بين {settings.min_budget:,.0f} و{settings.max_budget:,.0f} ريال.")

    destination = db.get_destination(request.destination)
    if destination is None:
        names = "، ".join(d["name"] for d in db.list_destinations())
        errors.append(f"الوجهة «{request.destination}» غير متوفرة. الوجهات المتاحة: {names}.")

    if errors:
        raise InvalidInputError("\n".join(errors))

    warnings: list[str] = []
    minimum = base_cost(destination, request.days, request.travelers)
    if request.budget < minimum:
        warnings.append(
            f"الميزانية ({request.budget:,.0f} ريال) أقل من التكلفة الأساسية التقديرية للسكن والأكل "
            f"والتنقل ({minimum:,.0f} ريال)؛ ستُقترح أنشطة مجانية قدر الإمكان."
        )
    return request, warnings


def validate_plan(plan: TravelPlan, request: TripRequest, available: dict[int, dict],
                  max_per_day: int = 4) -> list[str]:
    """
    يرجع قائمة بالمشكلات الجوهرية في خطة النموذج (قائمة فارغة = خطة سليمة).
    available: الأنشطة المسموح بها لهذه الوجهة {id: activity}.
    يصحح أيضاً أسماء الأنشطة لتطابق قاعدة البيانات.
    """
    issues: list[str] = []

    if len(plan.days) != request.days:
        issues.append(f"عدد الأيام في الخطة {len(plan.days)} بينما المطلوب {request.days}.")

    numbers = sorted(d.day_number for d in plan.days)
    if numbers != list(range(1, len(plan.days) + 1)):
        issues.append("ترقيم الأيام غير متسلسل.")

    seen: set[int] = set()
    for day in plan.days:
        if len(day.items) > max_per_day:
            issues.append(f"اليوم {day.day_number} يحتوي أكثر من {max_per_day} أنشطة.")
        for item in day.items:
            if item.activity_id not in available:
                issues.append(f"النشاط رقم {item.activity_id} ({item.activity_name}) غير موجود في بيانات الوجهة.")
                continue
            if item.activity_id in seen:
                issues.append(f"النشاط «{available[item.activity_id]['name']}» مكرر في أكثر من موضع.")
            seen.add(item.activity_id)
            # الاسم الرسمي من قاعدة البيانات يمنع أي تحريف من النموذج
            item.activity_name = available[item.activity_id]["name"]

    return issues
