"""
Move Effect Analyzer
====================

Analyzes WHAT CHANGES when a move is played.
This is the core of teaching - explaining WHY a move works.

Instead of: "Nd5 is +2.3"
We get: "Nd5 removes the defender of e7, opens the e-file for your rook,
        creates a threat of Nxf6+, and forces Black to react."

Features:
1. Before/After position comparison
2. Threat detection (new threats created)
3. Defender removal tracking
4. File/diagonal opening detection
5. Piece activity changes
6. King safety impact
7. Pawn structure changes
8. Forcing move detection

Usage:
    analyzer = MoveEffectAnalyzer()
    effects = analyzer.analyze_move(board, move)
    # Returns: detailed breakdown of what the move does
"""

import chess
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ThreatType(str, Enum):
    """Types of threats a move can create."""
    CAPTURE = "capture"           # Threatens to take a piece
    CHECK = "check"               # Gives check
    CHECKMATE = "checkmate"       # Gives checkmate
    FORK = "fork"                 # Attacks multiple pieces
    PIN = "pin"                   # Pins a piece to king/queen
    SKEWER = "skewer"             # Attacks through one piece to another
    DISCOVERED_ATTACK = "discovered_attack"
    PROMOTION = "promotion"       # Pawn threatens to promote
    MATE_THREAT = "mate_threat"   # Threatens checkmate next move


class EffectType(str, Enum):
    """Types of effects a move can have."""
    DEVELOPS_PIECE = "develops_piece"
    CAPTURES_MATERIAL = "captures_material"
    CREATES_THREAT = "creates_threat"
    REMOVES_DEFENDER = "removes_defender"
    OPENS_FILE = "opens_file"
    OPENS_DIAGONAL = "opens_diagonal"
    CONTROLS_SQUARE = "controls_square"
    IMPROVES_PIECE = "improves_piece"
    WEAKENS_KING = "weakens_king"
    STRENGTHENS_KING = "strengthens_king"
    CREATES_WEAKNESS = "creates_weakness"
    FIXES_WEAKNESS = "fixes_weakness"
    GAINS_SPACE = "gains_space"
    FORCES_RESPONSE = "forces_response"


@dataclass
class Threat:
    """A threat created by a move."""
    threat_type: ThreatType
    attacking_piece: str        # e.g., "Nd5"
    target: str                 # e.g., "Qd8" or "f7 square"
    target_value: int           # Material value of target
    description: str
    is_forcing: bool            # Must it be answered?


@dataclass
class DefenderRemoval:
    """When a move removes a defender."""
    removed_piece: str          # The piece that was defending
    was_defending: List[str]    # What it was defending
    now_vulnerable: List[str]   # What's now undefended
    teaching_note: str


@dataclass
class FileChange:
    """When a move opens/closes a file or diagonal."""
    change_type: str            # "opens" or "closes"
    line_type: str              # "file", "diagonal", "rank"
    line_name: str              # e.g., "e-file", "a1-h8 diagonal"
    benefits: str               # Who benefits
    teaching_note: str


@dataclass
class MoveEffect:
    """Complete analysis of what a move does."""
    move: str                   # e.g., "Nd5"
    move_san: str               # Standard notation
    
    # What was captured
    captures: Optional[str]     # e.g., "pawn on e5"
    capture_value: int          # Material value
    
    # Is it forcing?
    is_check: bool
    is_checkmate: bool
    is_forcing: bool            # Must opponent respond to this?
    forcing_reason: str         # Why it's forcing
    
    # Threats created
    threats: List[Threat]
    
    # Defender removal
    defenders_removed: List[DefenderRemoval]
    
    # Line changes (files, diagonals)
    lines_opened: List[FileChange]
    lines_closed: List[FileChange]
    
    # Piece activity
    piece_activity_change: Dict[str, str]  # {"Ne2": "improved to d4"}
    
    # Square control
    squares_gained: List[str]   # Squares now controlled
    squares_lost: List[str]     # Squares no longer controlled
    
    # King safety
    king_safety_impact: str     # "weakens White king", "no impact", etc.
    
    # Pawn structure
    pawn_structure_change: str  # "creates isolated pawn", "opens e-file", etc.
    
    # Overall assessment
    move_type: str              # "tactical", "positional", "defensive", etc.
    main_idea: str              # One-sentence summary
    teaching_explanation: str   # Full teaching explanation
    
    # Follow-up
    logical_followups: List[str]  # What to do next
    opponent_responses: List[str]  # How opponent might respond


