import sys
import types
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.api.v1.endpoints import health as health_endpoint
from app.services.audit_service import _integration_summary
from app.integrations.llm import base
from app.integrations.llm.gemini import GeminiProvider
from app.integrations.llm.groq import GroqProvider


class ProviderError(Exception):
    def __init__(self, status_code, message="provider failure"):
        super().__init__(message)
        self.status_code = status_code


@pytest.fixture(autouse=True)
def clear_provider_health():
    base._provider_health.clear()
    yield
    base._provider_health.clear()


def install_gemini_sdk(monkeypatch, *, models, failures=None, listing_error=None):
    calls = []
    failures = failures or {}

    class FakeModel:
        def __init__(self, model_name):
            self.model_name = model_name

        def generate_content(self, prompt, generation_config):
            calls.append((self.model_name, prompt, generation_config))
            model_failures = failures.get(self.model_name, [])
            if model_failures:
                raise model_failures.pop(0)
            return SimpleNamespace(
                text="mock Gemini response",
                usage_metadata=SimpleNamespace(total_token_count=4),
            )

    genai = types.ModuleType("google.generativeai")
    genai.configure = lambda **kwargs: None
    genai.GenerativeModel = FakeModel

    def list_models():
        if listing_error:
            raise listing_error
        return [
            SimpleNamespace(
                name=f"models/{model_name}",
                supported_generation_methods=["generateContent"],
            )
            for model_name in models
        ]

    genai.list_models = list_models
    google = types.ModuleType("google")
    google.__path__ = []
    google.generativeai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.generativeai", genai)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "mock-secret")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "configured-gemini")
    monkeypatch.setattr(settings, "GEMINI_FALLBACK_MODEL", None)
    return calls


def install_groq_sdk(monkeypatch, *, models, failures=None, listing_error=None):
    calls = []
    failures = failures or {}

    class FakeCompletions:
        def create(self, *, model, messages, temperature, max_tokens):
            calls.append((model, messages, temperature, max_tokens))
            model_failures = failures.get(model, [])
            if model_failures:
                raise model_failures.pop(0)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="mock Groq response"))],
                usage=SimpleNamespace(total_tokens=5),
            )

    class FakeGroq:
        def __init__(self, api_key):
            self.models = SimpleNamespace(list=self.list_models)
            self.chat = SimpleNamespace(completions=FakeCompletions())

        def list_models(self):
            if listing_error:
                raise listing_error
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        id=getattr(model, "id", model),
                        active=getattr(model, "active", True),
                        max_completion_tokens=getattr(model, "max_completion_tokens", None),
                    )
                    for model in models
                ]
            )

    groq = types.ModuleType("groq")
    groq.Groq = FakeGroq
    monkeypatch.setitem(sys.modules, "groq", groq)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "mock-secret")
    monkeypatch.setattr(settings, "GROQ_MODEL", "configured-groq")
    monkeypatch.setattr(settings, "GROQ_FALLBACK_MODEL", None)
    return calls


def test_gemini_probe_checks_catalog_and_generation(monkeypatch):
    calls = install_gemini_sdk(monkeypatch, models=["configured-gemini"])
    provider = GeminiProvider()

    health = provider.check_availability(probe=True)

    assert health["connection_status"] == "Connected"
    assert health["configured_model"] == "configured-gemini"
    assert health["active_model"] == "configured-gemini"
    assert health["last_successful_test"]
    assert calls[0][0] == "configured-gemini"


def test_gemini_uses_listed_fallback_for_unavailable_configured_model(monkeypatch):
    calls = install_gemini_sdk(monkeypatch, models=["listed-gemini-flash"])
    provider = GeminiProvider()

    health = provider.check_availability(probe=True)

    assert health["connection_status"] == "Degraded"
    assert health["configured_model"] == "configured-gemini"
    assert health["active_model"] == "listed-gemini-flash"
    assert calls[0][0] == "listed-gemini-flash"


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (ProviderError(401, "invalid api key mock-secret"), "authentication"),
        (ProviderError(429, "rate limit"), "quota"),
        (TimeoutError("request timed out"), "network"),
    ],
)
def test_gemini_classifies_failures_without_exposing_credentials(monkeypatch, error, category):
    calls = install_gemini_sdk(
        monkeypatch,
        models=["configured-gemini"],
        failures={"configured-gemini": [error]},
    )
    response = GeminiProvider().generate("test prompt")

    assert not response.is_live
    assert response.error_category == category
    assert "mock-secret" not in (response.error or "")
    assert len(calls) == 1


