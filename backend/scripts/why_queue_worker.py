"""The Why queue worker: runs on Mohit's machine, studies what the button could not.

    python backend/scripts/why_queue_worker.py            # one pass, up to --limit rows
    python backend/scripts/why_queue_worker.py --key K    # one position, by key
    python backend/scripts/why_queue_worker.py --dry-run  # study, print, write nothing

Scheduled by Windows Task Scheduler every 15 minutes (see docs/why_queue_claude_scope.md).

One pass:
  1. claim up to N queued rows on prod (ssh + docker exec; the row is marked
     running with a lease so two passes never study the same position)
  2. for each: build the fact packet with the LOCAL Stockfish (services/why_study.py)
  3. run Claude Code headless (`claude -p`) with the packet and the claim schema
  4. the gate replays every claim; words are checked against the claims
  5. write the result to prod: why_reasons row + why_queue status

Nothing here reaches a player directly. A gate-passed study is
`held_for_review` until a human agrees in the admin tab (review-first), unless
WHY_QUEUE_AUTO_PUBLISH=1 on the worker.

Env (all optional):
  WHY_QUEUE_SSH         root@72.60.204.176
  WHY_QUEUE_CONTAINER   chess-coach-backend
  STOCKFISH_PATH        local engine binary
  CLAUDE_BIN            claude
  CLAUDE_MODEL          model for the study (default: DEFAULT_MODEL, never the CLI's default)
  WHY_QUEUE_AUTO_PUBLISH  "1" to publish gate-passed studies without a human
  WHY_QUEUE_LOG_DIR     where the log and the lock live
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
sys.path.insert(0, str(BACKEND))

SSH = os.environ.get("WHY_QUEUE_SSH", "root@72.60.204.176")
CONTAINER = os.environ.get("WHY_QUEUE_CONTAINER", "chess-coach-backend")
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
# Named, never the CLI's default: on 2026-11-11 the default moved from Fable 5.1
# to Opus 5.5 between two runs with nobody choosing it. Same e6 packet: Fable
# said no lesson (right), Opus wrote a false "Kd8 was better". One run each.
DEFAULT_MODEL = "claude-fable-5-1"
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL") or DEFAULT_MODEL
AUTO_PUBLISH = os.environ.get("WHY_QUEUE_AUTO_PUBLISH", "0") == "1"
LOG_DIR = Path(os.environ.get("WHY_QUEUE_LOG_DIR") or (Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ChessGuru" / "why_queue"))
LEASE_MINUTES = 30

log = logging.getLogger("why_queue_worker")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- prod, over ssh ------------------------------------------------------------

_REMOTE_PRELUDE = r'''
import base64, json, os, sys
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
PAYLOAD = json.loads(base64.b64decode(%(payload)r).decode("utf-8"))
db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
def now(): return datetime.now(timezone.utc).isoformat()
def emit(obj): print("RESULT_JSON:" + json.dumps(obj, default=str))
'''

_REMOTE_CLAIM = _REMOTE_PRELUDE + r'''
limit = int(PAYLOAD.get("limit") or 3)
key = PAYLOAD.get("key")
lease = (datetime.now(timezone.utc) + timedelta(minutes=int(PAYLOAD.get("lease_minutes") or 30))).isoformat()
q = {"key": key} if key else {"$or": [{"status": "queued"}, {"status": "running", "lease_until": {"$lt": now()}}]}
rows = []
for row in db.why_queue.find(q, {"_id": 0}).sort("created_at", 1).limit(limit):
    res = db.why_queue.update_one({"key": row["key"], "status": row["status"]},
                                  {"$set": {"status": "running", "lease_until": lease, "started_at": now()},
                                   "$inc": {"attempts": 1}})
    if res.modified_count == 1 or key:
        rows.append(row)
emit({"rows": rows})
'''

_REMOTE_WRITE = _REMOTE_PRELUDE + r'''
reason = PAYLOAD["reason"]
queue_status = PAYLOAD["queue_status"]
key = reason["key"]
reason["written_at"] = now()
# A re-study keeps the study it replaces, with its ruling, and starts the new
# one unruled: a person's Agree belongs to the text they read (2026-11-11).
old = db.why_reasons.find_one({"key": key}, {"_id": 0, "packet": 0, "previous_studies": 0})
update = {"$set": reason, "$setOnInsert": {"created_at": now()}}
if old:
    update["$push"] = {"previous_studies": old}
    clear = {k: "" for k in ("ruling", "ruled_by", "ruled_at", "ruling_note", "published_at")
             if k not in reason}
    if clear:
        update["$unset"] = clear
db.why_reasons.update_one({"key": key}, update, upsert=True)
db.why_queue.update_one({"key": key}, {"$set": {"status": queue_status, "finished_at": now(), "lease_until": None}})
# A published study is a card caption (docs/why_study_on_card_scope.md): when one
# appears or is replaced, the reviews that asked re-render on their next open.
stale = 0
if reason.get("status") == "published" or (old or {}).get("status") == "published":
    q = db.why_queue.find_one({"key": key}, {"_id": 0, "requests.game_id": 1}) or {}
    ids = sorted({r.get("game_id") for r in q.get("requests") or [] if r.get("game_id")})
    if ids:
        stale = db.game_analyses.update_many({"game_id": {"$in": ids}},
                                             {"$set": {"decryption_v5_version": 0}}).modified_count
emit({"ok": True, "key": key, "status": reason.get("status"), "queue_status": queue_status,
      "reviews_marked_stale": stale})
'''

_REMOTE_RELEASE = _REMOTE_PRELUDE + r'''
key = PAYLOAD["key"]
db.why_queue.update_one({"key": key, "status": "running"},
                        {"$set": {"status": PAYLOAD.get("status", "failed"), "lease_until": None,
                                  "last_error": str(PAYLOAD.get("error") or "")[:2000], "finished_at": now()}})
emit({"ok": True})
'''


def remote(script: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run a python snippet inside the prod container with a JSON payload; return its JSON."""
    encoded = base64.b64encode(json.dumps(payload, default=str).encode("utf-8")).decode("ascii")
    code = script % {"payload": encoded}
    cmd = ["ssh", "-o", "ConnectTimeout=20", "-o", "BatchMode=yes", SSH,
           f"docker exec -i {CONTAINER} python3 -"]
    proc = subprocess.run(cmd, input=code, text=True, capture_output=True, timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"remote failed ({proc.returncode}): {proc.stderr.strip()[-800:]}")
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith("RESULT_JSON:"):
            return json.loads(line[len("RESULT_JSON:"):])
    raise RuntimeError(f"remote printed no result: {proc.stdout[-800:]}")


