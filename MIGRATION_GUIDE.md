# Chess Coach AI - Self-Hosting Migration Guide

## Overview
This guide helps you migrate Chess Coach AI from Emergent infrastructure to your own AWS/self-hosted environment.

---

## 1. Prerequisites

- AWS Account (or any cloud provider)
- MongoDB Atlas account (or self-hosted MongoDB)
- OpenAI API Key (for GPT and TTS)
- Google Cloud Console project (for OAuth)
- SendGrid account (for emails - optional)
- GitHub repository access

---

## 2. Export Code from Emergent

1. Click **"Save to GitHub"** in the Emergent chat interface
2. Select your branch and push
3. Clone the repository locally:
   ```bash
   git clone https://github.com/your-username/your-repo.git
   cd your-repo
   ```

---

## 3. Database Setup

### Option A: MongoDB Atlas (Recommended)
1. Create a free cluster at [mongodb.com/atlas](https://mongodb.com/atlas)
2. Get your connection string: `mongodb+srv://user:pass@cluster.mongodb.net/chess_coach`
3. Run the initialization script:
   ```bash
   cd backend
   export MONGO_URL="mongodb+srv://user:pass@cluster.mongodb.net/"
   export DB_NAME="chess_coach"
   python init_db.py
   ```

### Option B: Self-hosted MongoDB
1. Install MongoDB on your server
2. Run: `python init_db.py`

---

## 4. Replace Emergent Dependencies

### 4.1 Replace `emergentintegrations` with OpenAI SDK

**Install OpenAI SDK:**
```bash
pip uninstall emergentintegrations
pip install openai
```

**Update `requirements.txt`:**
```diff
- emergentintegrations==0.1.0
+ openai>=1.0.0
```

**Code Changes in `server.py`:**

Find and replace all LLM calls:

```python
# BEFORE (Emergent)
from emergentintegrations.llm.chat import LlmChat, UserMessage

chat = LlmChat(
    api_key=EMERGENT_LLM_KEY,
    session_id="...",
    system_message="..."
).with_model("openai", "gpt-5.2")

response = await chat.a_send_message(UserMessage(text="..."))
result = response.text

# AFTER (Direct OpenAI)
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

response = await client.chat.completions.create(
    model="gpt-4o",  # or "gpt-4-turbo"
    messages=[
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."}
    ]
)
result = response.choices[0].message.content
```

**TTS Changes:**
```python
# BEFORE (Emergent)
from emergentintegrations.llm.openai import OpenAITextToSpeech

tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
audio = await tts.a_generate(text="...", voice="onyx")

# AFTER (Direct OpenAI)
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

response = await client.audio.speech.create(
    model="tts-1",
    voice="onyx",
    input="..."
)
audio_bytes = response.content
```

### 4.2 Replace Emergent Google Auth

**Set up Google OAuth:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable "Google+ API" or "Google Identity"
4. Create OAuth 2.0 credentials
5. Add authorized redirect URIs: `https://yourdomain.com/api/auth/google/callback`

**Update `server.py` auth endpoints:**
```python
# You'll need to implement standard Google OAuth flow
# Use libraries like: authlib, python-social-auth, or manual OAuth2
```

---

## 5. Environment Variables

### Backend (`/backend/.env`):
```env
# Database
MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net/
DB_NAME=chess_coach

# OpenAI (replaces EMERGENT_LLM_KEY)
OPENAI_API_KEY=sk-your-openai-api-key

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://yourdomain.com/api/auth/google/callback

# Email (optional)
SENDGRID_API_KEY=your-sendgrid-key
SENDER_EMAIL=noreply@yourdomain.com

# App
CORS_ORIGINS=https://yourdomain.com
SECRET_KEY=your-random-secret-key-for-sessions
```

### Frontend (`/frontend/.env`):
```env
REACT_APP_BACKEND_URL=https://api.yourdomain.com
REACT_APP_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

---

## 6. AWS Deployment

### Option A: Simple (EC2 + PM2)

```bash
# On EC2 instance
sudo apt update
sudo apt install nodejs npm python3 python3-pip nginx

# Backend
cd backend
pip install -r requirements.txt
pm2 start "uvicorn server:app --host 0.0.0.0 --port 8001" --name chess-backend

# Frontend
cd frontend
npm install
npm run build
# Serve build folder with nginx
```

### Option B: Containerized (ECS/Docker)

**Dockerfile.backend:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
```

**Dockerfile.frontend:**
```dockerfile
FROM node:18-alpine AS build
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install
COPY . .
RUN yarn build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
```

---

## 7. Nginx Configuration

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # Frontend
    location / {
        root /var/www/chess-coach/frontend/build;
        try_files $uri /index.html;
    }
    
    # Backend API
    location /api {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

---

## 8. Files to Modify

| File | Changes Needed |
|------|----------------|
| `backend/server.py` | Replace emergentintegrations, update auth |
| `backend/journey_service.py` | Replace LlmChat with OpenAI client |
| `backend/rag_service.py` | Replace embeddings calls |
| `backend/requirements.txt` | Remove emergentintegrations, add openai |
| `frontend/.env` | Update REACT_APP_BACKEND_URL |

---

## 9. Testing Checklist

- [ ] Database connection works
- [ ] User can sign in with Google
- [ ] Games can be imported from Chess.com/Lichess
- [ ] AI analysis generates correctly
- [ ] Voice coaching (TTS) works
- [ ] Background sync runs
- [ ] Email notifications work (if configured)

---

## 10. Cost Estimates

| Service | Monthly Cost |
|---------|-------------|
| MongoDB Atlas (M0 Free) | $0 |
| OpenAI API (moderate use) | $20-50 |
| AWS EC2 (t3.small) | ~$15 |
| Domain + SSL | ~$1 |
| **Total** | **~$35-65/month** |

---

## Need Help?

- OpenAI API Docs: https://platform.openai.com/docs
- MongoDB Atlas: https://docs.atlas.mongodb.com
- Google OAuth: https://developers.google.com/identity/protocols/oauth2
