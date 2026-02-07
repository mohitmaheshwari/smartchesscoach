"""
Centralized Configuration for Chess Coach App
Change settings here - they apply everywhere.
"""

# =============================================================================
# LLM CONFIGURATION
# =============================================================================

# Main LLM for commentary and analysis
LLM_PROVIDER = "openai"
LLM_MODEL = "gpt-4o-mini"

# Alternative models (uncomment to switch):
# LLM_MODEL = "gpt-5.2"           # Best quality, expensive
# LLM_MODEL = "gpt-4o"            # Great quality, moderate cost
# LLM_MODEL = "gpt-4o-mini"       # Good quality, cheap (RECOMMENDED)

# Text-to-Speech model
TTS_MODEL = "tts-1"
TTS_VOICE = "alloy"

# =============================================================================
# STOCKFISH CONFIGURATION
# =============================================================================

STOCKFISH_PATH = "/usr/games/stockfish"
STOCKFISH_DEPTH = 15              # Analysis depth (12-18 recommended)
STOCKFISH_PV_DEPTH = 12           # Depth for principal variation
STOCKFISH_PV_LENGTH = 5           # Number of moves in PV line

# =============================================================================
# GAME SYNC CONFIGURATION  
# =============================================================================

# First sync (new user)
FIRST_SYNC_MAX_GAMES = 15         # Max games to analyze on first sync
FIRST_SYNC_MONTHS = 3             # How far back to look

# Daily sync
DAILY_SYNC_MAX_GAMES = 3          # Max games to analyze per day
SYNC_INTERVAL_HOURS = 4           # Background sync interval

# Game preferences
PREFERRED_TIME_CONTROLS = ["rapid", "classical", "blitz"]
MIN_GAME_MOVES = 10               # Skip very short games

# =============================================================================
# ANALYSIS CONFIGURATION
# =============================================================================

# Centipawn thresholds for move classification
CP_THRESHOLDS = {
    "blunder": 200,       # >= 200 cp loss
    "mistake": 100,       # >= 100 cp loss
    "inaccuracy": 50,     # >= 50 cp loss
    "good": 20,           # <= 20 cp loss
    "excellent": 10,      # <= 10 cp loss
}

# =============================================================================
# COACH SETTINGS
# =============================================================================

COACH_STYLE = "calm_mentor"       # Coach personality
MAX_HABITS_TO_TRACK = 5           # Max habits to track per user
PDR_CANDIDATE_MOVES = 2           # Number of candidate moves in PDR (2 or 3)
