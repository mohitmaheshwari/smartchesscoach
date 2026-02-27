"""
Engine Configuration

Single source of truth for engine versioning.
Change this constant when upgrading behavioral analysis engine.

History:
- P1.0: Initial behavioral analysis (Feb 26, 2026)
- P1.5: Coach Memory & Learning Velocity (Feb 27, 2026)
- P1.6: Historical Re-Analysis + Adaptive Difficulty (Feb 27, 2026)
"""

ENGINE_VERSION = "P1.6"

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
