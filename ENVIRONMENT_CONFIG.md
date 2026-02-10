# Environment Configuration Guide

This app automatically switches between **Emergent** (for testing) and **Production** (your server) modes.

## How It Works

| Feature | Emergent Environment | Production (Your Server) |
|---------|---------------------|--------------------------|
| **LLM Calls** | Uses `emergentintegrations` | Uses OpenAI SDK directly |
| **TTS** | Uses `emergentintegrations` | Uses OpenAI SDK directly |
| **Google Auth** | Uses `auth.emergentagent.com` | Uses YOUR Google OAuth credentials |
| **Auth Endpoint** | `/api/auth/session` works | `/api/auth/google/login` only |

## Automatic Detection

### Backend (`llm_service.py`)
- If `OPENAI_API_KEY` is set → Uses **OpenAI directly**
- If only `EMERGENT_LLM_KEY` is set → Uses **Emergent integrations**

### Frontend (`Landing.jsx`)
- If hostname contains `emergentagent` or `preview` → Uses **Emergent auth**
- Otherwise → Uses **your Google OAuth**

---

## Production Setup (Your Server)

### Backend `.env`:
```env
# LLM - Use OpenAI directly (NOT Emergent)
OPENAI_API_KEY=sk-your-openai-api-key

# Google OAuth - YOUR credentials (NOT Emergent)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-secret
GOOGLE_REDIRECT_URI=https://chessguru.ai/api/auth/google/callback
FRONTEND_URL=https://chessguru.ai

# Database
MONGO_URL=mongodb://your-mongodb-host:27017
DB_NAME=chess_coach
```

### Frontend `.env` (or build with):
```env
REACT_APP_BACKEND_URL=https://chessguru.ai
```

### Google OAuth Setup:
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create OAuth 2.0 credentials
3. Add redirect URI: `https://chessguru.ai/api/auth/google/callback`

---

## Emergent Testing (Automatic)

When running in Emergent, these are automatically set:
- `EMERGENT_LLM_KEY` → LLM uses Emergent
- Preview URL detected → Auth uses Emergent

No configuration needed - just use Emergent as normal!

---

## Manual Override (Optional)

Force a specific provider mode in backend `.env`:
```env
LLM_PROVIDER_MODE=openai    # Force OpenAI even if Emergent key exists
# or
LLM_PROVIDER_MODE=emergent  # Force Emergent even if OpenAI key exists
```

---

## Files Involved

- `/backend/llm_service.py` - LLM abstraction layer
- `/backend/server.py` - Auth endpoints with environment check
- `/frontend/src/pages/Landing.jsx` - Auth flow detection
- `/frontend/src/App.js` - Auth callback handling

---

## Summary

**Push your code confidently!** 

The same codebase works in both environments:
- In Emergent → Uses Emergent services for testing
- On your server → Uses YOUR services (OpenAI, Google OAuth)

No code changes needed when deploying to production.
