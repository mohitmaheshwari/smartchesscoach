"""
Routes Module
=============

This module contains the modular route definitions extracted from the monolithic server.py.
Each route file handles a specific domain of the application.

Extracted Domains (IN USE):
- auth: Authentication endpoints (login, logout, session management, OAuth) - 9 endpoints
- feedback: Pattern learning and feedback endpoints for self-correction system - 10 endpoints
- games: Game listing, details, blunders, best-moves, analysis-status - 7 endpoints
- lab: Lab page analysis, deep strategy, mistake explanations - 4 endpoints
- reflect: Reflection engine, V1 endpoints, post-loss recovery - 11 endpoints
- training: Training sessions, cards, prescribed training, habits - 13 endpoints

Domains TO BE EXTRACTED (from server.py):
- coach: Coach-related endpoints (state, memory, analytics, play) (~50 endpoints)
- journey: Journey/progress dashboard endpoints (~15 endpoints)
- cognitive: Cognitive gap analysis endpoints (~20 endpoints)
- behavioral: Behavioral analysis endpoints (~15 endpoints)
- notifications: Notification management (~5 endpoints)

Total endpoints in server.py: ~220 (was ~315)
Endpoints extracted: ~54 (auth: 9, feedback: 10, games: 7, lab: 4, reflect: 11, training: 13)
Lines removed: ~1,592 (from 14,560 to 12,968)
"""

from fastapi import APIRouter

# Create main API router that will be included in the app
api_router = APIRouter(prefix="/api")