class MoveEffectAnalyzer:
    """
    Analyzes the effects of a move by comparing before/after positions.
    """
    
    # Piece values for threat assessment
    PIECE_VALUES = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0  # Can't capture king
    }
    
    def analyze_move(self, board: chess.Board, move: chess.Move) -> MoveEffect:
        """
        Analyze what a move does - the core teaching function.
        
        Args:
            board: Position BEFORE the move
            move: The move to analyze
            
        Returns:
            MoveEffect with complete breakdown
        """
        # Snapshot before
        before = self._position_snapshot(board)
        
        # Get move info
        move_san = board.san(move)
        moving_piece = board.piece_at(move.from_square)
        captured_piece = board.piece_at(move.to_square)
        
        # Make the move
        board.push(move)
        
        # Snapshot after
        after = self._position_snapshot(board)
        
        # Analyze differences
        is_check = board.is_check()
        is_checkmate = board.is_checkmate()
        
        # Find threats created
        threats = self._find_threats(board, move, moving_piece)
        
        # Find defender removals
        defenders_removed = self._find_defender_removals(before, after, move, board)
        
        # Find line changes
        lines_opened, lines_closed = self._find_line_changes(before, after, move, board)
        
        # Piece activity change
        activity_change = self._analyze_piece_activity(before, after, move, moving_piece)
        
        # Square control changes
        squares_gained, squares_lost = self._analyze_square_control(before, after)
        
        # King safety
        king_safety = self._analyze_king_safety_impact(before, after, board)
        
        # Pawn structure
        pawn_change = self._analyze_pawn_structure_change(before, after, move, moving_piece)
        
        # Determine if forcing
        is_forcing, forcing_reason = self._is_forcing_move(board, is_check, threats, captured_piece)
        
        # Generate teaching explanation
        move_type = self._classify_move_type(threats, defenders_removed, lines_opened, captured_piece, is_check)
        main_idea = self._generate_main_idea(move_san, threats, defenders_removed, lines_opened, captured_piece, is_check)
        teaching = self._generate_teaching_explanation(
            move_san, moving_piece, threats, defenders_removed, 
            lines_opened, captured_piece, is_check, is_checkmate
        )
        
        # Followups
        followups = self._suggest_followups(board, move, threats)
        responses = self._anticipate_responses(board)
        
        # Undo the move to restore position
        board.pop()
        
        # Capture info
        captures = None
        capture_value = 0
        if captured_piece:
            captures = f"{self._piece_name(captured_piece)} on {chess.square_name(move.to_square)}"
            capture_value = self.PIECE_VALUES.get(captured_piece.piece_type, 0)
        
        return MoveEffect(
            move=chess.square_name(move.from_square) + chess.square_name(move.to_square),
            move_san=move_san,
            captures=captures,
            capture_value=capture_value,
            is_check=is_check,
            is_checkmate=is_checkmate,
            is_forcing=is_forcing,
            forcing_reason=forcing_reason,
            threats=threats,
            defenders_removed=defenders_removed,
            lines_opened=lines_opened,
            lines_closed=lines_closed,
            piece_activity_change=activity_change,
            squares_gained=squares_gained,
            squares_lost=squares_lost,
            king_safety_impact=king_safety,
            pawn_structure_change=pawn_change,
            move_type=move_type,
            main_idea=main_idea,
            teaching_explanation=teaching,
            logical_followups=followups,
            opponent_responses=responses
        )
    
    def _position_snapshot(self, board: chess.Board) -> Dict:
        """Take a snapshot of position state for comparison."""
        return {
            "attacks": self._get_all_attacks(board),
            "defenses": self._get_all_defenses(board),
            "controlled_squares": self._get_controlled_squares(board),
            "piece_positions": self._get_piece_positions(board),
            "open_files": self._get_open_files(board),
            "king_safety": self._get_king_safety_score(board)
        }
    
    def _get_all_attacks(self, board: chess.Board) -> Dict[int, Set[int]]:
        """Get all squares attacked by each piece."""
        attacks = {}
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                attacks[square] = set(board.attacks(square))
        return attacks
    
    def _get_all_defenses(self, board: chess.Board) -> Dict[int, List[int]]:
        """Get what each piece defends."""
        defenses = {}
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                defenders = []
                for defender_sq in chess.SQUARES:
                    defender = board.piece_at(defender_sq)
                    if defender and defender.color == piece.color and defender_sq != square:
                        if square in board.attacks(defender_sq):
                            defenders.append(defender_sq)
                if defenders:
                    defenses[square] = defenders
        return defenses
    
    def _get_controlled_squares(self, board: chess.Board) -> Dict[str, Set[int]]:
        """Get squares controlled by each side."""
        white_controls = set()
        black_controls = set()
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                attacks = board.attacks(square)
                if piece.color == chess.WHITE:
                    white_controls.update(attacks)
                else:
                    black_controls.update(attacks)
        
        return {"white": white_controls, "black": black_controls}
    
    def _get_piece_positions(self, board: chess.Board) -> Dict[int, chess.Piece]:
        """Get all piece positions."""
        positions = {}
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                positions[square] = piece
        return positions
    
    def _get_open_files(self, board: chess.Board) -> Set[int]:
        """Get files with no pawns."""
        open_files = set()
        for file in range(8):
            has_pawn = False
            for rank in range(8):
                sq = chess.square(file, rank)
                piece = board.piece_at(sq)
                if piece and piece.piece_type == chess.PAWN:
                    has_pawn = True
                    break
            if not has_pawn:
                open_files.add(file)
        return open_files
    
    def _get_king_safety_score(self, board: chess.Board) -> Dict[str, int]:
        """Simple king safety heuristic."""
        white_king_sq = board.king(chess.WHITE)
        black_king_sq = board.king(chess.BLACK)
        
        white_safety = 0
        black_safety = 0
        
        if white_king_sq:
            # Count pawn shield
            for sq in chess.SQUARES:
                piece = board.piece_at(sq)
                if piece and piece.piece_type == chess.PAWN and piece.color == chess.WHITE:
                    if abs(chess.square_file(sq) - chess.square_file(white_king_sq)) <= 1:
                        if chess.square_rank(sq) > chess.square_rank(white_king_sq):
                            white_safety += 1
        
        if black_king_sq:
            for sq in chess.SQUARES:
                piece = board.piece_at(sq)
                if piece and piece.piece_type == chess.PAWN and piece.color == chess.BLACK:
                    if abs(chess.square_file(sq) - chess.square_file(black_king_sq)) <= 1:
                        if chess.square_rank(sq) < chess.square_rank(black_king_sq):
                            black_safety += 1
        
        return {"white": white_safety, "black": black_safety}
    
    def _find_threats(
        self, 
        board: chess.Board, 
        move: chess.Move,
        moving_piece: chess.Piece
    ) -> List[Threat]:
        """Find threats created by the move."""
        threats = []
        
        to_square = move.to_square
        piece_color = moving_piece.color
        opponent_color = not piece_color
        
        # Get squares attacked after the move
        attacked_squares = board.attacks(to_square)
        
        # Find valuable pieces being attacked
        for sq in attacked_squares:
            target = board.piece_at(sq)
            if target and target.color == opponent_color:
                value = self.PIECE_VALUES.get(target.piece_type, 0)
                
                # Check if target is defended
                is_defended = any(
                    board.piece_at(def_sq) and board.piece_at(def_sq).color == opponent_color
                    for def_sq in board.attackers(opponent_color, sq)
                )
                
                # Higher value targets or undefended pieces are significant threats
                if value >= 3 or not is_defended:
                    threats.append(Threat(
                        threat_type=ThreatType.CAPTURE,
                        attacking_piece=f"{self._piece_symbol(moving_piece)}{chess.square_name(to_square)}",
                        target=f"{self._piece_symbol(target)}{chess.square_name(sq)}",
                        target_value=value,
                        description=f"Threatens to capture {self._piece_name(target)} on {chess.square_name(sq)}",
                        is_forcing=value >= 5 or not is_defended
                    ))
        
        # Check for fork (attacking multiple pieces)
        valuable_targets = [t for t in threats if t.target_value >= 3]
        if len(valuable_targets) >= 2:
            target_names = [t.target for t in valuable_targets[:2]]
            threats.insert(0, Threat(
                threat_type=ThreatType.FORK,
                attacking_piece=f"{self._piece_symbol(moving_piece)}{chess.square_name(to_square)}",
                target=f"{target_names[0]} and {target_names[1]}",
                target_value=sum(t.target_value for t in valuable_targets[:2]),
                description=f"Forks {target_names[0]} and {target_names[1]}!",
                is_forcing=True
            ))
        
        # Check for discovered attacks
        # (simplified - would need more complex logic for full detection)
        
        # Check for mate threats
        for legal_move in board.legal_moves:
            board.push(legal_move)
            if board.is_checkmate():
                board.pop()
                threats.append(Threat(
                    threat_type=ThreatType.MATE_THREAT,
                    attacking_piece="",
                    target="King",
                    target_value=100,
                    description=f"Threatens checkmate with {board.san(legal_move)}!",
                    is_forcing=True
                ))
                break
            board.pop()
        
        return threats
    
    def _find_defender_removals(
        self,
        before: Dict,
        after: Dict,
        move: chess.Move,
        board: chess.Board
    ) -> List[DefenderRemoval]:
        """Find pieces that lost their defender due to this move."""
        removals = []
        
        # Compare defense structures
        old_defenses = before["defenses"]
        new_defenses = after["defenses"]
        
        # Find pieces that had defenders before but not after
        for sq, defenders in old_defenses.items():
            piece = board.piece_at(sq)
            if not piece:
                continue
                
            new_defenders = new_defenses.get(sq, [])
            lost_defenders = set(defenders) - set(new_defenders)
            
            if lost_defenders and len(new_defenders) == 0:
                removals.append(DefenderRemoval(
                    removed_piece=chess.square_name(move.from_square),
                    was_defending=[chess.square_name(sq)],
                    now_vulnerable=[chess.square_name(sq)],
                    teaching_note=f"The piece that moved was defending {chess.square_name(sq)}. Now it's undefended!"
                ))
        
        return removals[:3]  # Limit to most important
    
    def _find_line_changes(
        self,
        before: Dict,
        after: Dict,
        move: chess.Move,
        board: chess.Board
    ) -> Tuple[List[FileChange], List[FileChange]]:
        """Find files and diagonals opened or closed."""
        opened = []
        closed = []
        
        chess.square_file(move.from_square)
        chess.square_file(move.to_square)
        
        # Check if a file was opened (piece moved off it)
        old_open = before["open_files"]
        new_open = after["open_files"]
        
        newly_opened = new_open - old_open
        newly_closed = old_open - new_open
        
        for file in newly_opened:
            file_name = chr(ord('a') + file) + "-file"
            opened.append(FileChange(
                change_type="opens",
                line_type="file",
                line_name=file_name,
                benefits="Rooks can use this file",
                teaching_note=f"The {file_name} is now open! Perfect for rooks."
            ))
        
        for file in newly_closed:
            file_name = chr(ord('a') + file) + "-file"
            closed.append(FileChange(
                change_type="closes",
                line_type="file",
                line_name=file_name,
                benefits="File is blocked",
                teaching_note=f"The {file_name} is now blocked."
            ))
        
        return opened, closed
    
    def _analyze_piece_activity(
        self,
        before: Dict,
        after: Dict,
        move: chess.Move,
        moving_piece: chess.Piece
    ) -> Dict[str, str]:
        """Analyze how piece activity changed."""
        changes = {}
        
        # Count squares controlled before and after for the moving piece
        from_sq = move.from_square
        to_sq = move.to_square
        
        old_attacks = before["attacks"].get(from_sq, set())
        new_attacks = after["attacks"].get(to_sq, set())
        
        old_count = len(old_attacks)
        new_count = len(new_attacks)
        
        piece_name = f"{self._piece_symbol(moving_piece)}{chess.square_name(from_sq)}"
        
        if new_count > old_count:
            changes[piece_name] = f"Improved! Now controls {new_count} squares (was {old_count})"
        elif new_count < old_count:
            changes[piece_name] = f"Controls fewer squares: {new_count} (was {old_count})"
        
        return changes
    
    def _analyze_square_control(
        self,
        before: Dict,
        after: Dict
    ) -> Tuple[List[str], List[str]]:
        """Analyze changes in square control."""
        # This is simplified - would need the color context
        old_white = before["controlled_squares"]["white"]
        new_white = after["controlled_squares"]["white"]
        
        gained = new_white - old_white
        lost = old_white - new_white
        
        # Focus on central squares
        central = {chess.D4, chess.D5, chess.E4, chess.E5, chess.C4, chess.C5, chess.F4, chess.F5}
        
        gained_central = [chess.square_name(sq) for sq in gained if sq in central]
        lost_central = [chess.square_name(sq) for sq in lost if sq in central]
        
        return gained_central[:4], lost_central[:4]
    
    def _analyze_king_safety_impact(
        self,
        before: Dict,
        after: Dict,
        board: chess.Board
    ) -> str:
        """Analyze impact on king safety."""
        old_safety = before["king_safety"]
        new_safety = after["king_safety"]
        
        white_change = new_safety["white"] - old_safety["white"]
        black_change = new_safety["black"] - old_safety["black"]
        
        if white_change < 0:
            return "Weakens White's king safety"
        elif white_change > 0:
            return "Improves White's king safety"
        elif black_change < 0:
            return "Weakens Black's king safety"
        elif black_change > 0:
            return "Improves Black's king safety"
        
        return "No significant impact on king safety"
    
    def _analyze_pawn_structure_change(
        self,
        before: Dict,
        after: Dict,
        move: chess.Move,
        moving_piece: chess.Piece
    ) -> str:
        """Analyze pawn structure changes."""
        if moving_piece.piece_type != chess.PAWN:
            return "No pawn structure change"
        
        # Check for captures (might create isolated/doubled pawns)
        to_file = chess.square_file(move.to_square)
        from_file = chess.square_file(move.from_square)
        
        if to_file != from_file:
            return f"Pawn captured, potentially changing structure on {chr(ord('a') + to_file)}-file"
        
        return "Pawn advanced"
    
    def _is_forcing_move(
        self,
        board: chess.Board,
        is_check: bool,
        threats: List[Threat],
        captured: Optional[chess.Piece]
    ) -> Tuple[bool, str]:
        """Determine if the move is forcing (opponent must respond)."""
        if is_check:
            return True, "Check - must be answered"
        
        if captured and self.PIECE_VALUES.get(captured.piece_type, 0) >= 3:
            return True, f"Captured valuable piece"
        
        forcing_threats = [t for t in threats if t.is_forcing]
        if forcing_threats:
            return True, forcing_threats[0].description
        
        return False, ""
    
    def _classify_move_type(
        self,
        threats: List[Threat],
        defenders_removed: List[DefenderRemoval],
        lines_opened: List[FileChange],
        captured: Optional[chess.Piece],
        is_check: bool
    ) -> str:
        """Classify the type of move."""
        if is_check:
            return "tactical"
        
        if any(t.threat_type in [ThreatType.FORK, ThreatType.MATE_THREAT] for t in threats):
            return "tactical"
        
        if captured:
            return "capture"
        
        if defenders_removed:
            return "positional-tactical"
        
        if lines_opened:
            return "positional"
        
        return "developing"
    
    def _generate_main_idea(
        self,
        move_san: str,
        threats: List[Threat],
        defenders_removed: List[DefenderRemoval],
        lines_opened: List[FileChange],
        captured: Optional[chess.Piece],
        is_check: bool
    ) -> str:
        """Generate a one-sentence summary of the move's purpose."""
        parts = []
        
        if is_check:
            parts.append("gives check")
        
        if captured:
            parts.append(f"captures {self._piece_name(captured)}")
        
        # Find most important threat
        if threats:
            main_threat = threats[0]
            if main_threat.threat_type == ThreatType.FORK:
                parts.append(main_threat.description)
            elif main_threat.threat_type == ThreatType.MATE_THREAT:
                parts.append("threatens checkmate")
            elif main_threat.target_value >= 5:
                parts.append(f"attacks {main_threat.target}")
        
        if lines_opened:
            parts.append(f"opens the {lines_opened[0].line_name}")
        
        if defenders_removed:
            parts.append(f"removes defender of {defenders_removed[0].now_vulnerable[0]}")
        
        if not parts:
            parts.append("improves piece position")
        
        return f"{move_san} {', '.join(parts)}"
    
    def _generate_teaching_explanation(
        self,
        move_san: str,
        moving_piece: chess.Piece,
        threats: List[Threat],
        defenders_removed: List[DefenderRemoval],
        lines_opened: List[FileChange],
        captured: Optional[chess.Piece],
        is_check: bool,
        is_checkmate: bool
    ) -> str:
        """Generate a full teaching explanation of the move."""
        parts = []
        
        # Opening statement
        parts.append(f"I played {move_san}.")
        
        # Checkmate is special
        if is_checkmate:
            parts.append("Checkmate! The game is over.")
            return " ".join(parts)
        
        # Check
        if is_check:
            parts.append("This gives check, so you must respond to it.")
        
        # Capture
        if captured:
            parts.append(f"This captures your {self._piece_name(captured)}.")
        
        # Threats
        if threats:
            main_threat = threats[0]
            if main_threat.threat_type == ThreatType.FORK:
                parts.append(f"This is a FORK - I'm attacking two pieces at once: {main_threat.target}. You can't save both!")
            elif main_threat.threat_type == ThreatType.MATE_THREAT:
                parts.append("This threatens checkmate! You need to stop it.")
            elif main_threat.target_value >= 5:
                parts.append(f"I'm now threatening your {main_threat.target}.")
        
        # Defender removal
        if defenders_removed:
            dr = defenders_removed[0]
            parts.append(f"Notice that I've removed the defender of {dr.now_vulnerable[0]}. {dr.teaching_note}")
        
        # File opening
        if lines_opened:
            lo = lines_opened[0]
            parts.append(f"This also opens the {lo.line_name}. {lo.teaching_note}")
        
        # If nothing special, talk about piece improvement
        if not threats and not captured and not is_check and not defenders_removed:
            parts.append(f"This improves my {self._piece_name(moving_piece)}'s position.")
        
        return " ".join(parts)
    
    def _suggest_followups(
        self,
        board: chess.Board,
        move: chess.Move,
        threats: List[Threat]
    ) -> List[str]:
        """Suggest logical follow-up moves."""
        followups = []
        
        if threats:
            for threat in threats[:2]:
                if threat.threat_type == ThreatType.CAPTURE:
                    followups.append(f"Execute the threat: capture {threat.target}")
        
        # Generic positional ideas
        followups.append("Improve your worst-placed piece")
        followups.append("Look for tactical opportunities")
        
        return followups[:3]
    
    def _anticipate_responses(self, board: chess.Board) -> List[str]:
        """Anticipate how opponent might respond."""
        responses = []
        
        if board.is_check():
            responses.append("Must get out of check")
        
        responses.append("Defend the threatened piece")
        responses.append("Counter-attack")
        responses.append("Improve piece positioning")
        
        return responses[:3]
    
    def _piece_symbol(self, piece: chess.Piece) -> str:
        """Get piece symbol."""
        symbols = {
            chess.KING: "K",
            chess.QUEEN: "Q",
            chess.ROOK: "R",
            chess.BISHOP: "B",
            chess.KNIGHT: "N",
            chess.PAWN: ""
        }
        return symbols.get(piece.piece_type, "")
    
    def _piece_name(self, piece: chess.Piece) -> str:
        """Get piece name."""
        names = {
            chess.KING: "King",
            chess.QUEEN: "Queen",
            chess.ROOK: "Rook",
            chess.BISHOP: "Bishop",
            chess.KNIGHT: "Knight",
            chess.PAWN: "Pawn"
        }
        return names.get(piece.piece_type, "piece")


