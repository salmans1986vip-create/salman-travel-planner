"""
أدوات LangChain (Tools).

ثلاث أدوات تغلّف منطق قاعدة البيانات والحساب:
    search_activities  استرجاع الأنشطة المناسبة من SQLite (Retrieval)
    calculate_budget   حساب التكلفة التفصيلية ومقارنتها بالميزانية
    save_plan          حفظ الخطة في قاعدة البيانات

تُستدعى الأدوات داخل سلسلة المعالجة في مراحل محددة (وليس بقرار حر من النموذج)،
وهذا يجعل السلوك متوقعاً وقابلاً للاختبار، كما ورد في مقترح المشروع.
"""
from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from .budget import calculate_budget as _calculate_budget
from .database import Database


class SearchActivitiesInput(BaseModel):
    destination: str = Field(..., description="اسم الوجهة")
    categories: list[str] = Field(default_factory=list, description="رموز فئات الاهتمام")


class CalculateBudgetInput(BaseModel):
    destination: str
    days: int
    travelers: int
    budget: float
    activity_ids: list[int]


class SavePlanInput(BaseModel):
    request: dict
    plan: dict
    total_cost: float
    source: str = "llm"
    trip_id: int | None = None


def make_tools(db: Database) -> dict[str, StructuredTool]:
    """ينشئ الأدوات مرتبطة بقاعدة بيانات محددة."""

    def search_activities(destination: str, categories: list[str] | None = None) -> list[dict]:
        """يسترجع أنشطة الوجهة من قاعدة البيانات مرتبة حسب الاهتمامات."""
        return db.search_activities(destination, categories or [])

    def calculate_budget(destination: str, days: int, travelers: int, budget: float,
                         activity_ids: list[int]) -> dict:
        """يحسب تكلفة الرحلة التقديرية من قاعدة البيانات ويقارنها بالميزانية."""
        dest = db.get_destination(destination)
        acts = list(db.get_activities_by_ids(activity_ids).values())
        return _calculate_budget(dest, days, travelers, budget, acts).model_dump()

    def save_plan(request: dict, plan: dict, total_cost: float, source: str = "llm",
                  trip_id: int | None = None) -> int:
        """يحفظ الخطة (جديدة أو محدّثة) ويرجع رقم الرحلة."""
        return db.save_trip(request, plan, total_cost, source=source, trip_id=trip_id)

    return {
        "search_activities": StructuredTool.from_function(
            func=search_activities, name="search_activities",
            description="البحث عن الأنشطة السياحية لوجهة معينة في قاعدة البيانات",
            args_schema=SearchActivitiesInput,
        ),
        "calculate_budget": StructuredTool.from_function(
            func=calculate_budget, name="calculate_budget",
            description="حساب التكلفة التقديرية للرحلة ومقارنتها بالميزانية",
            args_schema=CalculateBudgetInput,
        ),
        "save_plan": StructuredTool.from_function(
            func=save_plan, name="save_plan",
            description="حفظ خطة الرحلة في قاعدة البيانات",
            args_schema=SavePlanInput,
        ),
    }