# --- Claude, headless -----------------------------------------------------------

def claude_binary() -> str:
    """The real executable. On Windows the npm shim is a .cmd that calls
    node_modules/@anthropic-ai/claude-code/bin/claude.exe; running the exe
    directly keeps the JSON schema argument out of cmd.exe's quoting."""
    import shutil
    found = shutil.which(CLAUDE_BIN) or CLAUDE_BIN
    if found.lower().endswith(".cmd"):
        exe = Path(found).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if exe.exists():
            return str(exe)
    return found


def run_claude(system_prompt: str, user_text: str, schema: Dict[str, Any], *, cwd: Path) -> Dict[str, Any]:
    """One headless Claude Code call. Returns {answer, raw, cost_usd, duration_ms, model}."""
    cmd = [claude_binary(), "-p", "--output-format", "json", "--max-turns", "1",
           "--tools", "", "--no-session-persistence",
           "--system-prompt", system_prompt, "--json-schema", json.dumps(schema)]
    if CLAUDE_MODEL:
        cmd += ["--model", CLAUDE_MODEL]
    # A worker started from inside a Claude Code session must not look like a child of it.
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    proc = subprocess.run(cmd, input=user_text, text=True, encoding="utf-8", capture_output=True,
                          timeout=900, cwd=str(cwd), env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"claude failed ({proc.returncode}): {proc.stderr.strip()[-800:]}")
    envelope: Optional[Dict[str, Any]] = None
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                envelope = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if envelope is None:
        raise RuntimeError(f"claude printed no JSON envelope: {proc.stdout[-800:]}")
    answer = envelope.get("structured_output")
    if answer is None:
        raw = envelope.get("result")
        if isinstance(raw, str):
            start, end = raw.find("{"), raw.rfind("}")
            answer = json.loads(raw[start:end + 1]) if start >= 0 and end > start else None
        elif isinstance(raw, dict):
            answer = raw
    if not isinstance(answer, dict):
        raise RuntimeError("claude's answer is not an object")
    return {"answer": answer, "raw": envelope, "cost_usd": envelope.get("total_cost_usd"),
            "duration_ms": envelope.get("duration_ms") or envelope.get("duration_api_ms"),
            "model": (envelope.get("modelUsage") and next(iter(envelope["modelUsage"]), None)) or CLAUDE_MODEL}


