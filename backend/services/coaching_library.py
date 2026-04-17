"""
Coaching Library — human-sounding templates that replace LLM for common scenarios.

Every template sounds like a coach talking to a friend. No textbook language.
Variables get filled from our detectors: {piece}, {square}, {opening}, {target}, etc.

Usage:
    from services.coaching_library import get_coaching_text
    text = get_coaching_text("opening_develop_knight", piece="knight", square="f6", opening="Italian Game")
    # Returns: {"explanation": "...", "question": "...", "hint": "..."}

Falls back to None if no template matches — then LLM handles it.
"""

import random
from typing import Optional, Dict


# ═══════════════════════════════════════════════════════════════════
# COACH MOVE EXPLANATIONS — what the coach says about their own move
# ═══════════════════════════════════════════════════════════════════

COACH_MOVE = {

    # ─── OPENING: Piece development ───

    "opening_develop_knight": [
        {"explanation": "I brought my {piece} to {square}. That's a natural spot for it in the {opening}.", "question": "Where are you going to put your {piece}?", "hint": "Think about which squares give your pieces the most room."},
        {"explanation": "{move} — my {piece} is in the game now. This is how the {opening} starts.", "question": "How many of your pieces are still on the back row?", "hint": "The faster you get your pieces out, the better."},
        {"explanation": "I played {move} to get my {piece} working. We're in the {opening}.", "question": "What's your plan for getting your pieces out?", "hint": "Knights and bishops should come out before the queen."},
    ],

    "opening_develop_bishop": [
        {"explanation": "My bishop is on {square} now — it can see a lot of the board from there.", "question": "Where do you want your bishops?", "hint": "Bishops like long open lines where nothing blocks them."},
        {"explanation": "{move} — putting my bishop where it does the most work.", "question": "Can you see what my bishop is looking at from {square}?", "hint": "Follow the diagonal from {square} and see what's there."},
        {"explanation": "I played {move}. My bishop has a nice view from {square}.", "question": "Are your bishops doing anything useful right now?", "hint": "A bishop stuck behind its own pawns isn't helping."},
    ],

    "opening_pawn_center": [
        {"explanation": "I pushed my pawn to {square} to fight for the center. We're playing the {opening}.", "question": "Who has more control of the center right now?", "hint": "Look at d4, d5, e4, e5 — who has more pieces and pawns there?"},
        {"explanation": "{move} — fighting for the center in the {opening}.", "question": "What are you doing to control the center?", "hint": "Pawns on e4/d4 or e5/d5 are your best tools for this."},
        {"explanation": "I played {move}. In the {opening}, the center is where the fight starts.", "question": "Do you have a pawn in the center?", "hint": "If not, think about how to get one there."},
    ],

    "opening_castle": [
        {"explanation": "I castled. My king is safe now and my rook can join the fight.", "question": "Have you castled yet?", "hint": "If your king is still in the center, it's time to fix that."},
        {"explanation": "King is tucked away, rook is connected. That's what castling does.", "question": "Is your king safe right now?", "hint": "Castling is usually the most important thing to do in the first 10 moves."},
    ],

    "opening_generic": [
        {"explanation": "I played {move}. We're in the {opening} — a solid way to start.", "question": "Do you know the main idea of this opening?", "hint": "Every opening has a plan. Think about what pieces you want to move first."},
        {"explanation": "{move} — following the {opening}. Both sides are setting up.", "question": "What's your next piece to develop?", "hint": "Look at your back row — who hasn't moved yet?"},
    ],

    # ─── MIDDLEGAME: Teaching intents ───

    "hanging_piece_capture": [
        {"explanation": "Your {target} on {square} had no protection — so I took it.", "question": "Before you moved, did you check if everything was safe?", "hint": "Before every move, scan the board: is anything of mine without protection?"},
        {"explanation": "I took your {target} on {square}. It was sitting there with no help.", "question": "What was supposed to protect your {target}?", "hint": "Count the pieces guarding each of your important pieces."},
        {"explanation": "Your {target} was alone on {square}. I took it for free.", "question": "How do you avoid leaving pieces without protection?", "hint": "After every move, ask yourself: did I leave anything hanging?"},
    ],

    "hanging_piece_create": [
        {"explanation": "I played {move}. Look carefully at your pieces — is everything protected?", "question": "Can you find which piece has no protection?", "hint": "One of your pieces is in trouble right now. Scan the board."},
        {"explanation": "{move} — now something on your side has no help. Can you see it?", "question": "Which one of your pieces is in danger?", "hint": "Check each of your pieces: who is guarding it?"},
        {"explanation": "I just played {move}. Something changed. Look at your pieces.", "question": "What's different after my move?", "hint": "One of your pieces lost its protection. Find it before I take it."},
    ],

    "fork_created": [
        {"explanation": "{move} — my {piece} is now attacking two things at once.", "question": "Can you see what two pieces I'm threatening?", "hint": "My {piece} on {square} is looking at more than one target."},
        {"explanation": "I played {move}. My {piece} is hitting two of your pieces at the same time.", "question": "Which piece will you save?", "hint": "You can't save both — pick the more valuable one."},
        {"explanation": "{move} — that's a double attack from my {piece}.", "question": "Where is my {piece} looking? Count the targets.", "hint": "Two of your pieces are under attack at the same time."},
    ],

    "threat_created_specific": [
        {"explanation": "I played {move}. Your {target} on {target_square} is now in danger.", "question": "What are you going to do about your {target}?", "hint": "It has {defenders} pieces protecting it. Is that enough?"},
        {"explanation": "{move} — now I'm looking at your {target} on {target_square}.", "question": "Can you see the threat?", "hint": "Check what my piece on {square} is attacking."},
    ],

    "threat_created_general": [
        {"explanation": "I played {move}. Something changed on the board.", "question": "What does my move threaten?", "hint": "Look at what my piece on {square} can do next turn."},
        {"explanation": "{move} — always check what changed after your opponent moves.", "question": "Before you play, what should you look at first?", "hint": "Ask yourself: what is my opponent threatening?"},
    ],

    "rook_open_file": [
        {"explanation": "I put my rook on {square} — it's an open file with no pawns in the way.", "question": "Do you have a rook on an open file?", "hint": "Rooks are most powerful when they have a clear path up and down."},
    ],

    "quiet_developing": [
        {"explanation": "I played {move} — getting my {piece} to a better spot.", "question": "What's your plan for the next move?", "hint": "Think about which of your pieces needs to be more active."},
        {"explanation": "{move} — making my position a bit better, step by step.", "question": "Which of your pieces is doing the least right now?", "hint": "Find your worst piece and improve it."},
    ],

    # ─── TRAPS ───

    "trap_hint": [
        {"explanation": "Be careful here... this position has a well-known trick called the {trap_name}.", "question": "Can you see the danger?", "hint": "Look at what happens if you play the obvious move."},
        {"explanation": "Watch out — we're close to the {trap_name}. A lot of players fall for this.", "question": "Do you know what to avoid here?", "hint": "The obvious move here is actually a mistake."},
    ],

    "trap_fell_for": [
        {"explanation": "That's the {trap_name}! This is a well-known trick in the {opening}. {trap_explanation}", "question": "Can you see why that move was a mistake now?", "hint": "Look at what I can do next."},
        {"explanation": "You fell for the {trap_name}. Don't worry — now you'll remember it forever. {trap_explanation}", "question": "What should you have played instead?", "hint": "The safe move was to avoid {trap_move}."},
    ],

    "trap_avoided": [
        {"explanation": "Nice — you avoided the {trap_name}! A lot of players fall for that here.", "question": "Did you see the trap, or did you just play a solid move?", "hint": "Either way, good job staying safe."},
        {"explanation": "Good awareness! The {trap_name} catches many players, but not you.", "question": "What would have happened if you played the trap move?", "hint": "Think about what the trick was."},
    ],

    # ─── ENDGAME ───

    "endgame_king_active": [
        {"explanation": "I moved my king to {square}. In the endgame, the king needs to be active.", "question": "Where is your king? Is it in the action?", "hint": "In endgames, your king is a fighting piece — don't leave it on the back row."},
    ],

    "endgame_pawn_push": [
        {"explanation": "I pushed my pawn to {square}. In endgames, passed pawns are gold.", "question": "Can you stop my pawn from reaching the other side?", "hint": "A pawn that nobody can block is very dangerous."},
    ],
}


