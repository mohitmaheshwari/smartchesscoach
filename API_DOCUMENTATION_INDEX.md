# Smart Chess Coach API - Documentation Index

## Overview

This directory contains complete Swagger/OpenAPI documentation for the Smart Chess Coach API, a comprehensive chess analysis and coaching platform.

---

## 📚 Documentation Files

### 1. **openapi.yaml** (Main OpenAPI Specification)
- **Format**: YAML (OpenAPI 3.0.0)
- **Purpose**: Machine-readable API specification
- **Contains**:
  - All endpoint definitions
  - Request/response schemas
  - Authentication methods
  - Error codes and examples
  - Data model definitions
- **Usage**: 
  - Import into Postman/Insomnia
  - Generate client SDKs
  - Used by Swagger UI automatically

### 2. **API_DOCUMENTATION.md** (Comprehensive Documentation)
- **Format**: Markdown
- **Purpose**: Human-readable API reference
- **Contains**:
  - Detailed endpoint descriptions
  - Request/response examples (JSON)
  - Authentication workflows
  - Data model schemas
  - Common workflows
  - Error handling guide
  - Rate limiting info
  - Quick copy-paste examples
- **Best for**: Developers learning the API

### 3. **DEVELOPER_GUIDE.md** (Implementation Guide)
- **Format**: Markdown
- **Purpose**: Step-by-step integration guide
- **Contains**:
  - How to access documentation
  - Authentication flow examples
  - Complete workflow examples (with curl/Python/JavaScript)
  - Testing in Swagger UI
  - Common integration patterns
  - Troubleshooting guide
  - Development tips
- **Best for**: Frontend/mobile developers integrating the API

### 4. **API_ENDPOINTS.json** (Quick Reference)
- **Format**: JSON
- **Purpose**: Machine-readable endpoint reference
- **Contains**:
  - List of all endpoints
  - Method and path
  - Required parameters
  - Voice options
  - Platform options
  - Status codes
  - Rate limits
- **Best for**: Building tools, quick lookups

### 5. **server.py Configuration**
- **Updated**: Added OpenAPI metadata to FastAPI app
- **Title**: "Smart Chess Coach API"
- **Description**: Full platform description
- **Version**: 1.0.0
- **Tags**: Organized by category

### 6. **redoc.html** (Beautiful Documentation UI)
- **Format**: HTML
- **Purpose**: ReDoc-powered API documentation
- **URL**: Served at `/redoc` endpoint
- **Features**:
  - Beautiful, responsive design
  - Full-text search
  - Code examples in multiple languages

---

## 🌐 Accessing Documentation

### In Development

When running locally (`python server.py`):

| Tool | URL | Purpose |
|------|-----|---------|
| **Swagger UI** | `http://localhost:8000/docs` | Interactive testing |
| **ReDoc** | `http://localhost:8000/redoc` | Beautiful documentation |
| **OpenAPI JSON** | `http://localhost:8000/openapi.json` | Machine-readable spec |

### Configuration in Code

The FastAPI app is configured with:
```python
app = FastAPI(
    title="Smart Chess Coach API",
    description="AI-Powered Chess Learning Platform...",
    version="1.0.0",
    openapi_tags=[...]
)
```

---

## 📖 Documentation Structure

### By Role

**For Product Managers:**
- Read: `API_DOCUMENTATION.md` - Overview section
- Skim: `DEVELOPER_GUIDE.md` - Common workflows

**For Backend Developers:**
- Read: `openapi.yaml` - Full specification
- Skim: `API_DOCUMENTATION.md` - Technical details

**For Frontend Developers:**
- Read: `DEVELOPER_GUIDE.md` - Complete integration flow
- Reference: `API_DOCUMENTATION.md` - Detailed endpoints
- Test: Swagger UI at `/docs`

**For Mobile Developers:**
- Read: `DEVELOPER_GUIDE.md` - Mobile auth section
- Reference: `API_ENDPOINTS.json` - Quick endpoint list
- Test: `http://localhost:8000/docs`

**For DevOps/API Gateway:**
- Reference: `openapi.yaml` - Full specification
- Reference: `API_ENDPOINTS.json` - All endpoints

---

## 🚀 Quick Start

### 1. Start the Server
```bash
cd backend
python server.py
```

### 2. View Documentation
- **Interactive**: Open `http://localhost:8000/docs`
- **Readable**: Open `http://localhost:8000/redoc`
- **Raw**: Open `http://localhost:8000/openapi.json`

### 3. Test an Endpoint
1. Go to `http://localhost:8000/docs`
2. Find the endpoint you want to test
3. Click "Try it out"
4. Fill in parameters
5. Click "Execute"
6. See live response

### 4. Get Authentication
1. Find `POST /auth/demo-login`
2. Enter test email: `test@example.com`
3. Copy returned `session_token`
4. Click green "Authorize" button
5. Paste token and authorize
6. All subsequent requests will use this token

---

## 📋 API Categories

### Authentication (7 endpoints)
- Google OAuth flow
- Mobile authentication
- Demo login (testing)
- Session management
- Current user info

### Platforms (1 endpoint)
- Connect Chess.com/Lichess accounts

### Games (6 endpoints)
- Import games
- List games
- Get specific game
- List analyzed games
- List blunders
- List best moves

### Analysis (2 endpoints)
- Analyze a game (Stockfish + AI)
- Get analysis results

