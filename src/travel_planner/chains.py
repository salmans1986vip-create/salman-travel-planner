"""
سلاسل LangChain (LCEL) والذاكرة.

سلسلة الإنشاء:
    المدخلات ─► [Retrieval: أداة search_activities] ─► ChatPromptTemplate ─► ChatGroq ─► PydanticOutputParser ─► TravelPlan

سلسلة التعديل:
    RunnableWithMessageHistory( revision_prompt | ChatGroq ) ─► PydanticOutputParser
    حيث يُحفظ سجل المحادثة في SQLite عبر SQLiteChatHistory، فيتذكر النموذج
    طلبات التعديل السابقة لنفس الرحلة.
"""
from __future__ import annotations

from typing import Sequence

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory

from .database import Database
from .formatting import activities_table
from .prompts import planning_prompt, revision_prompt
from .schemas import TravelPlan


# ---------------------------------------------------------------- الذاكرة
class SQLiteChatHistory(BaseChatMessageHistory):
    """سجل محادثة دائم في جدول chat_messages، مفتاحه رقم الجلسة (الرحلة)."""

    def __init__(self, db: Database, session_id: str, max_messages: int = 6):
        self.db = db
        self.session_id = session_id
        self.max_messages = max_messages  # آخر الرسائل فقط حتى لا يطول السياق

    @property
    def messages(self) -> list[BaseMessage]:  # type: ignore[override]
        rows = self.db.get_messages(self.session_id)[-self.max_messages:]
        return [HumanMessage(r["content"]) if r["role"] == "human" else AIMessage(r["content"]) for r in rows]

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        for m in messages:
            role = "human" if m.type == "human" else "ai"
            content = m.content if isinstance(m.content, str) else str(m.content)
            if role == "ai":
                # نحفظ ملخصاً مختصراً لرد النموذج بدل JSON كاملاً لتوفير السياق
                content = _summarize_ai_plan(content)
            self.db.add_message(self.session_id, role, content)

    def clear(self) -> None:
        self.db.clear_messages(self.session_id)


def _summarize_ai_plan(raw: str) -> str:
    try:
        plan = TravelPlan.model_validate_json(_extract_json(raw))
        days = "؛ ".join(
            f"اليوم {d.day_number}: " + "، ".join(i.activity_name for i in d.items) for d in plan.days
        )
        return f"عدّلتُ الخطة. {plan.summary} ({days})"
    except Exception:  # الرد ليس JSON صالحاً
        return raw[:500]


def _extract_json(text: str) -> str:
    """يقتطع كتلة JSON من الرد حتى لو أحاطها النموذج بعلامات ```."""
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end != -1 else text


# ---------------------------------------------------------------- المحلل
def plan_parser() -> PydanticOutputParser:
    return PydanticOutputParser(pydantic_object=TravelPlan)


def _clean_llm_output(message: AIMessage) -> str:
    """تنظيف بسيط قبل التحليل: إزالة أي نص خارج كتلة JSON."""
    return _extract_json(message.content if isinstance(message.content, str) else str(message.content))


# ---------------------------------------------------------- سلسلة الإنشاء
def build_planning_chain(llm, search_tool) -> Runnable:
    """
    سلسلة LCEL كاملة: استرجاع ─► قالب ─► نموذج ─► تنظيف ─► محلل Pydantic.
    search_tool: أداة LangChain (search_activities) تُستدعى أولاً لجلب السياق.
    """
    parser = plan_parser()

    def retrieve(inputs: dict) -> str:
        acts = search_tool.invoke({"destination": inputs["destination"], "categories": inputs["categories"]})
        return activities_table(acts)

    return (
        RunnablePassthrough.assign(
            activities_table=RunnableLambda(retrieve),
            format_instructions=lambda _: parser.get_format_instructions(),
        )
        | planning_prompt()
        | llm
        | RunnableLambda(_clean_llm_output)
        | parser
    )


# ---------------------------------------------------------- سلسلة التعديل
def build_revision_chain(llm, db: Database) -> Runnable:
    """سلسلة تعديل الخطة مع ذاكرة محادثة دائمة لكل رحلة."""
    parser = plan_parser()
    core = revision_prompt() | llm  # يخرج AIMessage حتى تحفظه الذاكرة

    with_history = RunnableWithMessageHistory(
        core,
        lambda session_id: SQLiteChatHistory(db, session_id),
        input_messages_key="request",
        history_messages_key="history",
    )
    return (
        RunnablePassthrough.assign(format_instructions=lambda _: parser.get_format_instructions())
        | with_history
        | RunnableLambda(_clean_llm_output)
        | parser
    )
