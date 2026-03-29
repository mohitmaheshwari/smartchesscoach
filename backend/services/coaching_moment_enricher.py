"""
Coaching Moment Enricher

Transforms raw critical moment data into structured coaching objects.
Each moment gets: thinking_lens, coach_prompt, thinking_questions,
lesson_takeaway, and reflection data.

All coaching logic lives here — frontend only renders.
"""


# ============================================================
# THINKING LENS MAPPING
# ============================================================
# Maps backend tags to guided attention lenses

THINKING_LENS_MAP = {
    # Tactical tags
    "missed_tactic": {
        "label": "Tactical Opportunity",
        "lens": "Look for forcing moves: checks, captures, or threats.",
        "icon": "zap"
    },
    "hung_piece": {
        "label": "Hanging Piece",
        "lens": "Check if any piece is undefended or poorly defended.",
        "icon": "alert-triangle"
    },
    "one_move_blunder": {
        "label": "Piece Safety",
        "lens": "Before you move, ask: is anything left undefended?",
        "icon": "alert-triangle"
    },
    # Calculation / vision tags
    "didnt_see_far_enough": {
        "label": "Calculation Required",
        "lens": "Calculate the sequence move by move. What happens after your move?",
        "icon": "brain"
    },
    "calculation_error": {
        "label": "Calculation Required",
        "lens": "Calculate the forcing sequence move by move.",
        "icon": "brain"
    },
    # Opening tags
    "opening_theory_deviation": {
        "label": "Opening Decision",
        "lens": "Think about development, center control, and king safety.",
        "icon": "book-open"
    },
    "early_queen_adventure": {
        "label": "Opening Principle",
        "lens": "Is your queen safe? Are your minor pieces developed?",
        "icon": "crown"
    },
    # Positional tags
    "threw_winning_position": {
        "label": "Convert Your Advantage",
        "lens": "You're ahead. Look for the safest way to maintain your edge.",
        "icon": "trending-up"
    },
    "defensive_resource": {
        "label": "Defense Required",
        "lens": "Identify what your opponent is threatening before moving.",
        "icon": "shield"
    },
    "piece_activity": {
        "label": "Piece Activity",
        "lens": "Look for a move that improves your least active piece.",
        "icon": "move"
    },
    "king_safety": {
        "label": "King Safety",
        "lens": "Evaluate whether the king needs protection or evacuation.",
        "icon": "crown"
    },
    "pawn_structure": {
        "label": "Pawn Structure",
        "lens": "Consider how pawn moves change the long-term position.",
        "icon": "layers"
    },
    "positional_squeeze": {
        "label": "Positional Pressure",
        "lens": "Look for ways to restrict your opponent's pieces.",
        "icon": "lock"
    },
    # Endgame tags
    "endgame_technique_error": {
        "label": "Endgame Technique",
        "lens": "Focus on king activity and pawn promotion potential.",
        "icon": "flag"
    },
    "endgame_technique": {
        "label": "Endgame Technique",
        "lens": "Focus on king activity and pawn promotion potential.",
        "icon": "flag"
    },
    # Time pressure
    "time_pressure_blunder": {
        "label": "Time Pressure",
        "lens": "Even under pressure, check for threats before moving.",
        "icon": "clock"
    },
    "time_pressure": {
        "label": "Critical Decision",
        "lens": "Slow down. This position requires careful thought.",
        "icon": "clock"
    },
}

# Default lens for unrecognized tags
DEFAULT_LENS = {
    "label": "Key Moment",
    "lens": "Pause and study the position. Something important is happening.",
    "icon": "eye"
}


# ============================================================
# COACH PROMPTS
# ============================================================
# Contextual introductions based on position characteristics

def generate_coach_prompt(moment_data):
    """Generate a short coach prompt based on position context."""
    tags = moment_data.get("tags", {})
    primary_tag = tags.get("primary_tag", "")
    threat = moment_data.get("threat", "")
    cp_loss = abs(moment_data.get("cp_loss", 0))
    insight = moment_data.get("insight", {})
    position = moment_data.get("position_analysis", {})

    # Check for specific threats
    threats = position.get("threats", [])
    has_threat = len(threats) > 0 or bool(threat)

    # Check for undefended pieces
    undefended = position.get("piece_activity", {}).get("undefended", [])
    has_undefended = len([u for u in undefended if u.get("is_attacked")]) > 0

    # Check for opponent undefended pieces
    opp_pieces = position.get("pieces", {}).get("opponent", [])
    opp_undefended = [p for p in opp_pieces if not p.get("is_defended") and p.get("piece") != "K"]

    if primary_tag == "hung_piece" and has_undefended:
        return "Pause here. One of your pieces is in danger."

    if primary_tag == "hung_piece" and opp_undefended:
        return "Take a moment. Your opponent may have left something undefended."

    if primary_tag in ("missed_tactic", "one_move_blunder"):
        return "Look carefully. There's a tactical idea in this position."

    if primary_tag in ("defensive_resource",) or has_threat:
        return "Your opponent just created a threat. Can you spot it?"

    if primary_tag == "king_safety":
        return "The king position is critical here. What does it need?"

    if primary_tag == "piece_activity":
        return "One of your pieces isn't pulling its weight. Can you activate it?"

    if primary_tag in ("endgame_technique", "endgame_technique_error"):
        return "Endgame precision matters. Every move counts."

    if primary_tag == "pawn_structure":
        return "Think about the long-term consequences of your pawn moves."

    if primary_tag == "threw_winning_position":
        return "You're ahead here. How do you keep the advantage?"

    if primary_tag == "opening_theory_deviation":
        return "Opening decision point. What do the principles tell you?"

    if primary_tag == "early_queen_adventure":
        return "Your queen is out early. Is it safe?"

    if primary_tag == "didnt_see_far_enough":
        return "This position requires deeper calculation. Look further ahead."

    if primary_tag in ("time_pressure", "time_pressure_blunder"):
        return "Even in time trouble, pause for one safety check."

    if cp_loss >= 300:
        return "Pause here. Something important changed after your opponent's last move."

    if cp_loss >= 200:
        return "This is a critical position. Take your time."

    return "Stop and think. What does this position demand?"


