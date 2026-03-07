"""
Routes Module
=============

This module contains the modular route definitions extracted from the monolithic server.py.
Each route file handles a specific domain of the application.

Extracted Domains (IN USE):
- auth: Authentication endpoints (login, logout, session management, OAuth) - 9 endpoints
- feedback: Pattern learning and feedback endpoints for self-correction system - 14 endpoints
- games: Game listing, details, blunders, best-moves, analysis-status - 7 endpoints
- lab: Lab page analysis, deep strategy, mistake explanations - 4 endpoints
- reflect: Reflection engine, V1 endpoints, post-loss recovery - 11 endpoints
- training: Training sessions, cards, prescribed training, habits - 13 endpoints
- coach: Coach-related endpoints (state, memory, analytics, play) - 17 endpoints
- journey: Journey/progress dashboard, account linking, sync - 11 endpoints
- cognitive: Cognitive gap analysis, patterns, training priority, TSI - 18 endpoints
- behavioral: Behavioral analysis, missions, reanalysis - 9 endpoints
- notifications: Notification management, push, device registration - 8 endpoints
- missions: Daily missions, mission sessions, completion - 8 endpoints
- settings: Email notifications, profile, onboarding - 6 endpoints

Total endpoints in server.py: ~200 (was ~274)
Endpoints extracted: ~135 (auth: 9, feedback: 14, games: 7, lab: 4, reflect: 11, training: 13, coach: 17, journey: 11, cognitive: 18, behavioral: 9, notifications: 8, missions: 8, settings: 6)
Lines removed: ~3,870 (from 14,560 to ~10,690)
"""

from fastapi import APIRouter

# Create main API router that will be included in the app
api_router = APIRouter(prefix="/api")
