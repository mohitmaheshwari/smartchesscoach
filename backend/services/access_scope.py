"""
Access-scope helper for cross-user reads by reviewers.

Most game/analysis routes filter by `{"user_id": user.user_id}` so each
user only sees their own games. Reviewers (`User.is_reviewer == True`)
need to see games from every user so they can flag content-quality
bugs against any decryption output.

Use `user_scope_filter(user)` to build the user-id filter for a Mongo
query. Returns {} for reviewers (no filter), {"user_id": user.user_id}
otherwise. Drop it into existing find/find_one calls in place of the
hard-coded user filter.

Example:
    games = await db.games.find(
        user_scope_filter(user),
        {"_id": 0}
    ).to_list(100)

For composite filters, merge:
    flt = {"is_analyzed": True, **user_scope_filter(user)}
"""
from __future__ import annotations

from typing import Any, Dict


def user_scope_filter(user: Any) -> Dict[str, Any]:
    """Return the user-id filter clause appropriate for `user`.

    - Reviewer (is_reviewer=True): {} (no scoping, all users' data)
    - Regular user: {"user_id": user.user_id}
    """
    if getattr(user, "is_reviewer", False):
        return {}
    return {"user_id": user.user_id}
