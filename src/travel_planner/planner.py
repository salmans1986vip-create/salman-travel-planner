"""
خدمة التخطيط: الطبقة التي تنسّق بين الواجهة وقاعدة البيانات وسلاسل LangChain.

تدفق إنشاء خطة:
    1) التحقق من المدخلات (validation)
    2) استرجاع الأنشطة (أداة search_activities)
    3) سلسلة LangChain ─► TravelPlan منظم
    4) التحقق من الخطة مقابل البيانات؛ عند الخطأ إعادة المحاولة مع تغذية راجعة
    5) حساب الميزانية برمجياً (أداة calculate_budget)؛ عند التجاوز الكبير محاولة خطة أوفر
    6) الحفظ (أداة save_plan)
    عند تعذّر النموذج: خطة احتياطية بالقواعد مع تنبيه المستخدم.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from .budget import base_cost, calculate_budget
from .config import Settings, get_settings
from .database import Database
from .exceptions import APIUnavailableError, InvalidInputError, InvalidModelResponseError, TravelPlannerError
from .exporter import parse_import
from .fallback import build_fallback_plan
from .formatting import activities_table, plan_to_text
from .schemas import BudgetReport, TravelPlan, TripRequest
from .validation import validate_plan, validate_request

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3          # محاولات توليد خطة صالحة
OVER_BUDGET_TOLERANCE = 0.10  # نسمح بتجاوز 10% قبل طلب خطة أوفر


@dataclass
class PlanResult:
    """ناتج إنشاء أو تعديل خطة، كما تعرضه الواجهة."""

    trip_id: int
    request: dict
    plan: TravelPlan
    budget: BudgetReport
    source: str                       # llm | fallback | imported
    warnings: list[str] = field(default_factory=list)
    attempts: int = 1


class TravelPlannerService:
    """واجهة برمجية واحدة يستخدمها تطبيق Streamlit ودفتر Colab."""

    def __init__(self, settings: Settings | None = None, db: Database | None = None, llm=None):
        self.settings = settings or get_settings()
        self.db = db or Database(self.settings.db_path)
        self.db.initialize()
        self._llm = llm            # يمكن حقن نموذج وهمي في الاختبارات
        self._tools = None
        self._planning_chain = None
        self._revision_chain = None

    # ---------------------------------------------------------- مكونات كسولة
    @property
    def tools(self):
        if self._tools is None:
            from .tools import make_tools  # استيراد متأخر: LangChain مطلوبة هنا فقط
            self._tools = make_tools(self.db)
        return self._tools

    def _get_llm(self):
        if self._llm is None:
            from .llm import build_llm
            self._llm = build_llm(self.settings)
        return self._llm

    def _get_planning_chain(self):
        if self._planning_chain is None:
            llm = self._get_llm()  # يرفع APIUnavailableError أولاً إن لم يوجد مفتاح
            from .chains import build_planning_chain
            self._planning_chain = build_planning_chain(llm, self.tools["search_activities"])
        return self._planning_chain

    def _get_revision_chain(self):
        if self._revision_chain is None:
            llm = self._get_llm()
            from .chains import build_revision_chain
            self._revision_chain = build_revision_chain(llm, self.db)
        return self._revision_chain

    @property
    def llm_available(self) -> bool:
        return self._llm is not None or self.settings.has_api_key

    # ---------------------------------------------------------- إنشاء خطة
    def create_plan(self, raw_request: dict) -> PlanResult:
        request, warnings = validate_request(dict(raw_request), self.db, self.settings)
        destination = self.db.get_destination(request.destination)
        activities = self.db.search_activities(request.destination, request.interest_codes)
        available = {a["id"]: a for a in activities}

        try:
            plan, attempts, extra = self._generate_with_llm(request, destination, available)
            source = "llm"
            warnings += extra
        except (APIUnavailableError, InvalidModelResponseError) as exc:
            logger.warning("Fallback planner used: %s", exc)
            plan = build_fallback_plan(request, activities)
            source, attempts = "fallback", 0
            warnings.append(f"{exc.user_message} — عُرضت خطة احتياطية مبسطة من البيانات المحلية.")

        budget = self._budget(request, plan)
        trip_id = self._save(request, plan, budget.total, source)
        return PlanResult(trip_id, request.model_dump(), plan, budget, source, warnings + budget.warnings, attempts)

    def _generate_with_llm(self, request: TripRequest, destination: dict,
                           available: dict[int, dict]) -> tuple[TravelPlan, int, list[str]]:
        """يستدعي السلسلة حتى MAX_ATTEMPTS مع تغذية راجعة بالأخطاء."""
        chain = self._get_planning_chain()
        base = base_cost(destination, request.days, request.travelers)
        inputs = {
            "destination": request.destination,
            "destination_description": destination["description"],
            "categories": request.interest_codes,
            "days": request.days,
            "travelers": request.travelers,
            "budget": f"{request.budget:,.0f}",
            "base_cost": f"{base:,.0f}",
            "activities_budget": f"{max(request.budget - base, 0):,.0f}",
            "interests": "، ".join(request.interests),
            "notes": request.notes or "لا يوجد",
            "max_per_day": self.settings.max_activities_per_day,
            "feedback": "",
        }
        last_error = ""
        best: TravelPlan | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                plan: TravelPlan = chain.invoke(inputs)
            except TravelPlannerError:
                raise
            except Exception as exc:  # أخطاء التحليل أو الخدمة
                if _is_parse_error(exc):
                    last_error = "الرد لم يكن JSON مطابقاً للتنسيق."
                    inputs["feedback"] = _feedback([last_error])
                    continue
                from .llm import translate_llm_error
                raise translate_llm_error(exc) from exc

            issues = validate_plan(plan, request, available, self.settings.max_activities_per_day)
            if issues:
                last_error = "؛ ".join(issues)
                inputs["feedback"] = _feedback(issues)
                continue

            best = plan
            report = self._budget(request, plan)
            over = -report.remaining
            if over > request.budget * OVER_BUDGET_TOLERANCE and attempt < MAX_ATTEMPTS:
                inputs["feedback"] = _feedback(
                    [f"الخطة تتجاوز الميزانية بنحو {over:,.0f} ريال؛ استبدل الأنشطة المكلفة بأنشطة مجانية أو أرخص."]
                )
                continue
            return plan, attempt, []

        if best is not None:  # خطة صحيحة لكنها فوق الميزانية بعد كل المحاولات
            return best, MAX_ATTEMPTS, ["تعذّر الوصول لخطة ضمن الميزانية بالأنشطة المتاحة."]
        raise InvalidModelResponseError(f"رد النموذج غير مناسب بعد {MAX_ATTEMPTS} محاولات: {last_error}")

    # ---------------------------------------------------------- تعديل خطة
    def revise_plan(self, trip_id: int, user_request: str) -> PlanResult:
        user_request = (user_request or "").strip()
        if len(user_request) < 3:
            raise InvalidInputError("اكتب طلب التعديل بوضوح (مثال: استبدل نشاط اليوم الثاني بنشاط بحري).")
        if len(user_request) > 400:
            raise InvalidInputError("طلب التعديل طويل جداً (400 حرف كحد أقصى).")

        trip = self.db.get_trip(trip_id)
        if not trip or not trip["plan"]:
            raise InvalidInputError("الرحلة غير موجودة.")
        if not self.llm_available:
            raise APIUnavailableError("التعديل بالمحادثة يحتاج خدمة النموذج اللغوي. أضف مفتاح GROQ_API_KEY.")

        request = TripRequest(**{k: trip[k] for k in ("destination", "days", "travelers", "budget", "interests")})
        activities = self.db.search_activities(request.destination, request.interest_codes)
        available = {a["id"]: a for a in activities}
        chain = self._get_revision_chain()
        inputs = {
            "trip_context": (f"الوجهة {request.destination}، {request.days} أيام، {request.travelers} مسافر، "
                             f"الميزانية {request.budget:,.0f} ريال، الاهتمامات: {'، '.join(request.interests)}"),
            "current_plan": json.dumps(trip["plan"], ensure_ascii=False),
            "activities_table": activities_table(activities),
            "request": user_request,
            "max_per_day": self.settings.max_activities_per_day,
            "feedback": "",
        }
        config = {"configurable": {"session_id": f"trip-{trip_id}"}}

        last_error = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                plan: TravelPlan = chain.invoke(inputs, config=config)
            except TravelPlannerError:
                raise
            except Exception as exc:
                if _is_parse_error(exc):
                    last_error = "الرد لم يكن JSON مطابقاً للتنسيق."
                    inputs["feedback"] = _feedback([last_error])
                    continue
                from .llm import translate_llm_error
                raise translate_llm_error(exc) from exc
            issues = validate_plan(plan, request, available, self.settings.max_activities_per_day)
            if not issues:
                budget = self._budget(request, plan)
                self._save(request, plan, budget.total, "llm", trip_id=trip_id)
                return PlanResult(trip_id, request.model_dump(), plan, budget, "llm", budget.warnings, attempt)
            last_error = "؛ ".join(issues)
            inputs["feedback"] = _feedback(issues)
        raise InvalidModelResponseError(f"تعذّر تطبيق التعديل؛ بقيت الخطة السابقة كما هي. ({last_error})")

    # ---------------------------------------------------------- أدوات مساعدة
    def _budget(self, request: TripRequest, plan: TravelPlan) -> BudgetReport:
        ids = [i.activity_id for d in plan.days for i in d.items]
        if self._tools is not None or _langchain_installed():
            data = self.tools["calculate_budget"].invoke({
                "destination": request.destination, "days": request.days,
                "travelers": request.travelers, "budget": request.budget, "activity_ids": ids,
            })
            return BudgetReport.model_validate(data)
        # مسار بديل إن لم تكن LangChain مثبتة (للاختبارات الأساسية فقط)
        dest = self.db.get_destination(request.destination)
        return calculate_budget(dest, request.days, request.travelers, request.budget,
                                list(self.db.get_activities_by_ids(ids).values()))

    def _save(self, request: TripRequest, plan: TravelPlan, total: float, source: str,
              trip_id: int | None = None) -> int:
        payload = {"request": request.model_dump(), "plan": plan.model_dump(), "total_cost": total,
                   "source": source, "trip_id": trip_id}
        if self._tools is not None or _langchain_installed():
            return self.tools["save_plan"].invoke(payload)
        return self.db.save_trip(payload["request"], payload["plan"], total, source=source, trip_id=trip_id)

    # ---------------------------------------------------------- الخطط المحفوظة
    def list_trips(self) -> list[dict]:
        return self.db.list_trips()

    def load_trip(self, trip_id: int) -> PlanResult:
        trip = self.db.get_trip(trip_id)
        if not trip:
            raise InvalidInputError("الرحلة غير موجودة.")
        request = TripRequest(**{k: trip[k] for k in ("destination", "days", "travelers", "budget", "interests")})
        plan = TravelPlan.model_validate(trip["plan"])
        budget = self._budget(request, plan)
        return PlanResult(trip_id, request.model_dump(), plan, budget, trip["source"], budget.warnings, 0)

    def delete_trip(self, trip_id: int) -> None:
        self.db.delete_trip(trip_id)

    def chat_history(self, trip_id: int) -> list[dict]:
        return self.db.get_messages(f"trip-{trip_id}")

    def export_text(self, result: PlanResult) -> str:
        ids = [i.activity_id for d in result.plan.days for i in d.items]
        return plan_to_text(result.plan, result.request, result.budget, self.db.get_activities_by_ids(ids))

    def import_plan(self, filename: str, data: bytes) -> PlanResult:
        """يستورد خطة JSON ويتحقق منها مقابل قاعدة البيانات قبل حفظها."""
        raw_request, plan = parse_import(filename, data)
        request, _ = validate_request(raw_request, self.db, self.settings)
        available = {a["id"]: a for a in self.db.search_activities(request.destination)}
        issues = validate_plan(plan, request, available, self.settings.max_activities_per_day)
        if issues:
            raise InvalidInputError("الخطة المستوردة لا تطابق البيانات: " + "؛ ".join(issues))
        budget = self._budget(request, plan)
        trip_id = self._save(request, plan, budget.total, "imported")
        return PlanResult(trip_id, request.model_dump(), plan, budget, "imported", budget.warnings, 0)


def _feedback(issues: list[str]) -> str:
    bullet = "\n".join(f"- {i}" for i in issues)
    return f"## تنبيه: محاولتك السابقة رُفضت للأسباب التالية، صحّحها\n{bullet}"


def _is_parse_error(exc: Exception) -> bool:
    return type(exc).__name__ in {"OutputParserException", "ValidationError", "JSONDecodeError"}


def _langchain_installed() -> bool:
    try:
        import langchain_core  # noqa: F401
        return True
    except ImportError:
        return False
