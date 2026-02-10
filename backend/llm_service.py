"""
LLM Service Abstraction Layer

This module provides a unified interface for LLM calls that works with:
- Emergent integrations (for development/testing on Emergent platform)
- Direct OpenAI SDK (for production deployment)

AUTOMATIC DETECTION:
- Emergent environment: Has EMERGENT_LLM_KEY, no OPENAI_API_KEY
- Production environment: Has OPENAI_API_KEY

Manual override: Set LLM_PROVIDER_MODE="emergent" or "openai"
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
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
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
    from emergentintegrations.llm.openai import OpenAITextToSpeech
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
async def call_llm(system_message: str, user_message: str, model: str = "gpt-4o-mini") -> str:
    """
    Call LLM with automatic provider selection.
    
    Args:
        system_message: System prompt
        user_message: User prompt
        model: Model name (default: gpt-4o-mini)
    
    Returns:
        LLM response text
    """
    if LLM_PROVIDER_MODE == "emergent":
        return await _call_emergent(system_message, user_message, model)
    else:
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
