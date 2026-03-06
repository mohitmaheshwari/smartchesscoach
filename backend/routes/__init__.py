"""
Routes Module
=============

This module contains the modular route definitions extracted from the monolithic server.py.
Each route file handles a specific domain of the application.

Extracted Domains (IN USE):
- auth: Authentication endpoints (login, logout, session management, OAuth)
- feedback: Pattern learning and feedback endpoints for self-correction system

Domains TO BE EXTRACTED (from server.py):
- games: Game import, listing, and analysis (~40 endpoints)
- coach: Coach-related endpoints (state, memory, analytics, play) (~50 endpoints)
- reflect: Reflection engine endpoints (~15 endpoints)
- training: Training and puzzle endpoints (~20 endpoints)
- journey: Journey/progress dashboard endpoints (~15 endpoints)
- cognitive: Cognitive gap analysis endpoints (~20 endpoints)
- behavioral: Behavioral analysis endpoints (~15 endpoints)
- notifications: Notification management (~5 endpoints)
- eval: Position evaluation endpoints (~5 endpoints)

Total endpoints in server.py: ~315
Endpoints extracted: ~20 (auth: 10, feedback: 8)
Remaining: ~295
"""

from fastapi import APIRouter

# Create main API router that will be included in the app
api_router = APIRouter(prefix="/api")