# ═══════════════════════════════════════════════════════════════════
# USER MOVE FEEDBACK — what the coach says about the student's move
# ═══════════════════════════════════════════════════════════════════

USER_FEEDBACK = {

    # ─── Blunders ───

    "blunder_hanging_piece": [
        {"narrative": "Wait — your {piece} on {square} has no protection now! Before you move anything, always check: is everything safe?", "question": "Which piece did you leave without protection?", "hint": "Look at {square}. Who is guarding your {piece} there?", "plan": "Take a breath. Check all your pieces are safe."},
        {"narrative": "Your {piece} is just sitting on {square} with nobody guarding it. That's free for me to take.", "question": "What was protecting your {piece} before you moved?", "hint": "Whatever was guarding it — you moved it away.", "plan": "Before your next move, count the guards on every piece."},
    ],

    "blunder_allows_fork": [
        {"narrative": "Wait — did you see that? {threat} That's the game right there. Before moving, always check what your opponent's pieces can jump to.", "question": "Can you see how {threat_piece} gets to {threat_square}?", "hint": "Look at where their {threat_piece} can go next move.", "plan": "Before every move, ask: can my opponent fork anything?"},
        {"narrative": "Oh no — {threat} You just lost your most valuable piece. Always look at your opponent's knight moves — they're the trickiest.", "question": "What squares can their {threat_piece} reach?", "hint": "Knights can jump over pieces — check all their landing squares.", "plan": "Build the habit: before moving, check opponent's knight moves."},
    ],

    "blunder_allows_capture": [
        {"narrative": "Wait — {threat} You just gave away a piece for free!", "question": "Did you check if that square was safe before moving?", "hint": "Look at what's now without protection.", "plan": "Before every move, scan: is anything of mine without protection?"},
    ],

    "blunder_allows_mate": [
        {"narrative": "That's checkmate! {threat} Always check if your king is safe before anything else.", "question": "Can you see the checkmate?", "hint": "Look at all the pieces pointing at your king.", "plan": "King safety first — always."},
    ],

    "blunder_calculation": [
        {"narrative": "You didn't see what happens next. After your move, something bad happens.", "question": "Did you think about what I would do after your move?", "hint": "Try the 2-move rule: your move, then my reply. What happens?", "plan": "Slow down. Think: what will my opponent do?"},
        {"narrative": "This move looks okay at first, but look one step ahead — it falls apart.", "question": "What can I do now that I couldn't do before?", "hint": "Something changed after your move. Find it.", "plan": "Before moving, always check your opponent's best reply."},
    ],

    "blunder_king_safety": [
        {"narrative": "Your king is in trouble! You need to think about king safety first.", "question": "Is your king safe right now?", "hint": "Look at the pieces pointing at your king.", "plan": "Get your king safe. That's the only priority right now."},
    ],

    # ─── Mistakes ───

    "mistake_hanging_piece": [
        {"narrative": "Good idea, but you left your {piece} without enough protection on {square}.", "question": "Is your {piece} on {square} safe?", "hint": "Count how many pieces are attacking it vs defending it.", "plan": "Check your pieces are safe before going for your plan."},
    ],

    "mistake_calculation": [
        {"narrative": "Not bad, but there was something better. You stopped thinking one move too early.", "question": "What did you miss about my reply?", "hint": "Think one move deeper — what can I do now?", "plan": "Try to see your opponent's best answer before you commit."},
    ],

    "mistake_check_opponent": [
        {"narrative": "You didn't look at what I just did. My last move changed something important.", "question": "What did my last move threaten?", "hint": "Go back and look at what my piece is now doing.", "plan": "After every opponent move, ask: what changed?"},
    ],

    "mistake_development": [
        {"narrative": "You moved the same piece again instead of bringing a new one into the game.", "question": "How many of your pieces are still on the back row?", "hint": "Every piece sitting at home is a piece not helping.", "plan": "Develop a new piece before moving one that's already out."},
    ],

    # ─── Inaccuracies ───

    "inaccuracy_generic": [
        {"narrative": "That's okay, but there was something a bit better.", "question": "Can you think of what might have been stronger here?", "hint": "Look at what the best move achieves that your move doesn't."},
    ],

    # ─── Good moves ───

    "good_best_move": [
        {"narrative": "Yes! {move} — that's exactly the right move. Well played."},
        {"narrative": "Perfect! {move} is the best move here. You saw it."},
        {"narrative": "{move} — spot on. That's what the engine plays too."},
    ],

    "good_move": [
        {"narrative": "Good move. {move} keeps your position solid."},
        {"narrative": "{move} — nice. You're playing well here."},
        {"narrative": "Solid choice. {move} keeps things under control."},
    ],

    "good_theory": [
        {"narrative": "{move} — that's the book move. You know your openings."},
        {"narrative": "That's theory! {move} is exactly what the books say to play here."},
    ],

    # ─── Brilliant ───

    "brilliant_sacrifice": [
        {"narrative": "Brilliant! You gave up your {piece} with {move} — but it wins. That takes real vision."},
        {"narrative": "Wow! {move} — giving up your {piece} for something bigger. Incredible."},
    ],
}


