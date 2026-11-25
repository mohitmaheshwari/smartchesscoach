"""Nothing engine-derived may be served while the user is in a live Lichess game.

Why this test exists, and why it is written BEFORE the feature
-------------------------------------------------------------
`docs/play_through_lichess_scope.md` proposes playing a real Lichess game on
our board. Lichess's Board API permits that explicitly -- *"Play on Lichess
with physical boards and third-party clients"* -- on one condition: *"Engine
assistance, or any kind of outside help, is forbidden."*

The penalty for breaking it does not land on us. `BoardReport.scala` matches
the referer host against a server-side regex described as "referer domains
that use engine"; a match publishes `BoardApiMark`, which `modules/mod/
Env.scala` hands to `ModApi.autoEngine` -> `userRepo.setEngine`. That is a
full engine mark on **the player's** Lichess account, with our domain written
into their mod note, their reports auto-processed as cheating and their
opponents' ratings refunded. It is checked once per game at a pseudo-random
ply and lands after a delay that is longest for the weakest players (up to
~24h under 1800), so it cannot be found by testing.

So this cannot be a feature flag. A flag that flips the wrong way does not
break a page; it brands real people as cheats.

The audit this test encodes (2026-11-25)
----------------------------------------
A static scan of `routes/` found **163 endpoints** where a client-supplied
position can reach the engine -- including `POST /api/best-moves`, which
returns best moves for any FEN you hand it, and `POST /api/coach/line/move`,
which plays any line at depth 16. Both are live today. The first version of
this scan said 73; it was wrong, because it looked only inside each handler
and missed engine access through neutrally-named helpers. Either way the
conclusion is the same and stronger: guarding them by hand would rot -- one
will be missed, and new endpoints land weekly.

Therefore the guard is **one layer above every route and fails closed**: while
the authenticated user has a live Lichess Board-API game, every API path is
refused except a small, explicitly reviewed allowlist of what playing itself
requires. A new endpoint is covered the day it is written, by doing nothing.

What must exist for this test to pass
-------------------------------------
`services/live_play_guard.py` exposing:

    PLAY_ALLOWLIST: frozenset[str]   # exact paths usable during a live game
    def is_blocked_during_live_game(path: str) -> bool
    async def user_has_live_lichess_game(db, user_id) -> bool

and `server.py` installing it as middleware. Until then this test fails, which
is the point: it is the gate, not the proof.
"""

from __future__ import annotations

import ast
import io
import os
import re
import sys
from pathlib import Path
from typing import List, Set, Tuple

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


# --------------------------------------------------------------- the audit

_POSITION_HINT = re.compile(
    r"\bfen\b|\bmoves\b|\bstart_fen\b|\bmoment_fen\b|\bfen_before\b|\bposition\b", re.I
)
# Names that mean "the engine is in reach". Kept broad on purpose -- see the
# module-level note below about why a narrow version was wrong.
_ENGINE_HINT = re.compile(
    r"stockfish|best_move|bestmove|evaluat|eval_|\beval\b|centipawn|cp_loss"
    r"|analy[sz]|engine|depth\s*=|_depth\b|tablebase|\bpv\b",
    re.I,
)


def engine_reachable_endpoints() -> List[Tuple[str, str]]:
    """(METHOD path, file:line) for routes where a client position meets the engine.

    Deliberately over-inclusive. A false positive costs one allowlist review;
    a false negative costs a real person their Lichess account.

    This is judged per MODULE, not per handler body. The first version of this
    scan looked only inside the handler and so missed `routes/line_board.py`,
    whose handler reads `body.start_fen` and then calls a local `_engine()` /
    `step(...)` helper -- neutral names that match no engine keyword. The
    positive-control test below is what caught that, which is the whole reason
    it exists. So: if a route module can reach the engine anywhere in it, every
    handler in it that accepts a position counts.
    """
    found: List[Tuple[str, str]] = []
    for path in sorted((BACKEND / "routes").glob("*.py")):
        if path.name.startswith(("admin", "test")):
            continue
        source = io.open(path, encoding="utf-8", errors="replace").read()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        module_reaches_engine = bool(_ENGINE_HINT.search(source))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            routes = []
            for dec in node.decorator_list:
                m = re.search(
                    r'router\.(get|post|put|patch)\(\s*[\'"]([^\'"]+)',
                    ast.unparse(dec),
                )
                if m:
                    routes.append((m.group(1).upper(), m.group(2)))
            if not routes:
                continue
            body = ast.unparse(node)
            takes_position = bool(
                _POSITION_HINT.search(ast.unparse(node.args))
                or _POSITION_HINT.search(body)
            )
            if takes_position and module_reaches_engine:
                for verb, route in routes:
                    found.append((f"{verb} {route}", f"{path.name}:{node.lineno}"))
    return found


