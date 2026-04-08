"""
Fundamentals Checklist Service
================================

Runs every mistake/blunder position through 7 chess fundamentals.
Identifies WHICH fundamental was violated and generates Socratic
coaching: question + hint + plan. Never reveals the best move.

Philosophy: Teach them to THINK, not what to THINK.
"""

import chess
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any


# ─── FUNDAMENTALS ─────────────────────────────────────────────────

class Fundamental(str, Enum):
    CHECK_OPPONENTS_MOVE = "check_opponents_move"
    HANGING_PIECES = "hanging_pieces"
    KING_SAFETY = "king_safety"
    CALCULATE = "calculate"
    DEVELOPMENT = "development"
    CENTER_CONTROL = "center_control"
    HAVE_A_PLAN = "have_a_plan"


# Priority order: when multiple are violated, pick the highest
FUNDAMENTAL_PRIORITY = [
    Fundamental.CHECK_OPPONENTS_MOVE,
    Fundamental.HANGING_PIECES,
    Fundamental.KING_SAFETY,
    Fundamental.CALCULATE,
    Fundamental.DEVELOPMENT,
    Fundamental.CENTER_CONTROL,
    Fundamental.HAVE_A_PLAN,
]

FUNDAMENTAL_LABELS = {
    Fundamental.CHECK_OPPONENTS_MOVE: "Check opponent's last move",
    Fundamental.HANGING_PIECES: "Piece safety",
    Fundamental.KING_SAFETY: "King safety",
    Fundamental.CALCULATE: "Calculate before moving",
    Fundamental.DEVELOPMENT: "Develop your pieces",
    Fundamental.CENTER_CONTROL: "Control the center",
    Fundamental.HAVE_A_PLAN: "Play with a plan",
}


@dataclass
class FundamentalsDiagnosis:
    violated: Optional[Fundamental]
    fundamental_label: str
    question: str
    hint: str
    plan: str
    opening_idea: Optional[str]
    checklist_results: Dict[str, bool]


# ─── PIECE HELPERS ────────────────────────────────────────────────

PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def _square_name(sq: int) -> str:
    return chess.square_name(sq)


def _piece_name(board: chess.Board, sq: int) -> str:
    piece = board.piece_at(sq)
    if piece:
        return PIECE_NAMES.get(piece.piece_type, "piece")
    return "piece"


def _board_area(sq: int) -> str:
    file = chess.square_file(sq)
    if file <= 2:
        return "queenside"
    elif file >= 5:
        return "kingside"
    return "center"


def _find_hanging(board: chess.Board, color: chess.Color) -> List[Dict]:
    """Find pieces of `color` that are attacked and undefended."""
    hanging = []
    opponent = not color
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.color != color:
            continue
        if piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(opponent, sq)
        defenders = board.attackers(color, sq)
        if attackers and not defenders:
            hanging.append({
                "square": _square_name(sq),
                "piece": PIECE_NAMES.get(piece.piece_type, "piece"),
                "value": PIECE_VALUES.get(piece.piece_type, 0),
                "area": _board_area(sq),
            })
    return hanging


def _is_castled(board: chess.Board, color: chess.Color) -> bool:
    """Check if king has likely castled (king on g1/c1 for white, g8/c8 for black)."""
    king_sq = board.king(color)
    if king_sq is None:
        return False
    if color == chess.WHITE:
        return king_sq in (chess.G1, chess.C1)
    else:
        return king_sq in (chess.G8, chess.C8)


def _count_developed(board: chess.Board, color: chess.Color) -> Tuple[int, int]:
    """Count developed minor pieces vs total minor pieces."""
    back_rank = 0 if color == chess.WHITE else 7
    total = 0
    developed = 0
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.color != color:
            continue
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            total += 1
            if chess.square_rank(sq) != back_rank:
                developed += 1
    return developed, total