# ═══════════════════════════════════════════════════════════════════
# LOOKUP FUNCTION
# ═══════════════════════════════════════════════════════════════════

def get_coach_move_text(scenario_key: str, **kwargs) -> Optional[Dict]:
    """
    Get a random coaching template for a coach move scenario.
    Returns dict with explanation, question, hint — or None if no template.
    """
    templates = COACH_MOVE.get(scenario_key)
    if not templates:
        return None

    template = random.choice(templates)
    try:
        result = {}
        for key, value in template.items():
            result[key] = value.format(**kwargs) if isinstance(value, str) else value
        return result
    except KeyError:
        # Missing variable — return template as-is with unfilled vars
        return template


def get_user_feedback_text(scenario_key: str, **kwargs) -> Optional[Dict]:
    """
    Get a random coaching template for user move feedback.
    Returns dict with narrative, question, hint, plan — or None if no template.
    """
    templates = USER_FEEDBACK.get(scenario_key)
    if not templates:
        return None

    template = random.choice(templates)
    try:
        result = {}
        for key, value in template.items():
            result[key] = value.format(**kwargs) if isinstance(value, str) else value
        return result
    except KeyError:
        return template


def match_coach_scenario(
    intent: str,
    move_type: str,
    piece: str,
    phase: str,
    opening_detected: bool = False,
    has_target: bool = False,
    target_piece: Optional[str] = None,
) -> Optional[str]:
    """
    Map v2 intent + context to a library scenario key.
    Returns the key or None if no match.
    """
    # Opening phase — only use opening templates when actually IN the opening,
    # not just because an opening was detected at the start of the game.
    if phase == "opening":
        if move_type == "castle":
            return "opening_castle"
        if piece == "knight":
            return "opening_develop_knight"
        if piece == "bishop":
            return "opening_develop_bishop"
        if piece == "pawn":
            return "opening_pawn_center"
        return "opening_generic"

    # Middlegame/endgame with intent
    if intent == "hanging_piece_punishment":
        if move_type == "capture":
            return "hanging_piece_capture"
        return "hanging_piece_create"

    if intent == "fork_opportunity":
        return "fork_created"

    if intent == "threat_awareness":
        if has_target:
            return "threat_created_specific"
        return "threat_created_general"

    # Endgame
    if phase == "endgame":
        if piece == "king":
            return "endgame_king_active"
        if piece == "pawn":
            return "endgame_pawn_push"

    # Fallback
    return "quiet_developing"


