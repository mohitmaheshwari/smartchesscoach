"""
Minimal LLM helper to replace emergentintegrations package
"""
import httpx
import os
from typing import Optional


class UserMessage:
    def __init__(self, text: str):
        self.text = text


class LlmChat:
    def __init__(self, api_key: str, session_id: str, system_message: str):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        self.provider = "openai"
        self.model = "gpt-4o-mini"
        
    def with_model(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        return self
    
    async def send_message(self, message: UserMessage) -> str:
        """Send message to OpenAI and return response"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.system_message},
                        {"role": "user", "content": message.text}
                    ],
                    "temperature": 0.7
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


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
