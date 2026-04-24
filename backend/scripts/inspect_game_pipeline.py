"""
Inspect a game's pipeline state + learnings.

For a specific game (or the user's latest game), prints:

  1. IMPORT status — is the game in the `games` collection?
  2. ANALYSIS status — is it queued, in-progress, completed, or failed?
  3. ENGINE 1 (Stockfish) — accuracy, blunder counts, top critical moves
  4. ENGINE 2 (behavioral interpretation) — cognitive-gap distribution,
     the coach's per-move classification
  5. COACH verdict — compute_game_summary output for the game

Use this after playing a chess.com / lichess game when you want to know:
  - "is the game even imported yet?"
  - "is Stockfish done with it?"
  - "what did the coach learn from this game?"

Usage:
  docker cp scripts/inspect_game_pipeline.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/inspect_game_pipeline.py --user <user_id> --latest
  docker exec -it chess-coach-backend python3 scripts/inspect_game_pipeline.py --game-id <game_id>
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient


def _fmt(val, max_len=80):
    """Short display for arbitrary values."""
    s = str(val) if val is not None else "—"
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


def _section(title: str):
    print()
    print(f"── {title} " + "─" * max(4, 60 - len(title)))


async def resolve_latest_game(db, user_id: str):
    """Return the most recently imported game for the user."""
    g = await db.games.find_one(
        {"user_id": user_id},
        sort=[("imported_at", -1)],
    )
    return g


async def inspect(db, game_id: str, user_id: str):
    """Print the full pipeline report for one game."""
    # 1. IMPORT status
    _section("1. IMPORT")
    game = await db.games.find_one({"game_id": game_id})
    if not game:
        print(f"  NOT IMPORTED. No record in `games` for game_id={game_id}")
        # Queue check — maybe it's pending import
        q = await db.analysis_queue.find_one({"game_id": game_id})
        if q:
            print(f"  queue record found: status={_fmt(q.get('status'))}")
        print()
        print("  What to try:")
        print("   - If you just played: wait a minute and re-run (chess.com sync is async).")
        print("   - Run sync: POST /api/journey/sync to pull recent chess.com games.")
        return

    print(f"  game_id:        {_fmt(game.get('game_id'))}")
    print(f"  user_id:        {_fmt(game.get('user_id'))}")
    print(f"  platform:       {_fmt(game.get('platform'))}")
    print(f"  user_color:     {_fmt(game.get('user_color'))}")
    print(f"  result:         {_fmt(game.get('result'))}")
    print(f"  termination:    {_fmt(game.get('termination'))}")
    print(f"  opponent:       {_fmt(game.get('opponent_name') or game.get('opponent'))}")
    print(f"  opening:        {_fmt(game.get('opening'))}")
    print(f"  imported_at:    {_fmt(game.get('imported_at'))}")
    print(f"  is_analyzed:    {_fmt(game.get('is_analyzed'))}")
    print(f"  analysis_status:{_fmt(game.get('analysis_status'))}")
    print(f"  reviewed:       {_fmt(game.get('reviewed'))}")

    # 2. ANALYSIS queue
    _section("2. ANALYSIS QUEUE")
    q = await db.analysis_queue.find_one({"game_id": game_id})
    if q:
        print(f"  queue status:   {_fmt(q.get('status'))}")
        print(f"  queued_at:      {_fmt(q.get('queued_at') or q.get('created_at'))}")
        print(f"  started_at:     {_fmt(q.get('started_at'))}")
        print(f"  completed_at:   {_fmt(q.get('completed_at'))}")
        print(f"  heartbeat:      {_fmt(q.get('last_heartbeat'))}")
        print(f"  attempts:       {_fmt(q.get('attempts'))}")
        if q.get("error"):
            print(f"  ERROR:          {_fmt(q.get('error'), 200)}")
    else:
        print("  no queue record (normal once analysis has completed)")

    # 3. ENGINE 1 (Stockfish) summary
    _section("3. ENGINE 1 — Stockfish")
    analysis = await db.game_analyses.find_one({"game_id": game_id, "user_id": user_id})
    if not analysis:
        # Try without user_id filter (diagnostic)
        analysis = await db.game_analyses.find_one({"game_id": game_id})
        if analysis:
            print(f"  WARN: analysis exists but under a different user_id ({analysis.get('user_id')})")
    if not analysis:
        print("  NOT ANALYZED YET. No record in `game_analyses`.")
        if game.get("analysis_status") == "failed":
            print("  (analysis_status=failed — inspect the queue's `error` field above)")
        else:
            print("  Analysis usually completes ~30-60s after import. Re-run in a minute.")
        return

    sf = analysis.get("stockfish_analysis") or {}
    print(f"  analyzed_at:    {_fmt(analysis.get('analyzed_at'))}")
    print(f"  depth:          {_fmt(analysis.get('analysis_depth'))}")
    print(f"  duration (s):   {_fmt(analysis.get('analysis_duration_seconds'))}")
    print(f"  engine_version: {_fmt(analysis.get('engine_version'))}")
    print(f"  accuracy:       {_fmt(sf.get('accuracy'))}%")
    print(f"  blunders:       {_fmt(sf.get('blunders'))}")
    print(f"  mistakes:       {_fmt(sf.get('mistakes'))}")
    print(f"  inaccuracies:   {_fmt(sf.get('inaccuracies'))}")
    print(f"  best_moves:     {_fmt(sf.get('best_moves'))}")
    print(f"  brilliant:      {_fmt(sf.get('brilliant_moves'))}")
    print(f"  sacrifices:     {_fmt(sf.get('sacrifices'))}")
    print(f"  avg cp_loss:    {_fmt(sf.get('avg_cp_loss'))}")

    evals = sf.get("move_evaluations") or []
    print(f"  total moves:    {len(evals)}")

    # 4. ENGINE 2 (behavioral interpretation)
    _section("4. ENGINE 2 — Behavioral interpretation")

    # Filter to user's moves (FEN active-color match)
    user_color = game.get("user_color", "white")
    user_is_white = user_color == "white"
    user_moves = []
    for i, m in enumerate(evals):
        fen = m.get("fen_before") or ""
        parts = fen.split(" ")
        side = parts[1] if len(parts) > 1 else ""
        if side in ("w", "b"):
            is_user = (side == "w") == user_is_white
        else:
            is_user = (i % 2 == 0) == user_is_white
        if is_user:
            user_moves.append(m)

    # Cognitive-gap distribution on user's critical moves
    gap_counts = {}
    for m in user_moves:
        gap = m.get("cognitive_gap")
        if gap:
            gap_counts[gap] = gap_counts.get(gap, 0) + 1

    if gap_counts:
        print("  cognitive-gap distribution (on your critical moves):")
        for gap, cnt in sorted(gap_counts.items(), key=lambda kv: -kv[1]):
            print(f"    {gap:28s} {cnt}")
    else:
        print("  no cognitive-gap tags on your moves (classifier hasn't tagged this game)")

    # Top critical moments
    ranked = sorted(
        user_moves,
        key=lambda m: (m.get("cp_loss") or 0),
        reverse=True,
    )[:5]
    print()
    print("  top 5 moments by cp_loss (YOUR moves):")
    print(f"    {'move':>4}  {'san':>7}  {'cp_loss':>7}  {'best':>7}  {'gap':>20}  coaching_focus")
    for m in ranked:
        san = m.get("move") or m.get("san") or "?"
        cp = m.get("cp_loss") or 0
        best = m.get("best_move") or "?"
        gap = m.get("cognitive_gap") or "—"
        focus = (m.get("coaching_focus") or "")[:40]
        print(
            f"    {_fmt(m.get('move_number'), 4):>4}  "
            f"{_fmt(san, 7):>7}  "
            f"{str(cp):>7}  "
            f"{_fmt(best, 7):>7}  "
            f"{_fmt(gap, 20):>20}  "
            f"{focus}"
        )

    # 5. COACH verdict
    _section("5. COACH VERDICT (compute_game_summary)")
    try:
        from services.game_coach_summary import compute_game_summary

        summary = compute_game_summary(
            evals,
            game.get("result", ""),
            user_color,
            game.get("opening", "") or "",
            termination=game.get("termination", "") or "",
        )
        print(f"  diagnosis:      {summary.get('diagnosis')}")
        print(f"  root_cause:     {summary.get('root_cause')}")
        print(f"  subline:        {_fmt(summary.get('subline'))}")
        crit = summary.get("critical_move") or {}
        if crit:
            print(
                f"  critical_move:  move {crit.get('move_number')} {crit.get('san')} "
                f"(cp_loss={crit.get('cp_loss')}, best={crit.get('best_move')})"
            )
        ctx = summary.get("context") or []
        if ctx:
            print("  context:")
            for c in ctx:
                print(f"    · {c}")
        print(f"  coach_note:     {_fmt(summary.get('coach_note'), 200)}")
    except Exception as e:
        print(f"  coach summary failed: {e}")

    # 6. Cached decryption / move narratives (if present)
    _section("6. MOVE-BY-MOVE NARRATIVES (cached)")
    decryption = analysis.get("decryption_v5_data")
    if decryption and isinstance(decryption, list):
        mistakes = [
            d for d in decryption
            if d.get("severity") in ("mistake", "blunder", "inaccuracy")
            and d.get("is_user_move")
        ]
        print(f"  cached decryption entries: {len(decryption)}")
        print(f"  user mistakes with narrative: {len(mistakes)}")
        pv_tactical = sum(1 for m in mistakes if m.get("narrative_source") == "pv_tactical")
        print(f"  deterministic (PV-tactical) narratives: {pv_tactical}")
        print(f"  LLM / rule-based narratives: {len(mistakes) - pv_tactical}")
        if mistakes:
            print()
            print("  sample narratives:")
            for m in mistakes[:5]:
                src = m.get("narrative_source") or "?"
                narrative = _fmt(m.get("narrative"), 110)
                print(f"    [move {m.get('move_number')} {m.get('move_san')}] ({src}) {narrative}")
    else:
        print("  no cached decryption yet (generated on first Lab/game-review visit)")


async def main():
    parser = argparse.ArgumentParser(description="Inspect a game's pipeline state + learnings.")
    parser.add_argument("--game-id", type=str, help="Specific game_id to inspect.")
    parser.add_argument("--user", type=str, help="User id — used for --latest and for analysis lookup.")
    parser.add_argument("--latest", action="store_true", help="Use the user's most recent game.")
    args = parser.parse_args()

    if not args.game_id and not (args.user and args.latest):
        parser.error("Pass either --game-id <id> or --user <id> --latest")

    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    game_id = args.game_id
    user_id = args.user or ""

    if args.latest and not game_id:
        g = await resolve_latest_game(db, user_id)
        if not g:
            print(f"No games found for user {user_id}")
            return
        game_id = g.get("game_id")
        print(f"Latest game for {user_id}: {game_id}")

    if not user_id:
        # Derive user_id from the game record
        g = await db.games.find_one({"game_id": game_id}, {"user_id": 1})
        user_id = (g or {}).get("user_id", "")

    print(f"Inspecting game_id={game_id} user_id={user_id}")
    await inspect(db, game_id, user_id)


if __name__ == "__main__":
    asyncio.run(main())