def match_user_scenario(
    severity: str,
    fundamental: Optional[str] = None,
    is_best: bool = False,
    is_sacrifice: bool = False,
    is_theory: bool = False,
    opponent_threat: Optional[str] = None,  # "fork", "capture", "mate"
) -> Optional[str]:
    """
    Map user move severity + fundamental to a library scenario key.
    """
    # Blunders with specific opponent threats — most urgent
    if severity == "blunder" and opponent_threat:
        if opponent_threat == "fork":
            return "blunder_allows_fork"
        if opponent_threat == "mate":
            return "blunder_allows_mate"
        if opponent_threat == "capture":
            return "blunder_allows_capture"

    if severity == "brilliant" or is_sacrifice:
        return "brilliant_sacrifice"

    if severity == "good":
        if is_best:
            return "good_best_move"
        if is_theory:
            return "good_theory"
        return "good_move"

    if severity == "blunder":
        if fundamental == "hanging_pieces":
            return "blunder_hanging_piece"
        if fundamental == "king_safety":
            return "blunder_king_safety"
        return "blunder_calculation"

    if severity == "mistake":
        if fundamental == "hanging_pieces":
            return "mistake_hanging_piece"
        if fundamental == "check_opponents_move":
            return "mistake_check_opponent"
        if fundamental == "development":
            return "mistake_development"
        return "mistake_calculation"

    if severity == "inaccuracy":
        return "inaccuracy_generic"

    return None
