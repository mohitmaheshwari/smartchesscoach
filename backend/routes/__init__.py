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
- coach: Coach-related endpoints (state, memory, analytics, play) - 17 endpoints
- journey: Journey/progress dashboard, account linking, sync - 11 endpoints
- cognitive: Cognitive gap analysis, patterns, training priority, TSI - 18 endpoints

Domains TO BE EXTRACTED (from server.py):
- behavioral: Behavioral analysis endpoints (~9 endpoints)
- missions: Mission management endpoints (~8 endpoints)
- notifications: Notification management (~9 endpoints)

Total endpoints in server.py: ~234 (was ~274)
Endpoints extracted: ~100 (auth: 9, feedback: 10, games: 7, lab: 4, reflect: 11, training: 13, coach: 17, journey: 11, cognitive: 18)
Lines removed: ~2,600 (from 14,560 to ~11,960)
"""

from fastapi import APIRouter

# Create main API router that will be included in the app
api_router = APIRouter(prefix="/api")
