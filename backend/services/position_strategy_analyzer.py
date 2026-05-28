"""
Position Strategy Analyzer - Deep position-specific analysis

This generates SPECIFIC strategic insights for a position, not generic advice.
A human coach would tell you:
- What the position actually required
- What threats you missed
- Why your move was wrong in THIS context
- What you should have seen

Uses Stockfish data + position analysis + LLM for human-readable explanations.
"""

import chess
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


def analyze_position_deeply(fen: str, user_color: str = "white") -> Dict[str, Any]:
    """
    Analyze a chess position to extract strategic elements.
    
    Returns piece activity, threats, tactical motifs, pawn structure details.
    """
    try:
        board = chess.Board(fen)
    except Exception as e:
        logger.error(f"Invalid FEN: {fen}, error: {e}")
        return {"error": "Invalid position"}
    
    analysis = {
        "fen": fen,
        "to_move": "white" if board.turn == chess.WHITE else "black",
        "user_color": user_color,
        "pieces": {
            "user": [],
            "opponent": []
        },
        "threats": [],
        "tactical_motifs": [],
        "piece_activity": {
            "active": [],
            "passive": [],
            "undefended": []
        },
        "pawn_structure": {
            "weaknesses": [],
            "strengths": []
        },
        "key_squares": []
    }
    
    user_is_white = user_color == "white"
    user_pieces_color = chess.WHITE if user_is_white else chess.BLACK
    
    # Catalog all pieces
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            piece_info = {
                "piece": piece.symbol().upper(),
                "square": chess.square_name(sq),
                "attacks": [chess.square_name(s) for s in board.attacks(sq)],
                "is_defended": board.is_attacked_by(piece.color, sq),
                "is_attacked": board.is_attacked_by(not piece.color, sq)
            }
            
            if piece.color == user_pieces_color:
                analysis["pieces"]["user"].append(piece_info)
            else:
                analysis["pieces"]["opponent"].append(piece_info)
    
    # Find undefended pieces
    for piece_info in analysis["pieces"]["user"]:
        if not piece_info["is_defended"] and piece_info["is_attacked"]:
            analysis["piece_activity"]["undefended"].append(piece_info)
    
    # Find threats (opponent pieces attacking user pieces)
    for opp_piece in analysis["pieces"]["opponent"]:
        for user_piece in analysis["pieces"]["user"]:
            if user_piece["square"] in opp_piece["attacks"]:
                analysis["threats"].append({
                    "attacker": f"{opp_piece['piece']} on {opp_piece['square']}",
                    "target": f"{user_piece['piece']} on {user_piece['square']}",
                    "is_defended": user_piece["is_defended"]
                })
    
    # Check for tactical motifs
    # Forks
    for piece_info in analysis["pieces"]["user"] + analysis["pieces"]["opponent"]:
        piece = board.piece_at(chess.parse_square(piece_info["square"]))
        if piece and piece.piece_type == chess.KNIGHT:
            attacked_valuable = []
            for target_sq in piece_info["attacks"]:
                target = board.piece_at(chess.parse_square(target_sq))
                if target and target.color != piece.color:
                    if target.piece_type in [chess.QUEEN, chess.ROOK, chess.KING]:
                        attacked_valuable.append(f"{target.symbol().upper()} on {target_sq}")
            if len(attacked_valuable) >= 2:
                analysis["tactical_motifs"].append({
                    "type": "fork",
                    "piece": f"Knight on {piece_info['square']}",
                    "targets": attacked_valuable
                })
    
    # Pins and skewers (simplified check)
    for rook_or_bishop in ["R", "B", "Q"]:
        for piece_info in analysis["pieces"]["opponent"]:
            if piece_info["piece"] == rook_or_bishop:
                # Check if any user piece is between this piece and a more valuable piece
                pass  # Complex analysis - simplified for now
    
    # Piece activity analysis
    for piece_info in analysis["pieces"]["user"]:
        num_attacks = len(piece_info["attacks"])
        if num_attacks >= 5:
            analysis["piece_activity"]["active"].append(piece_info)
        elif num_attacks <= 2 and piece_info["piece"] in ["R", "B", "N"]:
            analysis["piece_activity"]["passive"].append(piece_info)
    
    return analysis


