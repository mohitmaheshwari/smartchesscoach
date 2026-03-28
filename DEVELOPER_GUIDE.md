# Smart Chess Coach API - Developer Guide

## Quick Start

### Accessing API Documentation

The Smart Chess Coach API provides multiple ways to explore and test endpoints:

#### 1. **Swagger UI (Interactive Testing)**
- **URL**: `http://localhost:8000/docs`
- **Best for**: Testing endpoints, trying requests
- **Features**: 
  - Try out buttons for each endpoint
  - Request/response examples
  - Schema validation

#### 2. **ReDoc (Beautiful Documentation)**
- **URL**: `http://localhost:8000/redoc`
- **Best for**: Reading documentation, understanding endpoints
- **Features**:
  - Clean, searchable interface
  - Code examples in multiple languages
  - Full API schema

#### 3. **OpenAPI JSON Schema**
- **URL**: `http://localhost:8000/openapi.json`
- **Best for**: Integrating into other tools, code generation
- **Usage**: Import into Postman, generate SDKs, etc.

---

## Authentication Guide

### For Web / Frontend

1. Start OAuth flow:
   ```
   GET /api/auth/google/login
   ```
   Receive `auth_url` → Redirect user to Google

2. Handle callback (redirected by Google):
   ```
   GET /api/auth/google/callback?code=...
   ```
   Automatically sets `session_token` cookie

3. Use in subsequent requests:
   ```
   Cookie: session_token=session_xxx
   ```

### For Mobile Apps

1. Get Google access token from Google Sign-In SDK
2. Send to backend:
   ```
   POST /api/auth/google/mobile
   Body: { "access_token": "..." }
   ```
3. Receive `session_token` in response
4. Include in headers:
   ```
   Authorization: Bearer session_token_here
   ```

### For Testing / Demo

Use demo login (localhost only):
```
POST /api/auth/demo-login
Body: { "email": "test@example.com" }
```

---

## Common Workflows

### Workflow 1: Import and Analyze Games

```bash
# 1. Get authenticated user
curl http://localhost:8000/api/auth/me \
  -H "Cookie: session_token=session_xxx"

# 2. Import games from Chess.com
curl -X POST http://localhost:8000/api/import-games \
  -H "Cookie: session_token=session_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "chess.com",
    "username": "someplayer"
  }'

# Response: { "imported": 15, "total_found": 20 }

# 3. Get list of imported games
curl http://localhost:8000/api/games \
  -H "Cookie: session_token=session_xxx"

# 4. Analyze a game (takes 30-60 seconds)
curl -X POST http://localhost:8000/api/analyze-game \
  -H "Cookie: session_token=session_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "game_id": "game_abc123",
    "force": false
  }'

# 5. Get analysis results
curl http://localhost:8000/api/analysis/game_abc123 \
  -H "Cookie: session_token=session_xxx"

# 6. Get list of all blunders
curl http://localhost:8000/api/games/blunders \
  -H "Cookie: session_token=session_xxx"

# 7. Get list of best moves
curl http://localhost:8000/api/games/best-moves \
  -H "Cookie: session_token=session_xxx"
```

### Workflow 2: Get Analyzed Games with Stats

```bash
# Get all analyzed games with summary stats
curl http://localhost:8000/api/games/analyzed \
  -H "Cookie: session_token=session_xxx"

# Response includes:
# - List of analyzed games
# - Accuracy percentage for each
# - Count of blunders, mistakes, best moves
# - Game platform and opponent info
```

### Workflow 3: Voice Coaching Feedback

