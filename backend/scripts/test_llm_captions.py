"""
Test LLM caption generation on N games (default 1).

Loads existing decryption_v5_data from game_analyses, extracts facts per
move, and (when there's a teaching signal) sends to gpt-4o-mini through
call_llm with:
  - Coach Voice rules (services/coach_voice_prompt.py)
  - The 28 caption principle catalog (services/caption_principles.py)
  - The 23 shape pattern catalog (services/shape_patterns.py)

Per-move gate: if facts contain no best_move-difference, no shape
pattern, no principles, and severity is non-teaching ("good"/"context"),
the LLM is never called for that move — empty caption returned. This
stops the model from hallucinating on quiet positions.

Retry-with-backoff handles 429 rate-limit errors transparently.

Does NOT touch production data. Writes a side-by-side markdown report.

Usage:
    docker exec -it chess-coach-backend python scripts/test_llm_captions.py
    docker exec -it chess-coach-backend python scripts/test_llm_captions.py --n 10 --source queue
    docker exec -it chess-coach-backend python scripts/test_llm_captions.py --n 5 --source random --output /tmp/llm_test.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

from llm_service import call_llm
from services.coach_voice_prompt import with_coach_voice
from services.shape_patterns import SHAPE_PATTERNS
from services.caption_principles import PRINCIPLES
from services.trap_recognition import detect_trap_setup, match_trap_line_step
from services.opening_lookup import match_opening_for_mover

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

TEACHING_SEVERITIES = {"mistake", "blunder", "opp_mistake", "opp_blunder"}


def build_principle_catalog_block() -> str:
    """The 28 named teaching principles.

    Sends ONLY `id`, `name`, `phase_in_scope`. The cue lines from the
    catalog are NOT sent — they were authored as full captions for the
    renderer (with advice tails and placeholder squares) and they
    bait the LLM into copying their shape. The LLM has the voice rules
    + the evidence dict per principle in facts — that's enough.
    """
    lines = [
        "TEACHING PRINCIPLES — use these NAMES verbatim when the facts say one fires.",
        "Do NOT invent new principle names. Per-move facts.principles_present[].evidence",
        "carries the specifics (square, piece type, who owns it).",
        "",
    ]
    for p in PRINCIPLES:
        phases = ",".join(p.get("phase_in_scope") or [])
        lines.append(f"- {p['name']} ({p['id']}) [{phases}]")
    return "\n".join(lines)


def build_shape_catalog_block() -> str:
    """The 23 named shape patterns the coach can call out on the board.

    Sends ONLY `name`. The authored descriptions (e.g. "Just take it",
    "Attack it once more — it falls") contain imperative advice tails
    that the LLM copies verbatim into output, violating Rule A. The
    pattern name is descriptive enough; per-move facts.shape_pattern
    carries the specifics (mover, targets, executing_move).
    """
    lines = [
        "SHAPE PATTERNS — use these NAMES verbatim when facts.shape_pattern.name matches.",
        "Do NOT invent new shape names. Per-move facts.shape_pattern carries the",
        "specifics (mover, targets, executing_move).",
        "",
    ]
    for s in SHAPE_PATTERNS:
        lines.append(f"- {s['name']}")
    return "\n".join(lines)


# Prompt v3:
# - Forbidden phrases moved to top.
# - Explicit "Queen Fork" ban (rule D).
# - Best-move fabrication ban (rule E).
# - Perspective lock on opp moves (rule H).
# - TRAP OVERRIDE — when facts.trap is present, mechanical principles
#   describe the BAIT; the trap IS the teaching idea.
CAPTION_TASK_PROMPT = """You write ONE-SENTENCE captions for chess moves, for players rated 600-1500.

You receive a facts dict about ONE move. Your only job: find a TEACHING IDEA grounded in those facts.

═════ TRAP OVERRIDE — HIGHEST PRIORITY ═════