def generate_move_specific_insight(
    fen_before: str,
    user_move: str,
    best_move: str,
    pv_after_best: List[str],
    cp_loss: int,
    user_color: str,
    threat: str = None  # The threat that was missed
) -> Dict[str, Any]:
    """
    Generate a specific insight about why a move was wrong and what should have been seen.
    
    This is what a human coach would tell you about THIS specific position.
    """
    try:
        board = chess.Board(fen_before)
    except Exception as e:
        return {"error": str(e)}
    
    insight = {
        "position_type": "",
        "what_you_missed": "",
        "why_your_move_was_wrong": "",
        "what_best_move_achieves": "",
        "the_idea_you_should_learn": "",
        "how_to_spot_this": "",
        "was_checkmate_threat": False
    }
    
    # Check if this was a checkmate-level blunder
    is_checkmate_blunder = cp_loss >= 9000
    
    # If there was a specific threat mentioned, use it
    if threat and is_checkmate_blunder:
        insight["what_you_missed"] = f"Your opponent had {threat} — this was checkmate (or winning)"
        insight["was_checkmate_threat"] = True
        insight["the_idea_you_should_learn"] = "Before every move, ask: 'What can my opponent do to me RIGHT NOW?'"
        insight["how_to_spot_this"] = "Look for checks, captures, and threats — in that order. If you see a check is possible against YOU, stop everything."
        
        # The best move was defensive
        insight["what_best_move_achieves"] = f"Prevents the checkmate threat of {threat}"
        insight["why_your_move_was_wrong"] = f"You played {user_move} without seeing that your opponent could play {threat} and win immediately."
        insight["position_type"] = "Your king was in immediate danger — defense was the only priority"
        
        return insight
    
    # Analyze what the best move achieves
    try:
        best_move_obj = board.parse_san(best_move)
        from_sq = best_move_obj.from_square
        to_sq = best_move_obj.to_square
        moving_piece = board.piece_at(from_sq)
        captured_piece = board.piece_at(to_sq)
        
        # What does best move capture?
        if captured_piece:
            piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
            value = piece_values.get(captured_piece.piece_type, 0)
            attacker_value = piece_values.get(moving_piece.piece_type, 0) if moving_piece else 0
            piece_name = chess.piece_name(captured_piece.piece_type).title()
            moving_piece_name = chess.piece_name(moving_piece.piece_type) if moving_piece else "piece"

            # ── SAC GATE (Parth fb_6f2a5ba1f626) ──
            # When attacker is worth MORE than the target AND the
            # destination is defended (we get recaptured), it's a
            # sacrifice — saying "wins the pawn" is the opposite of
            # what's actually happening (we LOSE material on its face
            # for an attacking compensation). Surface that.
            is_sacrifice = False
            captured_near_king = False
            if attacker_value > value:
                board_after = board.copy()
                board_after.push(best_move_obj)
                opponent_color = not board.turn
                if board_after.attackers(opponent_color, to_sq):
                    is_sacrifice = True
                    enemy_king_sq = board.king(opponent_color)
                    if enemy_king_sq is not None:
                        # Distance from the sacrificed-on square to the
                        # enemy king. <= 2 means we are tearing at the
                        # pawn shield / king cover.
                        captured_near_king = chess.square_distance(to_sq, enemy_king_sq) <= 2

            if is_sacrifice and captured_near_king and captured_piece.piece_type == chess.PAWN:
                # King-shred sacrifice — the engine's pick rips open the
                # pawn shield in front of the enemy king. Honest, accurate,
                # and tells the user WHAT to look for.
                insight["what_best_move_achieves"] = (
                    f"is a sacrifice. After the recapture your {moving_piece_name} is gone, "
                    f"but the pawn shield in front of their king is destroyed — that's the attack the engine sees."
                )
                insight["what_you_missed"] = (
                    f"a sacrifice on {chess.square_name(to_sq)} that opens the pawn shield around the enemy king"
                )
                insight["the_idea_you_should_learn"] = (
                    "When the opponent's king has a thin pawn shield, scan for piece sacrifices that "
                    "blow it open — the attacking lines that follow matter more than the material."
                )
                insight["how_to_spot_this"] = (
                    "Look at the pawns directly in front of the enemy king. If one of your pieces can capture one "
                    "of those pawns, count the attackers you'd swarm in with after the recapture."
                )
            elif is_sacrifice:
                # Sac for non-king-shred compensation (deflection, fork,
                # discovered, clearance, etc.). We don't know which, so
                # name it as a sacrifice without inventing the motif.
                insight["what_best_move_achieves"] = (
                    f"is a sacrifice — the engine sees compensation (an attack or tactic) worth more than the {piece_name.lower()}."
                )
                insight["what_you_missed"] = (
                    f"a tactical sacrifice of your {moving_piece_name}"
                )
                insight["the_idea_you_should_learn"] = (
                    "Best moves aren't always material gains. When the engine prefers a capture that "
                    "loses material on its face, look for the tactic or attack that pays for it."
                )
                insight["how_to_spot_this"] = (
                    "Ask: 'If I make this capture and they recapture, what threat or follow-up do I have next?'"
                )
            else:
                # Non-sac capture: cheaper-or-equal attacker, or undefended
                # target. Honest "wins material" framing. Lowercase verb so
                # it composes cleanly after a SAN prefix ("Nxh3+ wins...").
                insight["what_best_move_achieves"] = f"wins the {piece_name} on {chess.square_name(to_sq)} (worth {value} points)"
                insight["what_you_missed"] = f"The {piece_name} on {chess.square_name(to_sq)} was undefended or poorly defended"
                insight["the_idea_you_should_learn"] = "Before making any move, scan the board for undefended opponent pieces"
                insight["how_to_spot_this"] = "Ask yourself: 'Can any of my pieces capture something valuable right now?'"

        else:
            # Best move doesn't capture - it's positional
            board_after = board.copy()
            board_after.push(best_move_obj)
            
            # Check if it creates a threat
            is_check = board_after.is_check()
            if is_check:
                insight["what_best_move_achieves"] = f"{best_move} delivers check, forcing your opponent to respond"
                insight["what_you_missed"] = "You had a forcing move that puts pressure on the opponent"
                insight["the_idea_you_should_learn"] = "Checks are powerful because they limit opponent's options"
            else:
                # Analyze piece activity improvement
                piece_name = chess.piece_name(moving_piece.piece_type).title()
                new_attacks = len(list(board_after.attacks(to_sq)))
                old_attacks = len(list(board.attacks(from_sq)))
                
                if new_attacks > old_attacks:
                    insight["what_best_move_achieves"] = f"The {piece_name} becomes more active on {chess.square_name(to_sq)}, controlling more squares"
                else:
                    insight["what_best_move_achieves"] = f"The {piece_name} on {chess.square_name(to_sq)} is better placed strategically"
                    
    except Exception as e:
        logger.error(f"Error analyzing best move: {e}")
    
    # Analyze what user's move did wrong
    try:
        user_move_obj = board.parse_san(user_move)
        from_sq = user_move_obj.from_square
        to_sq = user_move_obj.to_square
        moving_piece = board.piece_at(from_sq)
        piece_name = chess.piece_name(moving_piece.piece_type).title()
        
        board_after_user = board.copy()
        board_after_user.push(user_move_obj)
        
        # Did it leave something undefended?
        # Did it ignore a threat?
        # Did it miss a tactic?
        
        if cp_loss >= 300:
            insight["why_your_move_was_wrong"] = f"Your {piece_name} moved to {chess.square_name(to_sq)}, but this was the wrong priority. There was a much more important move available."
        elif cp_loss >= 100:
            insight["why_your_move_was_wrong"] = f"Moving the {piece_name} to {chess.square_name(to_sq)} was too slow. The position required immediate action elsewhere."
        else:
            insight["why_your_move_was_wrong"] = f"The {piece_name} move to {chess.square_name(to_sq)} was inaccurate given what was available."
            
    except Exception as e:
        logger.error(f"Error analyzing user move: {e}")
    
    # Determine position type
    material_balance = sum(
        (1 if p.color == chess.WHITE else -1) * 
        {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}.get(p.piece_type, 0)
        for sq in chess.SQUARES
        for p in [board.piece_at(sq)]
        if p
    )
    
    is_user_white = user_color == "white"
    user_advantage = material_balance if is_user_white else -material_balance
    
    if user_advantage >= 3:
        insight["position_type"] = "You were ahead in material - the strategy was to simplify and convert"
    elif user_advantage <= -3:
        insight["position_type"] = "You were behind in material - you needed to create complications"
    else:
        insight["position_type"] = "The material was roughly equal - piece activity and tactics were key"
    
    return insight


