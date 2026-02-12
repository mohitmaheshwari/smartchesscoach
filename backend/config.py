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

STOCKFISH_PATH = "/app/stockfish"
STOCKFISH_DEPTH = 18              # Main analysis depth (15-20 recommended)
STOCKFISH_QUICK_DEPTH = 12        # Quick analysis depth
STOCKFISH_PV_DEPTH = 12           # Depth for principal variation
STOCKFISH_PV_LENGTH = 5           # Number of moves in PV line
STOCKFISH_MAX_RETRIES = 3         # Retry attempts if analysis fails

# =============================================================================
# GAME SYNC CONFIGURATION  
# =============================================================================

# First sync (new user)
FIRST_SYNC_MAX_GAMES = 15         # Max games to analyze on first sync
FIRST_SYNC_MONTHS = 3             # How far back to look (months)

# Daily sync
DAILY_SYNC_MAX_GAMES = 3          # Max games to analyze per day
SYNC_INTERVAL_HOURS = 4           # Background sync interval (hours)
BACKGROUND_SYNC_INTERVAL_SECONDS = 6 * 60 * 60  # Full background sync (6 hours)

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

# =============================================================================
# HABIT ROTATION SETTINGS
# =============================================================================

HABIT_CONSECUTIVE_CORRECT = 4     # Correct PDR answers in a row to rotate
HABIT_TOTAL_CORRECT = 6           # Total correct out of last 8 attempts
HABIT_MIN_ATTEMPTS = 5            # Minimum attempts before rotation

# =============================================================================
# QUALITY CONTROL (CQS) SETTINGS
# =============================================================================

CQS_ACCEPT_THRESHOLD = 80         # Score to accept commentary
CQS_WARNING_THRESHOLD = 70        # Score for warning
CQS_REJECT_THRESHOLD = 70         # Score to reject (retry)
CQS_CRITICAL_THRESHOLD = 60       # Absolute minimum acceptable
CQS_MAX_REGENERATIONS = 2         # Max retry attempts

# =============================================================================
# SESSION & AUTH SETTINGS
# =============================================================================

SESSION_EXPIRY_DAYS = 7           # Login session duration
COOKIE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # Cookie expiry (7 days)
PLAY_SESSION_LOOKBACK_HOURS = 2   # Hours to look back for recent games

# =============================================================================
# DEFAULT VALUES
# =============================================================================

DEFAULT_RATING = 1200             # Default rating for new users