def explain_move(board: chess.Board, move_uci: str) -> Dict:
    """
    Convenience function to explain a move.
    
    Args:
        board: Current position
        move_uci: Move in UCI format (e.g., "e2e4", "g1f3")
        
    Returns:
        Dictionary with move explanation
    """
    try:
        move = chess.Move.from_uci(move_uci)
        if move not in board.legal_moves:
            return {"error": f"Illegal move: {move_uci}"}
    except ValueError:
        return {"error": f"Invalid move format: {move_uci}"}
    
    analyzer = MoveEffectAnalyzer()
    effect = analyzer.analyze_move(board, move)
    
    return {
        "move": effect.move_san,
        "main_idea": effect.main_idea,
        "explanation": effect.teaching_explanation,
        "is_forcing": effect.is_forcing,
        "forcing_reason": effect.forcing_reason,
        "captures": effect.captures,
        "is_check": effect.is_check,
        "threats": [
            {
                "type": t.threat_type.value,
                "target": t.target,
                "description": t.description
            }
            for t in effect.threats
        ],
        "lines_opened": [
            {"line": l.line_name, "teaching": l.teaching_note}
            for l in effect.lines_opened
        ],
        "piece_activity": effect.piece_activity_change,
        "king_safety": effect.king_safety_impact,
        "move_type": effect.move_type,
        "followups": effect.logical_followups
    }