def generate_strategic_lesson(
    game_data: Dict,
    move_evaluations: List[Dict],
    user_color: str
) -> Dict[str, Any]:
    """
    Generate a full strategic lesson for a game.
    
    This replaces the generic "trade pieces when ahead" advice with
    specific insights from THIS game.
    """
    lesson = {
        "critical_moments": [],
        "main_strategic_theme": "",
        "specific_lessons": [],
        "patterns_to_recognize": [],
        "improvement_exercises": []
    }
    
    # Find the most instructive moments (biggest mistakes)
    critical_moves = sorted(
        [m for m in move_evaluations if abs(m.get('cp_loss', 0)) >= 100],
        key=lambda x: abs(x.get('cp_loss', 0)),
        reverse=True
    )[:3]  # Top 3 most instructive moments
    
    for move in critical_moves:
        fen = move.get('fen_before', '')
        user_move = move.get('move', '')
        best_move = move.get('best_move', '')
        pv = move.get('pv_after_best', [])
        cp_loss = move.get('cp_loss', 0)
        move_num = move.get('move_number', 0)
        
        if fen and user_move and best_move:
            insight = generate_move_specific_insight(
                fen, user_move, best_move, pv, cp_loss, user_color
            )
            
            lesson["critical_moments"].append({
                "move_number": move_num,
                "fen": fen,
                "your_move": user_move,
                "best_move": best_move,
                "cp_loss": cp_loss,
                "insight": insight
            })
    
    # Determine main theme from the mistakes
    themes = []
    for moment in lesson["critical_moments"]:
        insight = moment.get("insight", {})
        if "capture" in insight.get("what_best_move_achieves", "").lower():
            themes.append("tactical_vision")
        if "check" in insight.get("what_best_move_achieves", "").lower():
            themes.append("forcing_moves")
        if "active" in insight.get("what_best_move_achieves", "").lower():
            themes.append("piece_activity")
    
    if themes:
        from collections import Counter
        most_common = Counter(themes).most_common(1)[0][0]
        theme_names = {
            "tactical_vision": "Spotting Tactical Opportunities",
            "forcing_moves": "Using Forcing Moves",
            "piece_activity": "Improving Piece Activity"
        }
        lesson["main_strategic_theme"] = theme_names.get(most_common, "Tactical Awareness")
    else:
        lesson["main_strategic_theme"] = "Critical Moment Recognition"
    
    return lesson
