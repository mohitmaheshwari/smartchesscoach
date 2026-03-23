"""
Game Decryption Service v4
==========================

LLM-powered, thinking-simulator coaching.

Architecture:
1. Parse PGN → classify every move by eval_loss
2. Opening moves → JSON knowledge base (openings are constant structures)
3. Good moves (loss < 30cp) → short rule-based narrative
4. Mistakes/blunders (loss > 30cp) → batch to LLM with Master Coach Prompt
5. Store in DB → cache forever

Output: Single flowing narrative per move, not disconnected sections.

Key fields per move:
- narrative (THE HOOK — if user reads only this, they learn something)
- thinking_gap (THE MOAT — what question they didn't ask)
- position_breakdown, mistake_analysis, better_plan, principle, confidence
"""

import chess
import chess.pgn
import json
import os
import io
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

COACHING_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "coaching")


def load_json_safe(filepath: str) -> dict:
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {filepath}: {e}")
        return {}


_COACHING_CACHE = {}

def get_coaching_data(key: str) -> dict:
    global _COACHING_CACHE
    if key not in _COACHING_CACHE:
        filepath = os.path.join(COACHING_DATA_DIR, f"{key}.json")
        _COACHING_CACHE[key] = load_json_safe(filepath)
    return _COACHING_CACHE[key]


# ─── OPENING DETECTION ──────────────────────────────────────────────

def detect_opening_from_pgn(pgn: str) -> Tuple[Optional[str], Optional[str]]:
    opening_name = None
    eco_code = None
    eco_match = re.search(r'\[ECO\s+"([^"]+)"\]', pgn)
    if eco_match:
        eco_code = eco_match.group(1)
    opening_match = re.search(r'\[Opening\s+"([^"]+)"\]', pgn)
    if opening_match:
        opening_name = opening_match.group(1)
    if not opening_name:
        eco_url_match = re.search(r'\[ECOUrl\s+"[^"]*openings/([^"]+)"\]', pgn)
        if eco_url_match:
            opening_name = eco_url_match.group(1).replace("-", " ").title()
    return opening_name, eco_code


def get_opening_data(eco_code: Optional[str], opening_name: Optional[str]) -> dict:
    opening_plans = get_coaching_data("opening_plans")
    if not opening_plans:
        return {}

    if eco_code:
        eco_prefix = eco_code[:2] if len(eco_code) >= 2 else eco_code
        for key, data in opening_plans.items():
            if key.startswith("_"):
                continue
            prefixes = data.get("eco_prefix", [])
            if eco_code in prefixes or eco_prefix in [p[:2] for p in prefixes]:
                return data

    if opening_name:
        name_lower = opening_name.lower()
        for key, data in opening_plans.items():
            if key.startswith("_"):
                continue
            if key.replace("_", " ") in name_lower or data.get("name", "").lower() in name_lower:
                return data
        keywords = {
            "queens_indian": ["queen's indian", "queens indian"],
            "london_system": ["london"],
            "sicilian_najdorf": ["najdorf", "sicilian najdorf"],
            "italian_game": ["italian", "giuoco piano", "two knights"],
            "caro_kann": ["caro-kann", "caro kann"],
            "french_defense": ["french"],
            "kings_indian": ["king's indian", "kings indian"],
            "ruy_lopez": ["ruy lopez", "spanish", "morphy"]
        }
        for opening_key, kws in keywords.items():
            for kw in kws:
                if kw in name_lower and opening_key in opening_plans:
                    return opening_plans[opening_key]

    return opening_plans.get("default", {})


# ─── HELPERS ─────────────────────────────────────────────────────────

def detect_phase(board: chess.Board, move_number: int) -> str:
    piece_count = len(board.piece_map())
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    if move_number <= 10 and piece_count >= 28:
        return "opening"
    if move_number <= 15 and piece_count >= 24:
        return "opening"
    if queens == 0 or piece_count <= 12:
        return "endgame"
    if piece_count <= 18:
        return "endgame"
    return "middlegame"


def get_piece_name(piece: chess.Piece) -> str:
    names = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
             chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
    return names.get(piece.piece_type, "piece")


def classify_move(cp_loss: int) -> str:
    """Classify move severity for LLM routing."""
    if cp_loss < 30:
        return "good"
    if cp_loss < 100:
        return "inaccuracy"
    if cp_loss < 250:
        return "mistake"
    return "blunder"


