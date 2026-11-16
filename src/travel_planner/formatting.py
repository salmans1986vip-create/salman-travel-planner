"""
دوال تنسيق نصية (بدون LangChain) لتجهيز السياق للنموذج وللتصدير.
"""
from __future__ import annotations

from .schemas import BudgetReport, TravelPlan

CATEGORY_AR = {
    "heritage": "تاريخ وتراث",
    "nature": "طبيعة ومغامرة",
    "shopping": "تسوق",
    "food": "مطاعم ومقاهي",
    "culture": "ثقافة وفنون",
    "family": "ترفيه وعائلة",
}


def activities_table(activities: list[dict]) -> str:
    """جدول Markdown مضغوط بالأنشطة؛ هو المصدر الوحيد الذي يختار منه النموذج."""
    header = "| الرقم | النشاط | الفئة | المدة (ساعة) | التكلفة للفرد (ريال) | الوقت المفضل |\n|---|---|---|---|---|---|"
    rows = [
        f"| {a['id']} | {a['name']} | {CATEGORY_AR.get(a['category'], a['category'])} | "
        f"{a['duration_hours']:g} | {a['cost_per_person']:g} | {a['best_time']} |"
        for a in activities
    ]
    return "\n".join([header, *rows])


def plan_to_text(plan: TravelPlan, request: dict, budget: BudgetReport | None,
                 activities: dict[int, dict] | None = None) -> str:
    """نسخة نصية من الخطة للتصدير (ملف .txt)."""
    activities = activities or {}
    lines = [
        "مساعد تخطيط السفر — برنامج الرحلة",
        "=" * 40,
        f"الوجهة: {request['destination']} | الأيام: {request['days']} | "
        f"المسافرون: {request['travelers']} | الميزانية: {request['budget']:,.0f} ريال",
        "",
        plan.summary,
        "",
    ]
    for day in plan.days:
        lines.append(f"اليوم {day.day_number}: {day.title}")
        for item in day.items:
            act = activities.get(item.activity_id, {})
            cost = act.get("cost_per_person")
            cost_txt = f" — {cost:g} ريال/فرد" if cost is not None else ""
            lines.append(f"  • {item.time_slot}: {item.activity_name}{cost_txt}")
            lines.append(f"      {item.reason}")
        lines.append("")
    if budget:
        lines.append("التكلفة التقديرية")
        lines.append("-" * 40)
        for line in budget.lines:
            lines.append(f"  {line.label}: {line.amount:,.0f} ريال")
        lines.append(f"  الإجمالي: {budget.total:,.0f} ريال | المتبقي: {budget.remaining:,.0f} ريال")
        for w in budget.warnings:
            lines.append(f"  ! {w}")
        lines.append("")
    if plan.tips:
        lines.append("نصائح")
        lines.extend(f"  - {t}" for t in plan.tips)
    lines.append("")
    lines.append("تنبيه: جميع التكاليف تقديرية من بيانات تجريبية ولا تمثل أسعاراً رسمية.")
    return "\n".join(lines)
