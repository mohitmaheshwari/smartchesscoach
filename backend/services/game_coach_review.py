"""
Coach-shaped game review story.

Composes the structured narrative the "Indian coach" reviews we
analyzed (Mohit 2026-06-01, 3-game audit) gave us, but driven by
Stockfish's `move_evaluations` instead of LLM pattern-matching on
move SAN. Output is deterministic; no LLM call.

The audit findings drove the shape:

  - The coach picks moves that fit a teachable narrative; we pick
    by cp_loss with a hard ≥100cp gate. (Audited false-positive
    rate ~28% in the coach reviews; cp gate removes that.)
  - The coach falsely praised a 655cp blunder as "best move of the
    game." Showing the cp number on every principle prevents the
    same class of confabulation here.
  - The coach narrated a winning arc on a 0-1 loss. We anchor the
    opener line in the actual result.

Output shape (added to GET /api/games/{id}/coach-review as `story`):

  {
    "opener":         "<one-line setup: opening + result + turning move>",
    "result_arc":     {result_label, decided_at_move, phase},
    "principles":     [up to 5, each principle a numbered teaching card],
    "good_moves":     [up to 2 best moves the user found],
    "summary_table":  [{mistake, remedy}, ...],   # condenses principles
    "homework":       [up to 3 action items],
    "closing":        "<one-line signoff>",
  }

The frontend renders this above the existing "Key moments" cards;
the cards stay below as the granular drill-down.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Any


# ── Configuration knobs ─────────────────────────────────────────────────

# Anything below this cp_loss is the band where the coach was making
# things up. Below 100cp the "mistake" framing is misleading at 1200
# rating — engine has a preference, but the move isn't a teaching
# moment. Hard floor.
PRINCIPLE_CP_FLOOR = 100

# Max principle cards. Coach used 5 consistently; that's also enough
# for a 1200 to act on without overwhelming.
MAX_PRINCIPLES = 5

# Show a "good moves" credit when there's at least this many high-
# quality moves to surface.
MIN_GOOD_MOVES_TO_SHOW = 1
MAX_GOOD_MOVES_TO_SHOW = 2


# ── (cognitive_gap, phase) → principle template ─────────────────────────
#
# Hand-authored for the cells we see most often in 1200-rated games.
# Cells not in this map fall back to `_FALLBACK_BY_PHASE` so we
# never crash. Voice: neutral, plain, "teach me" — no persona yet.
#
# Fields per entry:
#   title       short header for the card (≤6 words)
#   principle   one-sentence rule the user can carry to the next game
#   diagnosis   verbatim template; {played}/{best} get substituted
#   homework    action item for the homework block (optional; deduped)

_PRINCIPLE_TABLE: Dict[tuple, Dict[str, str]] = {

    # ── piece_safety ──
    ("piece_safety", "opening"): {
        "title": "Defend before you develop",
        "principle": "Before any developing move in the opening, scan your pieces — is anything undefended on the next move?",
        "diagnosis": "{played} left a piece exposed. {best} would have kept your material safe.",
        "homework": "Replay openings with the 'piece safety check' habit — name every undefended piece each turn.",
    },
    ("piece_safety", "middlegame"): {
        "title": "Don't move the queen into the open",
        "principle": "In the middlegame, never place your queen on a square where a knight or pawn can attack her in one move.",
        "diagnosis": "{played} left material undefended — {best} kept the position together.",
        "homework": "Solve 5 puzzles tagged 'queen safety' — focus on knight forks on the queen.",
    },
    ("piece_safety", "endgame"): {
        "title": "Every piece counts in the endgame",
        "principle": "In the endgame, one undefended piece often loses the game. Check defenders before every move.",
        "diagnosis": "{played} hung material in the endgame. {best} kept the balance.",
        "homework": "Slow down on endgame moves — 5 seconds per move minimum on each piece check.",
    },

    # ── missed_tactic / tactical_oversight ──
    ("missed_tactic", "middlegame"): {
        "title": "Look for tactics before quiet moves",
        "principle": "Before any developing move, scan for checks, captures, and threats — yours AND opponent's.",
        "diagnosis": "You missed {best} here, which was the strongest move. {played} let the chance slip.",
        "homework": "Solve 10 tactics puzzles daily — focus on knight forks and pins.",
    },
    ("missed_tactic", "endgame"): {
        "title": "Endgame tactics are real tactics",
        "principle": "The endgame has tactics too — forks, skewers, and traps. Look for them before pushing pawns.",
        "diagnosis": "{best} was a forcing line; {played} let the position drift.",
        "homework": "Solve 5 endgame tactics puzzles this week.",
    },
    ("tactical_oversight", "middlegame"): {
        "title": "Check opponent's reply first",
        "principle": "Before any attacking move, ask: 'What's my opponent's best reply? Can they capture something of mine first?'",
        "diagnosis": "{played} didn't account for the opponent's reply. {best} was the safe path.",
        "homework": "On every move, name one opponent threat before you play.",
    },
    ("tactical_oversight", "endgame"): {
        "title": "Slow down in the endgame",
        "principle": "Endgame mistakes are rarely about ideas — they're about not checking the opponent's reply.",
        "diagnosis": "{played} missed the reply. {best} would have held.",
        "homework": "Replay 3 endgame positions slowly — verbalize the opponent's threat each move.",
    },

    # ── calculation_depth ──
    ("calculation_depth", "middlegame"): {
        "title": "Calculate two moves deeper",
        "principle": "When a move 'looks good', calculate one move further. The hidden tactic is usually one move past where you stopped.",
        "diagnosis": "{played} worked at the surface — {best} was what you'd find if you went one move deeper.",
        "homework": "Practice calculation: pick 3 positions, calculate 4 moves deep before playing.",
    },
    ("calculation_depth", "endgame"): {
        "title": "Count moves to promotion",
        "principle": "In K+P endings, count squares to promotion and squares the king needs. The rule of the square is geometry, not feel.",
        "diagnosis": "{played} didn't respect the geometry. {best} was the correct calculation.",
        "homework": "Drill the rule of the square — 5 puzzles in your skill drill.",
    },

    # ── king_safety ──
    ("king_safety", "opening"): {
        "title": "Castle early",
        "principle": "Castle within the first 10–12 moves. A king in the center invites a tactical storm.",
        "diagnosis": "{played} delayed king safety. Castling first ({best}) would have been more secure.",
        "homework": "Make castling your second-to-fourth move priority in every game.",
    },
    ("king_safety", "middlegame"): {
        "title": "Watch the king as the position opens",
        "principle": "When pawns start trading near your king, every check matters. Track which diagonals and files are opening up.",
        "diagnosis": "{played} left the king exposed. {best} addressed the safety first.",
        "homework": "Pause 5 seconds per move when files near your king are open.",
    },
    ("king_safety", "endgame"): {
        "title": "King in the corner = mate",
        "principle": "In a queen vs king endgame, your king belongs near the center (e4, d4, e5, d5). Corners are mating squares.",
        "diagnosis": "{played} ran the king to the edge. {best} kept the king active.",
        "homework": "Play out 3 K+Q vs K positions — defender keeps the king centralized.",
    },

    # ── endgame_technique ──
    ("endgame_technique", "endgame"): {
        "title": "Tempo decides every K+P endgame",
        "principle": "In a king-and-pawn endgame, every king move gains or loses a tempo. Count squares before pushing pawns.",
        "diagnosis": "{played} cost a tempo. {best} kept the right race.",
        "homework": "Solve 5 K+P-vs-K puzzles in the rule-of-the-square drill.",
    },

    # ── opening_knowledge ──
    ("opening_knowledge", "opening"): {
        "title": "Know your opening 2 moves deeper",
        "principle": "Pick one opening for each color and learn the first 10 moves cold. Most plateau players stop at move 5.",
        "diagnosis": "{played} stopped following the main opening line. {best} was the principled continuation.",
        "homework": "Spend 10 minutes reviewing your main opening's first 10 moves before your next session.",
    },

    # ── piece_activity ──
    ("piece_activity", "middlegame"): {
        "title": "Activate your worst piece",
        "principle": "Each move, ask: 'Which of my pieces is doing the least?' That's the piece to improve.",
        "diagnosis": "{played} kept a piece passive. {best} activated the lazy one.",
        "homework": "Play 3 slow games where you label your worst piece every move.",
    },

    # ── ignore_threat ──
    ("ignore_threat", "middlegame"): {
        "title": "Address threats before plans",
        "principle": "If your opponent's last move created a threat, defending comes first. Your plan can wait one move.",
        "diagnosis": "{played} carried on with a plan; {best} stopped to defend.",
        "homework": "On each opponent move, name the threat aloud before deciding your response.",
    },
}


# Fallbacks when the (gap, phase) combo isn't authored. Keep the
# voice consistent — neutral, plain, action-oriented.
_FALLBACK_BY_PHASE = {
    "opening": {
        "title": "Slow down on developing moves",
        "principle": "Each opening move should accomplish one of: develop, castle, control center. Moves that do none of these are usually a step backwards.",
        "diagnosis": "{played} didn't fit a developing principle. {best} was more purposeful.",
        "homework": "Before each opening move, name the principle it serves.",
    },
    "middlegame": {
        "title": "Find the strongest move, not the first",
        "principle": "When you see a move that looks good, take 10 more seconds and look for a stronger one. There's usually one.",
        "diagnosis": "{played} was reasonable but {best} was stronger.",
        "homework": "Solve 5 puzzles where the obvious move is wrong.",
    },
    "endgame": {
        "title": "Endgame: count every move",
        "principle": "Endgame mistakes are almost always counting errors. Slow down and count tempi on every move.",
        "diagnosis": "{played} miscounted. {best} was the right tempo.",
        "homework": "Replay 3 endgame positions move-by-move, counting tempi each turn.",
    },
}


# Generic homework lines added based on the gap distribution. Keep
# to ~6 — the goal is "one action this week", not a list of 20.
_HOMEWORK_BY_GAP = {
    "piece_safety": "Drill: 5 queen-safety puzzles before your next session.",
    "missed_tactic": "Daily: 10 tactics puzzles for the next 5 days.",
    "tactical_oversight": "Habit: name one opponent threat before every move.",
    "king_safety": "Habit: castle by move 10 unless it's clearly worse.",
    "endgame_technique": "Drill: rule-of-the-square puzzles in /training/skill/endgame_rule_of_square.",
    "opening_knowledge": "Study: 10 minutes per side learning your main opening 10 moves deep.",
    "calculation_depth": "Drill: 5 calculation puzzles where the answer is 3+ moves deep.",
    "piece_activity": "Habit: every move, label your most passive piece.",
    "ignore_threat": "Habit: on every opponent move, name the threat first.",
}


# ── helpers ──────────────────────────────────────────────────────────────


def _phase_for_move(move_number: int) -> str:
    """Same phase boundaries the rest of coach-review uses."""
    if move_number <= 12:
        return "opening"
    if move_number <= 30:
        return "middlegame"
    return "endgame"


def _is_user_move(ev: Dict[str, Any]) -> bool:
    """Eval entries are only stored for the user's side per our pipeline,
    but defend against future schema changes."""
    if "is_user_move" in ev:
        return bool(ev["is_user_move"])
    return True


def _result_label(result_str: str, user_color: str) -> str:
    """Translate '1-0' / '0-1' / '1/2-1/2' into 'you won/lost/drew'."""
    r = (result_str or "").strip()
    color = (user_color or "white").lower()
    if r == "1-0":
        return "you won as White" if color == "white" else "you lost as Black"
    if r == "0-1":
        return "you lost as White" if color == "white" else "you won as Black"
    if r in ("1/2-1/2", "½-½"):
        return f"you drew as {color.title()}"
    return f"as {color.title()}"


def _pick_principle_template(gap: str, phase: str) -> Dict[str, str]:
    """Look up the principle for this gap+phase, fall back to phase-only."""
    return _PRINCIPLE_TABLE.get((gap, phase)) or _FALLBACK_BY_PHASE.get(phase) or _FALLBACK_BY_PHASE["middlegame"]


def _format_cp(cp: int) -> str:
    """Tag for the cp_loss badge on each card — keeps the model honest."""
    return f"-{int(cp)}cp"


# Map caption first-verb to a short card title. Keeps the principle
# card header consistent with the failure-mode diagnosis instead of
# leaving the (gap, phase) header ("Castle early") attached to a
# different-shaped body ("walks into Nd4 attacking the queen").
_CAPTION_VERB_TO_TITLE = [
    ("walks into",        "Walks into the reply"),
    ("allows",            "Allows a tactic"),
    ("hangs to",          "Hanging piece"),
    ("loses to",          "Walks into check"),
    ("drops the exchange","Losing exchange"),
    ("leaves your",       "Undefended piece"),
]


def _title_for_caption(caption: str, fallback: str) -> str:
    """If the caption opens with a known failure-mode verb (per the
    R12_blunder failure variants shipped 2026-06-02), pick the short
    title matching that verb. Otherwise return the fallback (which is
    the (gap, phase) template title — usually fine for older captions
    or non-failure-mode shapes)."""
    if not caption:
        return fallback
    # The caption starts with the move SAN, then the verb.
    # Lowercase everything after the first word for matching.
    parts = caption.split(maxsplit=1)
    body = parts[1].lower() if len(parts) > 1 else ""
    for verb, title in _CAPTION_VERB_TO_TITLE:
        if body.startswith(verb):
            return title
    return fallback


def _split_r12_caption(caption: str) -> tuple:
    """Split a stored R12_blunder caption into (diagnosis, principle).

    R12 captions (after 2026-06-02 failure-mode shipping) follow one
    of these shapes:

      (a) "{played} {failure_clause}. {best} was better — {alternative}."
          → diagnosis = first sentence (failure clause).
          → principle = second sentence (alternative recommendation).

      (b) "{played} {failure_clause}. {teaching_principle}."
          → diagnosis = first sentence (failure clause).
          → principle = second sentence (teaching).

      (c) "{played} {severity_phrase}. {best} was better — {why_clause}"
          (older alternative-only variant)
          → diagnosis = first sentence.
          → principle = rest.

      (d) "{played} {severity_phrase}. {best} was better."
          (terse fallback when no why_clause)
          → diagnosis = first sentence.
          → principle = second sentence ("{best} was better.").

    We split on the first ". " — works for all four shapes. When the
    caption has only one sentence (unusual), return it as diagnosis
    with empty principle.
    """
    caption = caption.strip()
    if not caption:
        return "", ""
    # Prefer ". " split (matches all shapes above).
    parts = caption.split(". ", 1)
    if len(parts) == 2:
        diagnosis = parts[0].rstrip(".") + "."
        principle = parts[1].rstrip(".") + "." if not parts[1].endswith(("?", "!")) else parts[1]
        return diagnosis, principle
    # Single sentence — give it as diagnosis.
    return caption, ""


# ── core composer ───────────────────────────────────────────────────────


def compose_story(
    evals: List[Dict[str, Any]],
    result_str: str,
    user_color: str,
    opening_name: str,
    decryption_data: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Compose the structured coach-review story. Returns None if the
    game wasn't analyzed enough to produce a meaningful story."""

    user_evals = [e for e in evals if _is_user_move(e)]
    if not user_evals:
        return None

    # ── 0. Caption lookup from decryption_data ──
    # decryption_data lives on game_analyses.decryption_data and is the
    # V5 per-move narrative store. Each entry has caption (deterministic
    # R12_blunder output) and caption_llm (LLM-polished version, may be
    # None). We prefer caption_llm when present, fall back to caption.
    # See services/game_decryption_v5_service.py for the writer.
    caption_by_key: Dict[tuple, str] = {}
    for d in (decryption_data or []):
        if not isinstance(d, dict):
            continue
        mn = d.get("move_number")
        san = d.get("move_san") or d.get("move")
        if mn is None or not san:
            continue
        cap = (d.get("caption_llm") or d.get("caption") or "").strip()
        if cap:
            caption_by_key[(mn, san)] = cap

    # ── 1. Principles: top-N user moves by cp_loss, gated by floor ──
    scored = [
        e for e in user_evals
        if (e.get("cp_loss") or 0) >= PRINCIPLE_CP_FLOOR
    ]
    scored.sort(key=lambda e: e.get("cp_loss", 0), reverse=True)

    principles: List[Dict[str, Any]] = []
    seen_phase_gap: set = set()
    homework_items: List[str] = []

    for ev in scored:
        if len(principles) >= MAX_PRINCIPLES:
            break
        mn = ev.get("move_number") or 0
        phase = _phase_for_move(mn)
        gap = ev.get("cognitive_gap") or ""

        # Avoid hammering the same (gap, phase) twice unless we
        # already have <2 principles. Diversity > redundancy.
        key = (gap, phase)
        if key in seen_phase_gap and len(principles) >= 2:
            continue
        seen_phase_gap.add(key)

        tmpl = _pick_principle_template(gap, phase)
        played = ev.get("move") or "?"
        best = ev.get("best_move") or "?"
        cp_loss = int(ev.get("cp_loss") or 0)

        # Mohit 2026-06-02 — wire the R12_blunder failure-mode captions
        # (Phase 1/2 shipped earlier today) into Coach Review. When the
        # eval has a stored caption from R12 (which now diagnoses the
        # played move with concrete failure-mode wording — "walks into
        # Nd4 attacking the queen on f3" instead of generic templating),
        # prefer it over the (gap, phase) principle template.
        #
        # The (gap, phase) template fires generic developmental advice
        # ("Castle early", "Slow down on developing moves") even on
        # tactical opening collapses — Mohit's Italian Game/Nxf7 game
        # was the smoking gun. The R12 caption is much closer to what
        # the user actually needs to hear.
        #
        # Split the caption: first sentence = diagnosis (the failure
        # clause), rest = principle (alternative move + teaching, or
        # the universal teaching principle). Both are already grounded
        # in concrete facts per the failure-mode work.
        stored_caption = caption_by_key.get((mn, played), "").strip()
        if stored_caption:
            diagnosis_text, principle_text = _split_r12_caption(stored_caption)
            title_text = _title_for_caption(stored_caption, tmpl["title"])
        else:
            diagnosis_text = tmpl["diagnosis"].format(played=played, best=best)
            principle_text = tmpl["principle"]
            title_text = tmpl["title"]

        principle = {
            "n": len(principles) + 1,
            "move_number": mn,
            "phase": phase,
            "san_played": played,
            "san_best": best,
            "cp_loss": cp_loss,
            "cp_loss_label": _format_cp(cp_loss),
            "title": title_text,
            "diagnosis": diagnosis_text,
            "principle": principle_text,
            "fen_before": ev.get("fen_before"),
            "gap": gap or None,
        }
        principles.append(principle)

        hw = _HOMEWORK_BY_GAP.get(gap)
        if hw and hw not in homework_items:
            homework_items.append(hw)

    if not principles:
        # Game had nothing >100cp — either it was a clean game or
        # short. Skip the story; the user gets the existing data
        # sections.
        return None

    # ── 2. Result arc ──
    turning = principles[0]  # highest cp_loss
    result_arc = {
        "result_label": _result_label(result_str, user_color),
        "decided_at_move": turning["move_number"],
        "phase": turning["phase"],
    }

    # ── 3. Opener line ──
    op = (opening_name or "").strip() or "this game"
    rl = result_arc["result_label"]
    opener = (
        f"You played the {op} and {rl}. "
        f"The game turned at move {turning['move_number']} in the {turning['phase']}."
    )

    # ── 4. Good moves credit ──
    # "best" / "excellent" classifications, or cp_loss == 0 on a
    # non-trivial position. Pick the most impressive — earliest in
    # the game with the lowest cp_loss against an interesting position
    # (heuristic: top of the move list with classification == 'best').
    good_candidates = [
        e for e in user_evals
        if (e.get("classification") in ("best", "excellent", "brilliant"))
        and (e.get("cp_loss") or 0) == 0
        and (e.get("move_number") or 0) >= 6   # skip book moves
    ]
    good_candidates.sort(key=lambda e: -(e.get("move_number") or 0))  # later = more impressive
    good_moves = []
    for ev in good_candidates[:MAX_GOOD_MOVES_TO_SHOW]:
        good_moves.append({
            "move_number": ev.get("move_number"),
            "san": ev.get("move"),
            "phase": _phase_for_move(ev.get("move_number") or 0),
        })

    # ── 5. Summary table ──
    summary_table = [
        {
            "mistake": f"{p['san_played']} (move {p['move_number']})",
            "cp_loss_label": p["cp_loss_label"],
            "remedy": p["principle"],
        }
        for p in principles
    ]

    # ── 6. Homework ──
    # Take up to 3 unique items, prefer ones tied to the principles
    # we just listed so the homework reinforces the lesson.
    homework = homework_items[:3]
    if not homework:
        homework = ["Replay this game move-by-move at a slower pace this week."]

    # ── 7. Closing ──
    n = len(principles)
    closing = (
        f"{'One real mistake' if n == 1 else f'{n} real mistakes'} decided this game. "
        f"The biggest was move {turning['move_number']} — fix that pattern and the others follow."
    )

    return {
        "opener": opener,
        "result_arc": result_arc,
        "principles": principles,
        "good_moves": good_moves if len(good_moves) >= MIN_GOOD_MOVES_TO_SHOW else [],
        "summary_table": summary_table,
        "homework": homework,
        "closing": closing,
    }
