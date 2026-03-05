"""
Piece Metrics Analyzer

Concrete, deterministic metrics for piece evaluation.
No pseudo-science - every metric is board-verifiable.
"""

import chess
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class PieceMetrics:
    """Metrics for a single piece"""
    square: str
    piece_type: str
    color: str
    mobility: int                    # Count of legal moves
    participation: int               # Squares controlled in opponent half
    is_developed: bool               # Has moved from starting position
    is_active: bool                  # Composite: mobility + participation
    blocking_info: Optional[Dict] = None  # For bishops: what's blocking


@dataclass 
class PositionMetrics:
    """Aggregate metrics for a position"""
    # Piece counts
    white_pieces: Dict[str, List[PieceMetrics]]
    black_pieces: Dict[str, List[PieceMetrics]]
    
    # Development
    white_developed_count: int
    black_developed_count: int
    development_lead: int            # positive = white ahead
    
    # Piece activity
    white_worst_piece: Optional[PieceMetrics]
    black_worst_piece: Optional[PieceMetrics]
    
    # King safety
    white_king_safety: int           # 0-100, 100 = very safe
    black_king_safety: int
    white_castled: bool
    black_castled: bool
    
    # Pawn structure
    is_closed_position: bool
    pawn_breaks_available: List[str]
    center_tension: bool             # Pawns in contact in center
    
    # Files
    open_files: List[str]
    semi_open_white: List[str]
    semi_open_black: List[str]


