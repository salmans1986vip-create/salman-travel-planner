"""
إعدادات التطبيق المركزية.

تُقرأ كل القيم الحساسة (مثل مفتاح Groq) من ملف .env أو من متغيرات البيئة،
ولا يُكتب أي مفتاح داخل الكود إطلاقاً.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv اختياري: إن لم يكن مثبتاً نكتفي بمتغيرات البيئة
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

# جذر المشروع (المجلد الذي يحتوي app.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """قيم الإعداد التي يحتاجها التطبيق."""

    groq_api_key: str | None
    model_name: str
    temperature: float
    max_retries: int
    request_timeout: int
    db_path: Path

    # حدود التحقق من المدخلات
    min_days: int = 1
    max_days: int = 7
    min_travelers: int = 1
    max_travelers: int = 10
    min_budget: float = 100.0
    max_budget: float = 200_000.0
    max_activities_per_day: int = 4

    @property
    def has_api_key(self) -> bool:
        return bool(self.groq_api_key and self.groq_api_key.strip())


def get_settings() -> Settings:
    """يبني كائن الإعدادات من متغيرات البيئة مع قيم افتراضية آمنة."""
    db_path = Path(os.getenv("TRAVEL_DB_PATH", PROJECT_ROOT / "data" / "travel_planner.db"))
    return Settings(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
        max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
        request_timeout=int(os.getenv("LLM_TIMEOUT", "60")),
        db_path=db_path,
    )
