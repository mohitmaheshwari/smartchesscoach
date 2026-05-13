"""
Common MongoDB query fragments shared across routes/services.

Single source of truth — when filter semantics change, update here, not
in every consumer. Per memory rule feedback_no_parallel_surfaces.
"""

# Hide inactive games from coaching/training/dashboard surfaces.
# Inactive games stay in storage (visible to admin, re-activatable),
# but are not shown to the player or used for analytics.
#
# Legacy documents without `is_active` default to ACTIVE — this lets us
# roll out the flag gradually without breaking endpoints that read games
# the migration hasn't touched yet.
#
# Merge with other query filters via dict spread:
#     await db.games.find({**user_scope_filter(user), **ACTIVE_GAMES_FILTER})
ACTIVE_GAMES_FILTER = {"is_active": {"$ne": False}}
