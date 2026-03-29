"""
LLM helper - wraps emergentintegrations package for consistent interface.
Provides LlmChat, UserMessage, and OpenAITextToSpeech classes.
"""
import httpx
from emergentintegrations.llm.chat import LlmChat, UserMessage


class OpenAITextToSpeech:
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def generate_speech_base64(
        self, 
        text: str, 
        model: str = "tts-1",
        voice: str = "alloy",
        speed: float = 1.0
    ) -> str:
        """Generate speech and return as base64"""
        import base64
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "input": text,
                    "voice": voice,
                    "speed": speed
                }
            )
            response.raise_for_status()
            audio_bytes = response.content
            return base64.b64encode(audio_bytes).decode('utf-8')