class PieceMetricsAnalyzer:
    """
    Analyze piece activity and position metrics.
    All metrics are deterministic and board-verifiable.
    """
    
    # Starting squares for development tracking
    STARTING_SQUARES = {
        chess.WHITE: {
            chess.KNIGHT: [chess.B1, chess.G1],
            chess.BISHOP: [chess.C1, chess.F1],
            chess.ROOK: [chess.A1, chess.H1],
            chess.QUEEN: [chess.D1],
        },
        chess.BLACK: {
            chess.KNIGHT: [chess.B8, chess.G8],
            chess.BISHOP: [chess.C8, chess.F8],
            chess.ROOK: [chess.A8, chess.H8],
            chess.QUEEN: [chess.D8],
        }
    }
    
    def __init__(self, board: chess.Board):
        self.board = board
    
    def get_piece_mobility(self, square: chess.Square) -> int:
        """Count legal moves for piece on square"""
        piece = self.board.piece_at(square)
        if not piece:
            return 0
        
        count = 0
        for move in self.board.legal_moves:
            if move.from_square == square:
                count += 1
        return count
    
    def get_piece_participation(self, square: chess.Square) -> int:
        """Count squares controlled in opponent's half"""
        piece = self.board.piece_at(square)
        if not piece:
            return 0
        
        # Get attacked squares
        attacks = self.board.attacks(square)
        
        # Count those in opponent half
        opponent_half_start = 32 if piece.color == chess.WHITE else 0
        opponent_half_end = 64 if piece.color == chess.WHITE else 32
        
        count = 0
        for sq in attacks:
            if opponent_half_start <= sq < opponent_half_end:
                count += 1
        return count
    
    def is_piece_developed(self, square: chess.Square) -> bool:
        """Check if piece has moved from starting position"""
        piece = self.board.piece_at(square)
        if not piece:
            return False
        
        starting = self.STARTING_SQUARES.get(piece.color, {}).get(piece.piece_type, [])
        return square not in starting
    
    def get_bishop_blocking_info(self, square: chess.Square) -> Optional[Dict]:
        """
        Deterministic ray trace for bishop blocking.
        Returns info about what's blocking the bishop.
        """
        piece = self.board.piece_at(square)
        if not piece or piece.piece_type != chess.BISHOP:
            return None
        
        blocking_info = {
            "blocked_by_own_pawn": False,
            "blocking_pawn_square": None,
            "diagonal_length": 0,
            "usable_squares": 0,
        }
        
        # Check all four diagonal directions
        directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        file_idx = chess.square_file(square)
        rank_idx = chess.square_rank(square)
        
        total_squares = 0
        usable_squares = 0
        
        for df, dr in directions:
            f, r = file_idx + df, rank_idx + dr
            distance = 1
            
            while 0 <= f <= 7 and 0 <= r <= 7:
                sq = chess.square(f, r)
                total_squares += 1
                
                blocker = self.board.piece_at(sq)
                if blocker:
                    # Check if blocked by own pawn within 2 squares
                    if (blocker.color == piece.color and 
                        blocker.piece_type == chess.PAWN and 
                        distance <= 2):
                        blocking_info["blocked_by_own_pawn"] = True
                        blocking_info["blocking_pawn_square"] = chess.square_name(sq)
                    break
                else:
                    usable_squares += 1
                
                f += df
                r += dr
                distance += 1
        
        blocking_info["diagonal_length"] = total_squares
        blocking_info["usable_squares"] = usable_squares
        
        return blocking_info
    
    def get_rook_file_info(self, square: chess.Square) -> Dict:
        """Check if rook is on open/semi-open file"""
        piece = self.board.piece_at(square)
        if not piece or piece.piece_type != chess.ROOK:
            return {"on_open_file": False, "on_semi_open": False}
        
        file_idx = chess.square_file(square)
        
        white_pawn_on_file = False
        black_pawn_on_file = False
        
        for rank in range(8):
            sq = chess.square(file_idx, rank)
            p = self.board.piece_at(sq)
            if p and p.piece_type == chess.PAWN:
                if p.color == chess.WHITE:
                    white_pawn_on_file = True
                else:
                    black_pawn_on_file = True
        
        is_open = not white_pawn_on_file and not black_pawn_on_file
        is_semi_open = (
            (piece.color == chess.WHITE and not white_pawn_on_file and black_pawn_on_file) or
            (piece.color == chess.BLACK and not black_pawn_on_file and white_pawn_on_file)
        )
        
        return {"on_open_file": is_open, "on_semi_open": is_semi_open}
    
    def get_development_count(self, color: chess.Color) -> int:
        """Count developed minor pieces"""
        count = 0
        for piece_type in [chess.KNIGHT, chess.BISHOP]:
            starting_squares = self.STARTING_SQUARES[color].get(piece_type, [])
            for sq in starting_squares:
                piece = self.board.piece_at(sq)
                # If piece is NOT on starting square, it's developed
                if not piece or piece.piece_type != piece_type:
                    count += 1
        return count
    
    def is_castled(self, color: chess.Color) -> bool:
        """Check if king has castled (approximate by king position)"""
        king_sq = self.board.king(color)
        if king_sq is None:
            return False
        
        # Typical castled king positions
        if color == chess.WHITE:
            return king_sq in [chess.G1, chess.C1, chess.H1, chess.B1]
        else:
            return king_sq in [chess.G8, chess.C8, chess.H8, chess.B8]
    
    def get_king_safety(self, color: chess.Color) -> int:
        """
        King safety score 0-100.
        Factors: castled, pawn shield, open files near king, attackers.
        """
        score = 50  # Baseline
        
        king_sq = self.board.king(color)
        if king_sq is None:
            return 0
        
        # Bonus for castling
        if self.is_castled(color):
            score += 20
        
        # Check pawn shield
        king_file = chess.square_file(king_sq)
        king_rank = chess.square_rank(king_sq)
        
        pawn_direction = 1 if color == chess.WHITE else -1
        shield_rank = king_rank + pawn_direction
        
        if 0 <= shield_rank <= 7:
            shield_pawns = 0
            for f in [king_file - 1, king_file, king_file + 1]:
                if 0 <= f <= 7:
                    sq = chess.square(f, shield_rank)
                    piece = self.board.piece_at(sq)
                    if piece and piece.piece_type == chess.PAWN and piece.color == color:
                        shield_pawns += 1
            score += shield_pawns * 10
        
        # Penalty for king in center (not castled)
        if not self.is_castled(color) and 2 <= king_file <= 5:
            score -= 15
        
        return max(0, min(100, score))
    
    def is_closed_position(self) -> bool:
        """
        Determine if position is closed.
        Closed = many pawn chains, blocked center pawns.
        """
        # Count center pawns
        center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
        center_pawns = 0
        
        for sq in center_squares:
            piece = self.board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN:
                center_pawns += 1
        
        # Count pawn contacts (pawns facing each other)
        pawn_contacts = 0
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == chess.WHITE:
                # Check if black pawn directly ahead
                ahead = sq + 8
                if ahead < 64:
                    opp = self.board.piece_at(ahead)
                    if opp and opp.piece_type == chess.PAWN and opp.color == chess.BLACK:
                        pawn_contacts += 1
        
        return center_pawns >= 2 or pawn_contacts >= 3
    
    def get_open_files(self) -> Tuple[List[str], List[str], List[str]]:
        """Return open files, semi-open for white, semi-open for black"""
        open_files = []
        semi_open_white = []
        semi_open_black = []
        
        for file_idx in range(8):
            file_name = chess.FILE_NAMES[file_idx]
            white_pawn = False
            black_pawn = False
            
            for rank in range(8):
                sq = chess.square(file_idx, rank)
                piece = self.board.piece_at(sq)
                if piece and piece.piece_type == chess.PAWN:
                    if piece.color == chess.WHITE:
                        white_pawn = True
                    else:
                        black_pawn = True
            
            if not white_pawn and not black_pawn:
                open_files.append(file_name)
            elif not white_pawn and black_pawn:
                semi_open_white.append(file_name)
            elif white_pawn and not black_pawn:
                semi_open_black.append(file_name)
        
        return open_files, semi_open_white, semi_open_black
    
    def get_worst_piece(self, color: chess.Color) -> Optional[PieceMetrics]:
        """Find the least active piece for the given color"""
        worst = None
        worst_score = float('inf')
        
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if not piece or piece.color != color:
                continue
            if piece.piece_type in [chess.PAWN, chess.KING]:
                continue
            
            mobility = self.get_piece_mobility(sq)
            participation = self.get_piece_participation(sq)
            score = mobility + participation * 2
            
            if score < worst_score:
                worst_score = score
                worst = PieceMetrics(
                    square=chess.square_name(sq),
                    piece_type=chess.piece_name(piece.piece_type),
                    color="white" if color == chess.WHITE else "black",
                    mobility=mobility,
                    participation=participation,
                    is_developed=self.is_piece_developed(sq),
                    is_active=score > 5,
                )
        
        return worst
    
    def analyze(self) -> PositionMetrics:
        """Full position analysis"""
        open_files, semi_open_w, semi_open_b = self.get_open_files()
        
        return PositionMetrics(
            white_pieces={},  # Can be expanded
            black_pieces={},
            white_developed_count=self.get_development_count(chess.WHITE),
            black_developed_count=self.get_development_count(chess.BLACK),
            development_lead=self.get_development_count(chess.WHITE) - self.get_development_count(chess.BLACK),
            white_worst_piece=self.get_worst_piece(chess.WHITE),
            black_worst_piece=self.get_worst_piece(chess.BLACK),
            white_king_safety=self.get_king_safety(chess.WHITE),
            black_king_safety=self.get_king_safety(chess.BLACK),
            white_castled=self.is_castled(chess.WHITE),
            black_castled=self.is_castled(chess.BLACK),
            is_closed_position=self.is_closed_position(),
            pawn_breaks_available=[],  # Can be expanded
            center_tension=self._has_center_tension(),
            open_files=open_files,
            semi_open_white=semi_open_w,
            semi_open_black=semi_open_b,
        )
    
    def _has_center_tension(self) -> bool:
        """Check if there's pawn tension in the center"""
        # d4 vs d5 or e4 vs e5 tension
        d4 = self.board.piece_at(chess.D4)
        d5 = self.board.piece_at(chess.D5)
        e4 = self.board.piece_at(chess.E4)
        e5 = self.board.piece_at(chess.E5)
        
        d_tension = (d4 and d4.piece_type == chess.PAWN and 
                     d5 and d5.piece_type == chess.PAWN and
                     d4.color != d5.color)
        e_tension = (e4 and e4.piece_type == chess.PAWN and 
                     e5 and e5.piece_type == chess.PAWN and
                     e4.color != e5.color)
        
        return d_tension or e_tension


def analyze_position(fen: str) -> PositionMetrics:
    """Helper function to analyze a position from FEN"""
    board = chess.Board(fen)
    analyzer = PieceMetricsAnalyzer(board)
    return analyzer.analyze()


def get_bishop_blocking(fen: str, square: str) -> Optional[Dict]:
    """Helper to check if bishop is blocked"""
    board = chess.Board(fen)
    analyzer = PieceMetricsAnalyzer(board)
    sq = chess.parse_square(square)
    return analyzer.get_bishop_blocking_info(sq)
