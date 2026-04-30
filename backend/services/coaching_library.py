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
        {"explanation": "{piece} to {square}. Natural spot for it in the {opening}.", "question": "Where are you going to put your {piece}?", "hint": "Pick squares that give your pieces room to do something."},
        {"explanation": "{move} — my {piece} is out. This is how the {opening} usually goes.", "question": "How many of your pieces are still sitting on the back row?", "hint": "Faster you get them out, better off you are."},
        {"explanation": "{move} — getting my {piece} into the game.", "question": "What's your plan for getting your pieces out?", "hint": "Knights and bishops first. Queen later."},
    ],

    "opening_develop_bishop": [
        {"explanation": "Bishop to {square}. Sees a lot of the board from here.", "question": "Where do you want your bishops?", "hint": "Bishops like long lines with nothing in the way."},
        {"explanation": "{move} — putting my bishop where it actually does something.", "question": "What's my bishop looking at from {square}?", "hint": "Follow the line from {square} — what's down it?"},
        {"explanation": "{move} — my bishop's got a clear view from {square}.", "question": "Are your bishops doing anything?", "hint": "A bishop stuck behind your own pawns isn't helping."},
    ],

    "opening_pawn_center": [
        {"explanation": "Pawn to {square} — fighting for the middle. We're in the {opening}.", "question": "Who's got more in the middle right now?", "hint": "Look at d4, d5, e4, e5 — who's got more there?"},
        {"explanation": "{move} — fighting for the middle in the {opening}.", "question": "What are you doing about the middle?", "hint": "Pawns on e4/d4 or e5/d5 are your best tool."},
        {"explanation": "{move}. In the {opening}, the middle is where the game gets decided.", "question": "Do you have a pawn in the middle?", "hint": "If not, think about how to get one there."},
    ],

    "opening_pawn_flank": [
        # Coach voice rewrite (2026-04-27): plain words, short sentences,
        # the way a friend who plays chess would actually say it.
        # No jargon ("flank", "initiative"). Pivot to concrete user move.
        {"explanation": "{move}. Just a small move on the side.", "question": "What can you do in the middle?", "hint": "A center pawn, or get a knight or bishop out."},
        {"explanation": "I played {move} — staying on the edge. The middle is yours.", "question": "What's your best move in the center?", "hint": "When I'm playing on the side, answer in the middle."},
    ],

    "opening_pawn_support": [
        {"explanation": "{move} — quiet move, just keeping my setup solid.", "question": "Is your side of the board steady, or are there gaps?", "hint": "Sometimes the best move is the calm one that closes a hole."},
    ],

    # ─── Coach captures (piece-specific) — routed when move_type=="capture" ───

    "capture_trade": [
        {"explanation": "{move} — took your {target}. Whenever you capture, check what you give back.", "question": "Is this trade good for me or you?", "hint": "Count what's left: who's got the better pieces after?"},
        {"explanation": "Took your {target} with {move}.", "question": "Did I have to take, or did I want to?", "hint": "When someone trades, ask: did their side get better or worse after?"},
    ],

    "capture_free": [
        {"explanation": "Took your {target} — nobody was guarding it.", "question": "Who was supposed to be watching that {target}?", "hint": "Before every move, look at each of your pieces — who's defending it?"},
        {"explanation": "{move} — free piece. Your {target} on {square} had no help.", "question": "How do you stop pieces from hanging like that?", "hint": "After every move you make, check each piece — who's protecting it?"},
    ],

    # ─── Coach retreats / piece shuffles — not development ───

    "retreat_knight": [
        {"explanation": "Pulled my knight back to {square}. Sometimes the right move is backwards.", "question": "What's my knight up to from {square}?", "hint": "Not every move goes forward. Going back to a better spot is fine."},
    ],

    "retreat_bishop": [
        {"explanation": "Bishop's stepping back to {square}. Keeps it safe and ready.", "question": "Why might my bishop be better here than further forward?", "hint": "Bishops want the right diagonal, not the longest one."},
    ],

    "piece_reposition": [
        {"explanation": "Moving my {piece} to {square} — just finding it a better spot.", "question": "Is your {piece} on a good square right now?", "hint": "Every piece has a best spot. Worth a few seconds to find it."},
    ],

    "opening_castle": [
        {"explanation": "Castled. King's safe, rook's free to play.", "question": "Have you castled yet?", "hint": "If your king is still in the middle, get it tucked away."},
        {"explanation": "King's tucked into the corner. Rook's already in the game.", "question": "Is your king safe?", "hint": "Castling is usually the most important thing to do in the first 10 moves."},
    ],

    "opening_generic": [
        {"explanation": "{move}. We're in the {opening} — solid start.", "question": "Know the main idea of this opening?", "hint": "Every opening has a plan. Think about which pieces to move first."},
        {"explanation": "{move} — playing the {opening}. We're both still setting up.", "question": "Which piece are you bringing out next?", "hint": "Look at your back row — who hasn't moved yet?"},
    ],

    # ─── MIDDLEGAME: Teaching intents ───

    "hanging_piece_capture": [
        {"explanation": "Your {target} on {square} had nobody guarding it. So I took it.", "question": "Did you check if your stuff was safe before you moved?", "hint": "Before every move, look around: is anything of mine alone?"},
        {"explanation": "Took your {target} on {square}. Nobody was watching it.", "question": "What was supposed to be guarding your {target}?", "hint": "Count who's protecting each of your important pieces."},
        {"explanation": "Your {target} was just sitting on {square} alone. Free for me.", "question": "How do you stop leaving pieces alone like that?", "hint": "After every move, ask: did I leave anything hanging?"},
    ],

    "hanging_piece_create": [
        {"explanation": "{move}. Look at your pieces — is anything left alone now?", "question": "Which one of your pieces has no protection?", "hint": "One of your pieces just lost its guard. Find it."},
        {"explanation": "{move} — something on your side just got exposed. See it?", "question": "Which of your pieces is in trouble?", "hint": "Go piece by piece: who's guarding each one?"},
        {"explanation": "{move}. Something just changed — look at your pieces.", "question": "What's different after my move?", "hint": "One of your pieces lost its protection. Find it before I do."},
    ],

    "fork_created": [
        {"explanation": "{move} — my {piece} is hitting two things at once.", "question": "Can you see both pieces I'm attacking?", "hint": "My {piece} on {square} is aiming at more than one target."},
        {"explanation": "{move}. My {piece} is on two of your pieces at the same time.", "question": "Which one will you save?", "hint": "You can't save both. Save the bigger one."},
        {"explanation": "{move} — fork. My {piece} attacks two things.", "question": "Where's my {piece} looking? Count the targets.", "hint": "Two of your pieces are under attack right now."},
    ],

    "threat_created_specific": [
        {"explanation": "{move}. Your {target} on {target_square} is in trouble now.", "question": "What are you going to do about your {target}?", "hint": "It's got {defenders} guarding it. Enough?"},
        {"explanation": "{move} — now I'm aiming at your {target} on {target_square}.", "question": "See the threat?", "hint": "Look at what my piece on {square} is attacking."},
    ],

    "threat_created_general": [
        {"explanation": "{move}. Something just changed on the board.", "question": "What does my move threaten?", "hint": "Look at what my piece on {square} can do next turn."},
        {"explanation": "{move}. Always look at what changed after I move.", "question": "Before you play, what should you check first?", "hint": "Ask: what is my opponent threatening?"},
    ],

    "rook_open_file": [
        {"explanation": "Rook to {square} — open file, no pawns blocking it.", "question": "Got a rook on an open file?", "hint": "Rooks are strongest when they've got a clear path up and down."},
    ],

    "quiet_developing": [
        {"explanation": "{move} — just getting my {piece} to a better spot.", "question": "What's your plan for next move?", "hint": "Look at your pieces — which one is doing the least?"},
        {"explanation": "{move} — small move, makes my side a bit better.", "question": "Which of your pieces is just sitting there?", "hint": "Find your laziest piece. Move it somewhere useful."},
    ],

    # ─── TRAPS ───

    "trap_hint": [
        {"explanation": "Careful here — there's a trick: the {trap_name}.", "question": "See the danger?", "hint": "Try the obvious move in your head — see what happens."},
        {"explanation": "Watch out — the {trap_name} catches a lot of players right here.", "question": "Know what to avoid?", "hint": "The obvious move is actually the mistake."},
    ],

    "trap_fell_for": [
        {"explanation": "That's the {trap_name}. {trap_explanation}", "question": "See why that move was a mistake now?", "hint": "Look at what I can do next."},
        {"explanation": "You walked into the {trap_name}. No worries — now you'll remember it. {trap_explanation}", "question": "What should you have played instead?", "hint": "The safe move was anything except {trap_move}."},
    ],

    "trap_avoided": [
        {"explanation": "Nice — you didn't fall for the {trap_name}.", "question": "Did you spot the trap, or just play a safe move?", "hint": "Either way — good."},
        {"explanation": "Good — the {trap_name} catches a lot of players, but not you.", "question": "What would have happened if you played the trap move?", "hint": "Think about what the trick was."},
    ],

    # ─── ENDGAME ───

    "endgame_king_active": [
        {"explanation": "King to {square}. In endgames, your king has to fight too.", "question": "Where's your king? Is it doing anything?", "hint": "In endgames the king is a fighting piece — get it off the back row."},
    ],

    "endgame_pawn_push": [
        {"explanation": "Pushed my pawn to {square}. A pawn nobody can stop is gold in the endgame.", "question": "Can you stop my pawn from reaching the other end?", "hint": "If nothing blocks or attacks it, it's going to queen."},
    ],
}


