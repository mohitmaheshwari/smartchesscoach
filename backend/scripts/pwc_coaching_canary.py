"""Does the coach actually SPEAK when the player blunders?

Run on the server after every deploy, from scripts/post_deploy_check.sh.

Born 2026-09-15, after a unified_v1 release passed its gate and then coached
NOTHING in a real 27-move game: 14 of 15 decisions silent, 0 messages, the
only word arriving on move 27 after the player had lost a rook, a knight, a
bishop and another rook.

The gate passed because it played e4, saw an engine reply, and called that a
PASS. A coach that goes quiet under collapse survives that check perfectly --
e4 is a fine move and a coach SHOULD be quiet about it. The check has to reach
a position where the player is losing material and assert that a word comes
out.

So this plays a real game through the real HTTP endpoints, walks into a
position where the queen is hanging in plain sight, and fails the deploy if
the coach says nothing. It cleans up the account it creates, whatever happens.

    python scripts/pwc_coaching_canary.py            # exit 0 = coach spoke
"""
from __future__ import annotations

import os
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess
import requests
from pymongo import MongoClient

BASE = os.environ.get("PWC_CANARY_BASE", "http://localhost:8002/api")
# 1.e4 e5 2.Qh5 Nc6 then 3.Qxe5+?? -- the queen takes a pawn the knight
# defends and stands en prise. Chosen because it needs no search to see: the
# board heuristics flag it even when the engine is degraded, which is exactly
# the condition that produced the silent game.
OPENING = ["e4", "Qh5"]
BLUNDER_FEN = "r1bqkbnr/pppp1ppp/2n5/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 2 3"
BLUNDER_UCI = "h5e5"
# Only these count. An "ambient" nudge is filler -- it is what the coach says
# when it has nothing specific, and accepting it is how a silent coach passes.
SPEAKING_LAYERS = {"advisory", "critical_interrupt"}


def _db():
    return MongoClient(
        os.environ["MONGO_URL"], serverSelectionTimeoutMS=10000
    )[os.environ.get("DB_NAME", "chess_coach")]


def _make_account(db):
    uid = f"canary_{uuid.uuid4().hex[:12]}"
    token = uuid.uuid4().hex
    db.users.insert_one({
        "user_id": uid, "email": f"{uid}@canary.invalid", "name": "Canary",
        "rating_source": "assessed_rating", "assessed_rating": 800,
        "_canary": True,
    })
    db.user_sessions.insert_one({
        "user_id": uid, "session_token": token,
        "expires_at": "2099-01-01T00:00:00+00:00", "_canary": True,
    })
    sess = requests.Session()
    sess.cookies.set("session_token", token)
    return uid, sess


def _cleanup(db, uid):
    for name in ("users", "user_sessions", "coach_sessions", "coach_messages",
                 "coach_memory", "player_profiles", "player_identity",
                 "pwc_session_traces", "learning_sessions", "coaching_cache"):
        try:
            db[name].delete_many({"user_id": uid})
        except Exception:
            pass


def _wait_for_turn(sess, sid, seconds=30):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            r = sess.get(f"{BASE}/coach/play/state/{sid}", timeout=20)
            if r.status_code == 200:
                body = r.json()
                if body.get("current_fen") and body.get("is_player_turn"):
                    return body["current_fen"]
                if body.get("game_over"):
                    return body.get("current_fen")
        except Exception:
            pass
        time.sleep(0.5)
    return None


def main() -> int:
    db = _db()
    uid, sess = _make_account(db)
    try:
        started = sess.post(
            f"{BASE}/coach/play/start",
            json={"user_color": "white", "time_control": "15+10"}, timeout=90,
        )
        if started.status_code != 200:
            print(f"FAIL: /coach/play/start returned {started.status_code}")
            return 1
        sid = started.json().get("session_id")

        # Walk into the losing position through the real move endpoint.
        for san in OPENING:
            r = sess.post(f"{BASE}/coach/play/move",
                          json={"session_id": sid, "move": san}, timeout=90)
            if r.status_code != 200:
                print(f"FAIL: move {san} returned {r.status_code}")
                return 1
            if _wait_for_turn(sess, sid) is None:
                print(f"FAIL: coach never replied to {san}")
                return 1

        # Evaluate the CANONICAL position, not whatever the game drifted to.
        # The first version of this canary took the live session FEN and paired
        # it with a hardcoded move -- the coach answered 2.Qh5 with something
        # other than Nc6, so Qxe5 was not a blunder in the position it actually
        # asked about, and the canary passed on a generic nudge. The point is
        # to exercise the coaching path on a KNOWN hanging queen, not to test
        # move sequencing.
        board = chess.Board(BLUNDER_FEN)
        move = chess.Move.from_uci(BLUNDER_UCI)
        assert move in board.legal_moves, "canary position is wrong"

        # fast_eval is non-deterministic: three consecutive calls on this exact
        # position have returned depth [0, 10, 10], the first being a cold
        # engine blowing its own 800ms budget. One retry, so a cold start does
        # not fail a deploy -- but two silent answers in a row is a real fault.
        attempts = []
        for attempt in range(2):
            r = sess.post(f"{BASE}/coach/play/evaluate-pending", json={
                "sessionId": sid, "fenBefore": BLUNDER_FEN, "uci": BLUNDER_UCI,
                "moveIndexPreview": board.fullmove_number, "userRating": 800,
            }, timeout=90)
            if r.status_code != 200:
                print(f"FAIL: evaluate-pending returned {r.status_code}")
                return 1
            body = r.json()
            decision = body.get("coachingDecision") or {}
            layer = decision.get("layer")
            text = (decision.get("text") or "").strip()
            quality = (body.get("moveEvaluation") or {}).get("moveQuality")
            attempts.append((layer, quality, text))
            print(f"  attempt {attempt + 1}: layer={layer!r} "
                  f"quality={quality!r} text={text[:66]!r}")
            if layer in SPEAKING_LAYERS and text:
                print("  OK: the coach named the problem.")
                return 0
            time.sleep(1.0)

        print("FAIL: the coach did not speak about a hanging queen.")
        print(f"      attempts: {attempts}")
        print("      An 'ambient' nudge does NOT count. The first version of")
        print("      this check accepted 'Your pieces are not fully")
        print("      coordinated yet.' on a move that drops a queen — that is")
        print("      the same shape of pass that let 2026-09-15 ship.")
        return 1
    finally:
        _cleanup(db, uid)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a broken canary must fail loudly, not pass
        print(f"FAIL: canary raised {type(exc).__name__}: {exc}")
        sys.exit(1)
