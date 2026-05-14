"""
LLM Service Abstraction Layer

Supports:
- Anthropic Claude SDK (preferred — used by V5 caption pipeline with prompt caching)
- Direct OpenAI SDK (legacy callers + TTS)
- Emergent integrations (legacy, being removed)

Routing rule for call_llm():
- model starts with "claude-" → Claude SDK
- otherwise → OpenAI/Emergent (based on LLM_PROVIDER_MODE)
"""

import os
import logging

logger = logging.getLogger(__name__)

# Determine which provider to use based on available keys
def _detect_provider_mode():
    """Auto-detect which LLM provider to use based on environment"""
    # Check for manual override first
    manual_mode = os.environ.get("LLM_PROVIDER_MODE", "").lower()
    if manual_mode in ["emergent", "openai"]:
        return manual_mode
    
    # Auto-detect based on which keys are available
    has_emergent_key = bool(os.environ.get("EMERGENT_LLM_KEY", "").strip())
    has_openai_key = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    
    if has_openai_key:
        # Production: OpenAI key takes priority
        return "openai"
    elif has_emergent_key:
        # Emergent environment
        return "emergent"
    else:
        # Default to OpenAI (will fail if no key, but that's expected)
        return "openai"

LLM_PROVIDER_MODE = _detect_provider_mode()
logger.info(f"LLM Provider Mode: {LLM_PROVIDER_MODE}")


# ==================== ANTHROPIC (CLAUDE) IMPLEMENTATION ====================
_anthropic_client = None

# Default Claude model when caller passes generic "claude" or for cached caption calls.
# Sonnet 4.6 has a 2K-token cache minimum, making it cheaper than Haiku 4.5 (4K min)
# for our ~2K caption-system-prompt use case.
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
    """Direct OpenAI API call"""
    client = _get_openai_client()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content


async def _openai_tts(text: str, voice: str = "onyx", model: str = "tts-1") -> bytes:
    """Direct OpenAI TTS call - returns audio bytes"""
    client = _get_openai_client()
    response = await client.audio.speech.create(
        model=model,
        voice=voice,
        input=text[:4000]
    )
    return response.content


# ==================== EMERGENT IMPLEMENTATION ====================
async def _call_emergent(system_message: str, user_message: str, model: str = "gpt-4o-mini") -> str:
    """Emergent integrations API call"""
    from llm_helper import LlmChat, UserMessage
    
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    
    chat = LlmChat(
        api_key=api_key,
        session_id=f"chat_{os.urandom(8).hex()}",
        system_message=system_message
    ).with_model("openai", model)
    
    response = await chat.send_message(UserMessage(text=user_message))
    return response


async def _emergent_tts(text: str, voice: str = "onyx", model: str = "tts-1") -> bytes:
    """Emergent TTS call - returns audio bytes"""
    from llm_helper import OpenAITextToSpeech
    import base64
    
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    tts = OpenAITextToSpeech(api_key=api_key)
    
    audio_base64 = await tts.generate_speech_base64(
        text=text[:4000],
        model=model,
        voice=voice,
        speed=1.0
    )
    return base64.b64decode(audio_base64)


# ==================== PUBLIC API ====================
async def call_llm(
    system_message: str,
    user_message: str,
    model: str = "gpt-4o-mini",
    *,
    max_tokens: int = 1024,
    cache_system: bool = False,
) -> str:
    """
    Call LLM with provider selection by model prefix.

    Routing:
      - model startswith "claude" → Claude SDK (supports cache_system, max_tokens)
      - otherwise → OpenAI or Emergent based on LLM_PROVIDER_MODE
        (max_tokens/cache_system are ignored on the legacy path)
    """
    if model.startswith("claude"):
        return await _call_claude(
            system_message, user_message, model,
            max_tokens=max_tokens, cache_system=cache_system,
        )
    if LLM_PROVIDER_MODE == "emergent":
        return await _call_emergent(system_message, user_message, model)
    return await _call_openai(system_message, user_message, model)


async def call_tts(text: str, voice: str = "onyx", model: str = "tts-1") -> bytes:
    """
    Generate speech audio with automatic provider selection.
    
    Args:
        text: Text to convert to speech
        voice: Voice name (default: onyx)
        model: TTS model (default: tts-1)
    
    Returns:
        Audio bytes (MP3 format)
    """
    if LLM_PROVIDER_MODE == "emergent":
        return await _emergent_tts(text, voice, model)
    else:
        return await _openai_tts(text, voice, model)


def get_provider_mode() -> str:
    """Get current LLM provider mode"""
    return LLM_PROVIDER_MODE