If facts.trap is present, this position is inside a named opening trap. Everything else in facts (TAC_HANGING_PIECE, OP_SAME_PIECE_TWICE, OP_FINISH_DEVELOPMENT, etc.) describes SURFACE features of how the trap looks. These critiques are WRONG when a trap is active — the moves are intentional bait or intentional punishment, not mistakes.

There are TWO trap phases. Use the right one based on facts.trap.step_label:

PHASE 1 — setup_completed (facts.trap.step == 0):
  - This move COMPLETES a known trap setup. The bait is now set.
  - Name the trap (facts.trap.name verbatim).
  - State the idea in ≤ 14 words using facts.trap.description as ground truth.
  - You may name facts.trap.next_expected_move as the bait-grabbing move.
  - Form: "{move} — {trap_name}. {one clause about the idea}."
  - Example: "Nd4 — Blackburne Shilling Gambit. The e5 pawn is bait; if they grab with Nxe5, Qg5! wins."

PHASE 2 — victim_falls or trap_player_punishes (facts.trap.step >= 1):
  - This move is step N of the trap_line — the game is following the authored line.
  - facts.trap.step_explanation gives the authored idea for this step (use it as ground truth, do NOT copy verbatim).
  - If step_label == "victim_falls": describe what just happened. The mover walked into the prepared idea.
    Form: "{move} — {trap_name}, step {N}. They walked into it; next comes {next_expected_move}."
  - If step_label == "trap_player_punishes": describe what this move achieves in the trap's plan.
    Form: "{move} — {trap_name}, step {N}. {what punishment this delivers, from step_explanation}."
  - In both cases NAME THE TRAP. The trap is the lesson.

NEVER critique a move when facts.trap is present using mechanical principles. Even if principles_present says hanging/same-piece-twice/etc., the trap context overrides those.

If facts.trap is null/absent, continue to the regular rules below.

═════ OPENING CONTEXT (facts.opening) ═════

In opening-phase moves, facts.opening is populated when the side's played moves match a known opening's setup_order. Fields:
  - facts.opening.name           — "Italian Game", "London System", etc.
  - facts.opening.summary        — authored one-sentence pitch of the opening's idea.
  - facts.opening.golden_rules   — list of authored short principles for this opening.
  - facts.opening.matched_steps  — how many setup moves of this opening have been played.
  - facts.opening.next_expected  — the canonical next setup move, or null at end of setup.

When facts.opening is present and no trap is active:
  - You MAY name the opening using facts.opening.name verbatim.
  - You MAY draw on facts.opening.summary or one of facts.opening.golden_rules to teach the IDEA behind this move — pick the rule that fits.
  - Use those authored lines as INSPIRATION for content, not templates. Rewrite in your own voice. Do not copy verbatim more than 3 consecutive words.
  - On step 1 (matched_steps == 1) it is often useful to NAME the opening once and state its core idea. After that, focus on the specific job of THIS move.
  - If facts.opening.next_expected is present and the played move IS that expected move, your caption can simply describe what this move does and what's coming.

If facts.opening is null/absent, fall back to PRIMARY-REASON CATEGORIES below.

═════ NEVER DO THESE — each one fails the task ═════

A. NEVER end with advice. Forbidden phrases (any tense): "focus on...", "try to...", "in future games...", "consider...", "watch for...", "castle soon", "remember to...", "be careful with...", "scan every move", "scan after...", "attack it again", "reroute or trade", "keep the initiative", "keep the pressure". If your sentence ends with imperative advice to the player, rewrite or drop it.

B. NEVER use generic praise: "Good move!", "Nice!", "Great move!", "Well done!", "Excellent!". Praise must name a specific principle or shape pattern from the catalogs.

C. NEVER name a square, piece, or move that is NOT in the facts dict (including inside `principles_present[].evidence` and `shape_pattern`). If facts don't contain "e5" anywhere, you must not write "e5". If facts don't say "pawn", do not mention a pawn.