def test_the_audit_scanner_still_finds_the_endpoints_it_was_built_from() -> None:
    """Positive control: a clean run below must mean "guarded", not "scanner broke".

    These two are the worst cases found on 2026-11-25 and both are live. If the
    scanner stops seeing them, every other assertion here is worthless.
    """
    endpoints = {ep for ep, _ in engine_reachable_endpoints()}
    assert "POST /best-moves" in endpoints, (
        "the scanner lost POST /api/best-moves, which returns best moves for an "
        "arbitrary FEN -- fix the scanner before trusting any result here"
    )
    assert "POST /move" in endpoints or "POST /why" in endpoints, (
        "the scanner lost the line board (routes/line_board.py), which plays any "
        "line at depth 16"
    )
    assert len(endpoints) >= 120, (
        f"scanner found only {len(endpoints)} engine-reachable endpoints; the "
        "2026-11-25 audit found 163, so something stopped matching"
    )


# ----------------------------------------------------------- the guard itself


def _guard():
    """Import the guard, failing with the reason rather than an ImportError."""
    try:
        from services import live_play_guard  # noqa: WPS433
    except ImportError as exc:
        pytest.fail(
            "services/live_play_guard.py does not exist yet. This is the gate "
            "for docs/play_through_lichess_scope.md: the guard is written and "
            "proven BEFORE the board, because the cost of getting it wrong is "
            f"a real user's Lichess account, not a broken page. ({exc})"
        )
    return live_play_guard


def test_the_guard_denies_an_unknown_path_by_default() -> None:
    """Fail closed. An endpoint written next month must be blocked by default."""
    guard = _guard()
    assert guard.is_blocked_during_live_game(
        "/api/some/endpoint/invented/next/month"
    ), "the guard allowed an unknown path -- it must deny by default, not allow"


def test_the_guard_is_inert_when_there_is_no_live_game() -> None:
    """The negative control. A guard that blocks everything always is not a guard.

    Without a live Lichess game nothing changes for anyone, so the blocking
    decision must depend on the live-game check, not on the path alone.
    """
    guard = _guard()
    assert hasattr(guard, "user_has_live_lichess_game"), (
        "the guard has no live-game check, so it cannot be inert when there is "
        "no live game -- it would break the whole product"
    )


def test_the_allowlist_is_small_and_contains_nothing_engine_derived() -> None:
    """What playing requires, and not one path more."""
    guard = _guard()
    allowlist: Set[str] = set(guard.PLAY_ALLOWLIST)
    assert allowlist, "an empty allowlist means the player cannot even move"
    assert len(allowlist) <= 20, (
        f"the allowlist has grown to {len(allowlist)} paths. Every entry is a "
        "path reachable during a live Lichess game; review each one by hand."
    )
    forbidden = re.compile(
        r"best.?move|analy[sz]e|eval|why|caption|coach(?!/play/live)|hint|socratic|decryption",
        re.I,
    )
    leaked = sorted(p for p in allowlist if forbidden.search(p))
    assert not leaked, (
        "these allowlisted paths look engine-derived, so they would serve help "
        "during a live Lichess game:\n  " + "\n  ".join(leaked)
    )


def test_every_engine_reachable_endpoint_is_blocked() -> None:
    """All 163 from the audit, each one checked against the guard."""
    guard = _guard()
    unguarded: List[str] = []
    for endpoint, where in engine_reachable_endpoints():
        _verb, route = endpoint.split(" ", 1)
        # Routers are mounted under /api; the guard sees the full request path.
        if not guard.is_blocked_during_live_game(f"/api{route}"):
            unguarded.append(f"{endpoint}  ({where})")
    assert not unguarded, (
        "these endpoints can serve engine-derived output during a live Lichess "
        "game. Each one risks an engine mark on the player's own account:\n  "
        + "\n  ".join(sorted(unguarded))
    )


def test_the_guard_is_installed_as_middleware_not_per_route() -> None:
    """Coverage must be structural, so a new endpoint is guarded by default."""
    os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
    os.environ.setdefault("DB_NAME", "test_database")
    _guard()  # fail with the readable reason first

    import server  # noqa: WPS433

    installed = " ".join(str(m) for m in server.app.user_middleware)
    assert "live_play" in installed.lower() or "liveplay" in installed.lower(), (
        "the live-play guard is not installed as middleware. A per-route guard "
        "over 163 endpoints will be forgotten the first time someone adds the "
        "164th; the guard must sit above the route table."
    )


def test_the_whole_api_surface_is_covered() -> None:
    """Against the real route table, not a hand-kept list.

    787 paths were mounted under /api on 2026-11-25. Anything not in the
    allowlist must be blocked, so this keeps holding as routes are added.
    """
    os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
    os.environ.setdefault("DB_NAME", "test_database")
    guard = _guard()

    import server  # noqa: WPS433

    allowlist = set(guard.PLAY_ALLOWLIST)
    paths = {
        r.path
        for r in server.app.routes
        if getattr(r, "path", "").startswith("/api")
    }
    assert len(paths) > 100, f"only {len(paths)} /api routes found; app changed shape"
    leaked = sorted(
        p for p in paths
        if p not in allowlist and not guard.is_blocked_during_live_game(p)
    )
    assert not leaked, (
        f"{len(leaked)} API paths are neither allowlisted nor blocked during a "
        "live Lichess game:\n  " + "\n  ".join(leaked[:40])
    )
