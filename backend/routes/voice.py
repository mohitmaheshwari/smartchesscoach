"""
Voice Coaching (TTS) Routes
============================

Handles text-to-speech generation for coaching feedback.

Endpoints:
- POST /tts/generate - Generate speech audio from text
- POST /tts/analysis-summary/{game_id} - Generate voice coaching for game analysis
- POST /tts/move-explanation - Generate voice explanation for a specific move
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Create router for voice/TTS endpoints
router = APIRouter(tags=["Voice"])

# Database reference - will be set by server.py
db = None

# TTS function reference - will be set by server.py
call_tts = None

def set_db(database):
    """Set the database reference for voice routes"""
    global db
    db = database

def set_tts(tts_func):
    """Set the TTS function reference for voice routes"""
    global call_tts
    call_tts = tts_func


# Import User model and get_current_user from auth routes
from routes.auth import User, get_current_user


# ==================== MODELS ====================

class TTSRequest(BaseModel):
    text: str
    voice: str = "onyx"  # Male coach voice - deep, authoritative

class MoveVoiceRequest(BaseModel):
    game_id: str
    move_index: int


# ==================== ENDPOINTS ====================

@router.post("/tts/generate")
async def generate_speech(req: TTSRequest, user: User = Depends(get_current_user)):
    """Generate speech audio from text using OpenAI TTS"""
    import base64

    if not req.text or len(req.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text is required")

    # Limit text length (OpenAI TTS limit is 4096 chars)
    text = req.text[:4000]

    try:
        audio_bytes = await call_tts(text=text, voice=req.voice)
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        return {
            "audio_base64": audio_base64,
            "format": "mp3",
            "voice": req.voice
        }

    except Exception as e:
        logger.error(f"TTS generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")

@router.post("/tts/analysis-summary/{game_id}")
async def generate_analysis_voice(game_id: str, user: User = Depends(get_current_user)):
    """Generate voice coaching for a game analysis summary"""
    import base64

    # Get the analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user.user_id},
        {"_id": 0}
    )

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Check if we already have cached audio
    if analysis.get("voice_audio_base64"):
        return {
            "audio_base64": analysis["voice_audio_base64"],
            "format": "mp3",
            "voice": "onyx",
            "cached": True
        }

    # Build the voice script
    summary = analysis.get("overall_summary", "")
    key_lesson = analysis.get("key_lesson", "")

    # Create a natural speaking script
    voice_script = summary
    if key_lesson:
        voice_script += f" And here's the key lesson from this game: {key_lesson}"

    if not voice_script:
        raise HTTPException(status_code=400, detail="No summary available for voice generation")

    try:
        audio_bytes = await call_tts(text=voice_script[:4000], voice="onyx")
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        # Cache the audio in the database
        await db.game_analyses.update_one(
            {"game_id": game_id},
            {"$set": {"voice_audio_base64": audio_base64}}
        )

        return {
            "audio_base64": audio_base64,
            "format": "mp3",
            "voice": "onyx",
            "cached": False
        }

    except Exception as e:
        logger.error(f"TTS analysis voice error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")

@router.post("/tts/move-explanation")
async def generate_move_voice(req: MoveVoiceRequest, user: User = Depends(get_current_user)):
    """Generate voice explanation for a specific move"""
    import base64

    analysis = await db.game_analyses.find_one(
        {"game_id": req.game_id, "user_id": user.user_id},
        {"_id": 0}
    )

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    commentary = analysis.get("commentary", [])
    if req.move_index < 0 or req.move_index >= len(commentary):
        raise HTTPException(status_code=400, detail="Invalid move index")

    move = commentary[req.move_index]

    # Build voice script for this move
    parts = []

    move_num = move.get("move_number", "")
    move_name = move.get("move", "")
    parts.append(f"Move {move_num}, {move_name}.")

    if move.get("player_intention"):
        parts.append(f"I see what you were going for: {move['player_intention']}")

    if move.get("coach_response"):
        parts.append(move["coach_response"])
    elif move.get("comment"):
        parts.append(move["comment"])

    if move.get("better_move"):
        parts.append(f"A better option was {move['better_move']}.")

    explanation = move.get("explanation", {})
    if explanation.get("one_repeatable_rule"):
        parts.append(f"Remember: {explanation['one_repeatable_rule']}")

    voice_script = " ".join(parts)

    if not voice_script:
        raise HTTPException(status_code=400, detail="No explanation available for this move")

    try:
        audio_bytes = await call_tts(text=voice_script[:4000], voice="onyx")
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        return {
            "audio_base64": audio_base64,
            "format": "mp3",
            "voice": "onyx",
            "move_number": move_num
        }

    except Exception as e:
        logger.error(f"TTS move voice error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")