def generate_opening_introduction(opening_data: dict, opening_name: Optional[str], user_color: str) -> Optional[Dict]:
    if not opening_data or opening_data.get("name") == "General Opening":
        return None
    name = opening_data.get("name", opening_name or "Unknown Opening")
    intro_text = opening_data.get("introduction")
    white_plan = opening_data.get("white_plan", "")
    black_plan = opening_data.get("black_plan", "")
    phase_focus = opening_data.get("phase_focus", {})
    if not intro_text:
        intro_text = f"This is the {name}."
        if white_plan:
            intro_text += f" White's goal is to {white_plan.lower().rstrip('.')}."
        if black_plan:
            intro_text += f" Black's strategy is to {black_plan.lower().rstrip('.')}."
    your_plan = white_plan if user_color == "white" else black_plan
    their_plan = black_plan if user_color == "white" else white_plan
    return {
        "name": name,
        "description": intro_text,
        "your_plan": your_plan,
        "their_plan": their_plan,
        "key_focus": phase_focus.get("opening", ""),
        "common_mistakes": opening_data.get("common_mistakes", {}),
    }


# ─── RULE-BASED COACHING (for good moves / opponent moves) ──────────

def _rule_based_narrative(
    board: chess.Board,
    move: chess.Move,
    move_san: str,
    opening_data: dict,
    phase: str,
    is_user_move: bool,
    is_good: bool
) -> str:
    """Generate a short rule-based narrative for non-LLM moves."""
    piece = board.piece_at(move.from_square)
    if not piece:
        return f"Played {move_san}."

    piece_name = get_piece_name(piece)
    to_sq = chess.square_name(move.to_square)

    # Opening-specific ideas
    typical_ideas = opening_data.get("typical_ideas", {})
    if move_san in typical_ideas:
        idea = typical_ideas[move_san]
        if is_user_move and is_good:
            return f"Good — {move_san}. {idea}"
        return f"{move_san} — {idea}"

    # Castling
    if board.is_castling(move):
        side = "kingside" if chess.square_file(move.to_square) > chess.square_file(move.from_square) else "queenside"
        return f"Castled {side} — king is safe, rooks connected."

    # Captures
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        captured_name = get_piece_name(captured) if captured else "piece"
        return f"Captured the {captured_name} on {to_sq}."

    # Development
    back_rank = 0 if piece.color == chess.WHITE else 7
    if chess.square_rank(move.from_square) == back_rank and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
        return f"Developed the {piece_name} to {to_sq}."

    # Pawn moves
    if piece.piece_type == chess.PAWN:
        if move.promotion:
            return f"Promoted to a {get_piece_name(chess.Piece(move.promotion, piece.color))}!"
        return f"Played {move_san}."

    # Default
    if is_user_move and is_good:
        return f"Solid — {piece_name} to {to_sq}."
    return f"{piece_name} to {to_sq}."


def _get_opening_hint(move_san: str, opening_data: dict, phase: str) -> str:
    """Get opening-specific context hint for the LLM prompt."""
    hints = []

    # Check intents
    move_intents = opening_data.get("move_intents", {})
    if move_san in move_intents:
        intent = move_intents[move_san]
        hints.append(f"Likely intent: {intent.get('likely_idea', '')}")

    # Check sideline warnings
    sideline_warnings = opening_data.get("sideline_warnings", {})
    if move_san in sideline_warnings:
        hints.append(f"Sideline: {sideline_warnings[move_san]}")

    # Check main lines
    main_lines = opening_data.get("main_lines", {})
    for key, line_data in main_lines.items():
        if isinstance(line_data, dict):
            theory = line_data.get("theory", [])
            if theory:
                hints.append(f"Main theory moves: {', '.join(theory)}")
                lines_info = line_data.get("lines", {})
                for m, desc in lines_info.items():
                    hints.append(f"  {m}: {desc}")
            break

    return " | ".join(hints) if hints else ""


# ─── MAIN ORCHESTRATOR ──────────────────────────────────────────────