# ═══════════════════════════════════════════════════════════════════
# USER MOVE FEEDBACK — what the coach says about the student's move
# ═══════════════════════════════════════════════════════════════════

USER_FEEDBACK = {

    # ─── Blunders ───

    "blunder_hanging_piece": [
        {"narrative": "Wait — your {piece} on {square} just lost its guard. Before you move anything, always check: is my stuff safe?", "question": "Which piece did you leave alone?", "hint": "Look at {square}. Who's guarding your {piece}?", "plan": "Pause for a second. Check every one of your pieces is protected."},
        {"narrative": "Your {piece} is sitting on {square} with nobody watching it. Free for me.", "question": "Who was guarding your {piece} before you moved?", "hint": "Whatever was protecting it — you moved away from it.", "plan": "Before your next move, count guards on every piece."},
    ],

    "blunder_allows_fork": [
        {"narrative": "Wait — did you see that? {threat} That's the game right there. Before you move, look at where my pieces can jump.", "question": "Can you see how my {threat_piece} gets to {threat_square}?", "hint": "Look at every square my {threat_piece} can reach next move.", "plan": "Before every move, ask: can my opponent fork anything?"},
        {"narrative": "Oh — {threat} You just lost your biggest piece. Knights are sneaky — always check their jumps.", "question": "What squares can my {threat_piece} reach?", "hint": "Knights jump over pieces — check every landing square.", "plan": "Habit: before moving, check the opponent's knight squares."},
    ],

    "blunder_allows_capture": [
        {"narrative": "Wait — {threat} That's a piece, just gone.", "question": "Did you check that square was safe before moving?", "hint": "Look — what just lost its protection?", "plan": "Before every move, scan: is anything of mine alone?"},
    ],

    "blunder_allows_mate": [
        {"narrative": "Checkmate. {threat} Before anything else, always check if your king is safe.", "question": "See the checkmate?", "hint": "Look at every piece aiming at your king.", "plan": "King safety first. Always."},
    ],

    "blunder_calculation": [
        {"narrative": "You didn't see what comes next. After your move, things go bad.", "question": "Did you think about what I'd play after?", "hint": "Try the two-move rule: your move, my reply. What happens?", "plan": "Slow down. Ask: what will my opponent do after this?"},
        {"narrative": "Move looks fine at first — but one move ahead, it falls apart.", "question": "What can I do now that I couldn't do before?", "hint": "Something changed after your move. Find it.", "plan": "Before moving, always check my best reply."},
    ],

    "blunder_king_safety": [
        {"narrative": "Your king is in trouble. King safety comes first — always.", "question": "Is your king safe right now?", "hint": "Look at every piece pointing at your king.", "plan": "Get your king safe. Nothing else matters right now."},
    ],

    # ─── Mistakes ───

    "mistake_hanging_piece": [
        {"narrative": "Good idea — but your {piece} on {square} doesn't have enough cover.", "question": "Is your {piece} on {square} actually safe?", "hint": "Count: how many pieces attacking it vs defending it?", "plan": "Make sure your pieces are safe before going for the plan."},
    ],

    "mistake_calculation": [
        {"narrative": "{best_move} was the stronger move here.", "question": "What did I have as a reply to your move?", "hint": "Before you commit, ask: what's my opponent's best answer?", "plan": "Check my replies before you decide."},
    ],

    "mistake_check_opponent": [
        {"narrative": "You didn't look at what I just did. My last move changed something.", "question": "What did my last move threaten?", "hint": "Go back — what's my piece doing now?", "plan": "After every move I make, ask: what changed?"},
    ],

    "mistake_development": [
        {"narrative": "You moved the same piece again. Bring a new one out instead.", "question": "How many of your pieces are still on the back row?", "hint": "Every piece sitting at home is a piece not helping.", "plan": "Get a new piece out before moving one that's already played."},
    ],

    # ─── Inaccuracies ───

    "inaccuracy_generic": [
        {"narrative": "Fine move — there was something a touch better.", "question": "Can you think of what might've been stronger?", "hint": "Look at what the best move does that yours doesn't."},
    ],

    # ─── Good moves ───

    "good_best_move": [
        {"narrative": "Yes! {move} — that's exactly the right move. Well played."},
        {"narrative": "Perfect! {move} is the best move here. You saw it."},
        {"narrative": "{move} — spot on. That's the right move here."},
    ],

    "good_move": [
        {"narrative": "{move}. Solid — keeps things under control."},
        {"narrative": "{move}. Looks fine."},
        {"narrative": "{move} — clean move."},
    ],

    "good_theory": [
        {"narrative": "{move} — book move. Right plan in this opening."},
        {"narrative": "That's theory — {move} is what the books play here."},
    ],

    # ─── Brilliant ───

    "brilliant_sacrifice": [
        {"narrative": "Brilliant! You gave up your {piece} with {move} — but it wins. That takes real vision."},
        {"narrative": "{move} — you gave up your {piece} for something bigger. Incredible."},
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
    move_category: Optional[str] = None,
) -> Optional[str]:
    """
    Map v2 intent + context to a library scenario key.
    Returns the key or None if no match.

    move_category (when passed) is the PositionFacts MoveCategory value and
    refines pawn routing so a flank push like a3 doesn't get center-push text.
    """
    # CAPTURES — route before anything else. A capture is never "development".
    # has_target indicates we know what got taken; route to trade vs free capture.
    if move_type == "capture":
        return "capture_free" if has_target else "capture_trade"

    # RETREATS — based on move_category. A knight going back to its home rank
    # isn't "opening_develop_knight" — it's a retreat.
    if move_category == "knight_retreat":
        return "retreat_knight"
    if move_category == "bishop_retreat":
        return "retreat_bishop"

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
            # Use move_category to route precisely — old path blindly returned center.
            if move_category in ("central_pawn_push", "extended_center_pawn"):
                return "opening_pawn_center"
            if move_category == "flank_pawn_push":
                return "opening_pawn_flank"
            if move_category == "bishop_pawn_push":
                return "opening_pawn_support"
            # No category info — fall back to generic, not center.
            return "opening_pawn_support"
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