# ============================================================
# THINKING QUESTIONS
# ============================================================

def generate_thinking_questions(moment_data):
    """Generate 2-3 guiding questions based on the position."""
    tags = moment_data.get("tags", {})
    primary_tag = tags.get("primary_tag", "")
    position = moment_data.get("position_analysis", {})
    threat = moment_data.get("threat", "")

    questions = []

    # Tag-specific questions
    if primary_tag == "hung_piece":
        questions = [
            "Is any of your pieces undefended right now?",
            "Can your opponent capture something safely?",
            "How can you protect your vulnerable piece?"
        ]
    elif primary_tag == "missed_tactic":
        questions = [
            "What checks or captures are available?",
            "Can you create a double attack or fork?",
            "Is there a forcing sequence that wins material?"
        ]
    elif primary_tag == "one_move_blunder":
        questions = [
            "After your move, is anything left undefended?",
            "Can your opponent capture something for free?",
            "Did you check if your move leaves a piece hanging?"
        ]
    elif primary_tag == "didnt_see_far_enough":
        questions = [
            "What happens two moves from now?",
            "After your move, what will your opponent do?",
            "Can you calculate the full sequence before committing?"
        ]
    elif primary_tag == "opening_theory_deviation":
        questions = [
            "Are your pieces developing toward active squares?",
            "Is your king safe? Should you castle soon?",
            "Are you fighting for the center?"
        ]
    elif primary_tag == "threw_winning_position":
        questions = [
            "What is the safest way to maintain your advantage?",
            "Do you need to attack, or just improve your position?",
            "Can your opponent create counterplay if you're not careful?"
        ]
    elif primary_tag == "defensive_resource":
        questions = [
            "What is your opponent threatening?",
            "Can you block, capture, or move away from the threat?",
            "Is there a move that defends AND improves your position?"
        ]
    elif primary_tag == "piece_activity":
        questions = [
            "Which of your pieces is least active?",
            "Where would that piece be most effective?",
            "Can you improve your worst piece in one move?"
        ]
    elif primary_tag == "king_safety":
        questions = [
            "Is your king exposed to checks or attacks?",
            "Should you castle, or is it too late for that?",
            "Can you create a safe shelter for your king?"
        ]
    elif primary_tag in ("endgame_technique", "endgame_technique_error"):
        questions = [
            "Where should your king be headed?",
            "Which pawn has the best chance of promoting?",
            "Can you create a passed pawn?"
        ]
    elif primary_tag == "pawn_structure":
        questions = [
            "Will this pawn move create a weakness?",
            "Can you maintain tension instead of releasing it?",
            "Does this change benefit you or your opponent long-term?"
        ]
    elif primary_tag == "early_queen_adventure":
        questions = [
            "Is your queen safe from being chased by minor pieces?",
            "Are your other pieces still on their starting squares?",
            "Would developing a minor piece be better here?"
        ]
    elif primary_tag in ("time_pressure", "time_pressure_blunder"):
        questions = [
            "Is any of your pieces in danger right now?",
            "What is the simplest safe move available?",
            "Can you avoid complications and keep things stable?"
        ]
    else:
        # Generic but still useful
        questions = [
            "What changed after your opponent's last move?",
            "Are there any captures or checks available?",
            "Which of your pieces needs to be improved?"
        ]

    # Add threat-specific question if applicable
    if threat and len(questions) < 3:
        questions.insert(0, "What is your opponent threatening right now?")

    return questions[:3]


# ============================================================
# LESSON TAKEAWAY
# ============================================================

