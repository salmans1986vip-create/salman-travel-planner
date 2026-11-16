"""
ربط النموذج اللغوي (Groq) عبر LangChain، وتحويل أخطاء الخدمة إلى رسائل مفهومة.
"""
from __future__ import annotations

from .config import Settings
from .exceptions import APIUnavailableError


def build_llm(settings: Settings):
    """ينشئ ChatGroq. يرفع APIUnavailableError إذا لم يوجد مفتاح أو المكتبة."""
    if not settings.has_api_key:
        raise APIUnavailableError(
            "لم يُعثر على مفتاح GROQ_API_KEY. أضفه في ملف .env أو في أسرار Colab."
        )
    try:
        from langchain_groq import ChatGroq
    except ImportError as exc:  # pragma: no cover
        raise APIUnavailableError("مكتبة langchain-groq غير مثبتة. شغّل: pip install -r requirements.txt") from exc

    return ChatGroq(
        model=settings.model_name,
        temperature=settings.temperature,
        max_retries=settings.max_retries,  # إعادة المحاولة التلقائية عند أخطاء الشبكة المؤقتة
        timeout=settings.request_timeout,
        api_key=settings.groq_api_key,
    )


def translate_llm_error(exc: Exception) -> APIUnavailableError:
    """
    يحوّل أخطاء مكتبة Groq/الشبكة إلى رسالة عربية واضحة.
    نعتمد على اسم الصنف حتى لا نربط الكود بإصدار معين من المكتبة.
    """
    name = type(exc).__name__
    if "Authentication" in name or "401" in str(exc):
        return APIUnavailableError("مفتاح Groq غير صحيح أو منتهي الصلاحية.")
    if "RateLimit" in name or "429" in str(exc):
        return APIUnavailableError("تم تجاوز حد الطلبات في Groq. انتظر دقيقة ثم أعد المحاولة.")
    if "Connection" in name or "Timeout" in name:
        return APIUnavailableError("تعذّر الاتصال بخدمة Groq. تحقق من الإنترنت.")
    if "NotFound" in name or ("model" in str(exc).lower() and "not found" in str(exc).lower()):
        return APIUnavailableError("اسم النموذج غير متاح في Groq. غيّر GROQ_MODEL في ملف .env.")
    return APIUnavailableError(f"خطأ من خدمة النموذج: {name}")
