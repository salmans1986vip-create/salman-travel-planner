"""
تصدير الخطط واستيرادها (JSON)، مع رفض الملفات غير المدعومة.
"""
from __future__ import annotations

import json

from pydantic import ValidationError

from .exceptions import UnsupportedFileError
from .schemas import TravelPlan

ALLOWED_EXTENSIONS = {".json"}
MAX_FILE_BYTES = 200_000
EXPORT_VERSION = 1


def export_json(request: dict, plan: TravelPlan) -> str:
    payload = {
        "app": "travel-planner",
        "version": EXPORT_VERSION,
        "request": request,
        "plan": plan.model_dump(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def parse_import(filename: str, data: bytes) -> tuple[dict, TravelPlan]:
    """يتحقق من الامتداد والحجم والترميز والبنية، ثم يرجع (الطلب، الخطة)."""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileError(f"الامتداد «{ext or 'بدون امتداد'}» غير مدعوم. يُقبل ملف .json فقط.")
    if len(data) > MAX_FILE_BYTES:
        raise UnsupportedFileError("حجم الملف كبير جداً (الحد 200 كيلوبايت).")
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnsupportedFileError("الملف ليس JSON صالحاً أو ترميزه ليس UTF-8.") from exc
    if not isinstance(payload, dict) or payload.get("app") != "travel-planner":
        raise UnsupportedFileError("هذا الملف لم يُصدَّر من مساعد تخطيط السفر.")
    try:
        plan = TravelPlan.model_validate(payload["plan"])
        request = dict(payload["request"])
    except (KeyError, ValidationError, TypeError) as exc:
        raise UnsupportedFileError("بنية الخطة داخل الملف غير صحيحة.") from exc
    return request, plan
