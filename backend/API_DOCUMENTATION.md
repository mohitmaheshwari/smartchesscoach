# Smart Chess Coach API Documentation

## Overview

Smart Chess Coach API is a comprehensive chess analysis and coaching platform that provides game analysis, AI-powered coaching, player progression tracking, and voice-based feedback.

**Base URL**: `https://api.smartchesscoach.com` (Production) or `http://localhost:8000` (Development)

**API Version**: 1.0.0

---

## Table of Contents

1. [Authentication](#authentication)
2. [Platforms Integration](#platforms-integration)
3. [Game Management](#game-management)
4. [Game Analysis](#game-analysis)
5. [Voice Coaching](#voice-coaching)
6. [Player Journey & Progress](#player-journey--progress)
7. [Data Models](#data-models)
8. [Error Handling](#error-handling)

---

## Authentication

### Start Google OAuth Login

**Endpoint**: `GET /api/auth/google/login`

Redirects user to Google OAuth consent screen for authentication.

**Response**:
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

### Handle Google OAuth Callback

**Endpoint**: `GET /api/auth/google/callback`

Called by Google after user consent. Exchanges authorization code for session token.

**Query Parameters**:
- `code` (string, required): Authorization code from Google

**Response**: Redirects to frontend dashboard

### Create Session (Legacy - Emergent)

**Endpoint**: `POST /api/auth/session`

Exchange Emergent session_id for session_token (backwards compatibility only).

**Request Body**:
```json
{
  "session_id": "string"
}
```

**Response**:
```json
{
  "user_id": "user_xxx",
  "email": "user@example.com",
  "name": "John Doe",
  "picture": "https://...",
  "created_at": "2024-01-01T00:00:00Z",
  "chess_com_username": null,
  "lichess_username": null
}
```

### Mobile Google Authentication

**Endpoint**: `POST /api/auth/google/mobile`

Authenticate mobile app users with Google access token from SDK.

**Request Body**:
```json
{
  "access_token": "google_oauth_token_here"
}
```

**Response**:
```json
{
  "user": {
    "user_id": "user_xxx",
    "email": "user@example.com",
    "name": "John Doe",
    "picture": "https://...",
    "created_at": "2024-01-01T00:00:00Z"
  },
  "session_token": "mobile_session_xxx"
}
```

### Demo Login (Testing Only)

**Endpoint**: `POST /api/auth/demo-login`

Create demo user for testing without Google OAuth (localhost only).

**Request Body**:
```json
{
  "email": "test@example.com"
}
```

**Response**:
```json
{
  "user": {
    "user_id": "demo_test_example_com",
    "email": "test@example.com",
    "name": "Test",
    "picture": null,
    "created_at": "2024-01-01T00:00:00Z"
  },
  "session_token": "demo_session_xxx"
}
```

### Get Current User

**Endpoint**: `GET /api/auth/me`

Retrieve authenticated user's profile information.

**Authentication**: Required (Cookie or Bearer token)

**Response**:
```json
{
  "user_id": "user_xxx",
  "email": "user@example.com",
  "name": "John Doe",
  "picture": "https://...",
  "created_at": "2024-01-01T00:00:00Z",
  "chess_com_username": "johndoe",
  "lichess_username": "johndoe123"
}
```

### Logout

**Endpoint**: `POST /api/auth/logout`

Invalidate session and clear authentication cookies.

**Authentication**: Required

**Response**:
```json
{
  "message": "Logged out successfully"
}
```

---

## Platforms Integration

### Connect Platform Account

**Endpoint**: `POST /api/connect-platform`

Link user's Chess.com or Lichess username to their profile.

**Authentication**: Required

**Request Body**:
```json
{
  "platform": "chess.com",
  "username": "johndoe"
}
```

**Platforms**: `chess.com`, `lichess`

**Response**:
```json
{
  "message": "Connected chess.com account: johndoe"
}
```

**Errors**:
- `400`: Invalid platform or username not found
- `401`: Not authenticated

---

## Game Management

### Import Games

**Endpoint**: `POST /api/import-games`

Fetch and import recent games from user's Chess.com or Lichess account.

**Authentication**: Required

**Request Body**:
```json
{
  "platform": "chess.com",
  "username": "johndoe"
}
```

**Response**:
```json
{
  "imported": 15,
  "total_found": 20
}
```

**Notes**:
- Chess.com: Fetches last 3 months of games
- Lichess: Fetches last 30 games
- Awards gamification XP for imports

### Get All Games

**Endpoint**: `GET /api/games`

Retrieve all imported games for the authenticated user.

**Authentication**: Required

**Response**:
```json
[
  {
    "game_id": "game_abc123",
    "user_id": "user_xxx",
    "platform": "chess.com",
    "pgn": "[Event \"Blitz\"]\n[White \"Player1\"]\n[Black \"Player2\"]\n...",
    "white_player": "Player1",
    "black_player": "Player2",
    "result": "1-0",
    "time_control": "3+0",
    "date_played": "2024-01-15",
    "opening": "Sicilian Defense",
    "user_color": "white",
    "imported_at": "2024-01-16T10:00:00Z",
    "is_analyzed": false
  }
]
```

### Get Analyzed Games with Stats

**Endpoint**: `GET /api/games/analyzed`

Retrieve all analyzed games with accuracy, blunders, and mistakes summary.

**Authentication**: Required

**Response**:
```json
{
  "games": [
    {
      "game_id": "game_abc123",
      "opponent": "Player2",
      "result": "win",
      "accuracy": 87.5,
      "blunders": 1,
      "mistakes": 3,
      "best_moves": 12,
      "platform": "chess.com"
    }
  ],
  "total": 1
}
```

### Get All Blunders

**Endpoint**: `GET /api/games/blunders`

Retrieve all blunders from analyzed games with position and explanation.

**Authentication**: Required

**Response**:
```json
{
  "blunders": [
    {
      "game_id": "game_abc123",
      "move_number": 15,
      "move": "Qxb4",
      "evaluation": "blunder",
      "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "feedback": "You grabbed the pawn with Qxb4, but White has Bb5+ check.",
      "threat": "Bb5+"
    }
  ],
  "total": 3
}
```

### Get All Best Moves

**Endpoint**: `GET /api/games/best-moves`

Retrieve all best and excellent moves from analyzed games.

**Authentication**: Required

**Response**:
```json
{
  "best_moves": [
    {
      "game_id": "game_abc123",
      "move_number": 8,
      "move": "Nf3",
      "evaluation": "best",
      "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "feedback": "Controls the center and prepares castling"
    }
  ],
  "total": 15
}
```

### Get Specific Game

**Endpoint**: `GET /api/games/{game_id}`

Retrieve detailed information for a specific game including PGN and termination reason.

**Authentication**: Required

**Path Parameters**:
- `game_id` (string): Game identifier

**Response**: Same as Get All Games, with additional `termination_text` field

```json
{
  "game_id": "game_abc123",
  "...": "...",
  "termination": "resigned",
  "termination_text": "Opponent resigned"
}
```

---

## Game Analysis

### Analyze Game

**Endpoint**: `POST /api/analyze-game`

Perform comprehensive game analysis using Stockfish engine and AI coaching.

**Authentication**: Required

**Request Body**:
```json
{
  "game_id": "game_abc123",
  "force": false
}
```

**Query Parameters**:
- `force` (boolean, optional): Force re-analysis even if already analyzed

**Response**: [GameAnalysis object](#gameanalysis)

**Process**:
1. Stockfish engine analysis (depth 18) - move evaluations
2. PlayerProfile loading - user habits and style
3. RAG context building - relevant past games
4. AI coaching generation - personalized feedback
5. Quality scoring - ensure teaching quality

**Typical Duration**: 30-60 seconds

### Get Game Analysis

**Endpoint**: `GET /api/analysis/{game_id}`

Retrieve previously generated analysis for a game.

**Authentication**: Required

**Path Parameters**:
- `game_id` (string): Game identifier

**Response**: [GameAnalysis object](#gameanalysis)

---

## Voice Coaching

### Generate Speech from Text

**Endpoint**: `POST /api/tts/generate`

Convert text to speech using OpenAI TTS engine.

**Authentication**: Required

**Request Body**:
```json
{
  "text": "This is the feedback text",
  "voice": "onyx"
}
```

**Voice Options**:
- `onyx` (default): Deep, authoritative male voice
- `echo`: Warm male voice
- `fable`: Balanced male voice
- `nova`: Clear female voice
- `shimmer`: Bright female voice

**Response**: Audio stream (audio/mpeg)

### Generate Voice Summary for Analysis

**Endpoint**: `POST /api/tts/analysis-summary/{game_id}`

Generate TTS voice of the analysis summary for a game.

**Authentication**: Required

**Path Parameters**:
- `game_id` (string): Game identifier

**Response**: Audio stream (audio/mpeg)

### Generate Voice Explanation for Move

**Endpoint**: `POST /api/tts/move-explanation`

Generate TTS voice explanation for a specific move in a game.

**Authentication**: Required

**Request Body**:
```json
{
  "game_id": "game_abc123",
  "move_index": 15
}
```

**Response**: Audio stream (audio/mpeg)

---

## Player Journey & Progress

### Get Journey Dashboard

**Endpoint**: `GET /api/journey`

Get comprehensive player progression data and statistics.

**Authentication**: Required

**Response**:
```json
{
  "overview": {
    "games_analyzed": 42,
    "total_accuracy": 78.5,
    "improvement_trend": "improving",
    "key_strength": "tactical_vision",
    "key_weakness": "time_management"
  },
  "improvements": [
    {
      "category": "tactical",
      "metric": "accuracy",
      "prev_value": 72.1,
      "current_value": 78.5,
      "change": "+6.4%"
    }
  ],
  "challenges": [
    {
      "category": "time_management",
      "occurrences": 8,
      "severity": "high"
    }
  ],
  "focus_areas": [
    {
      "area": "opening_discipline",
      "priority": "high",
      "suggested_practice": "Study openings for 15 minutes daily"
    }
  ]
}
```

### Get Comprehensive Journey Data

**Endpoint**: `GET /api/journey/comprehensive`

Detailed journey data including all metrics and trends.

**Authentication**: Required

**Response**: Detailed metrics and historical trends

### Get Weekly Assessment

**Endpoint**: `GET /api/journey/weekly-assessment`

Weekly progress assessment and recommendations.

**Authentication**: Required

**Response**: Weekly summary, achievements, and next steps

### Get Weakness Trends

**Endpoint**: `GET /api/journey/weakness-trends`

Analyze trends in identified weaknesses over time.

**Authentication**: Required

**Response**:
```json
[
  {
    "subcategory": "pin_blindness",
    "first_seen": "2024-01-01",
    "last_seen": "2024-01-20",
    "total_occurrences": 5,
    "frequency_trend": "decreasing",
    "recommended_focus": "Study pin tactics training"
  }
]
```

### Link Platform Account for Journey

**Endpoint**: `POST /api/journey/link-account`

Link Chess.com or Lichess account for journey tracking.

**Authentication**: Required

**Request Body**:
```json
{
  "platform": "chess.com",
  "username": "johndoe"
}
```

### Get Linked Accounts

**Endpoint**: `GET /api/journey/linked-accounts`

Retrieve list of connected Chess.com and Lichess accounts.

**Authentication**: Required

**Response**:
```json
{
  "chess_com": {
    "username": "johndoe",
    "linked_at": "2024-01-01T10:00:00Z",
    "last_synced": "2024-01-16T15:30:00Z"
  },
  "lichess": {
    "username": "johndoe123",
    "linked_at": "2024-01-05T10:00:00Z",
    "last_synced": "2024-01-16T14:00:00Z"
  }
}
```

---

## Data Models

### User

```json
{
  "user_id": "user_xxx",
  "email": "user@example.com",
  "name": "John Doe",
  "picture": "https://example.com/pic.jpg",
  "created_at": "2024-01-01T00:00:00Z",
  "chess_com_username": "johndoe",
  "lichess_username": "johndoe123"
}
```

### Game

```json
{
  "game_id": "game_abc123",
  "user_id": "user_xxx",
  "platform": "chess.com",
  "pgn": "[Event \"Blitz\"]\n...",
  "white_player": "Player1",
  "black_player": "Player2",
  "result": "1-0",
  "time_control": "3+0",
  "date_played": "2024-01-15",
  "opening": "Sicilian Defense",
  "user_color": "white",
  "imported_at": "2024-01-16T10:00:00Z",
  "is_analyzed": false
}
```

### GameAnalysis

```json
{
  "analysis_id": "analysis_xyz",
  "game_id": "game_abc123",
  "user_id": "user_xxx",
  "commentary": [
    {
      "move_number": 15,
      "move": "Qxb4",
      "evaluation": "blunder",
      "intent": "Trying to grab material",
      "feedback": "After Qxb4, White has Bb5+ check. Your king gets pulled into the center.",
      "consider": "Better to consolidate with Nf3, developing while maintaining control",
      "thinking_pattern": "greed",
      "threat_line": "Bb5+ Kf7 Ng5+",
      "rule": "Don't trade safety for material in the opening"
    }
  ],
  "blunders": 2,
  "mistakes": 5,
  "inaccuracies": 8,
  "best_moves": 12,
  "summary_p1": "Overall game assessment - what went well and where discipline showed.",
  "summary_p2": "The one habit to focus on plus instruction for next game.",
  "identified_weaknesses": [
    {
      "category": "tactical",
      "subcategory": "pin_blindness",
      "description": "Missing opponent's pin tactics",
      "habit_description": "Not checking for attacker-target relationships"
    }
  ],
  "identified_strengths": [
    {
      "category": "tactical",
      "subcategory": "piece_coordination",
      "description": "Good coordination between pieces in attack"
    }
  ],
  "best_move_suggestions": [
    {
      "move_number": 8,
      "best_move": "Nf3",
      "reason": "Controls center and prepares castling"
    }
  ],
  "focus_this_week": "Work on defensive accuracy by always checking opponent's threats",
  "voice_script": "30-second calm voice summary",
  "created_at": "2024-01-16T10:30:00Z"
}
```

---

## Authentication Methods

### Cookie-based (Web)
```
Cookie: session_token=session_xxx
```

### Bearer Token (Mobile/API)
```
Authorization: Bearer session_token_here
```

Both methods are supported. The session token expires based on `SESSION_EXPIRY_DAYS` configuration (default: 30 days).

---

## Error Handling

All error responses follow this format:

```json
{
  "detail": "Error message here"
}
```

### Common HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Game analysis completed |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Not authenticated or session expired |
| 404 | Not Found | Game or analysis not found |
| 500 | Server Error | Stockfish analysis failed |

### Error Examples

**Invalid Game ID**:
```json
{
  "detail": "Game not found"
}
```

**Expired Session**:
```json
{
  "detail": "Session expired"
}
```

**Invalid Platform**:
```json
{
  "detail": "Invalid platform"
}
```

---

## Rate Limiting

- Game analysis: 1 per 30 seconds per user
- Game imports: 1 per 5 minutes per platform
- TTS generation: 10 per minute per user

---

## Headers

### Required Headers
```
Content-Type: application/json
```

### Optional Headers
```
User-Agent: SmartChessCoach/1.0
X-Request-ID: unique-request-id
```

---

## Examples

### Example: Complete Analysis Workflow

```bash
# 1. Import games
curl -X POST "http://localhost:8000/api/import-games" \
  -H "Cookie: session_token=session_xxx" \
  -H "Content-Type: application/json" \
  -d '{"platform": "chess.com", "username": "johndoe"}'

# 2. Get imported games
curl "http://localhost:8000/api/games" \
  -H "Cookie: session_token=session_xxx"

# 3. Analyze a game
curl -X POST "http://localhost:8000/api/analyze-game" \
  -H "Cookie: session_token=session_xxx" \
  -H "Content-Type: application/json" \
  -d '{"game_id": "game_abc123"}'

# 4. Get analysis
curl "http://localhost:8000/api/analysis/game_abc123" \
  -H "Cookie: session_token=session_xxx"

# 5. Generate voice feedback
curl -X POST "http://localhost:8000/api/tts/analysis-summary/game_abc123" \
  -H "Cookie: session_token=session_xxx" \
  -H "Accept: audio/mpeg" \
  --output analysis_voice.mp3
```

### Example: Mobile Authentication

```bash
# 1. Get Google access token from mobile SDK
# (Handled by Google Sign-In SDK on mobile)

# 2. Authenticate with access token
curl -X POST "http://localhost:8000/api/auth/google/mobile" \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "google_token_from_sdk"
  }'

# Response includes session_token for future requests
```

---

## Swagger UI

Access the interactive API documentation:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

---

## Changelog

### Version 1.0.0 (Initial Release)
- Authentication systems (Google OAuth, Mobile)
- Game import and management
- Stockfish-powered game analysis
- AI coaching with personalized feedback
- Voice coaching feedback (TTS)
- Player journey and progression tracking
- Weakness trend analysis

---

## Support

For API issues, bugs, or questions:
- Create an issue in the repository
- Contact: support@smartchesscoach.com
- Documentation: https://docs.smartchesscoach.com
