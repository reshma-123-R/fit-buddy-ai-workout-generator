"""Thin wrapper around the Google Gen AI SDK (`google-genai`).

Every Gemini call in FitBuddy goes through `generate_text`, which
  * creates the API client lazily (so the app starts even without a key),
  * turns every SDK / network failure into a `GeminiError` with a message that is
    safe and useful to show in the UI, and
  * never returns an empty string.
"""
import logging

from google import genai
from google.genai import types

from . import config

logger = logging.getLogger("fitbuddy.gemini")


class GeminiError(Exception):
    """A problem talking to Gemini. `str(error)` is safe to show to the user."""

    def __init__(self, message: str, *, fatal: bool = False, status: int | None = None):
        super().__init__(message)
        self.fatal = fatal      # True => trying another model will not help (e.g. bad API key)
        self.status = status


class GeminiConfigError(GeminiError):
    """Local configuration problem, e.g. no API key."""

    def __init__(self, message: str):
        super().__init__(message, fatal=True)


# We never use function calling; disabling it also silences an SDK console notice about it.
_GENERATION_CONFIG = types.GenerateContentConfig(
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
)

_client = None
_client_key = None


def get_client():
    """Return a cached Gemini client, creating it on first use."""
    global _client, _client_key
    api_key = config.get_gemini_api_key()
    if not api_key:
        raise GeminiConfigError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env, paste your key from "
            "https://aistudio.google.com/apikey and restart the server."
        )
    if _client is None or _client_key != api_key:
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=config.GEMINI_TIMEOUT_SECONDS * 1000),  # milliseconds
        )
        _client_key = api_key
    return _client


def _explain_error(exc: Exception, model: str) -> GeminiError:
    """Map an SDK/network exception to a friendly GeminiError."""
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    detail = str(getattr(exc, "message", None) or exc).strip().replace("\n", " ")
    if len(detail) > 300:
        detail = detail[:300] + "…"
    lowered = detail.lower()

    if status == 401 or "api key not valid" in lowered or "api_key_invalid" in lowered:
        return GeminiError("Gemini rejected the API key. Check GEMINI_API_KEY in your .env file.",
                           fatal=True, status=status)
    if status == 403:
        return GeminiError(
            f"Gemini refused the request (HTTP 403). Check that your API key is valid and that "
            f"model '{model}' is available to your account and region. Details: {detail}",
            fatal=True, status=status)
    if status == 404:
        return GeminiError(
            f"Gemini model '{model}' was not found - it may have been renamed or retired. "
            "Set GEMINI_PRO_MODEL / GEMINI_FLASH_MODEL in .env "
            "(see https://ai.google.dev/gemini-api/docs/models).", status=status)
    if status == 429:
        return GeminiError("Gemini rate limit or quota reached. Wait a minute and try again, "
                           "or check your quota and billing in Google AI Studio.", status=status)
    if isinstance(status, int) and status >= 500:
        return GeminiError("Gemini is temporarily unavailable. Please try again in a moment.", status=status)
    if isinstance(status, int):
        return GeminiError(f"Gemini request failed (HTTP {status}): {detail}", status=status)
    return GeminiError(f"Could not get a response from Gemini: {detail}")


def generate_text(prompt: str, model: str) -> str:
    """Send `prompt` to `model` and return the response text (stripped, never empty)."""
    client = get_client()
    try:
        response = client.models.generate_content(model=model, contents=prompt, config=_GENERATION_CONFIG)
        text = response.text
    except GeminiError:
        raise
    except Exception as exc:  # SDK errors, timeouts, connection problems...
        logger.warning("Gemini call to %s failed: %s", model, exc)
        raise _explain_error(exc, model) from exc

    if not text or not text.strip():
        raise GeminiError(f"Gemini model '{model}' returned an empty response "
                          "(it may have been blocked by a safety filter). Try rewording your goal.")
    return text.strip()


def generate_with_fallback(prompt: str) -> str:
    """Generate with the Pro model; if that fails, retry once with the Flash model."""
    primary, fallback = config.GEMINI_PRO_MODEL, config.GEMINI_FLASH_MODEL
    try:
        return generate_text(prompt, primary)
    except GeminiError as primary_error:
        if primary_error.fatal or not fallback or fallback == primary:
            raise
        logger.warning("Falling back from %s to %s", primary, fallback)
        try:
            return generate_text(prompt, fallback)
        except GeminiError as fallback_error:
            raise GeminiError(f"{primary_error} (Fallback model '{fallback}' also failed: {fallback_error})",
                              status=fallback_error.status) from fallback_error