D. NEVER invent principle or shape names. The shape catalog has Knight Fork, Bishop Fork, Rook Fork — NO "Queen Fork", NO "Pawn Fork". If TAC_FORK_PATTERN fires but no matching catalog shape is named in facts.shape_pattern, write "fork" lowercase as a generic noun, not as a named pattern.

E. NEVER fabricate what the best_move does. best_move is the engine's safer alternative — describe what it DOES only if facts contain explicit support (a shape pattern, a principle evidence). Otherwise just name it: "Better was Nf6." Don't say "Nf6 hits...", "Nf6 attacks...", "Nf6 captures..." unless facts back that claim.

F. NEVER use engine words or internal labels: cp, eval, evaluation, centipawn, accuracy, %, "context", "context move", "good move tag", "severity", "primary reason", "category". These are internal terms the player never sees.

G. NEVER say "this move" — name the move (e.g. "Nf3", not "this move").

H. PERSPECTIVE LOCK on opponent moves (when is_user_move = false):
   - Use "their" / "them" for opponent's pieces, NEVER "your" / "you".
   - Don't switch to giving the user advice mid-sentence.
   - Either observe what their move did, OR say nothing.
   - Example OK:    "Their a3 wastes a tempo — no piece developed."
   - Example WRONG: "Your bishop on c1 is blocked..."   (c1 is opp's square when user is black; "your" refers to opp's piece — confused)
   - Example WRONG: "a3 is a wasted move — develop your pieces instead." (mixes opp move with user advice)
   - On opp moves, if any principle (MID_BAD_BISHOP, OP_KNIGHT_ON_RIM, etc.) fires, the piece in question is the OPPONENT's piece. Refer to it as "their" piece.

I. NEVER name an opening unless facts.opening is present in the facts dict. The catalog name "Italian Game" must come from facts.opening.name and nowhere else. Even if move_played and phase suggest a common opening, DO NOT name it without the fact.
   - Example WRONG: "e4 — Italian Game..." (facts.opening absent on move 1)
   - Example OK:    "e4 — claims the centre and opens lines for the bishop."

J. FORCED RECAPTURE — if facts.primary_reason_category == "forced_recapture", ALWAYS output empty. Even if facts.opening is present, even if cp_loss is non-zero, even if principles fire. A forced move has no teaching value because no choice was made.

K. PIECE TYPE comes from the MOVE SAN, not from squares:
   - SAN starts with N → knight
   - SAN starts with B → bishop
   - SAN starts with R → rook
   - SAN starts with Q → queen
   - SAN starts with K → king
   - SAN starts with a-h → pawn
   - "Nxh8" means a KNIGHT captured on h8. The piece on h8 after the move is a knight, regardless of what used to be on that square.
   - NEVER infer "rook" because h8 is rook's starting square. The move tells you what landed there.

═════ PRIMARY-REASON CATEGORIES (facts.primary_reason_category) ═════

This is the V5 extractor's own classification of WHAT KIND of teaching this move offers. Use it as your primary teaching frame when no trap is active.

  - opening_central_pawn  — pawn move to d4/d5/e4/e5 in the first 2 moves. Teach: claims the center, opens lines for pieces.
  - development           — minor piece (knight/bishop) developing from start square in the opening. Teach: gets the piece out, attacks/defends a key square.
  - opening_castled       — castling. Teach: king safety, rook to centre.
  - material              — move that captures or wins/loses material. Teach: name what was taken / what was lost.
  - tactic_played         — a tactical motif was executed (fork, pin, skewer, discovered, etc.). Use the matching shape_pattern name when present.
  - check_plain           — a check. Teach: what the check forces.
  - check_extra           — a check that creates additional threats. Teach: what extra threat is created.
  - threat                — a non-check threat (attacks a piece, eyes a square). Teach: what is threatened.
  - forced_recapture      — recapture, no real choice. SKIP — output empty.
  - blunder / mistake     — engine flags move as losing eval. Teach: what's wrong, what's better.
  - mate                  — mate threat or mate. Teach: how the mate works.