```bash
# Generate audio for analysis summary
curl -X POST http://localhost:8000/api/tts/analysis-summary/game_abc123 \
  -H "Cookie: session_token=session_xxx" \
  -H "Accept: audio/mpeg" \
  --output summary.mp3

# Play summary.mp3 in your app

# Generate audio explanation for specific move
curl -X POST http://localhost:8000/api/tts/move-explanation \
  -H "Cookie: session_token=session_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "game_id": "game_abc123",
    "move_index": 15
  }' \
  -H "Accept: audio/mpeg" \
  --output move_15.mp3

# Or generate from any text
curl -X POST http://localhost:8000/api/tts/generate \
  -H "Cookie: session_token=session_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "You played a solid game with good opening preparation.",
    "voice": "onyx"
  }' \
  --output feedback.mp3
```

### Workflow 4: Player Journey Dashboard

```bash
# Get overall progress dashboard
curl http://localhost:8000/api/journey \
  -H "Cookie: session_token=session_xxx"

# Get detailed journey data
curl http://localhost:8000/api/journey/comprehensive \
  -H "Cookie: session_token=session_xxx"

# Get weekly assessment
curl http://localhost:8000/api/journey/weekly-assessment \
  -H "Cookie: session_token=session_xxx"

# Analyze weakness trends
curl http://localhost:8000/api/journey/weakness-trends \
  -H "Cookie: session_token=session_xxx"
```

---

## Testing in Swagger UI

### Step 1: Get a Session Token

1. Open `http://localhost:8000/docs`
2. Find `POST /api/auth/demo-login`
3. Click "Try it out"
4. Enter: `{ "email": "test@example.com" }`
5. Click "Execute"
6. Copy the `session_token` from response

### Step 2: Authorize All Requests

1. Click the green "Authorize" button at top
2. Enter: `session_token_here` (paste your token)
3. Click "Authorize" then "Close"

### Step 3: Test Endpoints

1. Find `GET /api/auth/me`
2. Click "Try it out"
3. Click "Execute"
4. See authenticated user profile

---

## API Response Patterns

### Successful Response (200)
```json
{
  "data": { /* endpoint specific */ },
  "message": "Success"
}
```

### Error Response (4xx/5xx)
```json
{
  "detail": "Error message describing what went wrong"
}
```

### List Response Pattern
```json
[
  { "item": 1 },
  { "item": 2 },
  { "item": 3 }
]
```

### Paginated Response Pattern
```json
{
  "data": [ /* items */ ],
  "total": 42,
  "page": 1,
  "per_page": 10
}
```

---

## Status Codes Reference

| Code | Meaning | When It Happens |
|------|---------|-----------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid parameters |
| 401 | Unauthorized | Not authenticated or expired session |
| 403 | Forbidden | Authenticated but no permission |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource already exists or conflict |
| 429 | Rate Limited | Too many requests |
| 500 | Server Error | Backend error |
| 503 | Service Unavailable | Server down or maintenance |

---

## Rate Limits

- **Game Analysis**: 1 per 30 seconds per user
- **Game Imports**: 1 per 5 minutes per platform
- **TTS Generation**: 10 per minute per user
- **API Calls**: 100 per minute per user (general)

When rate limited, you'll receive:
```json
{
  "detail": "Rate limit exceeded. Try again in 30 seconds."
}
```

---

## Header Requirements

### Required for all requests:
```
Content-Type: application/json
```

### Required for authenticated requests:
Either cookie:
```
Cookie: session_token=session_xxx
```

Or bearer token:
```
Authorization: Bearer session_token_xxx
```

### Optional headers:
```
User-Agent: MyApp/1.0
X-Request-ID: unique-id-123
X-Client-Version: 1.0.0
```

---

## Common Integration Patterns

### Pattern 1: Fetch & Analyze Games (Python)

```python
import requests

BASE_URL = "http://localhost:8000/api"
session_token = "your_token_here"
headers = {"Cookie": f"session_token={session_token}"}

# Import games
response = requests.post(
    f"{BASE_URL}/import-games",
    headers=headers,
    json={"platform": "chess.com", "username": "player"}
)
imported_count = response.json()["imported"]

# Get games
games = requests.get(f"{BASE_URL}/games", headers=headers).json()

# Analyze each
for game in games[:5]:  # Limit to 5 for demo
    analysis = requests.post(
        f"{BASE_URL}/analyze-game",
        headers=headers,
        json={"game_id": game["game_id"]}
    ).json()
    print(f"Game {game['game_id']}: {analysis['blunders']} blunders")
```

