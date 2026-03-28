"""
Teaching Coach Service

A human-like chess coach that TEACHES, not defeats.
The goal is collaborative learning - help the player understand chess,
not just play against them.

Core Principles:
1. ASK before TELL - Guide thinking with questions
2. SUGGEST moves to teach concepts, don't just play against
3. EXPLAIN what's happening in the position
4. CELEBRATE learning, not just good moves
5. Make mistakes TEACHABLE moments, not punishments
"""

import chess
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class TeachingMode(Enum):
    OPENING_LESSON = "opening_lesson"      # Teaching a specific opening
    GUIDED_PRACTICE = "guided_practice"    # Suggesting moves, explaining why
    FREE_PLAY = "free_play"                # Let them play, comment on interesting moments
    POSITION_STUDY = "position_study"      # Deep dive into a specific position


@dataclass
class TeachingMessage:
    """A message from the coach that teaches something"""
    message: str
    question: Optional[str] = None         # Question to ask the student
    suggested_move: Optional[str] = None   # Move suggestion with arrow
    explanation: Optional[str] = None      # Why this matters
    follow_up: Optional[str] = None        # What to look for next
    tone: str = "encouraging"              # encouraging, curious, celebrating


class TeachingCoach:
    """A coach that teaches chess, not just plays it"""
    
    def __init__(self):
        self.position_themes = self._load_position_themes()
    
    def _load_position_themes(self) -> Dict[str, List[str]]:
        """Common position themes and what to teach about them"""
        return {
            "open_center": [
                "The center is open - pieces are very active here",
                "With no pawns blocking, your rooks and queen have open lines",
                "Knights are slightly weaker in open positions - bishops shine"
            ],
            "closed_center": [
                "The center is locked - this is a slow, strategic game",
                "Knights can hop over pawns - they're strong in closed positions",
                "Look for pawn breaks to open things up when you're ready"
            ],
            "pawn_tension": [
                "There's tension in the center - pawns are attacking each other",
                "You have a choice: capture, advance, or maintain the tension",
                "Maintaining tension keeps options open but requires careful play"
            ],
            "development_lead": [
                "You're ahead in development - your pieces are more active",
                "Try to open the position before they catch up",
                "Don't let them castle safely and equalize"
            ],
            "king_safety": [
                "King safety is critical - always think about where your king is",
                "Castling connects your rooks and tucks your king away",
                "An exposed king can be attacked even with material advantage"
            ],
        }
    
    def generate_teaching_for_user_move(
        self,
        user_move: str,
        fen_before: str,
        fen_after: str,
        move_quality: str,
        best_move: str,
        opening_name: Optional[str] = None,
        move_number: int = 1
    ) -> TeachingMessage:
        """
        Generate teaching commentary for a user's move.
        Focus on UNDERSTANDING, not just evaluation.
        """
        board_before = chess.Board(fen_before)
        board_after = chess.Board(fen_after)
        
        # Determine what to teach based on the move
        if move_quality in ["blunder", "mistake"]:
            return self._teach_from_mistake(
                user_move, fen_before, best_move, move_number
            )
        elif move_quality == "great" or user_move == best_move:
            return self._celebrate_good_move(
                user_move, fen_before, fen_after, opening_name, move_number
            )
        else:
            return self._guide_understanding(
                user_move, fen_before, fen_after, best_move, opening_name, move_number
            )
    
    def _teach_from_mistake(
        self,
        user_move: str,
        fen_before: str,
        best_move: str,
        move_number: int
    ) -> TeachingMessage:
        """Turn a mistake into a learning moment"""
        board = chess.Board(fen_before)
        
        # Analyze what they missed
        explanation = self._explain_why_move_was_weak(board, user_move, best_move)
        
        return TeachingMessage(
            message=f"Interesting choice with {user_move}. Let me show you something...",
            question=f"What do you think {best_move} would have achieved here?",
            suggested_move=best_move,
            explanation=explanation,
            follow_up="Don't worry - this is how we learn. Let's continue and watch for similar patterns.",
            tone="encouraging"
        )
    
    def _celebrate_good_move(
        self,
        user_move: str,
        fen_before: str,
        fen_after: str,
        opening_name: Optional[str],
        move_number: int
    ) -> TeachingMessage:
        """Celebrate and reinforce good understanding"""
        board = chess.Board(fen_after)
        
        # Explain WHY it was good
        if opening_name and move_number <= 10:
            return TeachingMessage(
                message=f"Excellent! {user_move} is exactly right in the {opening_name}.",
                question="Do you know why this move is strong here?",
                explanation=self._explain_move_purpose(fen_before, user_move),
                tone="celebrating"
            )
        else:
            return TeachingMessage(
                message=f"Good thinking with {user_move}!",
                question="What's your plan from here?",
                explanation=self._explain_move_purpose(fen_before, user_move),
                tone="celebrating"
            )
    
    def _guide_understanding(
        self,
        user_move: str,
        fen_before: str,
        fen_after: str,
        best_move: str,
        opening_name: Optional[str],
        move_number: int
    ) -> TeachingMessage:
        """Guide them to deeper understanding"""
        board = chess.Board(fen_after)
        
        # Analyze the position
        position_theme = self._identify_position_theme(board)
        
        return TeachingMessage(
            message=f"{user_move} is playable. Let me ask you something...",
            question=self._generate_guiding_question(board, position_theme),
            explanation=self.position_themes.get(position_theme, [""])[0] if position_theme else None,
            tone="curious"
        )
    
    def generate_teaching_for_coach_move(
        self,
        coach_move: str,
        fen_before: str,
        fen_after: str,
        opening_name: Optional[str] = None,
        move_number: int = 1,
        teaching_moment: Optional[str] = None
    ) -> TeachingMessage:
        """
        Explain the coach's move in a teaching way.
        Not "I played X" but "Watch this - X because..."
        """
        board_after = chess.Board(fen_after)
        
        if teaching_moment:
            # We have specific teaching for this move
            return TeachingMessage(
                message=teaching_moment,
                question="Can you see why this move makes sense?",
                follow_up="Your turn - what are you thinking?",
                tone="encouraging"
            )
        
        # Generate position-based teaching
        if move_number <= 6 and opening_name:
            return self._teach_opening_move(coach_move, fen_before, fen_after, opening_name)
        else:
            return self._teach_positional_concept(coach_move, fen_before, fen_after, move_number)
    
    def _teach_opening_move(
        self,
        move: str,
        fen_before: str,
        fen_after: str,
        opening_name: str
    ) -> TeachingMessage:
        """Teach an opening move with context"""
        board = chess.Board(fen_after)
        
        purpose = self._explain_move_purpose(fen_before, move)
        
        return TeachingMessage(
            message=f"In the {opening_name}, this {move} has a specific purpose.",
            question="What squares or pieces do you think this move affects?",
            explanation=purpose,
            follow_up="Now it's your turn. Think about how to respond to this idea.",
            tone="encouraging"
        )
    
    def _teach_positional_concept(
        self,
        move: str,
        fen_before: str,
        fen_after: str,
        move_number: int
    ) -> TeachingMessage:
        """Teach based on positional concepts"""
        board_before = chess.Board(fen_before)
        board_after = chess.Board(fen_after)
        
        # Identify what the move accomplishes
        concept = self._identify_move_concept(board_before, move, board_after)
        
        return TeachingMessage(
            message=f"Watch this {move}...",
            question=f"Do you see what this {move} is preparing?",
            explanation=concept,
            follow_up="Your move - keep this idea in mind!",
            tone="curious"
        )
    
    def generate_position_explanation(self, fen: str) -> TeachingMessage:
        """Explain what's happening in a position - the big picture"""
        board = chess.Board(fen)
        
        explanations = []
        
        # Material
        material = self._assess_material(board)
        if material:
            explanations.append(material)
        
        # Pawn structure
        pawn_structure = self._assess_pawn_structure(board)
        if pawn_structure:
            explanations.append(pawn_structure)
        
        # King safety
        king_safety = self._assess_king_safety(board)
        if king_safety:
            explanations.append(king_safety)
        
        # Piece activity
        activity = self._assess_piece_activity(board)
        if activity:
            explanations.append(activity)
        
        combined = " ".join(explanations) if explanations else "The position is roughly equal - both sides have chances."
        
        return TeachingMessage(
            message=combined,
            question="What do you think is the most important factor here?",
            tone="curious"
        )
    
    def suggest_move_to_learn(
        self,
        fen: str,
        opening_name: Optional[str] = None,
        concept_to_teach: Optional[str] = None
    ) -> TeachingMessage:
        """Suggest a move for the student to play to learn a concept"""
        board = chess.Board(fen)
        
        # This would integrate with engine to find instructive moves
        # For now, return a general teaching approach
        
        return TeachingMessage(
            message="Let me suggest a move here...",
            question="Before I show you, what are you considering?",
            follow_up="Think about what each candidate move accomplishes.",
            tone="encouraging"
        )
    
    # === Helper methods ===
    
    def _explain_why_move_was_weak(self, board: chess.Board, move: str, best_move: str) -> str:
        """Explain why a move was not the best"""
        try:
            # Parse the moves
            user_move_obj = board.parse_san(move)
            best_move_obj = board.parse_san(best_move)
            
            # Compare what they accomplish
            user_to_square = chess.square_name(user_move_obj.to_square)
            best_to_square = chess.square_name(best_move_obj.to_square)
            
            return f"Your {move} went to {user_to_square}, but {best_move} to {best_to_square} was stronger because it creates more active play."
        except:
            return f"{best_move} was the stronger option here."
    
    def _explain_move_purpose(self, fen: str, move: str) -> str:
        """Explain the purpose of a move"""
        board = chess.Board(fen)
        
        try:
            move_obj = board.parse_san(move)
            piece = board.piece_at(move_obj.from_square)
            to_square = chess.square_name(move_obj.to_square)
            
            piece_names = {
                chess.PAWN: "pawn",
                chess.KNIGHT: "knight",
                chess.BISHOP: "bishop",
                chess.ROOK: "rook",
                chess.QUEEN: "queen",
                chess.KING: "king"
            }
            
            piece_name = piece_names.get(piece.piece_type, "piece") if piece else "piece"
            
            # Check if it's a capture
            if board.is_capture(move_obj):
                captured = board.piece_at(move_obj.to_square)
                if captured:
                    captured_name = piece_names.get(captured.piece_type, "piece")
                    return f"This {piece_name} captures the {captured_name}, winning material."
            
            # Check if it's a developing move
            if piece and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                rank = chess.square_rank(move_obj.to_square)
                if (board.turn == chess.WHITE and rank >= 2) or (board.turn == chess.BLACK and rank <= 5):
                    return f"Developing the {piece_name} to an active square, controlling the center."
            
            # Check if it attacks something
            board.push(move_obj)
            if board.is_check():
                board.pop()
                return "This move gives check, forcing a response."
            board.pop()
            
            # Default explanation
            return f"This {piece_name} moves to {to_square}, improving its position."
            
        except:
            return "This move improves the position."
    
    def _identify_position_theme(self, board: chess.Board) -> Optional[str]:
        """Identify the main theme of a position"""
        # Check center pawns
        center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
        center_pawns = sum(1 for sq in center_squares if board.piece_at(sq) and board.piece_at(sq).piece_type == chess.PAWN)
        
        if center_pawns >= 2:
            return "pawn_tension" if self._has_pawn_tension(board) else "closed_center"
        elif center_pawns == 0:
            return "open_center"
        
        # Check development
        white_developed = self._count_developed_pieces(board, chess.WHITE)
        black_developed = self._count_developed_pieces(board, chess.BLACK)
        
        if abs(white_developed - black_developed) >= 2:
            return "development_lead"
        
        # Check king safety
        if not board.has_castling_rights(chess.WHITE) and not board.has_castling_rights(chess.BLACK):
            return "king_safety"
        
        return None
    
    def _has_pawn_tension(self, board: chess.Board) -> bool:
        """Check if there's pawn tension in the center"""
        # Simplified check - are there pawns that can capture each other?
        for sq in [chess.D4, chess.D5, chess.E4, chess.E5]:
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN:
                # Check if any pawn can capture this one
                attackers = board.attackers(not piece.color, sq)
                if any(board.piece_at(a) and board.piece_at(a).piece_type == chess.PAWN for a in attackers):
                    return True
        return False
    
    def _count_developed_pieces(self, board: chess.Board, color: chess.Color) -> int:
        """Count how many minor pieces are developed"""
        count = 0
        back_rank = 0 if color == chess.WHITE else 7
        
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == color and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                if chess.square_rank(sq) != back_rank:
                    count += 1
        
        return count
    
    def _generate_guiding_question(self, board: chess.Board, theme: Optional[str]) -> str:
        """Generate a question to guide the student's thinking"""
        questions = {
            "open_center": "With the center open, which pieces become more valuable?",
            "closed_center": "The center is blocked - what type of piece works best here?",
            "pawn_tension": "There's tension in the center - should we capture, advance, or wait?",
            "development_lead": "One side is ahead in development - how should we use that?",
            "king_safety": "Where is the safest place for your king right now?",
        }
        
        if theme and theme in questions:
            return questions[theme]
        
        return "What do you think is the most important thing in this position?"
    
    def _assess_material(self, board: chess.Board) -> Optional[str]:
        """Assess material balance"""
        white_material = sum(
            len(board.pieces(pt, chess.WHITE)) * val
            for pt, val in [(chess.PAWN, 1), (chess.KNIGHT, 3), (chess.BISHOP, 3), (chess.ROOK, 5), (chess.QUEEN, 9)]
        )
        black_material = sum(
            len(board.pieces(pt, chess.BLACK)) * val
            for pt, val in [(chess.PAWN, 1), (chess.KNIGHT, 3), (chess.BISHOP, 3), (chess.ROOK, 5), (chess.QUEEN, 9)]
        )
        
        diff = white_material - black_material
        
        if abs(diff) >= 3:
            side = "White" if diff > 0 else "Black"
            return f"{side} is up material - about {abs(diff)} points worth."
        
        return None
    
    def _assess_pawn_structure(self, board: chess.Board) -> Optional[str]:
        """Assess pawn structure"""
        # Check for doubled pawns
        for color in [chess.WHITE, chess.BLACK]:
            for file in range(8):
                pawns_on_file = sum(1 for rank in range(8) 
                    if board.piece_at(chess.square(file, rank)) 
                    and board.piece_at(chess.square(file, rank)).piece_type == chess.PAWN
                    and board.piece_at(chess.square(file, rank)).color == color)
                if pawns_on_file >= 2:
                    side = "White" if color == chess.WHITE else "Black"
                    return f"{side} has doubled pawns - a long-term weakness."
        
        return None
    
    def _assess_king_safety(self, board: chess.Board) -> Optional[str]:
        """Assess king safety"""
        white_king_sq = board.king(chess.WHITE)
        black_king_sq = board.king(chess.BLACK)
        
        if white_king_sq and chess.square_file(white_king_sq) == 4:  # King still on e-file
            if not board.has_castling_rights(chess.WHITE):
                return "White's king is stuck in the center - this could be dangerous."
        
        if black_king_sq and chess.square_file(black_king_sq) == 4:
            if not board.has_castling_rights(chess.BLACK):
                return "Black's king is stuck in the center - an opportunity to attack."
        
        return None
    
    def _assess_piece_activity(self, board: chess.Board) -> Optional[str]:
        """Assess piece activity"""
        white_developed = self._count_developed_pieces(board, chess.WHITE)
        black_developed = self._count_developed_pieces(board, chess.BLACK)
        
        diff = white_developed - black_developed
        
        if diff >= 2:
            return "White has better piece development - the pieces are more active."
        elif diff <= -2:
            return "Black has better piece development - ready to attack."
        
        return None
    
    def _identify_move_concept(self, board_before: chess.Board, move: str, board_after: chess.Board) -> str:
        """Identify what concept a move demonstrates"""
        try:
            move_obj = board_before.parse_san(move)
            piece = board_before.piece_at(move_obj.from_square)
            
            if not piece:
                return "This move improves the position."
            
            # Check for development
            if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                back_rank = 0 if piece.color == chess.WHITE else 7
                if chess.square_rank(move_obj.from_square) == back_rank:
                    return "Developing a piece - getting it into the game early is important."
            
            # Check for castling
            if piece.piece_type == chess.KING and abs(move_obj.from_square - move_obj.to_square) == 2:
                return "Castling - protecting the king and connecting the rooks."
            
            # Check for center control
            center = [chess.D4, chess.D5, chess.E4, chess.E5]
            if move_obj.to_square in center:
                return "Fighting for the center - whoever controls the center has more space."
            
            # Check for attack
            board_after_move = board_before.copy()
            board_after_move.push(move_obj)
            if board_after_move.is_check():
                return "Giving check - forcing the opponent to respond to the attack."
            
            return "Improving the piece's position."
            
        except:
            return "This move has strategic importance."
