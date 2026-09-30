"""Test setup: temp database, fake API key, and a fake Gemini client (no network, no cost)."""
import os
import sys
import tempfile
from pathlib import Path

# These must be set BEFORE the app is imported (config reads them at import time).
_TMP = tempfile.mkdtemp(prefix="fitbuddy_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP, 'test.db').as_posix()}"
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["GEMINI_PRO_MODEL"] = "test-pro"
os.environ["GEMINI_FLASH_MODEL"] = "test-flash"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app import gemini_client
from app.database import Base, engine
from app.main import app


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, owner):
        self.owner = owner

    def generate_content(self, model, contents, **kwargs):
        self.owner.calls.append((model, contents))
        return FakeResponse(self.owner.handler(model, contents))


class FakeGemini:
    """Stands in for google.genai.Client. Replace `.handler` to script replies or raise errors."""

    def __init__(self):
        self.calls = []            # list of (model, prompt)
        self.models = FakeModels(self)
        self.handler = self.default_handler

    @staticmethod
    def default_handler(model, prompt):
        if "User Feedback" in prompt:
            return "UPDATED PLAN (" + model + ")"
        if "nutrition or recovery tip" in prompt:
            return "Eat more protein. (" + model + ")"
        return "Day 1: Warm-up ... (" + model + ")"

    def prompts_for(self, model):
        return [p for m, p in self.calls if m == model]


def api_error(code, message="boom"):
    exc = Exception(message)
    exc.code = code
    return exc


@pytest.fixture()
def gemini(monkeypatch):
    fake = FakeGemini()
    monkeypatch.setattr(gemini_client, "get_client", lambda: fake)
    return fake


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:      # `with` runs the startup hook, which creates the tables
        yield c