def generate_game_decryption(
    pgn: str,
    user_color: str,
    move_evaluations: List[Dict]
) -> List[Dict]:
    """
    Generate complete move-by-move coaching for a game.

    V4 Architecture:
    1. Parse all moves, classify by eval_loss
    2. Good moves → short rule-based narrative
    3. Mistakes/blunders → batch to LLM
    4. Merge results into final array
    """
    try:
        board = chess.Board()

        # Detect opening
        opening_name, eco_code = detect_opening_from_pgn(pgn)
        opening_data = get_opening_data(eco_code, opening_name)
        logger.info(f"[DECRYPTION V4] Opening: {opening_name or 'Unknown'} ({eco_code or 'N/A'})")

        # Parse PGN
        game = chess.pgn.read_game(io.StringIO(pgn))
        if not game:
            logger.error("Could not parse PGN")
            return []

        moves = list(game.mainline_moves())

        # Build eval lookup BY FEN (position-based matching)
        # Stockfish evals are indexed by user moves only, but PGN indices
        # include both colors. FEN matching is the only reliable way.
        eval_lookup_by_fen = {}
        for eval_data in move_evaluations:
            fen = eval_data.get("fen_before", "")
            if fen:
                # Use just the board+turn+castling+ep part (skip move counters)
                fen_key = " ".join(fen.split()[:4])
                eval_lookup_by_fen[fen_key] = eval_data

        # ── PHASE 1: Classify all moves ──────────────────────────
        all_moves_data = []
        temp_board = chess.Board()
        prev_move = None  # Track opponent's last move for recapture detection

        for idx, move in enumerate(moves):
            move_san = temp_board.san(move)
            full_move_number = (idx // 2) + 1
            is_white = (idx % 2 == 0)
            is_user = (user_color == "white" and is_white) or (user_color == "black" and not is_white)
            eval_data = eval_lookup_by_fen.get(" ".join(temp_board.fen().split()[:4]), {})
            cp_loss = abs(eval_data.get("cp_loss", 0))
            phase = detect_phase(temp_board, full_move_number)
            severity = classify_move(cp_loss) if is_user else "context"

            # ── FORCED RECAPTURE DETECTION ──────────────────
            # If the user's move is a capture on the same square the opponent
            # just captured on, AND it's the only legal capture on that square,
            # treat it as "good" regardless of engine eval.
            is_forced_recapture = False
            if is_user and temp_board.is_capture(move) and prev_move:
                target_sq = move.to_square
                prev_target = prev_move.to_square
                if target_sq == prev_target:
                    # Check if this is the only legal capture on that square
                    captures_on_sq = [m for m in temp_board.legal_moves
                                      if m.to_square == target_sq and temp_board.is_capture(m)]
                    if len(captures_on_sq) <= 1:
                        is_forced_recapture = True
                        severity = "good"  # Don't send forced recaptures to LLM

            fen_before = temp_board.fen()
            prev_move = move
            temp_board.push(move)
            fen_after = temp_board.fen()

            all_moves_data.append({
                "idx": idx,
                "move": move,
                "move_san": move_san,
                "move_number": full_move_number,
                "is_user_move": is_user,
                "is_white": is_white,
                "fen_before": fen_before,
                "fen_after": fen_after,
                "phase": phase,
                "cp_loss": cp_loss,
                "severity": severity,
                "eval_before": eval_data.get("eval_before"),
                "eval_after": eval_data.get("eval_after"),
                "best_move": eval_data.get("best_move"),
                "cognitive_gap": eval_data.get("cognitive_gap"),
                "coaching_focus": eval_data.get("coaching_focus"),
                "eval_data": eval_data,
                "is_forced_recapture": is_forced_recapture,
            })

        # ── PHASE 2: Identify moves needing LLM ─────────────────
        llm_moves = []
        llm_indices = set()

        for md in all_moves_data:
            if md["is_user_move"] and md["severity"] in ("inaccuracy", "mistake", "blunder"):
                md["opening_hint"] = _get_opening_hint(md["move_san"], opening_data, md["phase"])
                llm_moves.append(md)
                llm_indices.add(md["idx"])

        # Sort by move index for proper ordering
        llm_moves.sort(key=lambda m: m["idx"])

        logger.info(f"[DECRYPTION V4] {len(llm_moves)} user mistakes going to LLM")

        # ── PHASE 3: Call LLM for mistakes ───────────────────────
        llm_results = {}
        if llm_moves:
            # Build game context for LLM
            pgn_short = _extract_short_pgn(pgn)
            opening_context = ""
            if opening_data and opening_data.get("name") != "General Opening":
                parts = []
                if opening_data.get("name"):
                    parts.append(f"Opening: {opening_data['name']}")
                plan_key = "white_plan" if user_color == "white" else "black_plan"
                if opening_data.get(plan_key):
                    parts.append(f"Your plan: {opening_data[plan_key]}")
                main_lines = opening_data.get("main_lines", {})
                for key, ld in main_lines.items():
                    if isinstance(ld, dict) and ld.get("theory"):
                        parts.append(f"Main theory: {', '.join(ld['theory'])}")
                        break
                opening_context = ". ".join(parts)

            game_context = {
                "opening_name": opening_name or "Unknown",
                "user_color": user_color,
                "pgn_short": pgn_short,
                "opening_context": opening_context,
            }

            from services.game_decryption_llm_service import generate_llm_coaching_sync
            raw_results = generate_llm_coaching_sync(llm_moves, game_context)

            # Map results back to move indices
            for i, result in enumerate(raw_results):
                if i < len(llm_moves):
                    llm_results[llm_moves[i]["idx"]] = result

        # ── PHASE 4: Build final output ──────────────────────────
        decryption_data = []
        board = chess.Board()

        for md in all_moves_data:
            idx = md["idx"]
            is_user = md["is_user_move"]
            cp_loss = md["cp_loss"]
            severity = md["severity"]

            move_output = {
                "move_number": md["move_number"],
                "is_user_move": is_user,
                "move_san": md["move_san"],
                "fen_before": md["fen_before"],
                "fen_after": md["fen_after"],
                "phase": md["phase"],
                "opening_name": opening_name,

                # V4 LLM fields (defaults)
                "narrative": None,
                "position_breakdown": None,
                "mistake_analysis": None,
                "better_plan": None,
                "thinking_gap": None,
                "principle": None,
                "confidence": None,

                # Engine data
                "is_mistake": is_user and cp_loss >= 50,
                "cp_loss": cp_loss,
                "eval_before": md["eval_before"],
                "eval_after": md["eval_after"],
                "best_move_san": md["best_move"],

                # Opening theory (rule-based)
                "is_sideline": False,
                "sideline_warning": None,
                "main_line_moves": None,
                "main_line_theory": None,
            }

            # ── Merge LLM result if available ────────────────
            if idx in llm_results:
                llm = llm_results[idx]
                move_output["narrative"] = llm.get("narrative")

                # ONLY set coaching fields for USER moves — never for opponent
                if is_user:
                    move_output["position_breakdown"] = llm.get("position_breakdown")
                    move_output["mistake_analysis"] = llm.get("mistake_analysis")
                    move_output["thinking_gap"] = llm.get("thinking_gap")
                    move_output["principle"] = llm.get("principle")
                    move_output["confidence"] = llm.get("confidence")

                    # ENFORCE: better_plan.move ALWAYS comes from Stockfish, not LLM
                    llm_plan = llm.get("better_plan")
                    if llm_plan and isinstance(llm_plan, dict):
                        sf_best = md.get("best_move", "")
                        llm_plan["move"] = sf_best or llm_plan.get("move", "")
                        move_output["better_plan"] = llm_plan
                    elif md.get("best_move"):
                        move_output["better_plan"] = {"move": md["best_move"], "idea": "", "what_happens_next": ""}

                    if llm.get("mistake_analysis") and llm["mistake_analysis"].get("severity"):
                        sev = llm["mistake_analysis"]["severity"]
                        if sev in ("blunder", "mistake"):
                            move_output["is_mistake"] = True
            else:
                # Rule-based narrative for good/non-LLM moves
                if md.get("is_forced_recapture"):
                    # Forced recapture — acknowledge it as the natural move
                    piece = board.piece_at(md["move"].from_square)
                    piece_name = get_piece_name(piece) if piece else "piece"
                    captured = board.piece_at(md["move"].to_square)
                    captured_name = get_piece_name(captured) if captured else "piece"
                    move_output["narrative"] = f"Forced recapture — {md['move_san']} takes back the {captured_name}. This is the only way to recover the material."
                    move_output["is_mistake"] = False  # Never flag forced recaptures
                else:
                    move_output["narrative"] = _rule_based_narrative(
                        board, md["move"], md["move_san"],
                        opening_data, md["phase"], is_user,
                        severity == "good"
                    )

            # ── Opening theory checks (always rule-based) ────
            # Skip sideline warnings for forced recaptures
            if is_user and md["phase"] == "opening" and not md.get("is_forced_recapture"):
                is_sideline, warning, main_moves, main_theory = _check_sideline(
                    md["move_san"], md["move_number"], opening_data
                )
                if is_sideline:
                    move_output["is_sideline"] = True
                    move_output["sideline_warning"] = warning
                    move_output["main_line_moves"] = main_moves
                    move_output["main_line_theory"] = main_theory

            decryption_data.append(move_output)
            board.push(md["move"])

        logger.info(f"[DECRYPTION V4] Generated {len(decryption_data)} move coachings")
        return decryption_data

    except Exception as e:
        logger.error(f"Error in game decryption V4: {e}")
        import traceback
        traceback.print_exc()
        return []


def _check_sideline(move_san: str, move_number: int, opening_data: dict) -> Tuple[bool, Optional[str], Optional[List[str]], Optional[Dict]]:
    """Check if a move deviates from opening theory."""
    sideline_warnings = opening_data.get("sideline_warnings", {})
    if move_san in sideline_warnings:
        warning = sideline_warnings[move_san]
        main_lines = opening_data.get("main_lines", {})
        main_moves = None
        main_theory = None
        for key, line_data in main_lines.items():
            if isinstance(line_data, dict):
                theory = line_data.get("theory", [])
                if theory:
                    main_moves = theory
                    main_theory = {
                        "position": line_data.get("position", ""),
                        "best": line_data.get("best", ""),
                        "explanation": line_data.get("explanation", ""),
                        "lines": line_data.get("lines", {})
                    }
                    break

        # Empathetic rewrite using intents
        move_intents = opening_data.get("move_intents", {})
        if move_san in move_intents:
            intent = move_intents[move_san]
            idea = intent.get("likely_idea", "")
            if idea:
                warning = f"I see you played {move_san} ({idea.lower().rstrip('.')}). That's a reasonable thought! However, {warning[0].lower()}{warning[1:]}"

        return True, warning, main_moves, main_theory

    # Generic sideline check for early pawn moves
    if move_number <= 6:
        typical_ideas = opening_data.get("typical_ideas", {})
        if move_san not in typical_ideas:
            if len(move_san) == 2 and move_san[0] in 'abcdefgh':
                if move_san not in ['e4', 'e5', 'd4', 'd5', 'c4', 'c5', 'c6', 'e6', 'd6', 'b6', 'g6']:
                    return True, f"{move_san} is unusual here. Consider developing a piece instead.", None, None

    return False, None, None, None


def _extract_short_pgn(pgn: str) -> str:
    """Extract just the moves from a PGN (strip headers)."""
    lines = pgn.strip().split("\n")
    move_lines = [line for line in lines if not line.startswith("[")]
    return " ".join(move_lines).strip()[:500]


def generate_game_summary(decryption_data: List[Dict], user_color: str, opening_data: Optional[dict] = None) -> Dict:
    """Generate game summary with opening introduction."""
    if not decryption_data:
        return {"error": "No data available"}

    user_moves = [m for m in decryption_data if m.get("is_user_move")]
    mistakes = [m for m in user_moves if m.get("is_mistake")]
    good_moves = [m for m in user_moves if not m.get("is_mistake") and m.get("cp_loss", 999) <= 10]

    phases = {"opening": 0, "middlegame": 0, "endgame": 0}
    for m in decryption_data:
        phases[m.get("phase", "middlegame")] = phases.get(m.get("phase", "middlegame"), 0) + 1

    # Key moments from LLM-analyzed moves
    key_moments = []
    for m in sorted(mistakes, key=lambda x: x.get("cp_loss", 0), reverse=True)[:5]:
        summary_text = ""
        if m.get("thinking_gap"):
            summary_text = m["thinking_gap"]
        elif m.get("narrative"):
            summary_text = m["narrative"][:120] + "..." if len(m.get("narrative", "")) > 120 else m.get("narrative", "")
        else:
            summary_text = "A mistake occurred here"

        key_moments.append({
            "move_number": m.get("move_number"),
            "type": m.get("mistake_analysis", {}).get("type", "mistake") if m.get("mistake_analysis") else ("blunder" if m.get("cp_loss", 0) >= 250 else "mistake"),
            "move": m.get("move_san"),
            "summary": summary_text
        })

    opening_name = decryption_data[0].get("opening_name") if decryption_data else None

    # Overall message — use the biggest thinking gap
    if not mistakes:
        overall = "Excellent game! You played with very few inaccuracies."
    elif len(mistakes) == 1:
        m = mistakes[0]
        gap = m.get("thinking_gap", "")
        overall = f"Solid play overall. One key moment at move {m.get('move_number')}: {gap}" if gap else f"Solid play. Review move {m.get('move_number')}."
    else:
        worst = max(mistakes, key=lambda x: x.get("cp_loss", 0))
        gap = worst.get("thinking_gap", "")
        overall = f"Focus on move {worst.get('move_number')}: {gap}" if gap else f"Review your {len(mistakes)} mistakes — especially move {worst.get('move_number')}."

    opening_intro = None
    if opening_data:
        opening_intro = generate_opening_introduction(opening_data, opening_name, user_color)

    return {
        "total_moves": len(decryption_data),
        "user_moves": len(user_moves),
        "mistakes": len(mistakes),
        "good_moves": len(good_moves),
        "phases": phases,
        "key_moments": key_moments,
        "opening_name": opening_name,
        "overall_message": overall,
        "opening_introduction": opening_intro,
    }
