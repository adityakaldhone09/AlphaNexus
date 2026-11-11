from abc import ABC, abstractmethod
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, Any, Optional
from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    provider: str
    model: str
    tokens_used: int = 0
    message_type: str = "synthesis"  # fact_grounded, calculated, synthesis
    is_live: bool = True
    error: Optional[str] = None
    error_category: Optional[str] = None
    configured_model: Optional[str] = None


_health_lock = Lock()
_provider_health: Dict[str, Dict[str, Any]] = {}


def classify_provider_error(error: Exception) -> tuple[str, str]:
    status_code = getattr(error, "status_code", None)
    if status_code is None:
        status_code = getattr(error, "code", None)
    message = str(error).lower()

    if status_code == 429 or any(
        marker in message for marker in ("rate limit", "resource_exhausted", "quota exceeded", "too many requests")
    ):
        return "quota", "Provider rate limit or quota was reached."
    if status_code == 404 or any(
        marker in message for marker in ("model_not_found", "model not found", "not found")
    ):
        return "model_not_found", "The requested model is unavailable to this account."
    if isinstance(error, (TimeoutError, ConnectionError)) or any(
        marker in message
        for marker in (
            "timed out",
            "timeout",
            "connection error",
            "connection refused",
            "service unavailable",
        )
    ) or status_code in (500, 502, 503, 504):
        return "network", "The provider could not be reached."
    if status_code in (401, 403) or any(
        marker in message for marker in ("unauthorized", "invalid api key", "api_key_invalid", "permission denied")
    ):
        return "authentication", "Provider authentication failed."
    return "provider_error", "The provider request failed."


def update_provider_health(
    provider: str,
    configured_model: str,
    active_model: Optional[str],
    error_category: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _health_lock:
        previous = _provider_health.get(provider, {})
        status = "Unavailable"
        last_success = previous.get("last_successful_test")
        if active_model:
            status = "Connected" if active_model == configured_model else "Degraded"
            last_success = now
        _provider_health[provider] = {
            "provider": provider,
            "configured_model": configured_model,
            "active_model": active_model,
            "connection_status": status,
            "last_successful_test": last_success,
            "error_category": error_category,
            "error_message": error_message,
        }


def get_provider_health(provider: str, configured_model: str, configured: bool) -> Dict[str, Any]:
    if not configured:
        return {
            "provider": provider,
            "configured_model": configured_model,
            "active_model": None,
            "connection_status": "Not configured",
            "last_successful_test": None,
            "error_category": None,
            "error_message": None,
        }
    with _health_lock:
        health = _provider_health.get(provider)
        if health is None:
            return {
                "provider": provider,
                "configured_model": configured_model,
                "active_model": None,
                "connection_status": "Configured",
                "last_successful_test": None,
                "error_category": None,
                "error_message": "Connection has not been tested.",
            }
        if health.get("configured_model") != configured_model:
            return {
                "provider": provider,
                "configured_model": configured_model,
                "active_model": None,
                "connection_status": "Unavailable",
                "last_successful_test": None,
                "error_category": None,
                "error_message": "Connection has not been tested for the configured model.",
            }
        return {**health, "configured_model": configured_model}


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        pass

    @abstractmethod
    def check_availability(self, probe: bool = False) -> Dict[str, Any]:
        pass
