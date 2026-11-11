from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.logging import logger
from .base import (
    BaseLLMProvider,
    LLMResponse,
    classify_provider_error,
    get_provider_health,
    update_provider_health,
)


class GroqProvider(BaseLLMProvider):
    """Adapter for Groq's OpenAI-compatible chat completions API."""

    provider_name = "Groq"

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.model_name = settings.GROQ_MODEL
        self.fallback_model = settings.GROQ_FALLBACK_MODEL
        self._client = None
        self._probe_model_override: Optional[str] = None
        self._model_output_limits: Dict[str, int] = {}
        if self.api_key:
            try:
                from groq import Groq

                self._client = Groq(api_key=self.api_key)
            except Exception as error:
                category, safe_message = classify_provider_error(error)
                logger.warning("Groq client initialization failed (%s)", category)
                update_provider_health(
                    self.provider_name, self.model_name, None, category, safe_message
                )

    def _available_models(self) -> list[str]:
        if self._client is None:
            return []
        models = self._client.models.list()
        available = []
        for model in getattr(models, "data", []):
            model_id = str(getattr(model, "id", ""))
            if not model_id:
                continue
            if getattr(model, "active", True) is False:
                continue
            if any(part in model_id.lower() for part in ("whisper", "tts", "guard", "embed")):
                continue
            available.append(model_id)
            output_limit = getattr(model, "max_completion_tokens", None)
            if isinstance(output_limit, int) and output_limit > 0:
                self._model_output_limits[model_id] = output_limit
        return available

    def _fallback_model_name(self, available: Optional[list[str]] = None) -> str:
        if available is None:
            available = self._available_models()
        if self.fallback_model in available and self.fallback_model != self.model_name:
            return self.fallback_model
        candidates = [model for model in available if model != self.model_name]
        if not candidates:
            raise RuntimeError("Model not found: no accessible Groq chat model is available.")
        return sorted(
            candidates,
            key=lambda model: (
                not any(word in model.lower() for word in ("versatile", "instruct", "qwen")),
                model,
            ),
        )[0]

    def check_availability(self, probe: bool = False) -> Dict[str, Any]:
        if not self.api_key:
            health = get_provider_health(self.provider_name, self.model_name, False)
        elif probe:
            try:
                available = self._available_models()
                self._probe_model_override = (
                    self.model_name
                    if self.model_name in available
                    else self._fallback_model_name(available)
                )
                response = self.generate("Reply with OK.")
                health = get_provider_health(self.provider_name, self.model_name, True)
                health["active_model"] = response.model if response.is_live else None
                if not response.is_live:
                    health["connection_status"] = "Unavailable"
                    health["error_category"] = response.error_category
                    health["error_message"] = response.error
            except Exception as error:
                category, safe_message = classify_provider_error(error)
                update_provider_health(
                    self.provider_name, self.model_name, None, category, safe_message
                )
                health = get_provider_health(self.provider_name, self.model_name, True)
            finally:
                self._probe_model_override = None
        else:
            health = get_provider_health(self.provider_name, self.model_name, True)
        return {
            **health,
            "available": health["connection_status"] in ("Connected", "Degraded"),
            "provider": self.provider_name,
            "model": health["active_model"] or self.model_name,
            "status": health["connection_status"],
            "reason": health["error_message"],
        }

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        if not self.api_key:
            return LLMResponse(
                content="",
                provider=self.provider_name,
                model=self.model_name,
                is_live=False,
                error="Groq provider is not configured.",
                error_category="not_configured",
                configured_model=self.model_name,
            )
        if self._client is None:
            return LLMResponse(
                content="",
                provider=self.provider_name,
                model=self.model_name,
                is_live=False,
                error="Groq client initialization failed.",
                error_category="provider_error",
                configured_model=self.model_name,
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        active_model = self._probe_model_override or self.model_name
        max_tokens = min(2048, self._model_output_limits.get(active_model, 2048))
        try:
            try:
                completion = self._client.chat.completions.create(
                    model=active_model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=max_tokens,
                )
            except Exception as initial_error:
                category, _ = classify_provider_error(initial_error)
                if category != "model_not_found":
                    raise
                active_model = self._fallback_model_name()
                logger.warning(
                    "Groq configured model unavailable; trying listed fallback model %s",
                    active_model,
                )
                completion = self._client.chat.completions.create(
                    model=active_model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=max_tokens,
                )

            choices = getattr(completion, "choices", [])
            if not choices:
                raise RuntimeError("Groq returned no chat completion choices.")
            text_content = getattr(choices[0].message, "content", "") or ""
            usage = getattr(completion, "usage", None)
            tokens = getattr(usage, "total_tokens", 0) if usage else 0
            update_provider_health(
                self.provider_name,
                self.model_name,
                active_model,
            )
            logger.info("Groq generation succeeded with model %s", active_model)
            return LLMResponse(
                content=text_content,
                provider=self.provider_name,
                model=active_model,
                configured_model=self.model_name,
                tokens_used=tokens,
                message_type="fact_grounded",
                is_live=True,
            )
        except Exception as error:
            category, safe_message = classify_provider_error(error)
            update_provider_health(
                self.provider_name, self.model_name, None, category, safe_message
            )
            logger.error(
                "Groq generation failed (category=%s, model=%s)",
                category,
                active_model,
            )
            return LLMResponse(
                content="",
                provider=self.provider_name,
                model=active_model,
                configured_model=self.model_name,
                is_live=False,
                error=safe_message,
                error_category=category,
            )
