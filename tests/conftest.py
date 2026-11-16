"""إعدادات مشتركة للاختبارات: قاعدة بيانات مؤقتة وإعدادات بلا مفتاح API."""
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from travel_planner.config import get_settings  # noqa: E402
from travel_planner.database import Database  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    return replace(get_settings(), groq_api_key=None, db_path=tmp_path / "test.db")


@pytest.fixture
def db(settings):
    database = Database(settings.db_path)
    database.initialize()
    return database


@pytest.fixture
def valid_request():
    return {"destination": "جدة", "days": 2, "travelers": 2, "budget": 5000,
            "interests": ["تاريخ وتراث"], "notes": ""}
