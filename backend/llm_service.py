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

import contextlib
import contextvars
import os
import logging

logger = logging.getLogger(__name__)

# Who to bill a call to. A contextvar rather than an argument on call_llm:
# there are 16 live call sites, and a kwarg threaded through all of them is
# how most rows end up unlabelled. The caller that KNOWS the user -- the
# analysis worker knows the game and its owner -- opens a context, and
# every call underneath is labelled without touching the ones in between.
_USAGE_CONTEXT: "contextvars.ContextVar[dict]" = contextvars.ContextVar(
    "llm_usage_context", default=None)


@contextlib.contextmanager
def usage_context(**fields):
    """Label every LLM call made inside this block.

        with usage_context(surface="game_review_caption",
                           user_id=uid, game_id=gid):
            ...

    Fields: `surface`, `user_id`, `game_id`. Nesting replaces rather than
    merges, so an inner block is the whole label for what it contains.
    Propagates into tasks created inside the block, which is what the
    caption path needs -- it fans out with asyncio.gather.
    """
    token = _USAGE_CONTEXT.set({k: v for k, v in fields.items()
                                if v is not None})
    try:
        yield
    finally:
        _USAGE_CONTEXT.reset(token)


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
        # 2026-08-03: explicit timeout — the SDK default is 10 minutes, and
        # nothing in this codebase's caption/narrative callers (all short,
        # ~50-200 token completions) needs anywhere close to that. A hung
        # or slow-to-respond call was masking as a mysterious multi-hour
        # process hang elsewhere; this bounds the worst case regardless of
        # what turns out to be calling it. See
        # docs/caption_pipeline_architecture_reference.md §9/§11.
        _anthropic_client = AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            timeout=30.0,
        )
    return _anthropic_client


async def _call_claude(
    system_message: str,
    user_message: str,
    model: str = CLAUDE_DEFAULT_MODEL,
    max_tokens: int = 1024,
    cache_system: bool = False,
    reasoning_effort: str = "",
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

    _record_usage(resolved_model, getattr(response, "usage", None))

    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts)


def _record_usage(model: str, usage) -> None:
    """Book what the call cost. Never raises, never blocks the answer.

    Both providers hand back a usage object and both of these functions
    used to drop it, so "what are we spending" had no answer anywhere in
    the product. The caption path falls back to a deterministic caption
    when an LLM call fails; a bookkeeping error is not a reason to trigger
    that, which is why everything here is swallowed.

    The surface and the user come from a contextvar rather than a new
    argument, because there are 16 live call sites and threading a kwarg
    through all of them to label a row is how half of them end up
    unlabelled. An unlabelled call still records, as "unattributed", so the
    total is right even where the label is not.
    """
    try:
        from services import llm_usage
        ctx = _USAGE_CONTEXT.get() or {}
        llm_usage.record(
            model, usage,
            surface=ctx.get("surface") or llm_usage.env_default_surface(),
            user_id=ctx.get("user_id"),
            game_id=ctx.get("game_id"))
    except Exception:
        pass


# ==================== OPENAI IMPLEMENTATION ====================
_openai_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI
        # 2026-08-03: same reasoning as _get_anthropic_client — no caller
        # of this client needs the SDK's multi-minute default.
        _openai_client = AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            timeout=30.0,
        )
    return _openai_client


# Models that think before they answer. They reject `max_tokens` (it must be
# `max_completion_tokens`), they accept `reasoning_effort`, and they bill the
# thinking as output: measured 2026-10-21, gpt-6-luna spent 2,262 of 2,413
# completion tokens on reasoning for a 151-token answer. Left at default
# effort a small budget is consumed entirely by thinking and the answer comes
# back EMPTY, which is how this first looked like a JSON parse error.
_REASONING_MODELS = ("gpt-6-", "gpt-5.6-", "o1", "o3", "o4")


def _is_reasoning_model(model: str) -> bool:
    return any(model.startswith(p) for p in _REASONING_MODELS)


async def _call_openai(system_message: str, user_message: str,
                       model: str = "gpt-4o-mini", *,
                       max_tokens: int = 0,
                       reasoning_effort: str = "") -> str:
    """Direct OpenAI API call (legacy callers passing gpt-* model ids)."""
    client = _get_openai_client()
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
    }
    if _is_reasoning_model(model):
        # No temperature: these models reject it. The budget must leave room
        # for an answer AFTER the thinking, so it is deliberately generous.
        kwargs["max_completion_tokens"] = max_tokens or 2000
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
    else:
        kwargs["temperature"] = 0.7
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
    response = await client.chat.completions.create(**kwargs)
    _record_usage(model, getattr(response, "usage", None))
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
    reasoning_effort: str = "",
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
    return await _call_openai(
        system_message, user_message, model,
        max_tokens=max_tokens, reasoning_effort=reasoning_effort,
    )


async def call_tts(text: str, voice: str = "onyx", model: str = "tts-1") -> bytes:
    """Generate speech audio via OpenAI TTS."""
    return await _openai_tts(text, voice, model)


def get_provider_mode() -> str:
    """Get current LLM provider mode (legacy hook for routes/auth.py)."""
    return LLM_PROVIDER_MODE
