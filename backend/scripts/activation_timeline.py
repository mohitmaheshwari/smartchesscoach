"""
Activation Timeline — per-user objective event timeline, reconstructed from
SERVER data only (no reliance on client/PostHog events, which are lossy).

Answers Mohit's sprint ask (2026): for the 5-user watch, give each user's
objective timeline (signup -> diagnostic -> results -> training -> return)
with timestamps + deltas, plus the candidate trust-signals B-E. Signal A
(insight dwell time) is UI-only -> stays in PostHog; noted as such.

Deliberately NO thesis about which signal = "trust" — measure several,
correlate against the watched sessions later.

Usage (prod container):
  docker exec -i chess-coach-backend python3 scripts/activation_timeline.py --recent 8
  docker exec -i chess-coach-backend python3 scripts/activation_timeline.py --user <uid>
"""
import argparse, asyncio, os
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient


def _dt(v):
    """Parse a stored timestamp (ISO str or datetime) to an aware UTC datetime."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _delta(t0, t):
    if not t0 or not t:
        return "?"
    s = int((t - t0).total_seconds())
    if s < 0:
        return f"-{-s}s"
    if s < 90:
        return f"+{s}s"
    if s < 3600:
        return f"+{s//60}m{s%60:02d}s"
    if s < 86400:
        return f"+{s//3600}h{(s%3600)//60:02d}m"
    return f"+{s//86400}d{(s%86400)//3600:02d}h"


async def build_for_user(db, u):
    uid = u["user_id"]
    signup = _dt(u.get("created_at"))
    ev = []  # (timestamp, label)
    if signup:
        ev.append((signup, "SIGNUP"))

    # Diagnostic
    diag_completed = None
    async for ds in db.diagnostic_sessions.find({"user_id": uid}):
        st = _dt(ds.get("started_at"))
        if st:
            ev.append((st, "diagnostic_started"))
        atts = ds.get("attempts") or []
        for i, a in enumerate(atts, 1):
            at = _dt(a.get("attempted_at"))
            if at and (i == 1 or i == len(atts)):
                ev.append((at, f"diag_puzzle_{i}_answered ({'✓' if a.get('is_correct') else '✗'} {a.get('issue_type')})"))
        ct = _dt(ds.get("completed_at"))
        if ct:
            diag_completed = ct
            ev.append((ct, f"diagnostic_completed ({len(atts)} answered, status={ds.get('status')})"))

    # First training / puzzle attempt (with per-puzzle time we already store)
    first_train = None
    tr = await db.training_solve_attempts.find_one({"user_id": uid}, sort=[("attempted_at", 1)])
    if tr:
        first_train = _dt(tr.get("attempted_at"))
        if first_train:
            ev.append((first_train, f"first_training_solve (t={tr.get('time_taken_seconds')}s, {tr.get('pattern_type')})"))
    pz = await db.puzzle_attempts.find_one({"user_id": uid}, sort=[("created_at", 1)])
    if pz:
        pt = _dt(pz.get("created_at"))
        if pt:
            if not first_train or pt < first_train:
                first_train = pt
            ev.append((pt, f"first_puzzle_attempt (t={pz.get('time_taken_ms')}ms, {pz.get('weakness_type')})"))

    # First PWC
    pwc_times = [_dt(c.get("created_at")) async for c in db.coach_sessions.find({"user_id": uid}, {"created_at": 1})]
    pwc_times = sorted([t for t in pwc_times if t])
    if pwc_times:
        ev.append((pwc_times[0], f"first_play_with_coach (of {len(pwc_times)})"))

    # Imports (distinct import batches — a LATER batch = "imported another game")
    imp_times = [_dt(g.get("imported_at")) async for g in db.games.find({"user_id": uid}, {"imported_at": 1})]
    imp_times = sorted([t for t in imp_times if t])
    if imp_times:
        ev.append((imp_times[0], f"first_game_import ({len(imp_times)} games)"))

    ev.sort(key=lambda x: x[0])

    # ── Candidate trust signals (objective, server-derived) ──
    all_ts = [t for t, _ in ev if t]
    # C: returned on a later calendar day
    signup_day = signup.date() if signup else None
    returned = signup_day is not None and any(t.date() > signup_day for t in all_ts if t)
    # B: started training within 2 min of diagnostic completion
    b = bool(diag_completed and first_train and timedelta(0) <= (first_train - diag_completed) <= timedelta(minutes=2))
    # D: a game imported clearly AFTER the initial batch (>1h after the first import)
    d = bool(len(imp_times) >= 2 and (imp_times[-1] - imp_times[0]) > timedelta(hours=1))
    # E: started PWC
    e = bool(pwc_times)

    return {"uid": uid, "name": u.get("name"), "signup": signup, "events": ev,
            "B_train_within_2min": b, "C_returned_next_day": returned,
            "D_reimported_game": d, "E_started_pwc": e}


def render(r):
    print(f"\n{'='*72}")
    print(f"{r['name']}  ({r['uid']})   signup: {r['signup']}")
    print(f"{'='*72}")
    t0 = r["signup"]
    for t, label in r["events"]:
        print(f"  {_delta(t0, t):>10}  {label}")
    print(f"  CANDIDATES:  B(train<2min after diag)={r['B_train_within_2min']}  "
          f"C(returned later day)={r['C_returned_next_day']}  "
          f"D(re-imported)={r['D_reimported_game']}  E(PWC)={r['E_started_pwc']}")
    print(f"  (A = insight dwell time → PostHog only, not server-derivable)")


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", default=None)
    p.add_argument("--recent", type=int, default=8)
    args = p.parse_args()
    db = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=9000)[os.environ.get("DB_NAME", "chess_coach")]
    if args.user:
        users = [await db.users.find_one({"user_id": args.user})]
    else:
        users = await db.users.find({}, {"user_id": 1, "name": 1, "created_at": 1}).sort("created_at", -1).limit(args.recent).to_list(args.recent)
    # aggregate candidate rates
    agg = {"B": 0, "C": 0, "D": 0, "E": 0, "n": 0}
    for u in users:
        if not u:
            continue
        r = await build_for_user(db, u)
        render(r)
        agg["n"] += 1
        agg["B"] += r["B_train_within_2min"]; agg["C"] += r["C_returned_next_day"]
        agg["D"] += r["D_reimported_game"]; agg["E"] += r["E_started_pwc"]
    n = agg["n"] or 1
    print(f"\n{'='*72}\nCANDIDATE SIGNAL RATES over {agg['n']} users:")
    print(f"  B started-training-within-2min: {agg['B']}/{agg['n']} ({100*agg['B']//n}%)")
    print(f"  C returned-a-later-day:         {agg['C']}/{agg['n']} ({100*agg['C']//n}%)")
    print(f"  D re-imported a game:           {agg['D']}/{agg['n']} ({100*agg['D']//n}%)")
    print(f"  E started Play-with-Coach:      {agg['E']}/{agg['n']} ({100*agg['E']//n}%)")


asyncio.run(main())
