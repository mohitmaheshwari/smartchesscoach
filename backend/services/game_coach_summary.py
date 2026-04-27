"""
Game Coach Summary Service
===========================

Deterministic game diagnosis — no LLM, no storytelling.
Three outputs:

1. SUMMARY: One brutal truth about WHY you lost/won
2. HABITS:  Pass/fail checklist of behavioral patterns
3. MEMORY:  Identity snapshot + impact projection

Everything is derived from Stockfish eval + existing analysis data.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── GAME DIAGNOSIS TYPES ────────────────────────────────────────

class GameDiagnosis:
    THROW = "THROW"                            # Was winning, threw it away in one decisive moment
    TIME_LOSS_WHILE_WINNING = "TIME_LOSS_WHILE_WINNING"  # Had a winning peak but lost on the clock
    MATE_BLIND = "MATE_BLIND"                  # Allowed a real short mate (confirmed by mate_info + delivery)
    SLOW_BLEED = "SLOW_BLEED"                  # Accumulated small mistakes, no big blunder
    OPENING_COLLAPSE = "OPENING_COLLAPSE"      # Majority of mistakes in opening — real theory/positional gap
    PIECE_GIVEAWAY = "PIECE_GIVEAWAY"          # 1–3 single-move blunders hung material
    REPEATED_BLUNDERS = "REPEATED_BLUNDERS"    # 4+ blunders — pattern of one-move blindness
    SCATTERED_MISTAKES = "SCATTERED_MISTAKES"  # Mistakes distributed across phases — named by recurring gap
    TACTICAL_MISS = "TACTICAL_MISS"            # Missed a tactic, moderate cp_loss
    TIME_COLLAPSE = "TIME_COLLAPSE"            # Multiple blunders clustered in final quarter
    WON_CLEAN = "WON_CLEAN"                    # Won without major mistakes
    WON_OPPONENT_BLUNDER = "WON_OPPONENT_BLUNDER"  # Won largely because opponent blundered
    DRAW = "DRAW"                              # Draw
    ABANDONED = "ABANDONED"                    # Game ended by disconnect/abandon — not a coaching moment


# ─── SUMMARY COMPUTATION ─────────────────────────────────────────

def compute_game_summary(
    move_evaluations: List[Dict],
    game_result: str,
    user_color: str,
    opening_name: str = "",
    termination: str = "",
) -> Dict:
    """
    Translate Stockfish's facts into a coach verdict.

    Pipeline:
      1. _extract_facts — read move_evaluations in one pass. All facts
         (user_moves, blunders, mate-info, eval curve, opponent behavior,
         decisive-moment) come from Stockfish + the game-level termination.
      2. dispatch by result (win / loss / draw).
      3. each dispatch runs a decision tree on the facts and fills a
         template sentence with real numbers and move names.

    No heuristic proxies, no fabricated claims. If the data doesn't support
    a claim, we don't make it.

    Returns: { diagnosis, root_cause, critical_move, context[], coach_note }
    """
    if not move_evaluations:
        return _build_summary("UNKNOWN", "No move data available", "", None, [], "")

    profile = _extract_facts(move_evaluations, user_color)
    if not profile["user_moves"]:
        return _build_summary("UNKNOWN", "No user moves found", "", None, [], "")

    user_is_white = user_color == "white"
    user_won = (game_result == "1-0" and user_is_white) or (game_result == "0-1" and not user_is_white)
    is_draw = "1/2" in game_result

    if is_draw:
        return _summarize_draw(profile)
    if user_won:
        return _summarize_win(profile)
    return _summarize_loss(profile, opening_name, termination)


def _extract_facts(move_evaluations: List[Dict], user_color: str) -> Dict:
    """
    One pass over move_evaluations → a fact-rich profile.

    Array shape isn't consistent across the DB (some interleaved, some
    user-only), so we identify user moves by FEN active-color rather than
    index parity. Evals are stored from White's POV (Stockfish convention);
    we flip the sign for black users once here so every downstream check
    reads in the user's POV.
    """
    user_is_white = user_color == "white"
    sign = 1 if user_is_white else -1

    user_moves: List[Dict] = []
    opponent_moves: List[Dict] = []
    for i, m in enumerate(move_evaluations):
        fen = m.get("fen_before") or ""
        parts = fen.split(" ")
        side_to_move = parts[1] if len(parts) > 1 else ""
        if side_to_move in ("w", "b"):
            is_user_move = (side_to_move == "w") == user_is_white
        else:
            is_user_move = (i % 2 == 0) == user_is_white

        cp_loss = m.get("cp_loss", 0) or 0
        move_number = m.get("move_number") or ((i // 2) + 1)
        san = m.get("san", m.get("move", "?"))

        if not is_user_move:
            opponent_moves.append({
                "index": i,
                "move_number": move_number,
                "san": san,
                "cp_loss": cp_loss,
            })
            continue

        raw_before = m.get("eval_before", 0) or 0
        raw_after = m.get("eval_after", 0) or 0
        best_move = m.get("best_move", "")

        # Mate info is stored from White's POV (+N = white mates in N, -N = black mates in N).
        # From the user's POV, a negative number means the opponent will mate the user.
        mate_info = m.get("mate_info") or {}
        mate_after_raw = mate_info.get("after") if isinstance(mate_info, dict) else None
        user_mate_after = (mate_after_raw * sign) if mate_after_raw is not None else None

        user_moves.append({
            "index": i,
            "move_number": move_number,
            "san": san,
            "cp_loss": cp_loss,
            "eval_before": raw_before * sign,
            "eval_after": raw_after * sign,
            "best_move": best_move,
            "phase": _phase_from_move_number(move_number),
            "user_mate_after": user_mate_after,
            # cognitive_gap tagged upstream by analysis_interpreter — needed
            # for the SCATTERED_MISTAKES theme detection below.
            "cognitive_gap": m.get("cognitive_gap") or "",
        })

    if not user_moves:
        return {"user_moves": []}

    blunders = [m for m in user_moves if m["cp_loss"] >= 200]
    mistakes = [m for m in user_moves if 100 <= m["cp_loss"] < 200]
    worst_move = max(user_moves, key=lambda m: m["cp_loss"])
    peak_user_eval = max((m["eval_before"] for m in user_moves), default=0)
    total_cp_loss = sum(m["cp_loss"] for m in user_moves)
    total_user_moves = len(user_moves)

    # Real short mate: the engine reports mate_info.after with the opponent
    # mating within 5 moves (from user's POV, user_mate_after is in [-5, -1]).
    # This is the ONLY signal for MATE_BLIND — we do not use cp_loss >= 5000
    # any more because that also catches long mate-in-20 drops which aren't
    # "missed an immediate mate".
    short_mate_moves = [
        m for m in user_moves
        if m["user_mate_after"] is not None and -5 <= m["user_mate_after"] < 0
    ]

    # THROW: user's eval peaked at +3.0 or better, then a blunder dropped
    # them from winning (eval_before >= +2.0) to equal-or-losing AND the
    # user NEVER came back above +2.0 afterwards. If they recovered, this
    # wasn't a true throw — it was an oscillating game and the real story
    # is elsewhere (repeated blunders, time loss, etc.).
    threw_from_winning = False
    throw_move = None
    if peak_user_eval >= 300:
        for b in blunders:
            if b["eval_before"] >= 200 and b["eval_after"] < 100:
                later_user_moves = [m for m in user_moves if m["index"] > b["index"]]
                recovered = any(m["eval_before"] >= 200 for m in later_user_moves)
                if recovered:
                    continue  # not a real throw — user came back after this
                throw_move = b
                threw_from_winning = True
                break

    blunders_in_opening = [b for b in blunders if b["phase"] == "opening"]
    blunders_in_last_quarter = [
        b for b in blunders if b["move_number"] > total_user_moves * 0.75
    ]

    # Opponent behaviour — blunder + mistake counts. A "clean" opponent is
    # why a verdict says "you were outplayed" vs "both of you fumbled".
    opponent_blunders = [m for m in opponent_moves if m["cp_loss"] >= 200]
    opponent_mistakes = [m for m in opponent_moves if 100 <= m["cp_loss"] < 200]

    # Decisive moment: the EARLIEST user blunder after which the user's eval
    # never came back above -150 (half a pawn down). That's the point Stockfish
    # says the game was practically over — often far earlier than the last
    # blunder the player hit before resigning.
    decisive_blunder = None
    for b in blunders:
        if b["eval_after"] >= -150:
            continue  # this blunder didn't lock in a lost position
        later_user_moves = [m for m in user_moves if m["index"] > b["index"]]
        if not later_user_moves or all(m["eval_after"] < -150 for m in later_user_moves):
            decisive_blunder = b
            break

    # Did the opponent offer chances back AFTER the decisive moment?
    opponent_offered_chances = False
    if decisive_blunder and opponent_blunders:
        opponent_offered_chances = any(
            o["index"] > decisive_blunder["index"] for o in opponent_blunders
        )

    return {
        "user_moves": user_moves,
        "opponent_moves": opponent_moves,
        "blunders": blunders,
        "mistakes": mistakes,
        "worst_move": worst_move,
        "peak_user_eval": peak_user_eval,
        "total_cp_loss": total_cp_loss,
        "total_user_moves": total_user_moves,
        "short_mate_moves": short_mate_moves,
        "threw_from_winning": threw_from_winning,
        "throw_move": throw_move,
        "blunders_in_opening": blunders_in_opening,
        "blunders_in_last_quarter": blunders_in_last_quarter,
        "opponent_blunders": opponent_blunders,
        "opponent_mistakes": opponent_mistakes,
        "decisive_blunder": decisive_blunder,
        "opponent_offered_chances": opponent_offered_chances,
    }


def _describe_termination(termination: str, total_user_moves: int) -> str:
    """Open the verdict with HOW the game ended, in coach voice.

    `termination` comes from the games collection and is typically one of:
      checkmate / resignation / timeout / abandonment / stalemate / draw_agreed
    (both chess.com and lichess normalise to similar keywords). Unknown
    values fall back to a neutral opener so we don't fabricate.
    """
    t = (termination or "").lower()
    if "mate" in t and "stale" not in t:
        return f"Checkmated on move {total_user_moves}."
    if "resign" in t:
        return f"You resigned on move {total_user_moves}."
    if "time" in t and "insufficient" not in t:
        return f"Lost on time on move {total_user_moves}."
    if "abandon" in t:
        return f"Abandoned on move {total_user_moves}."
    return "Lost this one."


def _describe_opponent(profile: Dict) -> str:
    """One sentence about opponent behaviour — did they hand you chances back?

    Key question: was this clearly outplayed, or mutual fumbling?
    """
    opp_blunders = profile["opponent_blunders"]
    opp_mistakes = profile["opponent_mistakes"]
    offered_chances = profile["opponent_offered_chances"]

    if not opp_blunders and not opp_mistakes:
        return "Your opponent played clean — no mistakes to punish."
    if offered_chances:
        return f"Your opponent had {len(opp_blunders)} blunder{'s' if len(opp_blunders) != 1 else ''} after the game tilted — chances you didn't take."
    if opp_blunders:
        return f"Your opponent had {len(opp_blunders)} blunder{'s' if len(opp_blunders) != 1 else ''} earlier, but didn't give you anything back once you tilted."
    return "Your opponent played cleanly once the game turned."


def _describe_decisive_moment(profile: Dict) -> str:
    """Call out the moment the game was really lost — often earlier than the last blunder."""
    decisive = profile["decisive_blunder"]
    if not decisive:
        return ""
    worst = profile["worst_move"]
    # Only surface this as a standalone sentence when it's meaningfully
    # earlier than the player's worst move — otherwise it's redundant.
    if decisive["move_number"] >= worst["move_number"] - 2:
        return ""
    hung = _infer_hung_piece(decisive.get("san", ""), decisive.get("best_move", ""), decisive.get("cp_loss", 0))
    if hung not in ("material", ""):
        return f"The game was really decided at move {decisive['move_number']}, when {decisive['san']} hung {hung}."
    return f"The game was really decided at move {decisive['move_number']}, when {decisive['san']} tilted the eval past recovery."


def _summarize_loss(profile: Dict, opening_name: str, termination: str) -> Dict:
    """
    Decision tree on extracted facts. Each diagnosis returns:
      - headline (root_cause): ONE short, coach-voice sentence. The thing the
        user remembers. No engine numbers, no termination, no opponent.
      - subline: ONE supporting sentence with the specific move.
      - context[]: the detail panel — termination, opponent behavior, decisive
        moment, best move, etc. Surfaced when user expands.
    """
    blunders = profile["blunders"]
    mistakes = profile["mistakes"]
    worst = profile["worst_move"]
    short_mate_moves = profile["short_mate_moves"]
    total_moves = profile["total_user_moves"]

    # These are facts the user might want — but they go into context, not
    # the verdict. The verdict stays focused on the player's mistake.
    termination_clause = _describe_termination(termination, total_moves)
    opponent_clause = _describe_opponent(profile)
    decisive_clause = _describe_decisive_moment(profile)

    def _detail_context(extra: Optional[List[str]] = None) -> List[str]:
        """Compose the expandable detail context from side-facts."""
        ctx: List[str] = []
        if termination_clause:
            ctx.append(termination_clause)
        if decisive_clause:
            ctx.append(decisive_clause)
        if opponent_clause:
            ctx.append(opponent_clause)
        if extra:
            ctx.extend(extra)
        return ctx

    # 0a. Abandoned — game ended via disconnect, not over the board.
    # Don't moralize. The user wasn't there to play. Position state
    # (winning / losing) is informational, not a coaching verdict.
    # Routed ABOVE all position-based branches because termination
    # dominates here — same as timeout.
    if "abandon" in termination.lower():
        peak = profile["peak_user_eval"]
        headline = "Game abandoned."
        subline = "Likely a connection issue — not a coaching moment."
        extra: List[str] = []
        if peak >= 300:
            extra.append(f"You were ahead (+{peak / 100:.1f}) when it ended")
        elif peak <= -300:
            extra.append(f"You were behind ({peak / 100:.1f}) when it ended")
        return _build_summary(
            GameDiagnosis.ABANDONED,
            headline, subline, None,
            _detail_context(extra),
            ""
        )

    # 0. Time loss while winning — if the user had a real winning peak
    # (+3.0 or better) and the game ended on the clock, the lesson is
    # clock discipline, not "you let it slip". Routed ABOVE all the
    # position-based branches because termination dominates here.
    is_timeout = "time" in termination.lower() and "insufficient" not in termination.lower()
    if is_timeout and profile["peak_user_eval"] >= 300:
        peak = profile["peak_user_eval"]
        headline = "You had winning positions. Ran out the clock."
        subline = f"Peak advantage +{peak / 100:.1f}, but the clock beat the board."
        extra = [
            f"Peak advantage: +{peak / 100:.1f}",
            f"{len(blunders)} blunder{'s' if len(blunders) != 1 else ''} across {total_moves} moves",
        ]
        return _build_summary(
            GameDiagnosis.TIME_LOSS_WHILE_WINNING,
            headline, subline,
            worst if worst["cp_loss"] >= 150 else None,
            _detail_context(extra),
            "Clock discipline: in winning positions, play fast, simple moves. Save thinking time for critical choices."
        )

    # 1. Real short mate — engine confirms opponent had mate ≤ 5 moves.
    if short_mate_moves:
        m = short_mate_moves[0]
        mate_in = abs(m["user_mate_after"])
        headline = f"You walked into mate in {mate_in}."
        subline = f"Move {m['move_number']} {m['san']} allowed it."
        extra = []
        if m.get("best_move"):
            extra.append(f"{m['best_move']} would have defended")
        extra.append("King-safety habit, not a calculation skill")
        return _build_summary(
            GameDiagnosis.MATE_BLIND,
            headline, subline, m,
            _detail_context(extra),
            "Before every move: can I be mated? That one question catches most of these."
        )

    # 2. Threw a winning game — peak ≥ +3.0, one blunder from winning to losing.
    if profile["threw_from_winning"]:
        t = profile["throw_move"]
        peak = profile["peak_user_eval"]
        hung = _infer_hung_piece(t.get("san", ""), t.get("best_move", ""), t.get("cp_loss", 0))
        headline = "You were winning. You let it slip."
        if hung not in ("material", ""):
            subline = f"Move {t['move_number']} {t['san']} cost you {hung}."
        else:
            subline = f"Move {t['move_number']} {t['san']} gave it back."
        extra = [
            f"Peak advantage: +{peak / 100:.1f}",
            f"{t['cp_loss'] / 100:.1f} pawns of advantage given up on that move",
        ]
        if t.get("best_move"):
            extra.append(f"{t['best_move']} would have held the win")
        return _build_summary(
            GameDiagnosis.THROW,
            headline, subline, t,
            _detail_context(extra),
            "Winning positions need the same focus as losing ones. Check threats every move."
        )

    # 3. Repeated blunders — 4+ single-move errors. The pattern IS the story.
    if len(blunders) >= 4:
        hung = _infer_hung_piece(worst.get("san", ""), worst.get("best_move", ""), worst.get("cp_loss", 0))
        headline = f"{len(blunders)} single-move blunders in one game."
        if hung not in ("material", ""):
            subline = f"Worst was Move {worst['move_number']} {worst['san']} — hung {hung}."
        else:
            subline = f"Worst was Move {worst['move_number']} {worst['san']}."
        listing = ", ".join(f"Move {b['move_number']} {b['san']}" for b in blunders[:5])
        extra = [
            f"Blunders: {listing}" + (f" (+{len(blunders) - 5} more)" if len(blunders) > 5 else ""),
            f"Total material leaked: {sum(b['cp_loss'] for b in blunders) / 100:.1f} pawns worth",
            "Pattern: piece safety — the habit, not the calculation",
        ]
        return _build_summary(
            GameDiagnosis.REPEATED_BLUNDERS,
            headline, subline, worst,
            _detail_context(extra),
            "Before every move: what's attacked? What happens if I move anyway? That one check fixes most of these."
        )

    # 4. Piece giveaway — 1 to 3 blunders, worst is a real material loss (≥ 300cp).
    if blunders and worst["cp_loss"] >= 300:
        hung = _infer_hung_piece(worst.get("san", ""), worst.get("best_move", ""), worst.get("cp_loss", 0))
        if hung not in ("material", ""):
            headline = f"You hung {hung}."
        else:
            headline = "Single-move blunder cost you material."
        subline = f"Move {worst['move_number']} {worst['san']}."
        extra = [
            f"{worst['cp_loss'] / 100:.1f} pawns of material gone on that move",
        ]
        if worst.get("best_move"):
            extra.append(f"{worst['best_move']} would have saved {hung}")
        extra.append(
            "Position was equal before this"
            if abs(worst.get("eval_before", 0)) < 100
            else "You were already under pressure"
        )
        return _build_summary(
            GameDiagnosis.PIECE_GIVEAWAY,
            headline, subline, worst,
            _detail_context(extra),
            "Before every move: what's attacked? What happens if I move anyway?"
        )

    # 5a. Scattered mistakes — 4+ errors distributed across phases, no single
    # phase dominates, and there's a recurring cognitive-gap theme. This is
    # the honest diagnosis when the game is long and the mistakes aren't
    # concentrated (e.g. a 47-move game with errors in opening + middle +
    # endgame, all tagged king_safety — the lesson is the theme, not a
    # single phase).
    all_errors = mistakes + blunders  # cp_loss >= 100
    if len(all_errors) >= 4:
        phase_counts = {"opening": 0, "middlegame": 0, "endgame": 0}
        for m in all_errors:
            p = m.get("phase", "middlegame")
            if p in phase_counts:
                phase_counts[p] += 1
        max_phase_share = max(phase_counts.values()) / len(all_errors)
        is_scattered = max_phase_share < 0.6  # no phase dominates

        # Find the recurring cognitive-gap theme across errors.
        gap_counts: Dict[str, int] = {}
        for m in all_errors:
            gap = m.get("cognitive_gap") or ""
            if gap:
                gap_counts[gap] = gap_counts.get(gap, 0) + 1
        top_gap = None
        top_gap_count = 0
        if gap_counts:
            top_gap = max(gap_counts, key=gap_counts.get)
            top_gap_count = gap_counts[top_gap]

        if is_scattered:
            theme_human = (top_gap or "").replace("_", " ")
            if top_gap and top_gap_count >= 3:
                headline = f"Mistakes scattered across the game — {theme_human} was the theme."
                subline = f"{top_gap_count} of your {len(all_errors)} mistakes were about {theme_human}."
            else:
                headline = "Mistakes scattered across the game."
                subline = (
                    f"{len(all_errors)} errors spread across opening, middle, and endgame — "
                    "no single moment decided it."
                )
            return _build_summary(
                GameDiagnosis.SCATTERED_MISTAKES,
                headline, subline, worst,
                _detail_context([
                    f"By phase: opening {phase_counts['opening']}, "
                    f"middlegame {phase_counts['middlegame']}, "
                    f"endgame {phase_counts['endgame']}",
                    f"Worst single move: Move {worst['move_number']} {worst['san']} "
                    f"({worst['cp_loss'] / 100:.1f} pawns)",
                ]),
                (
                    f"The habit to build: before every move, {_habit_for_gap(top_gap)}."
                    if top_gap else
                    "The pattern isn't a single moment — it's a habit check every move."
                )
            )

    # 5b. Opening collapse — tightened: require MAJORITY of mistakes to be
    # in the opening. Previously fired when just the first blunder was in
    # the opening, which mis-narrated games where errors were actually
    # scattered across phases.
    opening_errors = [m for m in all_errors if m.get("phase") == "opening"]
    opening_dominates = (
        len(all_errors) > 0 and len(opening_errors) / len(all_errors) >= 0.6
    )
    if opening_dominates and profile["blunders_in_opening"] and blunders and blunders[0]["phase"] == "opening":
        first = profile["blunders_in_opening"][0]
        headline = "Your opening broke."
        subline = f"Move {first['move_number']} {first['san']} was the first critical error."
        opening_tail = f" (in your {opening_name})" if opening_name else ""
        return _build_summary(
            GameDiagnosis.OPENING_COLLAPSE,
            headline, subline, first,
            _detail_context([
                f"Opening phase lost {sum(m['cp_loss'] for m in profile['blunders_in_opening'])} centipawns{opening_tail}",
                f"{len(opening_errors)} of {len(all_errors)} mistakes were in the opening",
                "You were already struggling before the middlegame started",
            ]),
            "This opening needs study. Know the key ideas, not just the moves."
        )

    # 6. Time collapse — 2+ blunders clustered in the final quarter.
    if len(profile["blunders_in_last_quarter"]) >= 2:
        late = profile["blunders_in_last_quarter"]
        headline = "Late-game collapse."
        subline = f"{len(late)} blunders in the final phase."
        listing = ", ".join(f"Move {b['move_number']} {b['san']}" for b in late[:4])
        return _build_summary(
            GameDiagnosis.TIME_COLLAPSE,
            headline, subline, worst,
            _detail_context([
                f"Late blunders: {listing}",
                "Earlier play was decent — time/energy ran out, not ideas",
                "Time management is a skill, not luck",
            ]),
            "Spend time earlier on critical positions. Save the clock for when it matters."
        )

    # 7. Slow bleed — no blunders at all, just accumulated mistakes.
    if not blunders:
        headline = "Outplayed — no single blunder."
        subline = (
            f"{len(mistakes)} small mistake"
            f"{'s' if len(mistakes) != 1 else ''} adding up to "
            f"{profile['total_cp_loss'] / 100:.1f} pawns."
        )
        return _build_summary(
            GameDiagnosis.SLOW_BLEED,
            headline, subline,
            worst if worst["cp_loss"] > 50 else None,
            _detail_context([
                f"Total centipawn loss: {profile['total_cp_loss']}",
                f"Worst single move lost only {worst['cp_loss']} centipawns",
            ]),
            "This is the hardest loss type to learn from. Focus on plans, not moves."
        )

    # 8. Default — one tactical miss, moderate cp_loss (200-299).
    headline = "Missed a tactic."
    subline = f"Move {worst['move_number']} {worst['san']} cost {worst['cp_loss'] / 100:.1f} pawns."
    extra = []
    if worst.get("best_move"):
        extra.append(f"{worst['best_move']} was the right move")
    extra.append("The position required calculation, and the calculation fell short")
    return _build_summary(
        GameDiagnosis.TACTICAL_MISS,
        headline, subline, worst,
        _detail_context(extra),
        "Tactics come from calculation. Slow down on critical moves."
    )


def _summarize_draw(profile: Dict) -> Dict:
    user_moves = profile["user_moves"]
    worst = profile["worst_move"]
    peak = profile["peak_user_eval"]
    if peak >= 200:
        headline = "A draw you could have won."
        subline = f"Peak advantage +{peak / 100:.1f}."
    else:
        headline = "Drawn."
        subline = ""
    return _build_summary(
        GameDiagnosis.DRAW,
        headline, subline,
        worst if worst["cp_loss"] > 100 else None,
        _draw_context(user_moves, peak),
        "Draws happen. Was there a moment you could have pushed for more?"
    )


def _summarize_win(profile: Dict) -> Dict:
    """Win classification — clean vs opponent-blunder win."""
    user_moves = profile["user_moves"]
    blunders = profile["blunders"]
    total_cp_loss = profile["total_cp_loss"]
    worst = profile["worst_move"]
    opp_blunders = len(profile["opponent_blunders"])

    if not blunders:
        return _build_summary(
            GameDiagnosis.WON_CLEAN,
            "Clean win.",
            "You played accurately throughout.",
            None,
            _win_context(user_moves, total_cp_loss, opp_blunders),
            "Clean wins build confidence. Keep this level up."
        )
    return _build_summary(
        GameDiagnosis.WON_OPPONENT_BLUNDER,
        "Messy win.",
        f"You had {len(blunders)} blunder{'s' if len(blunders) > 1 else ''} too — your opponent's were bigger.",
        worst,
        _win_context(user_moves, total_cp_loss, opp_blunders),
        "A win is a win, but those blunders will cost you against stronger opponents."
    )


def _habit_for_gap(gap: str) -> str:
    """Map a cognitive_gap tag to the habit to build, in coach voice.

    Used by SCATTERED_MISTAKES to name the habit that would prevent the
    recurring theme. Falls back to a generic check if the gap is unknown.
    """
    habits = {
        "piece_safety":       "scan your pieces — is anything undefended",
        "king_safety":        "check your king's safety",
        "ignore_threat":      "name what your opponent just threatened",
        "calculation_depth":  "picture their best reply before committing",
        "missed_tactic":      "scan checks, captures, threats",
        "tactical_oversight": "pause for their sharpest response",
        "pawn_structure":     "ask what square this pawn move weakens",
        "piece_activity":     "look for moves that activate sleeping pieces",
        "opening_knowledge":  "know the key ideas, not just the moves",
        "endgame_technique":  "active king, passed pawns, clean decisions",
    }
    return habits.get(gap, "pause and ask what the position needs")


def _phase_from_move_number(move_number: int) -> str:
    """Phase based on the move number, not on array index.

    Safer than `_get_phase(i)` because array shape varies across the DB
    (interleaved vs user-only), which makes an index-based cutoff wrong
    for half the records.
    """
    if move_number <= 10:
        return "opening"
    if move_number <= 25:
        return "middlegame"
    return "endgame"


# ─── HABITS COMPUTATION ──────────────────────────────────────────

def compute_game_habits(
    move_evaluations: List[Dict],
    user_color: str,
    habits_report: Optional[Dict] = None,
    game_summary: Optional[Dict] = None
) -> Dict:
    """
    Compute pass/fail checklist for behavioral habits.
    Returns: { habits: [{ name, passed, evidence, impact }], focus_habit }
    """
    user_is_white = user_color == "white"

    # NOTE: move_evaluations from stockfish_service already contains ONLY user moves
    # (filtered by user_color during analysis). No even/odd filtering needed.
    user_moves = []
    for i, m in enumerate(move_evaluations):
        user_moves.append({
            "index": i,
            "move_number": m.get("move_number", i + 1),
            "san": m.get("san", m.get("move", "?")),
            "cp_loss": m.get("cp_loss", 0),
            "eval_before": m.get("eval_before", 0),
            "eval_after": m.get("eval_after", 0),
            "best_move": m.get("best_move", ""),
            "phase": _get_phase(m.get("move_number", i + 1) * 2),
            "time_spent": m.get("time_spent", 0),
        })

    habits = []

    # 1. Checked opponent threats
    missed_mate = any(m["cp_loss"] >= 5000 for m in user_moves)
    missed_tactics = [m for m in user_moves if m["cp_loss"] >= 200]
    if missed_mate:
        evidence = f"Move {next(m['move_number'] for m in user_moves if m['cp_loss'] >= 5000)}: you missed a checkmate threat and lost immediately."
        impact = "This lost the game on the spot."
    elif missed_tactics:
        worst = max(missed_tactics, key=lambda m: m["cp_loss"])
        evidence = f"Move {worst['move_number']}: you played {worst['san']} but missed {worst['best_move']}. That one mistake cost you about {_cp_to_pieces(worst['cp_loss'])}."
        impact = f"You missed {len(missed_tactics)} threat{'s' if len(missed_tactics) > 1 else ''}. This is the #1 thing to fix."
    else:
        evidence = "You checked what your opponent was doing before every move. No threats missed."
        impact = None
    habits.append({
        "name": "Checked opponent threats",
        "passed": not missed_mate and len(missed_tactics) == 0,
        "evidence": evidence,
        "impact": impact,
    })

    # 2. Castled early (before move 12)
    # NOTE: move_evaluations contains ONLY user moves (stockfish_service filters by user_color)
    # So we scan them directly — no even/odd filtering needed
    user_move_sans = [m.get("san", m.get("move", "")) for m in move_evaluations]
    castled = any("O-O" in m for m in user_move_sans[:12])
    castle_move = None
    for idx, m in enumerate(user_move_sans[:12]):
        if "O-O" in m:
            # Use the actual chess move number from the evaluation data
            castle_move = move_evaluations[idx].get("move_number", idx + 1) if idx < len(move_evaluations) else idx + 1
            break
    if castled:
        evidence = f"You castled on move {castle_move}. King is safe."
        impact = None
    else:
        evidence = "You didn't castle in the first 12 moves. Your king was exposed the whole game."
        impact = "An exposed king is the #1 reason beginners lose games they're winning."
    habits.append({
        "name": "Castled early",
        "passed": castled,
        "evidence": evidence,
        "impact": impact,
    })

    # 3. Developed pieces (didn't move same piece twice in opening)
    opening_user_moves = [m for m in user_moves if m["phase"] == "opening"]
    pieces_moved = {}
    repeated_piece = None
    for m in opening_user_moves:
        san = m["san"]
        if san.startswith("O") or san[0].islower():
            continue  # Castle or pawn
        piece_letter = san[0]  # N, B, R, Q, K
        pieces_moved[piece_letter] = pieces_moved.get(piece_letter, 0) + 1
        if pieces_moved[piece_letter] >= 3 and not repeated_piece:
            repeated_piece = {"N": "knight", "B": "bishop", "R": "rook", "Q": "queen", "K": "king"}.get(piece_letter, "piece")
    
    unique_pieces = len([p for p in pieces_moved if pieces_moved[p] >= 1])
    if repeated_piece:
        evidence = f"You moved your {repeated_piece} 3+ times in the opening instead of developing other pieces."
        impact = "Every move you spend on one piece is a move your other pieces aren't developing."
    elif unique_pieces >= 3:
        evidence = f"You developed {unique_pieces} different pieces in the opening. Good variety."
        impact = None
    else:
        evidence = "Your opening development was limited. Try to get knights and bishops out early."
        impact = "Undeveloped pieces can't help you attack or defend."
    habits.append({
        "name": "Developed pieces before attacking",
        "passed": repeated_piece is None and unique_pieces >= 2,
        "evidence": evidence,
        "impact": impact,
    })

    # 4. Followed opening principles
    opening_blunders = [m for m in opening_user_moves if m["cp_loss"] >= 100]
    if opening_blunders:
        worst = max(opening_blunders, key=lambda m: m["cp_loss"])
        evidence = f"Move {worst['move_number']}: {worst['san']} was a mistake. {worst['best_move']} was better. You lost about {_cp_to_pieces(worst['cp_loss'])} of advantage."
        impact = f"You made {len(opening_blunders)} opening mistake{'s' if len(opening_blunders) > 1 else ''}. Starting behind makes the whole game harder."
    else:
        evidence = "No mistakes in the opening. You came out of the opening in good shape."
        impact = None
    habits.append({
        "name": "Clean opening play",
        "passed": len(opening_blunders) == 0,
        "evidence": evidence,
        "impact": impact,
    })

    # 5. No hanging pieces
    hanging = [m for m in user_moves if 250 <= m["cp_loss"] < 5000 and m["phase"] != "opening"]
    if hanging:
        worst = max(hanging, key=lambda m: m["cp_loss"])
        evidence = f"Move {worst['move_number']}: you played {worst['san']} and left material undefended. Lost about {_cp_to_pieces(worst['cp_loss'])}."
        impact = f"Hung material {len(hanging)} time{'s' if len(hanging) > 1 else ''}. Before every move: is my piece safe where it's going?"
    else:
        evidence = "You kept all your pieces safe. No material left hanging."
        impact = None
    habits.append({
        "name": "Kept pieces safe",
        "passed": len(hanging) == 0,
        "evidence": evidence,
        "impact": impact,
    })

    # 6. Played with a plan
    aimless_count = 0
    aimless_stretch_start = None
    for j in range(1, len(user_moves)):
        cp_j = user_moves[j]["cp_loss"] if user_moves[j]["cp_loss"] < 5000 else 0
        cp_prev = user_moves[j-1]["cp_loss"] if user_moves[j-1]["cp_loss"] < 5000 else 0
        if cp_j >= 50 and cp_prev >= 50:
            aimless_count += 1
            if not aimless_stretch_start:
                aimless_stretch_start = user_moves[j-1]["move_number"]
    if aimless_count > 2:
        evidence = f"From move {aimless_stretch_start}, you made {aimless_count} small mistakes in a row. That usually means you didn't have a clear plan."
        impact = "Without a plan, you just react to what the opponent does. Ask: what are my next 3 moves?"
    else:
        evidence = "Your moves had direction. You weren't just shuffling pieces around."
        impact = None
    habits.append({
        "name": "Played with a plan",
        "passed": aimless_count <= 2,
        "evidence": evidence,
        "impact": impact,
    })

    # 7. Focus in critical moments
    critical_moments = [m for m in user_moves if abs(m["eval_before"]) >= 200]
    critical_blunders = [m for m in critical_moments if 100 <= m["cp_loss"] < 5000]
    if len(critical_blunders) > 1:
        evidence = f"You had {len(critical_moments)} critical positions and blundered in {len(critical_blunders)} of them. When the game is on the line, slow down."
        impact = "Critical moments decide the game. One extra second of thought can save everything."
    elif len(critical_blunders) == 1:
        cb = critical_blunders[0]
        evidence = f"Move {cb['move_number']}: one slip in a critical position. {cb['san']} instead of {cb['best_move']}."
        impact = "One mistake in a tense moment. Close to passing."
    else:
        if critical_moments:
            evidence = f"You had {len(critical_moments)} critical positions and handled them all. Strong nerves."
        else:
            evidence = "No critical moments in this game. Smooth sailing."
        impact = None
    habits.append({
        "name": "Stayed focused under pressure",
        "passed": len(critical_blunders) <= 1,
        "evidence": evidence,
        "impact": impact,
    })

    # 8. Endgame technique
    endgame_moves = [m for m in user_moves if m["phase"] == "endgame"]
    if endgame_moves:
        eg_blunders = [m for m in endgame_moves if m["cp_loss"] >= 100]
        if eg_blunders:
            worst = max(eg_blunders, key=lambda m: m["cp_loss"])
            evidence = f"Move {worst['move_number']}: endgame mistake. {worst['san']} instead of {worst['best_move']}. Endgames require patience."
            impact = f"{len(eg_blunders)} endgame error{'s' if len(eg_blunders) > 1 else ''}. In endgames: activate your king and push passed pawns."
        else:
            evidence = "Clean endgame play. You converted the position correctly."
            impact = None
        habits.append({
            "name": "Endgame technique",
            "passed": len(eg_blunders) == 0,
            "evidence": evidence,
            "impact": impact,
        })

    # Determine FOCUS HABIT
    failed_habits = [h for h in habits if not h["passed"]]
    focus_habit = None
    if failed_habits:
        priority_order = [
            "Checked opponent threats",
            "Castled early",
            "Kept pieces safe",
            "Stayed focused under pressure",
            "Clean opening play",
            "Developed pieces before attacking",
            "Played with a plan",
            "Endgame technique",
        ]
        for name in priority_order:
            focus = next((h for h in failed_habits if h["name"] == name), None)
            if focus:
                focus_habit = focus
                break
        if not focus_habit:
            focus_habit = failed_habits[0]

    return {
        "habits": habits,
        "focus_habit": focus_habit,
        "passed_count": len([h for h in habits if h["passed"]]),
        "total_count": len(habits),
    }


# ─── MEMORY COMPUTATION (Identity + Impact) ──────────────────────

async def compute_game_memory(
    db,
    user_id: str,
    game_summary: Dict,
    user_rating: int = 0,
) -> Dict:
    """
    Memory = Identity Snapshot + Impact Projection.
    
    Identity: Who you are as a player, how this game confirms/changes that.
    Impact: What fixing your #1 weakness would do to your rating.
    """

    # Pull player identity data
    identity_doc = await db.player_identity.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )

    # Pull recent game analysis for pattern counting
    recent_analyses = []
    cursor = db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "stockfish_analysis": 1, "game_id": 1, "habits_report": 1}
    ).sort("created_at", -1).limit(30)
    async for doc in cursor:
        recent_analyses.append(doc)

    # Count pattern occurrences across recent games
    diagnosis_type = game_summary.get("diagnosis", "UNKNOWN")
    pattern_counts = _count_patterns(recent_analyses, diagnosis_type)
    total_games = len(recent_analyses) or 1

    # ─── YOUR CHESS DNA ─────────────────────────────────
    # "Before this game" + "After this game" narrative
    style = "developing"
    weakest_area = "general play"
    strength = "determination"

    if identity_doc:
        style = identity_doc.get("play_style", identity_doc.get("style_profile", {}).get("primary_style", "developing"))
        # Find weakest area from blunder taxonomy
        taxonomy = identity_doc.get("blunder_taxonomy", {})
        if isinstance(taxonomy, dict):
            by_type = taxonomy.get("by_type", taxonomy)
            if by_type and isinstance(by_type, dict):
                worst_type = max(by_type.items(), key=lambda x: x[1], default=("general", 0))
                weakest_area = _readable_blunder_type(worst_type[0])

        # Find strength
        strengths = identity_doc.get("strengths", [])
        if strengths:
            strength = strengths[0] if isinstance(strengths[0], str) else strengths[0].get("name", "consistency")

    # Build "before/after this game" identity lines
    before_line, after_line, archetype = _build_chess_dna(
        diagnosis_type, pattern_counts, total_games, style, weakest_area, strength
    )

    # ─── IF YOU FIXED THIS ONE THING ──────────────────────
    games_lost_to_pattern = pattern_counts.get(diagnosis_type, 0)
    pattern_rate = games_lost_to_pattern / total_games if total_games > 0 else 0

    # Rating impact per pattern type
    estimated_rating_gain = 0
    if diagnosis_type in (GameDiagnosis.THROW, GameDiagnosis.MATE_BLIND):
        estimated_rating_gain = min(games_lost_to_pattern * 20, 200)
    elif diagnosis_type in (GameDiagnosis.PIECE_GIVEAWAY, GameDiagnosis.TACTICAL_MISS):
        estimated_rating_gain = min(games_lost_to_pattern * 15, 150)
    elif diagnosis_type in (GameDiagnosis.OPENING_COLLAPSE,):
        estimated_rating_gain = min(games_lost_to_pattern * 12, 120)
    elif diagnosis_type == GameDiagnosis.SLOW_BLEED:
        estimated_rating_gain = min(games_lost_to_pattern * 8, 80)
    elif diagnosis_type == GameDiagnosis.TIME_COLLAPSE:
        estimated_rating_gain = min(games_lost_to_pattern * 18, 180)

    severity = "CRITICAL" if pattern_rate > 0.3 else "HIGH" if pattern_rate > 0.15 else "MEDIUM" if pattern_rate > 0.05 else "LOW"

    # Build the 3-line punch
    fix_habit = _diagnosis_to_habit_fix(diagnosis_type)
    stat_line = f"You've had {games_lost_to_pattern} games with {_readable_diagnosis(diagnosis_type).lower()} in your last {total_games} games"
    fix_line = f"If you {fix_habit}, your rating would be ~{estimated_rating_gain} points higher" if estimated_rating_gain > 0 else ""
    diff_line = ""
    if user_rating and estimated_rating_gain > 0:
        diff_line = f"That's the difference between {user_rating} and {user_rating + estimated_rating_gain}"

    impact = {
        "pattern_name": _readable_diagnosis(diagnosis_type),
        "occurrences": games_lost_to_pattern,
        "out_of_games": total_games,
        "rate_percent": round(pattern_rate * 100),
        "estimated_rating_gain": estimated_rating_gain,
        "current_rating": user_rating,
        "projected_rating": user_rating + estimated_rating_gain if user_rating else None,
        "severity": severity,
        "stat_line": stat_line,
        "fix_line": fix_line,
        "diff_line": diff_line,
        "one_liner": _impact_one_liner(diagnosis_type, games_lost_to_pattern, total_games, estimated_rating_gain, user_rating),
    }

    return {
        "identity": {
            "style": style,
            "strength": strength,
            "weakest_area": weakest_area,
            "before_line": before_line,
            "after_line": after_line,
            "archetype": archetype,
            "this_game_confirms": _this_game_confirms(diagnosis_type, pattern_counts),
        },
        "impact": impact,
    }


# ─── HELPERS ──────────────────────────────────────────────────────


def _cp_to_pieces(cp: int) -> str:
    """Convert centipawns to human-readable piece equivalent."""
    if cp >= 900:
        return "a queen"
    elif cp >= 500:
        return "a rook"
    elif cp >= 300:
        return "a piece (knight or bishop)"
    elif cp >= 100:
        return "a pawn"
    else:
        return "a small advantage"


def _infer_hung_piece(played_san: str, best_san: str, cp_loss: int) -> str:
    """
    Name what the user just lost. Used to turn generic "you gave away material"
    into specific "you hung your queen."

    Strategy: when the best move and the played move are DIFFERENT piece types,
    the best move almost always saves the piece that was under attack — so the
    first char of the best-move SAN tells us which piece was meant to be saved.
    When the pieces match (or no best_move), fall back on cp_loss magnitude.
    """
    def _piece_letter(san: str) -> str:
        if not san:
            return ""
        s = san.lstrip("O").lstrip("-")  # strip castling noise
        if not s:
            return ""
        return s[0] if s[0].isupper() else "P"

    played_piece = _piece_letter(played_san)
    best_piece = _piece_letter(best_san)
    names = {
        "Q": "your queen",
        "R": "a rook",
        "B": "a bishop",
        "N": "a knight",
        "P": "a pawn",
    }

    # If the best move is a CAPTURE (contains 'x'), the user missed an
    # opportunity to take opponent material — they did NOT hang a piece of
    # their own. Returning a piece name here would mislead: e.g. best=Nxc3
    # vs played=Bd6 would say "cost you a knight" when the user actually
    # missed capturing opponent's knight. Return empty so callers fall
    # back to the "gave it back" phrasing instead of "cost you X".
    best_is_capture = "x" in (best_san or "")
    played_is_capture = "x" in (played_san or "")
    if best_is_capture and not played_is_capture:
        return ""

    if best_piece and played_piece and best_piece != played_piece:
        return names.get(best_piece, "material")

    # Fallback — cp_loss bands. A hung queen usually shows ~700+; a minor
    # piece with some positional compensation can land around 300-500.
    if cp_loss >= 700:
        return "your queen"
    if cp_loss >= 400:
        return "a major piece"
    if cp_loss >= 250:
        return "a piece"
    return "material"


def _get_phase(move_index: int) -> str:
    half_move = move_index
    if half_move < 20:
        return "opening"
    elif half_move < 50:
        return "middlegame"
    return "endgame"


def _build_summary(diagnosis, headline, subline, critical_move, context, coach_note):
    """
    Return shape:
      diagnosis      — internal enum (not rendered to users)
      root_cause     — the HEADLINE sentence. This is the coach's opening line:
                       one short, emotional, memorable truth. Rendered as
                       primary everywhere (game list, Coach's Pick, /game/:id).
      subline        — the SECONDARY line. Specific move detail. Rendered under
                       the headline on Coach's Pick / game-review pages.
      context[]      — detail-panel lines (termination, opponent behavior, etc).
                       Only shown when user expands "see details".
      critical_move  — structured data for the clickable move ref.
      coach_note     — one-liner takeaway below the context.

    The root_cause / subline split enforces the "one thing first, details on
    demand" rule — user remembers the headline, the subline reinforces it,
    the context is there for the curious.
    """
    result = {
        "diagnosis": diagnosis,
        "root_cause": headline,
        "subline": subline or "",
        "context": context if isinstance(context, list) else [context],
        "coach_note": coach_note,
    }
    if critical_move:
        result["critical_move"] = {
            "move_number": critical_move["move_number"],
            "san": critical_move["san"],
            "cp_loss": critical_move["cp_loss"],
            "eval_before": critical_move.get("eval_before", 0),
            "eval_after": critical_move.get("eval_after", 0),
            "best_move": critical_move.get("best_move", ""),
            "phase": critical_move.get("phase", ""),
        }
    return result


def _draw_context(user_moves, max_advantage):
    ctx = []
    if max_advantage > 200:
        ctx.append(f"You had up to +{max_advantage / 100:.1f} advantage but couldn't convert")
    blunders = [m for m in user_moves if m["cp_loss"] >= 200]
    if blunders:
        ctx.append(f"{len(blunders)} blunder{'s' if len(blunders) > 1 else ''} during the game")
    ctx.append(f"Total centipawn loss: {sum(m['cp_loss'] for m in user_moves)}")
    return ctx


def _win_context(user_moves, total_cp_loss, opp_blunders):
    ctx = []
    ctx.append(f"Your total inaccuracy: {total_cp_loss} centipawns")
    if opp_blunders:
        ctx.append(f"Opponent made {opp_blunders} blunder{'s' if opp_blunders > 1 else ''}")
    blunders = [m for m in user_moves if m["cp_loss"] >= 200]
    if blunders:
        ctx.append(f"You had {len(blunders)} blunder{'s' if len(blunders) > 1 else ''} yourself")
    return ctx


def _count_patterns(analyses: List[Dict], current_diagnosis: str) -> Dict:
    """Count how many recent games match each diagnosis pattern."""
    counts = {}
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        if not evals:
            continue

        # Quick diagnosis based on eval data
        max_loss = max((e.get("cp_loss", 0) for e in evals), default=0)
        has_mate_miss = max_loss >= 5000
        has_big_blunder = max_loss >= 200
        blunder_count = sum(1 for e in evals if e.get("cp_loss", 0) >= 200)

        if has_mate_miss:
            counts[GameDiagnosis.MATE_BLIND] = counts.get(GameDiagnosis.MATE_BLIND, 0) + 1
        elif has_big_blunder and blunder_count <= 2:
            counts[GameDiagnosis.PIECE_GIVEAWAY] = counts.get(GameDiagnosis.PIECE_GIVEAWAY, 0) + 1
            counts[GameDiagnosis.THROW] = counts.get(GameDiagnosis.THROW, 0) + 1
        elif not has_big_blunder and max_loss >= 50:
            counts[GameDiagnosis.SLOW_BLEED] = counts.get(GameDiagnosis.SLOW_BLEED, 0) + 1

    return counts


def _readable_diagnosis(diagnosis: str) -> str:
    return {
        GameDiagnosis.THROW: "Throwing winning positions",
        GameDiagnosis.MATE_BLIND: "Missing checkmate threats",
        GameDiagnosis.SLOW_BLEED: "Gradual positional loss",
        GameDiagnosis.OPENING_COLLAPSE: "Opening preparation failure",
        GameDiagnosis.PIECE_GIVEAWAY: "Leaving pieces hanging",
        GameDiagnosis.TACTICAL_MISS: "Missing tactics",
        GameDiagnosis.TIME_COLLAPSE: "Time pressure collapse",
        GameDiagnosis.WON_CLEAN: "Clean play",
        GameDiagnosis.WON_OPPONENT_BLUNDER: "Opponent error conversion",
    }.get(diagnosis, diagnosis)


def _readable_blunder_type(bt: str) -> str:
    return {
        "missed_fork": "missing forks",
        "missed_pin": "missing pins",
        "missed_checkmate": "missing checkmate",
        "hanging_piece": "leaving pieces hanging",
        "king_safety_neglect": "king safety",
        "winning_position_collapse": "throwing winning positions",
        "time_trouble_blunder": "time pressure mistakes",
        "impulse_move": "impulse moves",
    }.get(bt, bt.replace("_", " "))


def _build_chess_dna(diagnosis, pattern_counts, total_games, style, weakest_area, strength):
    """
    Build the "Before this game / After this game" Chess DNA narrative.
    Returns (before_line, after_line, archetype)
    """
    count = pattern_counts.get(diagnosis, 0)

    # Archetype: derived from dominant pattern
    archetype = _style_to_archetype(style, weakest_area, diagnosis, count, total_games)

    # "Before this game" — who you were coming in
    if style and style != "developing":
        style_label = style.replace("_", " ").title()
        if weakest_area and weakest_area != "general play":
            before_line = f"You were a {style_label.lower()} player who struggles with {weakest_area}"
        else:
            before_line = f"You were a {style_label.lower()} player with solid fundamentals"
    else:
        if weakest_area and weakest_area != "general play":
            before_line = f"You were a developing player with a recurring leak in {weakest_area}"
        else:
            before_line = "You were a developing player building your chess identity"

    # "After this game" — how this game changed things
    diag_label = _readable_diagnosis(diagnosis).lower()
    if diagnosis in (GameDiagnosis.WON_CLEAN,):
        after_line = "Solid performance. This is the player you want to be consistently."
    elif diagnosis in (GameDiagnosis.WON_OPPONENT_BLUNDER,):
        after_line = "You won, but the sloppiness is still there. Clean wins build identity — messy ones don't."
    elif count >= 5:
        after_line = f"+1 more game lost to {diag_label}. This is now your signature weakness."
    elif count >= 3:
        after_line = f"+1 more {diag_label}. This is becoming a pattern — {count + 1} times now."
    elif count >= 1:
        after_line = f"Another game with {diag_label}. It happened before — now it's happening again."
    else:
        after_line = f"First game lost to {diag_label}. One-off or emerging habit? Next games will tell."

    return before_line, after_line, archetype


def _style_to_archetype(style, weakest_area, diagnosis, count, total_games):
    """Determine player archetype label based on patterns."""
    # If dominant pattern is clear
    if count >= 5 and total_games > 0 and count / total_games > 0.2:
        return {
            GameDiagnosis.THROW: "The Thrower",
            GameDiagnosis.MATE_BLIND: "The Blind Spot",
            GameDiagnosis.SLOW_BLEED: "The Slow Leak",
            GameDiagnosis.OPENING_COLLAPSE: "The Opening Gambler",
            GameDiagnosis.PIECE_GIVEAWAY: "The Gift Giver",
            GameDiagnosis.TIME_COLLAPSE: "The Clock Fighter",
            GameDiagnosis.TACTICAL_MISS: "The Calculator (Broken)",
        }.get(diagnosis, style.replace("_", " ").title() if style else "Developing")

    # Otherwise use style
    return {
        "aggressive": "Attacker",
        "positional": "Strategist",
        "tactical": "Tactician",
        "defensive": "Fortress Builder",
        "universal": "All-Rounder",
    }.get(style, "Developing")


def _diagnosis_to_habit_fix(diagnosis):
    """Map diagnosis to the ONE habit that would fix it."""
    return {
        GameDiagnosis.THROW: "held focus in winning positions",
        GameDiagnosis.MATE_BLIND: "checked opponent threats before every move",
        GameDiagnosis.SLOW_BLEED: "played with a clear plan each move",
        GameDiagnosis.OPENING_COLLAPSE: "studied your opening repertoire",
        GameDiagnosis.PIECE_GIVEAWAY: "checked if your pieces are safe before moving",
        GameDiagnosis.TACTICAL_MISS: "spent 10 more seconds on critical moves",
        GameDiagnosis.TIME_COLLAPSE: "managed your clock better in the middlegame",
        GameDiagnosis.WON_CLEAN: "kept this level of focus consistently",
        GameDiagnosis.WON_OPPONENT_BLUNDER: "eliminated your own blunders",
        GameDiagnosis.DRAW: "pushed harder in equal positions",
    }.get(diagnosis, "fixed your most common mistake")


def _this_game_confirms(diagnosis, pattern_counts):
    count = pattern_counts.get(diagnosis, 0)
    if count >= 5:
        return f"This game confirms a recurring problem. {_readable_diagnosis(diagnosis)} is becoming your signature weakness."
    elif count >= 3:
        return f"This is a pattern now. You've done this {count} times."
    elif count >= 1:
        return "This has happened before. Watch for it becoming a habit."
    return "First occurrence. One-off or emerging pattern? Next few games will tell."


def _impact_one_liner(diagnosis, occurrences, total_games, rating_gain, current_rating):
    if rating_gain == 0:
        return "No significant rating impact from this pattern."
    if current_rating:
        return f"Fixing '{_readable_diagnosis(diagnosis).lower()}' could take you from {current_rating} to ~{current_rating + rating_gain}."
    return f"Fixing this one pattern could gain you ~{rating_gain} rating points."
