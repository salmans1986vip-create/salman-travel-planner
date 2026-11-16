"""
نماذج البيانات (Pydantic) المستخدمة في كامل التطبيق.

- TripRequest: طلب الرحلة القادم من الواجهة، مع قواعد التحقق.
- PlanItem / DayPlan / TravelPlan: البنية التي يجب أن يُرجعها النموذج اللغوي.
  تستخدمها LangChain عبر PydanticOutputParser لإجبار النموذج على مخرجات منظمة.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

TimeSlot = Literal["صباحاً", "ظهراً", "عصراً", "مساءً"]

# الاهتمامات المدعومة (تطابق عمود category في جدول الأنشطة)
SUPPORTED_INTERESTS = {
    "تاريخ وتراث": "heritage",
    "طبيعة ومغامرة": "nature",
    "تسوق": "shopping",
    "مطاعم ومقاهي": "food",
    "ثقافة وفنون": "culture",
    "ترفيه وعائلة": "family",
}


class TripRequest(BaseModel):
    """طلب الرحلة كما يدخله المستخدم."""

    destination: str = Field(..., description="اسم الوجهة كما في قاعدة البيانات")
    days: int = Field(..., ge=1, le=7)
    travelers: int = Field(..., ge=1, le=10)
    budget: float = Field(..., gt=0, description="الميزانية الإجمالية بالريال")
    interests: list[str] = Field(..., min_length=1)
    notes: str = Field("", max_length=300)

    @field_validator("destination")
    @classmethod
    def _strip_destination(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("يجب اختيار وجهة")
        return v

    @field_validator("interests")
    @classmethod
    def _known_interests(cls, v: list[str]) -> list[str]:
        unknown = [i for i in v if i not in SUPPORTED_INTERESTS]
        if unknown:
            raise ValueError(f"اهتمامات غير مدعومة: {', '.join(unknown)}")
        return v

    @property
    def interest_codes(self) -> list[str]:
        return [SUPPORTED_INTERESTS[i] for i in self.interests]


class PlanItem(BaseModel):
    """نشاط واحد داخل يوم من أيام الرحلة."""

    activity_id: int = Field(..., description="رقم النشاط من قائمة الأنشطة المتاحة فقط")
    activity_name: str = Field(..., description="اسم النشاط كما ورد في القائمة")
    time_slot: TimeSlot = Field(..., description="فترة النشاط: صباحاً أو ظهراً أو عصراً أو مساءً")
    reason: str = Field(..., description="سبب اختيار النشاط في جملة قصيرة")


class DayPlan(BaseModel):
    """برنامج يوم واحد."""

    day_number: int = Field(..., ge=1)
    title: str = Field(..., description="عنوان قصير لليوم")
    items: list[PlanItem] = Field(..., min_length=1, max_length=4)


class TravelPlan(BaseModel):
    """الخطة الكاملة التي يُرجعها النموذج."""

    summary: str = Field(..., description="ملخص الرحلة في جملتين")
    days: list[DayPlan]
    tips: list[str] = Field(default_factory=list, description="نصائح عملية قصيرة (3 كحد أقصى)")


class CostLine(BaseModel):
    """سطر تكلفة محسوب برمجياً (لا يعتمد على النموذج)."""

    label: str
    amount: float


class BudgetReport(BaseModel):
    """نتيجة حساب الميزانية."""

    lines: list[CostLine]
    total: float
    budget: float
    remaining: float
    within_budget: bool
    warnings: list[str] = Field(default_factory=list)