def _center_control(board: chess.Board, color: chess.Color) -> int:
    """Count how many center squares (e4, d4, e5, d5) are controlled by color."""
    center = [chess.E4, chess.D4, chess.E5, chess.D5]
    controlled = 0
    for sq in center:
        # Occupied by our pawn
        piece = board.piece_at(sq)
        if piece and piece.color == color and piece.piece_type == chess.PAWN:
            controlled += 1
        # Attacked by our pieces
        if board.attackers(color, sq):
            controlled += 1
    return controlled


def _opponent_threats(board_before: chess.Board, opponent_move: chess.Move) -> Dict:
    """Analyze what the opponent's last move threatens."""
    board_after = board_before.copy()
    board_after.push(opponent_move)

    to_sq = opponent_move.to_square
    moved_piece = board_before.piece_at(opponent_move.from_square)
    if not moved_piece:
        return {}

    # What does the moved piece now attack?
    user_color = moved_piece.color  # This is opponent's color
    target_color = not user_color

    threats = []
    attacked_squares = board_after.attacks(to_sq)
    for sq in attacked_squares:
        target = board_after.piece_at(sq)
        if target and target.color == target_color and target.piece_type != chess.KING:
            threats.append({
                "square": _square_name(sq),
                "piece": PIECE_NAMES.get(target.piece_type, "piece"),
                "value": PIECE_VALUES.get(target.piece_type, 0),
            })

    # Is there a check?
    is_check = board_after.is_check()

    return {
        "moved_piece": PIECE_NAMES.get(moved_piece.piece_type, "piece"),
        "from": _square_name(opponent_move.from_square),
        "to": _square_name(to_sq),
        "threats": threats,
        "is_check": is_check,
        "area": _board_area(to_sq),
    }


def _did_piece_move_twice(board: chess.Board, user_move: chess.Move, phase: str) -> Optional[str]:
    """Check if the user moved the same piece twice in the opening."""
    if phase != "opening":
        return None
    move_stack = list(board.move_stack)
    from_sq = user_move.from_square
    # Look back through user's previous moves
    for i in range(len(move_stack) - 2, -1, -2):  # Every other move is the user's
        prev = move_stack[i]
        if prev.to_square == from_sq:
            piece = board.piece_at(from_sq)
            if piece and piece.piece_type not in (chess.PAWN, chess.KING):
                return PIECE_NAMES.get(piece.piece_type, "piece")
    return None


# ─── QUESTION / HINT / PLAN TEMPLATES ────────────────────────────

QUESTIONS = {
    Fundamental.CHECK_OPPONENTS_MOVE: [
        "Before you played {move}, did you check what your opponent was threatening with {opp_move}?",
        "What was your opponent trying to do with {opp_move}? Did you consider that before moving?",
        "Your opponent just played {opp_move}. Before you moved — what changed on the board?",
    ],
    Fundamental.HANGING_PIECES: [
        "After {move}, is every one of your pieces defended?",
        "Before moving, did you scan for undefended pieces?",
        "Quick check — after {move}, count attackers vs defenders on your pieces.",
    ],
    Fundamental.KING_SAFETY: [
        "Your king is still in the center. What's stopping you from castling?",
        "Look at your king's position. Is it safe where it is?",
        "You've been playing for a while without castling. What happens if lines open up?",
    ],
    Fundamental.CALCULATE: [
        "Did you look at what happens AFTER {move}? Trace 2 moves ahead.",
        "Before playing {move} — what can your opponent capture or threaten in response?",
        "Your move walked into something. Did you calculate your opponent's reply?",
    ],
    Fundamental.DEVELOPMENT: [
        "You moved your {piece} again. How many of your pieces are still on the back rank?",
        "Count your developed pieces. Is there one still sleeping at home?",
        "In the opening, every move should bring a NEW piece into the game. Did this move do that?",
    ],
    Fundamental.CENTER_CONTROL: [
        "Look at the center squares — e4, d4, e5, d5. Who controls more of them right now?",
        "Your move went to the side of the board. What about the center?",
        "The center is where the battle is decided. Are you fighting for it?",
    ],
    Fundamental.HAVE_A_PLAN: [
        "What were you trying to achieve with {move}?",
        "Before touching a piece — what's your plan for the next 2-3 moves?",
        "Every move should have a purpose. What was the idea behind {move}?",
    ],
}