def generate_lesson_takeaway(moment_data):
    """Generate a short lesson from this moment."""
    tags = moment_data.get("tags", {})
    primary_tag = tags.get("primary_tag", "")
    insight = moment_data.get("insight", {})
    cp_loss = abs(moment_data.get("cp_loss", 0))

    # Use the pattern_to_remember if available
    pattern = insight.get("pattern_to_remember", "")
    if pattern:
        return pattern

    # Generate based on tag
    lessons = {
        "hung_piece": "Before every move, scan the board for undefended pieces — yours and your opponent's.",
        "missed_tactic": "Always check for forcing moves (checks, captures, threats) before playing a quiet move.",
        "one_move_blunder": "Before pressing the clock, ask: 'Is my move safe? Can my opponent take something?'",
        "defensive_resource": "Always check what your opponent is threatening before planning your own attack.",
        "piece_activity": "When you're unsure what to do, improve your least active piece.",
        "king_safety": "A safe king is the foundation of any plan. Prioritize king safety in the middlegame.",
        "endgame_technique": "In endgames, activate your king first. It becomes a powerful piece.",
        "endgame_technique_error": "In endgames, activate your king first. It becomes a powerful piece.",
        "pawn_structure": "Pawn moves are permanent. Think twice before pushing a pawn forward.",
        "calculation_error": "When you see a good move, look for a better one. Don't rush the first idea.",
        "positional_squeeze": "Restrict your opponent's pieces before launching an attack.",
        "time_pressure": "In critical positions, invest extra time. The right move now saves time later.",
        "time_pressure_blunder": "In time trouble, prioritize safety over ambition.",
        "opening_theory_deviation": "In the opening, follow principles: develop pieces, control the center, castle early.",
        "early_queen_adventure": "Develop minor pieces before bringing out your queen. It's easily harassed.",
        "threw_winning_position": "When ahead, don't rush. Simplify, trade pieces, and convert safely.",
        "didnt_see_far_enough": "Before committing to a move, calculate your opponent's best response.",
    }

    return lessons.get(primary_tag, "Every position tells you what it needs. Learn to listen to the board.")


# ============================================================
# REFLECTION
# ============================================================

def generate_reflection(moment_data):
    """Generate a reflection prompt and options for this moment."""
    tags = moment_data.get("tags", {})
    primary_tag = tags.get("primary_tag", "")

    reflection_prompt = "What did you overlook in this position?"

    # Options aligned with thinking patterns
    reflection_options = []

    if primary_tag == "hung_piece":
        reflection_prompt = "Why did you miss the hanging piece?"
        reflection_options = [
            {"id": "missed_threat", "label": "Didn't check opponent's threats"},
            {"id": "tunnel_vision", "label": "Was focused on my own plan"},
            {"id": "piece_safety", "label": "Forgot to check piece safety"},
            {"id": "unsure", "label": "Not sure what I missed"}
        ]
    elif primary_tag == "missed_tactic":
        reflection_prompt = "Why did you miss this tactic?"
        reflection_options = [
            {"id": "no_checks", "label": "Didn't check for forcing moves"},
            {"id": "stopped_early", "label": "Stopped calculating too early"},
            {"id": "pattern_blind", "label": "Didn't recognize the pattern"},
            {"id": "unsure", "label": "Not sure what I missed"}
        ]
    elif primary_tag == "defensive_resource":
        reflection_prompt = "What made you miss the threat?"
        reflection_options = [
            {"id": "missed_threat", "label": "Didn't see opponent's threat"},
            {"id": "overconfident", "label": "Was too focused on attacking"},
            {"id": "piece_safety", "label": "Forgot to check piece safety"},
            {"id": "unsure", "label": "Not sure what happened"}
        ]
    elif primary_tag == "king_safety":
        reflection_prompt = "What went wrong with your king safety?"
        reflection_options = [
            {"id": "delayed_castle", "label": "Should have castled earlier"},
            {"id": "pawn_weakness", "label": "Weakened pawns around king"},
            {"id": "missed_attack", "label": "Didn't see the attack coming"},
            {"id": "unsure", "label": "Not sure what I missed"}
        ]
    else:
        reflection_options = [
            {"id": "missed_threat", "label": "Missed a threat"},
            {"id": "tunnel_vision", "label": "Focused on my own plan"},
            {"id": "no_candidate", "label": "Didn't consider enough moves"},
            {"id": "unsure", "label": "Not sure what I missed"}
        ]

    return {
        "prompt": reflection_prompt,
        "options": reflection_options
    }


# ============================================================
# MAIN ENRICHMENT FUNCTION
# ============================================================

def enrich_moment_for_coaching(moment_data):
    """
    Transform a raw critical moment into a structured coaching object.
    
    This is the ONLY function the endpoint needs to call.
    Frontend receives a complete coaching moment ready to render.
    """
    tags = moment_data.get("tags", {})
    primary_tag = tags.get("primary_tag", "")

    # Get thinking lens
    lens_data = THINKING_LENS_MAP.get(primary_tag, DEFAULT_LENS)

    # Build the coaching object
    coaching = {
        "thinking_lens": {
            "label": lens_data["label"],
            "text": lens_data["lens"],
            "icon": lens_data["icon"]
        },
        "coach_prompt": generate_coach_prompt(moment_data),
        "thinking_questions": generate_thinking_questions(moment_data),
        "lesson_takeaway": generate_lesson_takeaway(moment_data),
        "reflection": generate_reflection(moment_data),
    }

    # Merge coaching data into the moment
    moment_data["coaching"] = coaching

    return moment_data
