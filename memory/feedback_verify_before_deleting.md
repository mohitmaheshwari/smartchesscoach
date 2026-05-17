---
name: Always verify imports before claiming dead code
description: Agent exploration reported ~40% false positives on dead code — always grep thoroughly and check App.js routes before recommending deletion
type: feedback
---

Never trust a single-pass grep to determine if code is dead. In this project:

- Pages reported as "not routed" WERE routed in App.js (Training, ChessJourney, CoachHome, JourneyIntelligence)
- A file reported as "non-existent" (LabClassic.jsx) DID exist
- A service reported as "stale stub" (services/player_profile_service.py) WAS actively imported
- Components reported as "unused" were still imported (TeachingPanel, GameDecryption, GuidedAnalysis, DrillCard, CoachMemoryPanel)
- A "duplicate set_db" bug was actually correct code (called once each)

**Why:** ~40% of the automated assessment was wrong. Deleting those files would have broken the app.

**How to apply:** Before recommending any file deletion, verify with at least: (1) recursive grep for the filename/export across the entire codebase, (2) check App.js routes for pages, (3) check index.js barrel exports. When unsure, ask the user to verify rather than assuming dead.
