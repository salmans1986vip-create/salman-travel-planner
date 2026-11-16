"""
اختبارات مكونات LangChain بنموذج وهمي (FakeListChatModel) — لا تحتاج مفتاح API.
تُتخطى تلقائياً إذا لم تكن LangChain مثبتة. تعمل في Colab بعد تثبيت requirements.txt.
"""
import json

import pytest

pytest.importorskip("langchain_core")

from langchain_core.language_models.fake_chat_models import FakeListChatModel  # noqa: E402

from travel_planner.chains import SQLiteChatHistory  # noqa: E402
from travel_planner.formatting import activities_table  # noqa: E402
from travel_planner.planner import TravelPlannerService  # noqa: E402
from travel_planner.prompts import planning_prompt  # noqa: E402
from travel_planner.tools import make_tools  # noqa: E402


def plan_json(days_ids, summary="رحلة تراثية"):
    return json.dumps({
        "summary": summary,
        "days": [
            {"day_number": n, "title": f"يوم {n}",
             "items": [{"activity_id": i, "activity_name": "اسم", "time_slot": "صباحاً", "reason": "مناسب"} for i in ids]}
            for n, ids in enumerate(days_ids, start=1)
        ],
        "tips": ["احجز مبكراً"],
    }, ensure_ascii=False)


def service_with(settings, responses):
    return TravelPlannerService(settings=settings, llm=FakeListChatModel(responses=responses))


def test_prompt_contains_rules_and_table(db):
    acts = db.search_activities("جدة")
    msgs = planning_prompt().format_messages(
        destination="جدة", destination_description="", days=2, travelers=2, budget="5,000",
        base_cost="1,000", activities_budget="4,000", interests="تسوق", notes="", max_per_day=4,
        activities_table=activities_table(acts), feedback="", format_instructions="JSON")
    assert "لا تخترع" in msgs[0].content
    assert acts[0]["name"] in msgs[1].content


def test_tools_work(db):
    tools = make_tools(db)
    acts = tools["search_activities"].invoke({"destination": "جدة", "categories": ["food"]})
    assert acts[0]["category"] == "food"
    report = tools["calculate_budget"].invoke({"destination": "جدة", "days": 1, "travelers": 1,
                                                "budget": 1000, "activity_ids": [acts[0]["id"]]})
    assert report["total"] > 0


def test_chain_produces_structured_plan(settings, valid_request):
    service = service_with(settings, [f"```json\n{plan_json([[1, 2], [3, 4]])}\n```"])
    result = service.create_plan(valid_request)
    assert result.source == "llm" and result.attempts == 1
    assert len(result.plan.days) == 2
    # الاسم صُحّح من قاعدة البيانات بدل "اسم"
    assert result.plan.days[0].items[0].activity_name != "اسم"


def test_hallucinated_activity_triggers_retry(settings, valid_request):
    service = service_with(settings, [plan_json([[999, 2], [3, 4]]), plan_json([[1, 2], [3, 4]])])
    result = service.create_plan(valid_request)
    assert result.source == "llm" and result.attempts == 2


def test_malformed_response_triggers_retry(settings, valid_request):
    service = service_with(settings, ["عذراً لا أستطيع", plan_json([[1, 2], [3, 4]])])
    assert service.create_plan(valid_request).attempts == 2


def test_persistently_bad_model_falls_back(settings, valid_request):
    service = service_with(settings, ["نص غير منظم"])
    result = service.create_plan(valid_request)
    assert result.source == "fallback"
    assert any("غير مناسب" in w for w in result.warnings)


def test_revision_uses_memory(settings, valid_request):
    service = service_with(settings, [plan_json([[1, 2], [3, 4]]),
                                      plan_json([[5, 6], [3, 4]], summary="بعد التعديل")])
    created = service.create_plan(valid_request)
    revised = service.revise_plan(created.trip_id, "غيّر أنشطة اليوم الأول")
    assert revised.plan.summary == "بعد التعديل"
    history = SQLiteChatHistory(service.db, f"trip-{created.trip_id}").messages
    assert [m.type for m in history] == ["human", "ai"]
    assert service.db.get_trip(created.trip_id)["plan"]["summary"] == "بعد التعديل"