### Voice Coaching (3 endpoints)
- TTS text rendering
- Analysis summary voice
- Move explanation voice

### Player Journey (6 endpoints)
- Journey dashboard
- Comprehensive data
- Weekly assessment
- Weakness trends
- Link accounts
- Get linked accounts

**Total: 25 endpoints**

---

## 🔐 Security

### Authentication Methods
1. **Cookie-based** (Web): `Cookie: session_token=xxx`
2. **Bearer Token** (Mobile/API): `Authorization: Bearer xxx`

### Session Management
- Default expiry: 30 days
- Clear old sessions on login
- HttpOnly cookies (secure for web)

### Rate Limiting
- Game analysis: 1 per 30 seconds
- Game imports: 1 per 5 minutes
- TTS: 10 per minute
- General: 100 per minute

---

## 🧪 Testing Guide

### Using Swagger UI
1. Go to `http://localhost:8000/docs`
2. Try demo login for quick auth
3. Use "Try it out" buttons
4. Check request/response format
5. Copy curl commands if needed

### Using cURL
```bash
# Get auth
curl -X POST http://localhost:8000/api/auth/demo-login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Use token
curl http://localhost:8000/api/auth/me \
  -H "Cookie: session_token=YOUR_TOKEN_HERE"
```

### Using Postman
1. Download openapi.yaml file
2. Postman → Import → Import File
3. Select openapi.yaml
4. Collections auto-created
5. Set session_token in Auth tab
6. Run requests

---

## 📊 Data Models

### Core Models
- **User**: Profile with chess platform usernames
- **Game**: Chess game with PGN and metadata
- **GameAnalysis**: Stockfish evaluations + AI coaching
- **MistakePattern**: Recurring weakness tracking

### Analysis Data
- **Commentary**: Move-by-move feedback
- **StockfishResult**: Engine evaluations
- **PlayerProfile**: User learning style and history

---

## 🔄 Common Workflows

### 1. Import and Analyze
```
1. POST /import-games (fetch from Chess.com/Lichess)
2. GET /games (list imported)
3. POST /analyze-game (analyze with Stockfish + AI)
4. GET /analysis/{game_id} (view results)
```

### 2. View Blunders
```
1. GET /games/analyzed (list analyzed games)
2. GET /games/blunders (all blunders from all games)
3. Click on blunder to review FEN position
```

### 3. Voice Feedback
```
1. POST /analyze-game (generate analysis)
2. POST /tts/analysis-summary/{game_id} (get audio)
3. Play audio in app
```

### 4. Track Progress
```
1. GET /journey (dashboard)
2. GET /journey/weakness-trends (improvement over time)
3. GET /journey/weekly-assessment (weekly stats)
```

---

## 🛠️ Integration Checklist

- [ ] Read DEVELOPER_GUIDE.md
- [ ] Access documentation at `/docs`
- [ ] Get demo session token
- [ ] Test GET /auth/me
- [ ] Connect platform account
- [ ] Import games
- [ ] Analyze a game
- [ ] View analysis results
- [ ] Generate voice feedback
- [ ] View journey dashboard
- [ ] Implement error handling
- [ ] Add loading states
- [ ] Cache results
- [ ] Test on production environment

---

## 📞 Support Resources

### Documentation Files
- `API_DOCUMENTATION.md` - Complete reference
- `DEVELOPER_GUIDE.md` - Implementation guide
- `API_ENDPOINTS.json` - Quick lookup
- `openapi.yaml` - Specification

### Live Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

### Code Files
- Main API: `server.py`
- Backend modules: See `backend/` directory

---

## 📝 Version History

### v1.0.0 (Current)
- All core endpoints implemented
- Swagger/OpenAPI documentation complete
- Developer guides written
- Authentication systems ready
- Game analysis fully functional
- Voice coaching integrated
- Journey dashboard active

---

## 🎯 Next Steps

1. **Developers**: Read `DEVELOPER_GUIDE.md` and access `/docs`
2. **PM/Design**: Review `API_DOCUMENTATION.md` overview
3. **QA**: Use Swagger UI to test all endpoints
4. **DevOps**: Reference `openapi.yaml` for API gateway setup

---

## 📄 File Summary

| File | Format | Purpose | Audience |
|------|--------|---------|----------|
| openapi.yaml | YAML | Machine-readable spec | Tools, DevOps |
| API_DOCUMENTATION.md | Markdown | Complete reference | Everyone |
| DEVELOPER_GUIDE.md | Markdown | Integration guide | Developers |
| API_ENDPOINTS.json | JSON | Quick reference | Tools |
| redoc.html | HTML | UI for docs | Browser |
| server.py | Python | FastAPI config | Backend |

---

**Last Updated**: February 2024  
**API Version**: 1.0.0  
**Status**: Production Ready  
**Maintained By**: Smart Chess Coach Team

---

## Quick Links

- 📖 [Full API Documentation](./API_DOCUMENTATION.md)
- 🚀 [Developer Guide](./DEVELOPER_GUIDE.md)
- 📋 [Endpoints Reference](./API_ENDPOINTS.json)
- 🔧 [OpenAPI Specification](./openapi.yaml)
- 🌐 [Swagger UI](http://localhost:8000/docs) (when running)
- 📚 [ReDoc](http://localhost:8000/redoc) (when running)