HINTS = {
    Fundamental.CHECK_OPPONENTS_MOVE: [
        "Your opponent's {opp_piece} is now looking at one of your pieces. Which one?",
        "Something changed on the {area}. Look again at what {opp_move} uncovered.",
        "Check the line from {opp_to} — what does it attack now?",
    ],
    Fundamental.HANGING_PIECES: [
        "One of your pieces on the {area} is now undefended.",
        "Count: how many pieces attack {key_square} vs how many defend it?",
        "Your {hanging_piece} on {key_square} — is anything protecting it?",
    ],
    Fundamental.KING_SAFETY: [
        "Your king is on {king_square}. If a file opens up, it could be in trouble.",
        "How many pieces are protecting your king right now?",
        "Castling takes one move. The penalty for not castling can be much worse.",
    ],
    Fundamental.CALCULATE: [
        "After {move}, your opponent can play... what? Think about checks, captures, and threats.",
        "Look at what your opponent can capture after {move}.",
        "Trace it: {move}, then your opponent plays... what happens?",
    ],
    Fundamental.DEVELOPMENT: [
        "You have {undeveloped} pieces still on the back rank. They're not helping.",
        "Moving the same piece twice costs you a tempo. Your opponent gets a free move.",
        "Look at your back rank — which piece could come out next?",
    ],
    Fundamental.CENTER_CONTROL: [
        "Your opponent has more control of the center. That means their pieces have more room.",
        "A knight or pawn in the center controls more squares than one on the edge.",
        "The center is the highway — control it and your pieces can go anywhere.",
    ],
    Fundamental.HAVE_A_PLAN: [
        "Look at your worst-placed piece. How can you improve it?",
        "What's the weakness in your opponent's position? Aim your pieces at it.",
        "A plan can be simple: improve your least active piece, or target a weakness.",
    ],
}

PLANS = {
    Fundamental.CHECK_OPPONENTS_MOVE: [
        "Build the habit: before touching a piece, name your opponent's threat.",
        "Start each turn by asking: what did my opponent just threaten?",
        "For the next few moves, pause before moving and check what changed.",
    ],
    Fundamental.HANGING_PIECES: [
        "Before each move, scan: is anything undefended? Add a defender first.",
        "Make it a habit: after choosing your move, check — did I leave anything hanging?",
        "Count attackers vs defenders. If the math is wrong, fix it before attacking.",
    ],
    Fundamental.KING_SAFETY: [
        "Prioritize castling in the next 2-3 moves. Get your king to safety.",
        "King safety first. Don't start an attack until your king is castled.",
        "Your king needs a safe home. Castle before pushing any more pawns.",
    ],
    Fundamental.CALCULATE: [
        "Before each move, check: can my opponent capture something after this?",
        "Practice the 2-move rule: before moving, calculate your move AND the opponent's best reply.",
        "Slow down on critical moves. Check for checks, captures, and threats — in that order.",
    ],
    Fundamental.DEVELOPMENT: [
        "Bring out a new piece each move. Knights and bishops first, then connect your rooks.",
        "Don't move the same piece twice unless there's a very good reason.",
        "Development is about getting ALL your pieces into the game quickly.",
    ],
    Fundamental.CENTER_CONTROL: [
        "Fight for e4, d4, e5, d5 with pawns and pieces. The center is the battlefield.",
        "Place your pieces where they influence the center. Knights on f3/c3, not on the rim.",
        "Whoever controls the center controls the game. Make it your priority.",
    ],
    Fundamental.HAVE_A_PLAN: [
        "Before your next move, decide: what am I trying to achieve in the next 3 moves?",
        "Find your worst piece and improve it. That's a plan.",
        "Look for your opponent's weakness and aim your pieces at it. That's how plans start.",
    ],
}