# --- one position -----------------------------------------------------------------

def study(row: Dict[str, Any], *, depth: int, engine_path: Optional[str], scratch: Path) -> Dict[str, Any]:
    from services import why_study

    fen = row["fen_before"]
    played = row["played_san"]
    requests = row.get("requests") or []
    side = (requests[0].get("side") if requests else None) or "user"
    mover_is_user = side != "opponent"
    better = row.get("stored_best") or None
    t0 = time.time()
    packet = why_study.build_packet(fen, played, better_san=better, mover_is_user=mover_is_user, depth=depth,
                                    engine_path=engine_path, stored_class=row.get("stored_class"),
                                    rating=row.get("rating"), live_engine_said=row.get("differential"))
    better = packet["better_san"]
    packet_s = time.time() - t0
    log.info("packet for %s in %.1fs (better %s)", row["key"], packet_s, better)

    settled = why_study.settled_before_the_model(packet, row.get("rating"))
    if settled:
        log.info("no lesson for %s before the model: %s", row["key"], settled)
        return {
            "key": row["key"], "fen_before": fen, "played_san": played, "better_san": better,
            "side": side, "stored_class": row.get("stored_class"), "rating": row.get("rating"),
            "class": (row.get("differential") or {}).get("class"), "gap_cp": (row.get("differential") or {}).get("gap_cp"),
            "requests": requests, "status": "no_lesson", "reason": None, "no_lesson_why": settled,
            "mechanism_label": None, "claims": [], "gate": {"passed": True, "failures": []},
            "readability": None, "notes": [], "attempts": 0,
            "packet": {k: packet.get(k) for k in ("pv_after_played", "pv_after_best", "root_candidates_cp_for_mover",
                                                   "shared_threat_probes", "material_along_best_lines")},
            "model": None, "settled_by": "engine", "cost_usd": 0.0,
            "seconds": {"packet": round(packet_s, 1), "model": 0.0},
            "worker_host": platform.node(), "studied_at": _now(),
        }

    t1 = time.time()
    model_out = run_claude(why_study.SYSTEM_PROMPT, why_study.user_prompt(packet), why_study.CLAIM_SCHEMA, cwd=scratch)
    answer = model_out["answer"]
    log.info("claude answered %s in %.1fs, cost %s", row["key"], time.time() - t1, model_out.get("cost_usd"))
    gate = why_study.run_gate(answer, fen_before=fen, played_san=played, better_san=better,
                              mover_is_user=mover_is_user, engine_path=engine_path)
    attempts = 1
    cost = float(model_out.get("cost_usd") or 0)

    # One rewrite when the board or the writing rules found fault. Mohit
    # 2026-11-02: "make sure the language is too easy for anybody to explain
    # and understand." A long sentence or a hard word never holds a true
    # reason (that would silence it); it earns one more pass with the notes.
    fixes = list(gate["failures"]) + list(gate.get("notes") or [])
    if fixes and not gate["no_lesson"]:
        log.info("rewrite for %s: %s", row["key"], fixes)
        t2 = time.time()
        second = run_claude(why_study.SYSTEM_PROMPT,
                            why_study.user_prompt(packet, previous=answer, fixes=fixes),
                            why_study.CLAIM_SCHEMA, cwd=scratch)
        attempts = 2
        cost += float(second.get("cost_usd") or 0)
        gate2 = why_study.run_gate(second["answer"], fen_before=fen, played_san=played, better_san=better,
                                   mover_is_user=mover_is_user, engine_path=engine_path)
        log.info("rewrite answered %s in %.1fs: passed=%s notes=%d (first: passed=%s notes=%d)",
                 row["key"], time.time() - t2, gate2["passed"], len(gate2.get("notes") or []),
                 gate["passed"], len(gate.get("notes") or []))
        better_second = (gate2["passed"], -len(gate2.get("notes") or [])) >= (gate["passed"], -len(gate.get("notes") or []))
        if better_second:
            answer, gate, model_out = second["answer"], gate2, {**model_out, "model": second.get("model") or model_out.get("model")}

    if gate["no_lesson"]:
        status = "no_lesson"
    elif gate["passed"]:
        status = "published" if AUTO_PUBLISH else "held_for_review"
    else:
        status = "held"
    reason = {
        "key": row["key"], "fen_before": fen, "played_san": played, "better_san": better,
        "side": side, "stored_class": row.get("stored_class"), "rating": row.get("rating"),
        "class": (row.get("differential") or {}).get("class"), "gap_cp": (row.get("differential") or {}).get("gap_cp"),
        "requests": requests, "status": status,
        "reason": None if answer.get("no_lesson") else str(answer.get("reason") or "").strip(),
        "no_lesson_why": str(answer.get("no_lesson_why") or "").strip() or None,
        "mechanism_label": str(answer.get("mechanism") or "").strip() or None,
        "claims": gate["claims"], "gate": {"passed": gate["passed"], "failures": gate["failures"]},
        "readability": gate.get("readability"), "notes": gate.get("notes") or [], "attempts": attempts,
        "packet": {k: packet.get(k) for k in ("pv_after_played", "pv_after_best", "root_candidates_cp_for_mover",
                                               "shared_threat_probes", "material_along_best_lines")},
        "model": model_out.get("model"), "cost_usd": round(cost, 4),
        "seconds": {"packet": round(packet_s, 1), "model": round(time.time() - t1, 1)},
        "worker_host": platform.node(),
        "studied_at": _now(),
    }
    if status == "published":
        reason["published_at"] = _now()
    return reason


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--key", default=None, help="study one position by its queue key, whatever its status")
    ap.add_argument("--depth", type=int, default=20)
    ap.add_argument("--engine", default=os.environ.get("STOCKFISH_PATH"))
    ap.add_argument("--dry-run", action="store_true", help="study and print; write nothing to prod")
    ap.add_argument("--local", nargs=2, metavar=("FEN", "PLAYED_SAN"), default=None,
                    help="study one position without touching prod (implies --dry-run)")
    ap.add_argument("--local-side", choices=("user", "opponent"), default="user",
                    help="with --local: whose move it is, for the pronouns")
    ap.add_argument("--local-best", default=None, help="with --local: the stored better move, if any")
    args = ap.parse_args(argv)

    if args.local:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        scratch = LOG_DIR / "claude_cwd"
        scratch.mkdir(exist_ok=True)
        fen, played = args.local
        row = {"key": f"local|{played}", "fen_before": fen, "played_san": played, "stored_best": args.local_best,
               "requests": [{"side": args.local_side}], "stored_class": None, "rating": None, "differential": None}
        reason = study(row, depth=args.depth, engine_path=args.engine, scratch=scratch)
        shown = {k: reason[k] for k in ("key", "status", "reason", "no_lesson_why", "mechanism_label",
                                         "claims", "gate", "readability", "notes", "attempts", "cost_usd",
                                         "seconds", "model")}
        out_path = LOG_DIR / f"local_{played}_{int(time.time())}.json"
        out_path.write_text(json.dumps(reason, indent=1, default=str), encoding="utf-8")
        print(json.dumps(shown, indent=1, default=str))
        print(f"full study written to {out_path}")
        return 0

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(LOG_DIR / "worker.log", encoding="utf-8"),
                                  logging.StreamHandler(sys.stdout)])
    lock = LOG_DIR / "worker.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime < 3600:
        log.info("another pass is running (lock %s); leaving", lock)
        return 0
    lock.write_text(str(os.getpid()))
    scratch = LOG_DIR / "claude_cwd"
    scratch.mkdir(exist_ok=True)
    try:
        claimed = remote(_REMOTE_CLAIM, {"limit": args.limit, "key": args.key, "lease_minutes": LEASE_MINUTES})
        rows = claimed.get("rows") or []
        log.info("claimed %d row(s)", len(rows))
        for row in rows:
            key = row["key"]
            try:
                reason = study(row, depth=args.depth, engine_path=args.engine, scratch=scratch)
            except Exception as exc:                    # noqa: BLE001
                log.exception("study failed for %s", key)
                if not args.dry_run:
                    remote(_REMOTE_RELEASE, {"key": key, "status": "failed", "error": f"{type(exc).__name__}: {exc}"})
                continue
            log.info("%s -> %s | %s | gate failures: %s", key, reason["status"],
                     reason.get("reason") or reason.get("no_lesson_why"), reason["gate"]["failures"])
            if args.dry_run:
                print(json.dumps({k: reason[k] for k in ("key", "status", "reason", "no_lesson_why", "claims", "gate")},
                                 indent=1, default=str))
                continue
            queue_status = "done" if reason["status"] in ("published", "held_for_review", "no_lesson") else "held"
            remote(_REMOTE_WRITE, {"reason": reason, "queue_status": queue_status})
        return 0
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
