"""
اختبارات المنطق الأساسي (لا تحتاج إنترنت ولا LangChain):
قاعدة البيانات، التحقق، الميزانية، الخطة الاحتياطية، الاستيراد والتصدير، معالجة الأخطاء.
"""
import json

import pytest

from travel_planner.budget import calculate_budget, nights_for, rooms_needed
from travel_planner.database import Database
from travel_planner.exceptions import (APIUnavailableError, DatabaseUnavailableError, InvalidInputError,
                                       UnsupportedFileError)
from travel_planner.exporter import export_json, parse_import
from travel_planner.fallback import build_fallback_plan
from travel_planner.planner import TravelPlannerService
from travel_planner.schemas import DayPlan, PlanItem, TravelPlan, TripRequest
from travel_planner.validation import validate_plan, validate_request


# ---------------------------------------------------------------- قاعدة البيانات
def test_seed_creates_three_destinations(db):
    names = [d["name"] for d in db.list_destinations()]
    assert names == ["جدة", "العلا", "المدينة المنورة"]


def test_seed_runs_only_once(db):
    db.initialize()  # تشغيل ثانٍ لا يكرر البيانات
    assert len(db.list_destinations()) == 3


def test_search_prioritises_interests(db):
    acts = db.search_activities("جدة", ["nature"])
    assert acts[0]["category"] == "nature"
    assert all(a["destination_id"] == acts[0]["destination_id"] for a in acts)


def test_unavailable_database_raises_friendly_error(tmp_path):
    blocker = tmp_path / "file.txt"
    blocker.write_text("x")
    bad = Database(blocker / "sub" / "db.sqlite")  # مسار تحت ملف عادي = غير صالح
    with pytest.raises(DatabaseUnavailableError):
        bad.initialize()


# ---------------------------------------------------------------- التحقق من المدخلات
def test_valid_request_passes(db, settings, valid_request):
    req, warnings = validate_request(valid_request, db, settings)
    assert req.days == 2 and warnings == []


@pytest.mark.parametrize("field,value,msg", [
    ("days", 0, "عدد الأيام"),
    ("days", 15, "عدد الأيام"),
    ("travelers", 0, "عدد المسافرين"),
    ("budget", -50, "الميزانية"),
    ("days", "ثلاثة", "رقماً"),
    ("interests", [], "الاهتمامات"),
    ("interests", ["سباحة فضائية"], "غير مدعومة"),
])
def test_invalid_inputs_rejected(db, settings, valid_request, field, value, msg):
    valid_request[field] = value
    with pytest.raises(InvalidInputError) as err:
        validate_request(valid_request, db, settings)
    assert msg in err.value.user_message


def test_unknown_destination_lists_available(db, settings, valid_request):
    valid_request["destination"] = "باريس"
    with pytest.raises(InvalidInputError) as err:
        validate_request(valid_request, db, settings)
    assert "المدينة المنورة" in err.value.user_message


def test_low_budget_gives_warning_not_error(db, settings, valid_request):
    valid_request["budget"] = 300
    _, warnings = validate_request(valid_request, db, settings)
    assert warnings and "أقل من التكلفة الأساسية" in warnings[0]


# ---------------------------------------------------------------- الميزانية
def test_rooms_and_nights():
    assert rooms_needed(1) == 1 and rooms_needed(3) == 2
    assert nights_for(1) == 0 and nights_for(3) == 2


def test_budget_arithmetic(db):
    dest = db.get_destination("المدينة المنورة")  # فندق 450، أكل 120، تنقل 150
    acts = [{"name": "أ", "cost_per_person": 100}, {"name": "ب", "cost_per_person": 0}]
    r = calculate_budget(dest, days=3, travelers=2, budget=5000, activities=acts)
    # سكن 450×1×2=900، أكل 120×2×3=720، تنقل 150×3=450، أنشطة 100×2=200
    assert r.total == 2270
    assert r.remaining == 2730 and r.within_budget