# ─── MAIN SERVICE ─────────────────────────────────────────────────

class FundamentalsChecklistService:
    """
    Runs every position through the 7 fundamentals checklist.
    Returns which fundamental was violated with Socratic coaching.
    """

    def __init__(self):
        # Track used templates per session to avoid repeats
        self._used_questions: Dict[str, set] = {}
        self._used_hints: Dict[str, set] = {}

    def diagnose(
        self,
        board_before: chess.Board,
        board_after: chess.Board,
        user_move: chess.Move,
        best_move_san: Optional[str],
        cp_loss: int,
        phase: str,
        user_color: str,
        opponent_last_move: Optional[chess.Move] = None,
        opening_match: Optional[dict] = None,
    ) -> FundamentalsDiagnosis:
        """Run all 7 checks, return the primary violated fundamental."""

        color = chess.WHITE if user_color == "white" else chess.BLACK
        move_san = board_before.san(user_move)
        opp_move_san = board_before.san(opponent_last_move) if opponent_last_move else None

        # Run all 7 checks
        results = {}
        details = {}

        # 1. Check opponent's last move
        passed, det = self._check_opponents_move(board_before, board_after, user_move, opponent_last_move, color)
        results[Fundamental.CHECK_OPPONENTS_MOVE] = passed
        details[Fundamental.CHECK_OPPONENTS_MOVE] = det

        # 2. Hanging pieces
        passed, det = self._check_hanging_pieces(board_before, board_after, user_move, color)
        results[Fundamental.HANGING_PIECES] = passed
        details[Fundamental.HANGING_PIECES] = det

        # 3. King safety
        passed, det = self._check_king_safety(board_after, color, phase)
        results[Fundamental.KING_SAFETY] = passed
        details[Fundamental.KING_SAFETY] = det

        # 4. Calculate
        passed, det = self._check_calculation(board_before, board_after, user_move, cp_loss, color)
        results[Fundamental.CALCULATE] = passed
        details[Fundamental.CALCULATE] = det

        # 5. Development
        passed, det = self._check_development(board_before, board_after, user_move, color, phase)
        results[Fundamental.DEVELOPMENT] = passed
        details[Fundamental.DEVELOPMENT] = det

        # 6. Center control
        passed, det = self._check_center_control(board_after, user_move, color, phase)
        results[Fundamental.CENTER_CONTROL] = passed
        details[Fundamental.CENTER_CONTROL] = det

        # 7. Have a plan (fallback — always fails for big mistakes)
        passed, det = self._check_has_plan(cp_loss)
        results[Fundamental.HAVE_A_PLAN] = passed
        details[Fundamental.HAVE_A_PLAN] = det

        # Find primary violated fundamental (highest priority)
        violated = None
        for f in FUNDAMENTAL_PRIORITY:
            if not results.get(f, True):
                violated = f
                break

        # Build the checklist snapshot
        checklist = {f.value: results.get(f, True) for f in Fundamental}

        if violated is None:
            # All passed — shouldn't happen for a mistake, but use fallback
            violated = Fundamental.HAVE_A_PLAN

        # Generate Socratic content
        det_data = details.get(violated, {})
        template_vars = self._build_template_vars(
            move_san, opp_move_san, opponent_last_move, board_before, board_after,
            user_move, color, det_data
        )

        question = self._pick_template(QUESTIONS, violated, template_vars)
        hint = self._pick_template(HINTS, violated, template_vars)
        plan = self._pick_template(PLANS, violated, template_vars)

        # Opening idea
        opening_idea = self._get_opening_idea(opening_match, user_color)

        return FundamentalsDiagnosis(
            violated=violated,
            fundamental_label=FUNDAMENTAL_LABELS.get(violated, ""),
            question=question,
            hint=hint,
            plan=plan,
            opening_idea=opening_idea,
            checklist_results=checklist,
        )

    # ─── CHECK METHODS ────────────────────────────────────────────

    def _check_opponents_move(
        self, board_before: chess.Board, board_after: chess.Board,
        user_move: chess.Move, opp_move: Optional[chess.Move], color: chess.Color
    ) -> Tuple[bool, Dict]:
        """Did user respond to opponent's threat?"""
        if opp_move is None:
            return True, {}

        # Get what the opponent threatened with their last move
        # We need the board BEFORE opponent's move to analyze it
        board_pre_opp = board_before.copy()
        try:
            board_pre_opp.pop()  # Undo opponent's move to get pre-opponent state
        except IndexError:
            return True, {}

        threat_info = _opponent_threats(board_pre_opp, opp_move)
        threats = threat_info.get("threats", [])

        if not threats:
            return True, threat_info

        # Did user address any of the threats?
        # User's move should: (a) capture the threatening piece, (b) defend the threatened piece,
        # (c) move the threatened piece, or (d) create a bigger threat
        addressed = False

        # (a) Captured the threatening piece?
        if user_move.to_square == opp_move.to_square:
            addressed = True

        # (c) Moved a threatened piece?
        for t in threats:
            threatened_sq = chess.parse_square(t["square"])
            if user_move.from_square == threatened_sq:
                addressed = True

        # (b) Added defender to a threatened square?
        for t in threats:
            threatened_sq = chess.parse_square(t["square"])
            if user_move.to_square != threatened_sq:
                # Check if the moved piece now defends the threatened square
                if threatened_sq in board_after.attacks(user_move.to_square):
                    addressed = True

        # Check if the threatened piece is still hanging after user's move
        still_hanging = False
        for t in threats:
            try:
                threatened_sq = chess.parse_square(t["square"])
                piece = board_after.piece_at(threatened_sq)
                if piece and piece.color == color:
                    attackers = board_after.attackers(not color, threatened_sq)
                    defenders = board_after.attackers(color, threatened_sq)
                    if attackers and not defenders:
                        still_hanging = True
            except (ValueError, IndexError):
                continue

        if still_hanging and not addressed:
            return False, threat_info

        return True, threat_info

    def _check_hanging_pieces(
        self, board_before: chess.Board, board_after: chess.Board,
        user_move: chess.Move, color: chess.Color
    ) -> Tuple[bool, Dict]:
        """Does the user's move leave their own pieces hanging?"""
        # Check for hanging pieces AFTER user's move
        hanging_after = _find_hanging(board_after, color)

        # Filter: only care about pieces that BECAME hanging because of this move
        hanging_before = _find_hanging(board_before, color)
        before_squares = {h["square"] for h in hanging_before}

        new_hanging = [h for h in hanging_after if h["square"] not in before_squares]

        # Also check: did the moved piece itself become hanging?
        to_sq = user_move.to_square
        moved_piece = board_after.piece_at(to_sq)
        if moved_piece and moved_piece.color == color and moved_piece.piece_type != chess.KING:
            attackers = board_after.attackers(not color, to_sq)
            defenders = board_after.attackers(color, to_sq)
            if attackers and not defenders:
                new_hanging.append({
                    "square": _square_name(to_sq),
                    "piece": PIECE_NAMES.get(moved_piece.piece_type, "piece"),
                    "value": PIECE_VALUES.get(moved_piece.piece_type, 0),
                    "area": _board_area(to_sq),
                })

        if new_hanging:
            # Sort by value — report the most valuable hanging piece
            new_hanging.sort(key=lambda h: h["value"], reverse=True)
            return False, {"hanging": new_hanging, "worst": new_hanging[0]}

        return True, {}

    def _check_king_safety(
        self, board_after: chess.Board, color: chess.Color, phase: str
    ) -> Tuple[bool, Dict]:
        """Is the king safe?"""
        if phase == "endgame":
            return True, {}  # King activity is good in endgames

        king_sq = board_after.king(color)
        if king_sq is None:
            return True, {}

        castled = _is_castled(board_after, color)
        move_number = board_after.fullmove_number

        # Not castled by move 10+ is a problem
        if not castled and move_number >= 10 and phase in ("opening", "middlegame"):
            # Check if castling is still possible
            can_castle = False
            if color == chess.WHITE:
                can_castle = board_after.has_kingside_castling_rights(chess.WHITE) or \
                             board_after.has_queenside_castling_rights(chess.WHITE)
            else:
                can_castle = board_after.has_kingside_castling_rights(chess.BLACK) or \
                             board_after.has_queenside_castling_rights(chess.BLACK)

            return False, {
                "king_square": _square_name(king_sq),
                "castled": False,
                "can_castle": can_castle,
                "move_number": move_number,
            }

        # Check pawn shield (if castled)
        if castled:
            shield_intact = self._check_pawn_shield(board_after, color, king_sq)
            if not shield_intact:
                return False, {
                    "king_square": _square_name(king_sq),
                    "castled": True,
                    "shield_broken": True,
                }

        return True, {"king_square": _square_name(king_sq), "castled": castled}

    def _check_pawn_shield(self, board: chess.Board, color: chess.Color, king_sq: int) -> bool:
        """Check if the pawn shield in front of the king is intact."""
        king_file = chess.square_file(king_sq)
        shield_rank = 1 if color == chess.WHITE else 6  # Pawns should be on 2nd/7th rank

        shield_files = [max(0, king_file - 1), king_file, min(7, king_file + 1)]
        pawns_intact = 0
        for f in shield_files:
            sq = chess.square(f, shield_rank)
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == color:
                pawns_intact += 1

        return pawns_intact >= 2  # At least 2 of 3 shield pawns should be there

    def _check_calculation(
        self, board_before: chess.Board, board_after: chess.Board,
        user_move: chess.Move, cp_loss: int, color: chess.Color
    ) -> Tuple[bool, Dict]:
        """Did the move lose material through missed calculation?"""
        # Big cp loss means they didn't calculate
        if cp_loss >= 200:
            # Check what the opponent can now do
            opponent_captures = []
            for opp_move in board_after.legal_moves:
                if board_after.is_capture(opp_move):
                    captured_sq = opp_move.to_square
                    captured = board_after.piece_at(captured_sq)
                    if captured:
                        opponent_captures.append({
                            "move": board_after.san(opp_move),
                            "captures": PIECE_NAMES.get(captured.piece_type, "piece"),
                            "value": PIECE_VALUES.get(captured.piece_type, 0),
                        })

            opponent_captures.sort(key=lambda c: c["value"], reverse=True)
            return False, {
                "cp_loss": cp_loss,
                "opponent_captures": opponent_captures[:3],
            }

        # Moderate cp loss — might be calculation issue
        if cp_loss >= 100:
            return False, {"cp_loss": cp_loss}

        return True, {}

    def _check_development(
        self, board_before: chess.Board, board_after: chess.Board,
        user_move: chess.Move, color: chess.Color, phase: str
    ) -> Tuple[bool, Dict]:
        """In opening: is user developing new pieces?"""
        if phase != "opening":
            return True, {}

        developed, total = _count_developed(board_after, color)
        undeveloped = total - developed

        # Check if user moved the same piece twice
        repeated_piece = _did_piece_move_twice(board_before, user_move, phase)
        if repeated_piece and undeveloped > 0:
            return False, {
                "piece": repeated_piece,
                "undeveloped": undeveloped,
                "developed": developed,
                "total": total,
                "reason": "same_piece_twice",
            }

        # Check if user has many undeveloped pieces but is doing other things
        move_number = board_after.fullmove_number
        if undeveloped >= 3 and move_number >= 6:
            return False, {
                "undeveloped": undeveloped,
                "developed": developed,
                "total": total,
                "reason": "undeveloped_pieces",
            }

        return True, {"developed": developed, "total": total}

    def _check_center_control(
        self, board_after: chess.Board, user_move: chess.Move,
        color: chess.Color, phase: str
    ) -> Tuple[bool, Dict]:
        """Is user fighting for center?"""
        if phase not in ("opening", "middlegame"):
            return True, {}

        our_control = _center_control(board_after, color)
        opp_control = _center_control(board_after, not color)

        # If opponent controls center significantly more
        if opp_control >= our_control + 4 and phase == "opening":
            # Also check: did the user move to a rim square?
            to_file = chess.square_file(user_move.to_square)
            rim_move = to_file in (0, 7)  # a-file or h-file

            return False, {
                "our_control": our_control,
                "opp_control": opp_control,
                "rim_move": rim_move,
            }

        return True, {"our_control": our_control, "opp_control": opp_control}

    def _check_has_plan(self, cp_loss: int) -> Tuple[bool, Dict]:
        """Fallback check — if nothing else matches but the move was bad."""
        # This always passes; it's the fallback fundamental
        # It gets selected only when no other fundamental is violated
        return True, {}

    # ─── TEMPLATE HELPERS ─────────────────────────────────────────

    def _build_template_vars(
        self, move_san: str, opp_move_san: Optional[str],
        opp_move: Optional[chess.Move], board_before: chess.Board,
        board_after: chess.Board, user_move: chess.Move,
        color: chess.Color, det_data: Dict
    ) -> Dict[str, str]:
        """Build the template variables for question/hint/plan formatting."""
        vars = {
            "move": move_san,
            "opp_move": opp_move_san or "their last move",
        }

        # Opponent's piece info
        if opp_move:
            opp_piece = board_before.piece_at(opp_move.from_square)
            if opp_piece:
                vars["opp_piece"] = PIECE_NAMES.get(opp_piece.piece_type, "piece")
            else:
                vars["opp_piece"] = "piece"
            vars["opp_to"] = _square_name(opp_move.to_square)
            vars["area"] = _board_area(opp_move.to_square)
        else:
            vars["opp_piece"] = "piece"
            vars["opp_to"] = ""
            vars["area"] = "board"

        # Hanging piece info
        worst = det_data.get("worst", {})
        vars["hanging_piece"] = worst.get("piece", "piece")
        vars["key_square"] = worst.get("square", "")
        if not vars["key_square"] and det_data.get("hanging"):
            vars["key_square"] = det_data["hanging"][0].get("square", "")
        if not vars["area"]:
            vars["area"] = worst.get("area", "board")

        # King info
        vars["king_square"] = det_data.get("king_square", "")

        # Development info
        vars["piece"] = det_data.get("piece", "piece")
        vars["undeveloped"] = str(det_data.get("undeveloped", 0))

        return vars

    def _pick_template(
        self, templates: Dict[Fundamental, List[str]],
        fundamental: Fundamental, vars: Dict[str, str]
    ) -> str:
        """Pick a template and format it with variables."""
        choices = templates.get(fundamental, [""])
        if not choices:
            return ""

        template = random.choice(choices)
        try:
            return template.format(**vars)
        except (KeyError, IndexError):
            # If template vars are missing, return as-is with placeholders cleaned
            return template.format_map(SafeDict(vars))

    def _get_opening_idea(self, opening_match: Optional[dict], user_color: str) -> Optional[str]:
        """Extract the strategic IDEA from an opening match. Never specific moves."""
        if not opening_match:
            return None

        # opening_match is (opening_key, opening_data, variation_key) or dict
        if isinstance(opening_match, tuple) and len(opening_match) >= 2:
            opening_data = opening_match[1]
        elif isinstance(opening_match, dict):
            opening_data = opening_match
        else:
            return None

        name = opening_data.get("name", "")
        plan_key = "white_plan" if user_color == "white" else "black_plan"
        plan = opening_data.get(plan_key, "")

        if not plan:
            return None

        return f"In the {name}: {plan}"


class SafeDict(dict):
    """Dict that returns the key name for missing keys in format_map."""
    def __missing__(self, key):
        return f"[{key}]"
