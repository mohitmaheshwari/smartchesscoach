"""
LLM Service Abstraction Layer

Supports:
- Anthropic Claude SDK (default — used by V5 caption pipeline + all coach narrators)
- Direct OpenAI SDK (legacy callers that pass gpt-* model ids + TTS)

Routing rule for call_llm():
- model starts with "claude" → Claude SDK (supports cache_system, max_tokens)
- otherwise → OpenAI

Emergent Integrations was removed in commit <this-commit>: every caller now goes
through call_llm() directly. get_provider_mode() is preserved so routes/auth.py
keeps its 404 gate on the Emergent-OAuth-only `/api/auth/session` endpoint.
"""

import os
import logging

logger = logging.getLogger(__name__)


def _detect_provider_mode():
    """Auto-detect which legacy provider to default to.

    With Emergent removed, this only really distinguishes "have OpenAI key" vs
    "default fallback". Claude calls bypass this entirely (routed by model prefix).
    """
    manual_mode = os.environ.get("LLM_PROVIDER_MODE", "").lower()
    if manual_mode in ("openai", "anthropic", "claude"):
        return manual_mode
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return "anthropic"
    return "openai"


LLM_PROVIDER_MODE = _detect_provider_mode()
logger.info(f"LLM Provider Mode: {LLM_PROVIDER_MODE}")


# ==================== ANTHROPIC (CLAUDE) IMPLEMENTATION ====================
_anthropic_client = None

# Default Claude model. Sonnet 4.6 has a 2K-token cache minimum, making it
# cheaper than Haiku 4.5 (4K min) for our ~2K caption-system-prompt use case.
CLAUDE_DEFAULT_MODEL = "claude-sonnet-4-6"


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import AsyncAnthropic
        _anthropic_client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return _anthropic_client


async def _call_claude(
    system_message: str,
    user_message: str,
    model: str = CLAUDE_DEFAULT_MODEL,
    max_tokens: int = 1024,
    cache_system: bool = False,
) -> str:
    """
    Anthropic Claude API call.

    Args:
        system_message: System prompt.
        user_message: User prompt.
        model: Claude model id (e.g. "claude-sonnet-4-6", "claude-haiku-4-5", "claude-opus-4-7").
               Pass "claude" to use CLAUDE_DEFAULT_MODEL.
        max_tokens: Output cap. Caption use case is ~50 tokens; default 1024 covers most callers.
        cache_system: If True, mark the system message with cache_control=ephemeral so
                      identical prompts are billed at the cached rate. Only worthwhile when
                      the system message exceeds the model's cache minimum
                      (Sonnet 4.6: 2048 tokens; Haiku 4.5: 4096 tokens).
    Returns:
        Assistant text. Raises on API error so callers can hit deterministic fallback.
    """
    client = _get_anthropic_client()
    resolved_model = CLAUDE_DEFAULT_MODEL if model == "claude" else model

    if cache_system:
        system_param = [{
            "type": "text",
            "text": system_message,
            "cache_control": {"type": "ephemeral"},
        }]
    else:
        system_param = system_message

    response = await client.messages.create(
        model=resolved_model,
        max_tokens=max_tokens,
        system=system_param,
        messages=[{"role": "user", "content": user_message}],
    )

    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts)


# ==================== OPENAI IMPLEMENTATION ====================
_openai_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI
        _openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    return _openai_client


async def _call_openai(system_message: str, user_message: str, model: str = "gpt-4o-mini") -> str:
    """Direct OpenAI API call (legacy callers passing gpt-* model ids)."""
    client = _get_openai_client()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content


async def _openai_tts(text: str, voice: str = "onyx", model: str = "tts-1") -> bytes:
    """Direct OpenAI TTS call — returns audio bytes (MP3)."""
    client = _get_openai_client()
    response = await client.audio.speech.create(
        model=model,
        voice=voice,
        input=text[:4000],
    )
    return response.content


# ==================== PUBLIC API ====================
async def call_llm(
    system_message: str,
    user_message: str,
    model: str = CLAUDE_DEFAULT_MODEL,
    *,
    max_tokens: int = 1024,
    cache_system: bool = False,
) -> str:
    """
    Call LLM with provider selection by model prefix.

    Routing:
      - model startswith "claude" → Claude SDK (supports cache_system, max_tokens)
      - otherwise → OpenAI (max_tokens/cache_system ignored)
    """
    if model.startswith("claude"):
        return await _call_claude(
            system_message, user_message, model,
            max_tokens=max_tokens, cache_system=cache_system,
        )
    return await _call_openai(system_message, user_message, model)


async def call_tts(text: str, voice: str = "onyx", model: str = "tts-1") -> bytes:
    """Generate speech audio via OpenAI TTS."""
    return await _openai_tts(text, voice, model)


def get_provider_mode() -> str:
    """Get current LLM provider mode (legacy hook for routes/auth.py)."""
    return LLM_PROVIDER_MODE