═════ WHAT TO WRITE ═════

ONE sentence, max 18 words.

Use the facts to choose ONE of these three teaching frames:

1. Mistake/blunder critique — if severity is mistake/blunder/opp_mistake/opp_blunder, OR principles_present is non-empty, OR shape_pattern is present and was missed by played move.
   Form: "{played_move} {what went wrong using a principle/shape name}. {best_move} {what it does}."
   Example: "Nd5 was sharper here — Nf3 gives up the center."

2. Best-move teaching — if played move is fine (severity good/context, cp_loss low) BUT best_move differs AND a principle/shape applies to the best move.
   Form: "Decent — {best_move} {what it does using a principle/shape name}."
   Example: "Decent — Qg4+ sets up the Skewer."

3. Specific praise — if played move applied a named principle/shape (catalog has the name).
   Form: "{played_move} {names the principle/shape that fires}."
   Example: "Qg5 — clean Knight Fork on the queen and rook."

═════ EMPTY OUTPUT RULE — STRICT ═════

If ALL of these are true, output an empty string (single space, nothing else):
  - principles_present is [] or null AND
  - shape_pattern is null AND
  - severity is not mistake/blunder/opp_mistake/opp_blunder AND
  - best_move is missing or equal to move_played

Examples that MUST be empty:
  - opponent quiet move with no facts → empty
  - forced recapture → empty
  - any move where you'd have to invent a chess idea to fill the caption → empty

Better silence than a generic line.

═════ FINAL CHECKLIST — DO BEFORE OUTPUT ═════

Before you emit the caption, scan it and answer each:

  1. Did I name an opening (e.g., "Italian Game", "London System", "King's Indian", "Sicilian", etc.)?
     IF YES — does facts.opening exist in the facts dict (not null)?
     IF facts.opening is null/absent → REMOVE the opening name. The sentence stays, but the opening name goes. No exceptions.

  2. Does my sentence end with imperative advice to the player?
     Phrases to check: "...focus on X", "...try Y", "...attack it again", "...castle soon", "...be ready", "...exploit", "...prepare", "...look for", "...pressure builds".
     IF YES → rewrite without the tail. End on the observation, not on instructions.

  3. Did I use "your/you" to refer to opponent's pieces (when is_user_move=false)?
     IF YES → switch to "their/them". Opp moves = third-person observation.

  4. Did I claim what best_move "does" / "hits" / "attacks" / "captures" / "forces"?
     IF YES — does the facts dict contain explicit support (shape_pattern, principle evidence, primary_reason, opening rule)?
     IF NO support → cut the claim. Just name the move: "Better was {best_move}."

  5. Did I use internal labels: "context", "context move", "severity", "primary reason", "category", "step"?
     IF YES → strip them. Player never sees these.

If any check fails, fix the sentence. Then output.

═════ OUTPUT ═════