def test_budget_overrun_warning(db):
    dest = db.get_destination("العلا")
    r = calculate_budget(dest, days=3, travelers=4, budget=1000, activities=[])
    assert not r.within_budget
    assert "تتجاوز الميزانية" in r.warnings[0]


# ---------------------------------------------------------------- التحقق من خطة النموذج
def _plan(days):
    return TravelPlan(summary="s", days=[
        DayPlan(day_number=n, title="t", items=[PlanItem(activity_id=i, activity_name="x", time_slot="صباحاً", reason="r")
                                                for i in ids])
        for n, ids in enumerate(days, start=1)
    ])


def test_validate_plan_detects_hallucination_and_duplicates(db):
    req = TripRequest(destination="جدة", days=2, travelers=1, budget=3000, interests=["تسوق"])
    available = {a["id"]: a for a in db.search_activities("جدة")}
    first = next(iter(available))
    issues = validate_plan(_plan([[first, 9999], [first]]), req, available)
    assert any("9999" in i for i in issues)
    assert any("مكرر" in i for i in issues)


def test_validate_plan_wrong_day_count(db):
    req = TripRequest(destination="جدة", days=3, travelers=1, budget=3000, interests=["تسوق"])
    available = {a["id"]: a for a in db.search_activities("جدة")}
    ids = list(available)
    issues = validate_plan(_plan([[ids[0]], [ids[1]]]), req, available)
    assert any("عدد الأيام" in i for i in issues)


def test_validate_plan_fixes_names(db):
    req = TripRequest(destination="جدة", days=1, travelers=1, budget=3000, interests=["تسوق"])
    available = {a["id"]: a for a in db.search_activities("جدة")}
    plan = _plan([[list(available)[0]]])
    assert validate_plan(plan, req, available) == []
    assert plan.days[0].items[0].activity_name == available[list(available)[0]]["name"]


# ---------------------------------------------------------------- الخطة الاحتياطية
def test_fallback_plan_is_valid(db):
    req = TripRequest(destination="العلا", days=3, travelers=2, budget=8000, interests=["طبيعة ومغامرة"])
    acts = db.search_activities("العلا", req.interest_codes)
    plan = build_fallback_plan(req, acts)
    assert len(plan.days) == 3
    assert validate_plan(plan, req, {a["id"]: a for a in acts}) == []


def test_service_without_api_key_uses_fallback(settings, valid_request):
    service = TravelPlannerService(settings=settings)
    result = service.create_plan(valid_request)
    assert result.source == "fallback"
    assert len(result.plan.days) == 2
    assert any("احتياطية" in w for w in result.warnings)
    assert service.list_trips()[0]["id"] == result.trip_id


def test_revision_without_api_key_is_explained(settings, valid_request):
    service = TravelPlannerService(settings=settings)
    trip = service.create_plan(valid_request)
    with pytest.raises(APIUnavailableError):
        service.revise_plan(trip.trip_id, "اجعل اليوم الأول أخف")


# ---------------------------------------------------------------- الاستيراد والتصدير
def test_export_import_roundtrip(settings, valid_request):
    service = TravelPlannerService(settings=settings)
    res = service.create_plan(valid_request)
    data = export_json(res.request, res.plan).encode("utf-8")
    imported = service.import_plan("trip.json", data)
    assert imported.source == "imported" and imported.budget.total == res.budget.total
    assert "اليوم 1" in service.export_text(res)


@pytest.mark.parametrize("name,data,msg", [
    ("plan.pdf", b"%PDF-1.4", "غير مدعوم"),
    ("plan.json", b"not json", "ليس JSON"),
    ("plan.json", json.dumps({"hello": 1}).encode(), "لم يُصدَّر"),
    ("plan.json", json.dumps({"app": "travel-planner", "request": {}, "plan": {"x": 1}}).encode(), "غير صحيحة"),
])
def test_unsupported_files_rejected(name, data, msg):
    with pytest.raises(UnsupportedFileError) as err:
        parse_import(name, data)
    assert msg in err.value.user_message