### Pattern 2: Get Weakness Trends (JavaScript)

```javascript
const BASE_URL = "http://localhost:8000/api";
const sessionToken = "your_token_here";

const headers = {
  "Cookie": `session_token=${sessionToken}`,
  "Content-Type": "application/json"
};

// Fetch weakness trends
const response = await fetch(
  `${BASE_URL}/journey/weakness-trends`,
  { headers }
);

const trends = await response.json();

trends.forEach(weakness => {
  console.log(`${weakness.subcategory}: ${weakness.frequency_trend}`);
});
```

### Pattern 3: Generate Voice Feedback (cURL)

```bash
#!/bin/bash

SESSION_TOKEN="your_token_here"
GAME_ID="game_abc123"

# Get analysis summary as audio
curl -X POST "http://localhost:8000/api/tts/analysis-summary/$GAME_ID" \
  -H "Cookie: session_token=$SESSION_TOKEN" \
  --output analysis_summary.mp3

# Play audio
mpv analysis_summary.mp3

# Or with ffplay
ffplay -nodisp -autoexit analysis_summary.mp3
```

---

## Troubleshooting

### 401 Unauthorized
- **Cause**: Session token missing, invalid, or expired
- **Solution**: 
  - Check cookie is being sent
  - Get a new session token via login
  - Verify token hasn't expired (30 days default)

### 404 Not Found
- **Cause**: Game ID or resource doesn't exist
- **Solution**:
  - Verify game was imported
  - Check game_id is correct
  - Ensure game belongs to authenticated user

### 500 Server Error on Analysis
- **Cause**: Stockfish analysis failed
- **Solution**:
  - Try analyzing again
  - Check game PGN is valid
  - Look at server logs for details

### 429 Rate Limited
- **Cause**: Too many requests
- **Solution**:
  - Wait before retrying
  - Implement exponential backoff
  - Cache results when possible

---

## Development Tips

### 1. Use Swagger UI for API Exploration
- Try out endpoints interactively
- See live responses from server
- Understand request/response format

### 2. Copy CURLs from Swagger
- Right-click "Execute" → "Copy as cURL"
- Test in terminal, use in scripts
- Debug network issues

### 3. Keep Session Tokens Safe
- Don't commit tokens to git
- Use environment variables
- Implement token rotation

### 4. Monitor Analysis Jobs
- Track game IDs being analyzed
- Check logs for failures
- Implement retry logic

### 5. Cache Analysis Results
- Don't re-analyze same game
- Cache weakness trends
- Fetch only when needed

---

## Example Integration Checklist

- [ ] Implement OAuth login flow
- [ ] Store session token securely
- [ ] Handle session expiration
- [ ] Implement game import
- [ ] Show analyzed games list
- [ ] Display game analysis UI
- [ ] Generate and play voice feedback
- [ ] Show player journey dashboard
- [ ] Track weakness trends
- [ ] Add error handling for API failures
- [ ] Implement retry logic
- [ ] Add loading states
- [ ] Cache analysis results
- [ ] Test on multiple browsers/devices

---

## Additional Resources

- **API Base**: `http://localhost:8000`
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`
- **Full Documentation**: See `API_DOCUMENTATION.md`
- **OpenAPI Spec**: See `openapi.yaml`

---

## Getting Help

1. Check `API_DOCUMENTATION.md` for detailed endpoint docs
2. Review example workflows above
3. Test endpoint in Swagger UI
4. Check server logs for error details
5. Review request/response in browser DevTools

---

**Last Updated**: February 2024
**API Version**: 1.0.0
**Status**: Active & Stable