Just the sentence text. No labels, no quotes, no JSON, no preamble like "Here is the caption:". Empty string allowed."""


def has_teaching_signal(move: Dict[str, Any]) -> bool:
    """Decide whether to even call the LLM. Hard gate on hallucination.

    Fires when any of these signals are present:
      - known opening trap (highest priority)
      - V5 caption rule fired (primary_reason set) — covers opening
        moves (e4, Nf3 etc.) where the extractor categorised the move
        as "opening_central_pawn" or "development" even though no
        principle was violated
      - shape pattern hit
      - any principle fired
      - mistake/blunder severity
      - best move differs from played
    """
    if move.get("_trap"):
        return True
    if move.get("caption_facts_primary_reason"):
        return True
    if move.get("shape_pattern_name"):
        return True
    if move.get("caption_facts_principles_violated"):
        return True
    if move.get("severity") in TEACHING_SEVERITIES:
        return True
    best = move.get("best_move_san")
    played = move.get("move_san")
    if best and played and best != played:
        return True
    return False


def build_move_facts(move: Dict[str, Any]) -> Dict[str, Any]:
    """The compact facts dict sent to the LLM. No FEN. No PV. Just facts.

    Per-principle evidence is included verbatim — that's where the
    concrete squares/pieces live (e.g. TAC_HANGING_PIECE.evidence
    contains hanging_piece_square + hanging_piece_type). Without this
    the LLM has nothing to anchor specifics to and invents them.
    """
    principles_present = []
    for p in (move.get("caption_facts_principles_violated") or []):
        if not p:
            continue
        principles_present.append({
            "id": p.get("principle_id"),
            "evidence": p.get("evidence") or {},
        })
    primary = move.get("caption_facts_primary_reason") or {}
    facts = {
        "move_played": move.get("move_san"),
        "move_number": move.get("move_number"),
        "is_user_move": move.get("is_user_move"),
        "phase": move.get("phase"),
        "opening_name": move.get("opening_name"),
        "best_move": move.get("best_move_san"),
        "severity": move.get("severity"),
        "cp_loss": move.get("cp_loss"),
        "primary_reason_category": primary.get("category") if isinstance(primary, dict) else None,
        "principles_present": principles_present,
    }
    if move.get("shape_pattern_name"):
        facts["shape_pattern"] = {
            "name": move["shape_pattern_name"],
            "description": move.get("shape_pattern_desc"),
            "mover": move.get("shape_pattern_mover"),
            "targets": move.get("shape_pattern_targets") or [],
            "executing_move": move.get("shape_pattern_executing_move"),
        }
    # Trap is computed at iteration time by the script (not yet in V5 DB)
    # and attached on the move dict under a runtime-only key.
    if move.get("_trap"):
        facts["trap"] = move["_trap"]
    # Opening curriculum match (name + summary + golden_rules) for the
    # side that just moved. Same runtime-attached pattern as _trap.
    if move.get("_opening"):
        facts["opening"] = move["_opening"]
    return facts


def _retry_seconds_from_error(err_text: str) -> Optional[float]:
    """OpenAI 429 messages embed 'Please try again in X.YYYs'. Extract it."""
    m = re.search(r"try again in ([\d.]+)s", err_text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


async def call_with_retry(sys_prompt: str, user_prompt: str, max_attempts: int = 4) -> str:
    """Call the LLM with retry-on-429. Backs off using the suggested wait
    if OpenAI tells us how long, otherwise exponential. Returns the
    response text, or '[ERROR: ...]' if all attempts failed.
    """
    last_err: Optional[Exception] = None
    delay = 2.0
    for attempt in range(1, max_attempts + 1):
        try:
            out = await call_llm(
                system_message=sys_prompt,
                user_message=user_prompt,
                model="gpt-4o-mini",
                max_tokens=80,
            )
            return (out or "").strip().strip('"').strip("'")
        except Exception as e:
            last_err = e
            err_text = str(e)
            if "rate_limit" in err_text or "429" in err_text:
                suggested = _retry_seconds_from_error(err_text)
                wait = suggested + 0.5 if suggested else delay
                print(f"[test] rate limit hit on attempt {attempt}/{max_attempts}, waiting {wait:.1f}s", file=sys.stderr)
                await asyncio.sleep(wait)
                delay = min(delay * 2, 30)
                continue
            return f"[ERROR: {e}]"
    return f"[ERROR after {max_attempts} attempts: {last_err}]"


async def generate_caption(move: Dict[str, Any], sys_prompt: str) -> str:
    if not has_teaching_signal(move):
        return ""  # hard gate — never call LLM on no-signal moves
    facts = build_move_facts(move)
    user_prompt = f"MOVE FACTS:\n{json.dumps(facts, indent=2)}\n\nWrite the caption."
    return await call_with_retry(sys_prompt, user_prompt)


def format_facts_inline(move: Dict[str, Any]) -> str:
    parts = []
    if move.get("_trap"):
        parts.append(f"TRAP={move['_trap']['name']}")
    if move.get("_opening"):
        parts.append(f"opening={move['_opening']['name']}@step{move['_opening']['matched_steps']}")
    if move.get("best_move_san"):
        parts.append(f"best={move['best_move_san']}")
    if move.get("caption_facts_primary_reason"):
        parts.append(f"rule={move['caption_facts_primary_reason']}")
    if move.get("shape_pattern_name"):
        parts.append(f"shape={move['shape_pattern_name']}")
    pids = [p.get("principle_id") for p in (move.get("caption_facts_principles_violated") or []) if p]
    if pids:
        parts.append(f"principles={','.join(pids)}")
    return " | ".join(parts) or "(none)"


async def pick_games(db, n: int, source: str) -> List[Dict[str, str]]:
    if source == "queue":
        items = await db.authoring_queue.find(
            {},
            {"_id": 0, "game_id": 1, "bucket": 1, "order_in_round": 1},
        ).sort("order_in_round", 1).limit(n).to_list(n)
        if items:
            return items
        print("[test] authoring_queue empty — falling back to random sample", file=sys.stderr)

    items: List[Dict[str, str]] = []
    async for g in db.games.aggregate([
        {"$match": {"is_active": {"$ne": False}, "is_analyzed": True}},
        {"$sample": {"size": n}},
        {"$project": {"_id": 0, "game_id": 1}},
    ]):
        items.append({"game_id": g["game_id"], "bucket": "random"})
    return items


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1,
                    help="Number of games to test (default 1 — keep low until prompt is validated).")
    ap.add_argument("--source", choices=["queue", "random"], default="queue",
                    help="queue=use active authoring_queue (default), random=random sample")
    args = ap.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    games = await pick_games(db, args.n, args.source)

    sys_prompt = with_coach_voice(
        CAPTION_TASK_PROMPT
        + "\n\n" + build_principle_catalog_block()
        + "\n\n" + build_shape_catalog_block()
    )

    totals = {"moves": 0, "called": 0, "gated": 0, "llm_empty": 0, "errors": 0}

    for idx, item in enumerate(games, 1):
        gid = item["game_id"]
        bucket = item.get("bucket", "?")

        print("")
        print("═" * 78)
        print(f"GAME {idx}/{len(games)}   game_id: {gid}   bucket: {bucket}")
        print(f"  open in UI:  /game/{gid}")
        print("═" * 78)

        analysis = await db.game_analyses.find_one(
            {"game_id": gid},
            {"_id": 0, "decryption_v5_data": 1},
        )
        if not analysis or not analysis.get("decryption_v5_data"):
            print("  (no V5 data for this game)")
            continue

        moves = analysis["decryption_v5_data"]

        # Walk the game's SAN sequence so we can:
        #   (a) fire the trap detector against the played-moves prefix
        #       to find the setup-completing move, and
        #   (b) walk subsequent moves against trap_line to annotate them
        #       as "in_line" (continues the trap) or break tracking if
        #       the player deviates.
        played_san_so_far: List[str] = []
        active_trap: Optional[Dict[str, Any]] = None
        active_trap_setup_completed_by_user: Optional[bool] = None
        active_trap_step_cursor: int = 0  # 0 = setup_complete, 1+ = in trap_line

        for m in moves:
            san = m.get("move_san")
            if not san:
                continue
            played_san_so_far.append(san)

            # Opening lookup — per move, for the side that just moved.
            mover_color = "white" if m.get("is_white") else "black"
            opening_match = match_opening_for_mover(played_san_so_far, mover_color)
            if opening_match:
                m["_opening"] = opening_match

            if active_trap is None:
                # Look for a new trap setup completing on this move.
                hit = detect_trap_setup(played_san_so_far)
                if hit:
                    active_trap = hit
                    active_trap_setup_completed_by_user = bool(m.get("is_user_move"))
                    active_trap_step_cursor = 0
                    m["_trap"] = {
                        "name": hit["name"],
                        "family": hit["family"],
                        "description": hit["description"],
                        "step": 0,
                        "step_label": "setup_completed",
                        "completed_by_user": active_trap_setup_completed_by_user,
                        "this_move_by_user": bool(m.get("is_user_move")),
                        "next_expected_move": hit["trap_line"][0] if hit["trap_line"] else None,
                    }
                    print(f"\n  ▶ TRAP DETECTED on move {m.get('move_number')}: "
                          f"{hit['name']} ({hit['family']}) — completed by "
                          f"{'user' if active_trap_setup_completed_by_user else 'opp'}")
            else:
                # We're in trap territory. Check whether this move follows
                # the expected trap_line step.
                step_index = active_trap_step_cursor  # 0 = first move after setup
                if match_trap_line_step(active_trap, san, step_index):
                    # Whose move is this in the trap_line?
                    #   step_index 0 = the side that DIDN'T play the setup
                    #                  (the "victim" who falls for the bait).
                    #   step_index 1 = the trap_player punishing.
                    #   alternates from there.
                    if step_index % 2 == 0:
                        step_label = "victim_falls"  # opp of trap_player
                    else:
                        step_label = "trap_player_punishes"
                    step_expl = ""
                    if step_index < len(active_trap.get("trap_line_steps") or []):
                        step_expl = active_trap["trap_line_steps"][step_index].get("explanation", "")
                    next_mv = None
                    if step_index + 1 < len(active_trap["trap_line"]):
                        next_mv = active_trap["trap_line"][step_index + 1]
                    m["_trap"] = {
                        "name": active_trap["name"],
                        "family": active_trap["family"],
                        "description": active_trap["description"],
                        "step": step_index + 1,
                        "step_label": step_label,
                        "step_explanation": step_expl,
                        "completed_by_user": active_trap_setup_completed_by_user,
                        "this_move_by_user": bool(m.get("is_user_move")),
                        "next_expected_move": next_mv,
                    }
                    active_trap_step_cursor = step_index + 1
                    print(f"  ▶ TRAP CONTINUATION on move {m.get('move_number')}.{san} "
                          f"— step {step_index + 1} ({step_label})")
                    if active_trap_step_cursor >= len(active_trap["trap_line"]):
                        # Reached end of authored line — clear.
                        active_trap = None
                        active_trap_step_cursor = 0
                else:
                    # Deviated from trap_line — clear tracking.
                    active_trap = None
                    active_trap_step_cursor = 0

        for m in moves:
            totals["moves"] += 1
            mv = m.get("move_san", "?")
            mn = m.get("move_number", "?")
            mover = "user" if m.get("is_user_move") else "opp "
            sev = (m.get("severity") or "?").ljust(13)

            if not has_teaching_signal(m):
                totals["gated"] += 1
                continue  # skip silently — no signal, no print

            totals["called"] += 1
            llm_caption = await generate_caption(m, sys_prompt)

            if not llm_caption:
                totals["llm_empty"] += 1
                tag = "[LLM-EMPTY]"
            elif llm_caption.startswith("[ERROR"):
                totals["errors"] += 1
                tag = "[ERROR]    "
            else:
                tag = "           "

            existing = (m.get("caption") or "").strip() or "(no existing)"
            print(f"\n  move {mn:>3}.{mv:<8}  {mover}  {sev}  {tag}")
            print(f"    existing : {existing}")
            print(f"    LLM      : {llm_caption or '(empty)'}")
            print(f"    facts    : {format_facts_inline(m)}")

    print("")
    print("─" * 78)
    print(
        f"moves={totals['moves']}  called={totals['called']}  "
        f"gated={totals['gated']}  llm_empty={totals['llm_empty']}  errors={totals['errors']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