def test_gemini_fallback_error_is_returned_not_raised(monkeypatch):
    calls = install_gemini_sdk(
        monkeypatch,
        models=["listed-gemini-flash"],
        failures={
            "configured-gemini": [ProviderError(404, "model not found")],
            "listed-gemini-flash": [ProviderError(429, "rate limit")],
        },
    )
    response = GeminiProvider().generate("test prompt")

    assert not response.is_live
    assert response.error_category == "quota"
    assert [call[0] for call in calls] == ["configured-gemini", "listed-gemini-flash"]


def test_groq_probe_checks_catalog_and_generation(monkeypatch):
    calls = install_groq_sdk(monkeypatch, models=["configured-groq"])
    health = GroqProvider().check_availability(probe=True)

    assert health["connection_status"] == "Connected"
    assert health["configured_model"] == "configured-groq"
    assert health["active_model"] == "configured-groq"
    assert health["last_successful_test"]
    assert calls[0][0] == "configured-groq"


def test_groq_respects_listed_model_output_limit(monkeypatch):
    calls = install_groq_sdk(
        monkeypatch,
        models=[
            SimpleNamespace(id="configured-groq", max_completion_tokens=512)
        ],
    )
    health = GroqProvider().check_availability(probe=True)

    assert health["connection_status"] == "Connected"
    assert calls[0][3] == 512


def test_groq_uses_listed_fallback_and_returns_generation(monkeypatch):
    calls = install_groq_sdk(
        monkeypatch,
        models=["listed-groq-chat"],
        failures={"configured-groq": [ProviderError(404, "model_not_found")]},
    )
    response = GroqProvider().generate("test prompt")

    assert response.is_live
    assert response.content == "mock Groq response"
    assert response.model == "listed-groq-chat"
    assert response.configured_model == "configured-groq"
    assert calls[0][0] == "configured-groq"
    assert calls[1][0] == "listed-groq-chat"


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (ProviderError(401, "invalid api key mock-secret"), "authentication"),
        (ProviderError(429, "rate limit"), "quota"),
        (TimeoutError("request timed out"), "network"),
    ],
)
def test_groq_classifies_failures_without_exposing_credentials(monkeypatch, error, category):
    install_groq_sdk(
        monkeypatch,
        models=["configured-groq"],
        failures={"configured-groq": [error]},
    )
    response = GroqProvider().generate("test prompt")

    assert not response.is_live
    assert response.error_category == category
    assert "mock-secret" not in (response.error or "")


def test_groq_fallback_failure_is_returned_not_raised(monkeypatch):
    calls = install_groq_sdk(
        monkeypatch,
        models=["listed-groq-chat"],
        failures={
            "configured-groq": [ProviderError(404, "model_not_found")],
            "listed-groq-chat": [ProviderError(429, "rate limit")],
        },
    )
    response = GroqProvider().generate("test prompt")

    assert not response.is_live
    assert response.error_category == "quota"
    assert [call[0] for call in calls] == ["configured-groq", "listed-groq-chat"]


@pytest.mark.parametrize(
    ("provider_cls", "api_key_attr", "model_attr"),
    [
        (GeminiProvider, "GEMINI_API_KEY", "GEMINI_MODEL"),
        (GroqProvider, "GROQ_API_KEY", "GROQ_MODEL"),
    ],
)
def test_provider_is_not_reported_operational_before_probe(
    monkeypatch, provider_cls, api_key_attr, model_attr
):
    monkeypatch.setattr(settings, api_key_attr, "mock-secret")
    provider = provider_cls()

    health = provider.check_availability()

    assert health["connection_status"] == "Unavailable"
    assert health["active_model"] is None
    assert health["last_successful_test"] is None


def test_integrations_health_uses_cached_status_unless_probe_is_requested(monkeypatch):
    monkeypatch.setattr(
        health_endpoint,
        "get_cached_integrations_status",
        lambda: {"status": "cached"},
    )
    monkeypatch.setattr(
        health_endpoint,
        "run_integrations_audit",
        lambda probe_ai: {"probed": probe_ai},
    )
    test_app = FastAPI()
    test_app.include_router(health_endpoint.router, prefix="/api/v1")

    with TestClient(test_app) as client:
        assert client.get("/api/v1/health/integrations").json() == {"status": "cached"}
        assert client.get("/api/v1/health/integrations?probe=true").json() == {"probed": True}


def test_integration_summary_sanitizes_provider_errors():
    summary = _integration_summary([
        {
            "provider": "Marketaux",
            "status": "Failed",
            "configured": True,
            "operational": False,
            "model": "Marketaux API",
            "http_status": 401,
            "error": "authorization failed with key=mock-secret",
        }
    ])
    result = summary["integrations"][0]

    assert result["status"] == "Unavailable"
    assert result["error_category"] == "authentication"
    assert result["error_message"] == "Provider authentication failed."
    assert "mock-secret" not in result["error"]
