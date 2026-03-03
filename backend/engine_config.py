"""
Engine Configuration

Single source of truth for engine versioning.
Change this constant when upgrading behavioral analysis engine.

History:
- P1.0: Initial behavioral analysis (Feb 26, 2026)
- P1.5: Coach Memory & Learning Velocity (Feb 27, 2026)
- P1.6: Historical Re-Analysis + Adaptive Difficulty (Feb 27, 2026)
- P1.7: Mission Completion & Feedback Loop (Feb 27, 2026)
- P2.0: CoachState Foundation (Mar 2, 2026)
- P2.3: Pattern Intelligence + Memory Continuity (Mar 2, 2026)
- P2.4: Intent Recognition Layer - Step 6 Complete (Mar 3, 2026)
- P2.5: Adaptive Teaching Style - Step 7 Complete (Mar 3, 2026)
- P2.6: Breakthrough & Plateau Detection - Step 8 Complete (Mar 3, 2026)
- P2.7: Focus Lock Mode - Step 9 Complete (Mar 3, 2026)
"""

ENGINE_VERSION = "P2.7"

# Configuration for reanalysis jobs
REANALYSIS_CONFIG = {
    "max_games_per_run": 50,
    "sleep_between_games_ms": 300,
    "max_concurrent_jobs_per_user": 1,
}

# Difficulty thresholds
DIFFICULTY_CONFIG = {
    "hard_min_confidence": 0.7,
    "hard_max_recent_collapses": 1,  # If 2+ collapses in last 3, cap at STANDARD
    "collapse_tilt_threshold": 0.6,
    "collapse_quality_bucket": "BAD",
}
