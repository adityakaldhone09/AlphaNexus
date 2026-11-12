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


class GeminiProvider(BaseLLMProvider):
    """Adapter for Google's Gemini generateContent API."""

    provider_name = "Google Gemini"

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self.fallback_model = settings.GEMINI_FALLBACK_MODEL
        self._client = None
        self._genai = None
        self._probe_model_override: Optional[str] = None
        self._init_client()

    def _init_client(self) -> None:
        if not self.api_key:
            return
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._genai = genai
            self._client = genai.GenerativeModel(self.model_name)
        except Exception as error:
            category, safe_message = classify_provider_error(error)
            logger.warning("Gemini client initialization failed (%s)", category)
            update_provider_health(
                self.provider_name, self.model_name, None, category, safe_message
            )

    @staticmethod
    def _model_id(model: Any) -> str:
        return str(getattr(model, "name", "")).removeprefix("models/")

    def _available_models(self) -> list[str]:
        if self._genai is None:
            return []
        models = self._genai.list_models()
        available = []
        for model in models:
            methods = getattr(model, "supported_generation_methods", [])
            if any(str(method).lower() == "generatecontent" for method in methods):
                model_id = self._model_id(model)
                if model_id:
                    available.append(model_id)
        return available

    def _fallback_model_name(self, available: Optional[list[str]] = None) -> str:
        if available is None:
            available = self._available_models()
        if self.fallback_model in available and self.fallback_model != self.model_name:
            return self.fallback_model
        candidates = [model for model in available if model != self.model_name]
        if not candidates:
            raise RuntimeError("Model not found: no accessible Gemini generateContent model is available.")
        # Prioritize newer generation models (gemini-3) and flash variants over older or deprecated tiers
        def _model_sort_key(m: str):
            score = 0
            m_lower = m.lower()
            if "gemini-3" in m_lower:
                score -= 20
            if "flash" in m_lower:
                score -= 10
            if "2.5" in m_lower:
                score += 5
            return (score, m)

        return sorted(candidates, key=_model_sort_key)[0]

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
                error="Gemini provider is not configured.",
                error_category="not_configured",
                configured_model=self.model_name,
            )
        if self._client is None or self._genai is None:
            return LLMResponse(
                content="",
                provider=self.provider_name,
                model=self.model_name,
                is_live=False,
                error="Gemini client initialization failed.",
                error_category="provider_error",
                configured_model=self.model_name,
            )

        full_prompt = (
            f"System Instruction: {system_prompt}\n\nUser Request: {prompt}"
            if system_prompt
            else prompt
        )
        generation_config = {"temperature": 0.2, "max_output_tokens": 2048}
        active_model = self._probe_model_override or self.model_name
        try:
            try:
                active_client = (
                    self._client
                    if active_model == self.model_name
                    else self._genai.GenerativeModel(active_model)
                )
                response = active_client.generate_content(full_prompt, generation_config=generation_config)
            except Exception as initial_error:
                category, _ = classify_provider_error(initial_error)
                if category != "model_not_found":
                    raise
                active_model = self._fallback_model_name()
                logger.warning(
                    "Gemini configured model unavailable; trying listed fallback model %s",
                    active_model,
                )
                fallback_client = self._genai.GenerativeModel(active_model)
                response = fallback_client.generate_content(
                    full_prompt, generation_config=generation_config
                )

            text_content = getattr(response, "text", "") or ""
            usage = getattr(response, "usage_metadata", None)
            tokens = getattr(usage, "total_token_count", 0) if usage else 0
            if not tokens:
                tokens = len(full_prompt.split()) + len(text_content.split())
            update_provider_health(
                self.provider_name,
                self.model_name,
                active_model,
            )
            logger.info("Gemini generation succeeded with model %s", active_model)
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
                "Gemini generation failed (category=%s, model=%s)",
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
