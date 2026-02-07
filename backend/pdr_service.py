"""
PDR (Personalized Decision Reconstruction) Service

Generates refutation moves and explanations for chess mistakes.
Uses Stockfish for move analysis and LLM for human-readable explanations.
"""

import chess
import logging
from typing import Dict, Optional, List
import os

# Import centralized config
from config import LLM_PROVIDER, LLM_MODEL, STOCKFISH_PATH

logger = logging.getLogger(__name__)

# Try to import Stockfish
try:
    from stockfish import Stockfish
    STOCKFISH_AVAILABLE = os.path.exists(STOCKFISH_PATH)
except ImportError:
    STOCKFISH_AVAILABLE = False


def get_refutation(fen: str, user_move_san: str, depth: int = 15) -> Optional[Dict]:
    """
    Get the refutation move after user's mistake.
    
    Returns:
        {
            "refutation_move": "Qxf7+",  # Opponent's punishing reply
            "refutation_uci": "d8f7",
            "threat_square": "f7",       # The key square being attacked
            "is_check": True,
            "is_capture": True,
            "captured_piece": "pawn",
            "fen_after_user_move": "...",
            "fen_after_refutation": "..."
        }
    """
    if not STOCKFISH_AVAILABLE:
        return None
    
    try:
        stockfish = Stockfish(path=STOCKFISH_PATH, depth=depth)
        stockfish.set_fen_position(fen)
        
        # Make the user's move
        board = chess.Board(fen)
        try:
            user_move = board.parse_san(user_move_san)
        except ValueError:
            # Try UCI format
            try:
                user_move = chess.Move.from_uci(user_move_san)
            except:
                return None
        
        board.push(user_move)
        fen_after_user_move = board.fen()
        
        # Get opponent's best reply (the refutation)
        stockfish.set_fen_position(fen_after_user_move)
        best_reply = stockfish.get_best_move()
        
        if not best_reply:
            return None
        
        # Parse the refutation move
        refutation_move = chess.Move.from_uci(best_reply)
        refutation_san = board.san(refutation_move)
        
        # Determine threat square and capture info
        to_square = chess.square_name(refutation_move.to_square)
        is_capture = board.is_capture(refutation_move)
        captured_piece = None
        if is_capture:
            captured = board.piece_at(refutation_move.to_square)
            if captured:
                piece_names = {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen", 6: "king"}
                captured_piece = piece_names.get(captured.piece_type, "piece")
        
        # Make the refutation move to get final position
        board.push(refutation_move)
        is_check = board.is_check()
        fen_after_refutation = board.fen()
        
        return {
            "refutation_move": refutation_san,
            "refutation_uci": best_reply,
            "threat_square": to_square,
            "from_square": chess.square_name(refutation_move.from_square),
            "is_check": is_check,
            "is_capture": is_capture,
            "captured_piece": captured_piece,
            "fen_after_user_move": fen_after_user_move,
            "fen_after_refutation": fen_after_refutation
        }
        
    except Exception as e:
        logger.error(f"Refutation analysis error: {e}")
        return None


async def generate_idea_chain_explanation(
    fen: str,
    user_move: str,
    best_move: str,
    refutation: Dict,
    db
) -> Dict:
    """
    Generate the idea chain explanation using LLM.
    
    Returns:
        {
            "your_plan": "You wanted to trade pieces and simplify.",
            "why_felt_right": "Trading seemed safe and reduced complexity.",
            "opponent_counter": "But your opponent can now play Qxf7+",
            "why_it_works": "This attacks your king and wins the f7 pawn with check.",
            "better_plan": "Rb1 develops your rook and protects the back rank.",
            "rule": "Before trading, check if it exposes your king."
        }
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        refutation_move = refutation.get("refutation_move", "")
        is_check = refutation.get("is_check", False)
        is_capture = refutation.get("is_capture", False)
        captured_piece = refutation.get("captured_piece", "")
        
        # Build context for LLM
        check_text = " with check" if is_check else ""
        capture_text = f", winning the {captured_piece}" if is_capture and captured_piece else ""
        
        system_prompt = """You are a calm, experienced chess coach explaining a mistake to a student.
Use simple language. No engine jargon. Sound like a mentor, not a computer.
Keep each explanation under 15 words."""
        
        user_prompt = f"""Position (FEN): {fen}
Student played: {user_move}
Opponent's punishing reply: {refutation_move}{check_text}{capture_text}
Better move was: {best_move}

Generate a simple explanation with these exact 6 parts:

Format your response exactly like this:
YOUR_PLAN: [What the student was trying to achieve with their move]
WHY_FELT_RIGHT: [Why this seemed like a reasonable idea]
OPPONENT_COUNTER: [What the opponent can now do - mention {refutation_move}]
WHY_IT_WORKS: [Why the opponent's reply is strong]
BETTER_PLAN: [What {best_move} achieves]
RULE: [A simple rule to remember for next time]"""

        import uuid
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"pdr_idea_{uuid.uuid4().hex[:8]}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o-mini")
        
        message = UserMessage(text=user_prompt)
        response = await chat.send_message(message)
        
        # Parse response
        text = response.strip() if isinstance(response, str) else str(response)
        
        result = {
            "your_plan": "",
            "why_felt_right": "",
            "opponent_counter": "",
            "why_it_works": "",
            "better_plan": "",
            "rule": ""
        }
        
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith("YOUR_PLAN:"):
                result["your_plan"] = line.replace("YOUR_PLAN:", "").strip()
            elif line.startswith("WHY_FELT_RIGHT:"):
                result["why_felt_right"] = line.replace("WHY_FELT_RIGHT:", "").strip()
            elif line.startswith("OPPONENT_COUNTER:"):
                result["opponent_counter"] = line.replace("OPPONENT_COUNTER:", "").strip()
            elif line.startswith("WHY_IT_WORKS:"):
                result["why_it_works"] = line.replace("WHY_IT_WORKS:", "").strip()
            elif line.startswith("BETTER_PLAN:"):
                result["better_plan"] = line.replace("BETTER_PLAN:", "").strip()
            elif line.startswith("RULE:"):
                result["rule"] = line.replace("RULE:", "").strip()
        
        # Ensure we have all fields
        if not result["your_plan"]:
            result["your_plan"] = f"You played {user_move}, perhaps to simplify or gain material."
        if not result["opponent_counter"]:
            result["opponent_counter"] = f"But now your opponent has {refutation_move}."
        if not result["rule"]:
            result["rule"] = "Before each move, ask: what is my opponent's best reply?"
        
        return result
        
    except Exception as e:
        logger.error(f"LLM explanation error: {e}")
        # Return fallback explanations
        refutation_move = refutation.get("refutation_move", "a strong reply")
        return {
            "your_plan": f"You played {user_move}, perhaps to simplify or gain material.",
            "why_felt_right": "It looked like a reasonable move in the position.",
            "opponent_counter": f"But now your opponent has {refutation_move}.",
            "why_it_works": "This move creates immediate threats you must address.",
            "better_plan": f"{best_move} was stronger, keeping your position solid.",
            "rule": "Before each move, ask: what is my opponent's best reply?"
        }


def get_simple_refutation_fallback(fen: str, user_move: str, best_move: str) -> Dict:
    """
    Fallback when Stockfish is not available - use chess.py for basic analysis.
    """
    try:
        board = chess.Board(fen)
        
        # Make user's move
        try:
            move = board.parse_san(user_move)
        except:
            try:
                move = chess.Move.from_uci(user_move)
            except:
                return None
        
        board.push(move)
        fen_after = board.fen()
        
        # Get a reasonable-looking reply (first capture or check)
        refutation = None
        for legal_move in board.legal_moves:
            if board.is_capture(legal_move) or board.gives_check(legal_move):
                refutation = legal_move
                break
        
        if not refutation:
            refutation = list(board.legal_moves)[0] if board.legal_moves else None
        
        if not refutation:
            return None
        
        refutation_san = board.san(refutation)
        to_square = chess.square_name(refutation.to_square)
        is_capture = board.is_capture(refutation)
        
        board.push(refutation)
        
        return {
            "refutation_move": refutation_san,
            "refutation_uci": refutation.uci(),
            "threat_square": to_square,
            "from_square": chess.square_name(refutation.from_square),
            "is_check": board.is_check(),
            "is_capture": is_capture,
            "captured_piece": None,
            "fen_after_user_move": fen_after,
            "fen_after_refutation": board.fen()
        }
        
    except Exception as e:
        logger.error(f"Fallback refutation error: {e}")
        return None


async def generate_why_options(fen: str, best_move: str, user_move: str, refutation: Dict, db) -> Dict:
    """
    Generate "why is this better" options to verify user understanding.
    Returns one correct reason and two plausible but wrong reasons.
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import uuid
        import random
        
        refutation_move = refutation.get("refutation_move", "") if refutation else ""
        
        system_prompt = """You are a chess coach creating a multiple choice question.
Use simple language. No chess jargon. Think like an Indian chess coach explaining to a student."""
        
        user_prompt = f"""Position (FEN): {fen}
Correct move: {best_move}
Wrong move the student played: {user_move}
If they play {user_move}, opponent can reply: {refutation_move}

Create 3 short reasons (max 12 words each) for why {best_move} is better:
- ONE correct reason (the real tactical/strategic reason)
- TWO plausible but wrong reasons (sound reasonable but aren't the main point)

Format exactly like this:
CORRECT: [the actual reason this move is good]
WRONG1: [sounds reasonable but not the key reason]
WRONG2: [sounds reasonable but not the key reason]"""

        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"pdr_why_{uuid.uuid4().hex[:8]}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o-mini")
        
        message = UserMessage(text=user_prompt)
        response = await chat.send_message(message)
        
        text = response.strip() if isinstance(response, str) else str(response)
        
        correct_reason = ""
        wrong_reasons = []
        
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith("CORRECT:"):
                correct_reason = line.replace("CORRECT:", "").strip()
            elif line.startswith("WRONG1:"):
                wrong_reasons.append(line.replace("WRONG1:", "").strip())
            elif line.startswith("WRONG2:"):
                wrong_reasons.append(line.replace("WRONG2:", "").strip())
        
        if not correct_reason:
            correct_reason = f"It avoids the opponent's threat and keeps the position solid."
        if len(wrong_reasons) < 2:
            wrong_reasons = [
                "It develops a piece to a better square.",
                "It controls more central squares."
            ]
        
        # Shuffle options for presentation
        options = [
            {"text": correct_reason, "is_correct": True},
            {"text": wrong_reasons[0], "is_correct": False},
            {"text": wrong_reasons[1], "is_correct": False}
        ]
        random.shuffle(options)
        
        # Also get the continuation line after best move for animation
        best_line = get_best_continuation(fen, best_move)
        
        return {
            "options": options,
            "correct_explanation": correct_reason,
            "best_line": best_line  # For animating on board when correct
        }
        
    except Exception as e:
        logger.error(f"Why options generation error: {e}")
        return {
            "options": [
                {"text": "It avoids the opponent's immediate threat.", "is_correct": True},
                {"text": "It activates a passive piece.", "is_correct": False},
                {"text": "It prepares a pawn break.", "is_correct": False}
            ],
            "correct_explanation": "It avoids the opponent's immediate threat.",
            "best_line": None
        }


def get_best_continuation(fen: str, best_move: str, depth: int = 3) -> Optional[List[str]]:
    """
    Get the best continuation line after the best move (for animation).
    Returns list of moves in SAN notation.
    """
    if not STOCKFISH_AVAILABLE:
        return None
    
    try:
        stockfish = Stockfish(path=STOCKFISH_PATH, depth=12)
        board = chess.Board(fen)
        
        # Make the best move
        try:
            move = board.parse_san(best_move)
        except:
            try:
                move = chess.Move.from_uci(best_move)
            except:
                return None
        
        board.push(move)
        line = [best_move]
        
        # Get next few moves
        for _ in range(depth):
            stockfish.set_fen_position(board.fen())
            next_move = stockfish.get_best_move()
            if not next_move:
                break
            
            uci_move = chess.Move.from_uci(next_move)
            san = board.san(uci_move)
            line.append(san)
            board.push(uci_move)
        
        return line if len(line) > 1 else None
        
    except Exception as e:
        logger.error(f"Best continuation error: {e}")
        return None
