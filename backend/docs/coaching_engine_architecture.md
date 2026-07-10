# Coaching Engine Architecture

## Overview

The Coaching Engine (`services/coaching_engine.py`) is a comprehensive coaching decision system that runs after every game analysis. It detects issues from move evaluations, aggregates patterns, and generates personalized training prescriptions.

## Core Functions

### 1. `detect_issues_from_move()`

Analyzes individual moves to detect coaching-relevant issues.

**Input:**
- `move_eval`: Move evaluation from Stockfish analysis
- `move_number`: Move number in game
- `user_color`: "white" or "black"
- `time_control`: time control type (optional)
- `time_remaining_seconds`: time at move (optional)

**Processing:**
1. Skips opponent moves and moves with cp_loss < 30
2. Determines severity from cp_loss thresholds
3. Maps cognitive_gap to IssueType
4. Detects motif-related issues (fork, pin, skewer, etc.)
5. Identifies rushing behavior (time + cp_loss)
6. Classifies game phase (opening/middlegame/endgame)

**Returns:** `DetectedIssue` or `None`

**Example:**
```python
from services.coaching_engine import detect_issues_from_move

issue = detect_issues_from_move(
    move_eval={
        "is_user_move": True,
        "move_san": "Nxe4",
        "cp_loss": 250,
        "evaluation": "mistake",
        "cognitive_gap": "piece_safety",
        "fen_before": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    },
    move_number=4,
    user_color="white",
    time_control="rapid"
)

print(issue.issue_type)  # IssueType.PIECE_SAFETY
print(issue.severity)    # IssueSeverity.HIGH
```

### 2. `issue_aggregation()`

Aggregates individual move issues into game-level summaries with trends.

**Input:**
- `detected_issues`: List of DetectedIssue from current game
- `recent_games`: List of recent game records (for trend analysis)

**Processing:**
1. Counts occurrences per issue type
2. Calculates severity distribution
3. Computes trend (improving/regressing/stable)
4. Tracks clean streaks (consecutive games without issue)
5. Calculates average cp_loss

**Returns:** `Dict[IssueType, AggregatedIssue]`

**Example:**
```python
from services.coaching_engine import issue_aggregation

aggregated = issue_aggregation(
    detected_issues=[issue1, issue2, issue3],
    recent_games=[game1, game2, game3, game4, game5]
)

piece_safety = aggregated[IssueType.PIECE_SAFETY]
print(f"Occurred {piece_safety.occurrence_count}x")
print(f"Trend: {piece_safety.trend}")  # "improving", "regressing", or "stable"
print(f"Clean streak: {piece_safety.clean_streak} games")
```

### 3. `prescription_generation()`

Generates personalized training prescriptions based on aggregated issues.

**Input:**
- `aggregated_issues`: Dict from issue_aggregation()
- `user_rating`: Player's estimated rating
- `user_id`: For logging

**Algorithm:**
1. Score each issue by priority (frequency × severity × trend × rating)
2. Select highest-priority issue
3. Check prerequisites (e.g., master piece_safety before pawn_structure)
4. Determine training phase (beginner/intermediate/advanced)
5. Build success metrics
6. Generate coaching message

**Returns:** `PrescriptionPlan` or `None`

**Example:**
```python
from services.coaching_engine import prescription_generation

prescription = prescription_generation(
    aggregated_issues={
        IssueType.PIECE_SAFETY: issue,
        IssueType.MISSED_TACTIC: issue2,
    },
    user_rating=1200,
    user_id="user_123"
)

print(prescription.primary_issue)        # IssueType.PIECE_SAFETY
print(prescription.training_focus)       # "Piece Protection Fundamentals"
print(prescription.coaching_message)     # Personalized message
print(prescription.success_metrics)      # ["0 hanging pieces per game", ...]
```

### 4. `metric_calculation()`

Calculates comprehensive metrics for a specific issue type.

**Input:**
- `issue_type`: The issue to analyze
- `detected_issues`: Issues detected in current game
- `recent_games`: Recent game history

**Calculates:**
- Frequency per game
- Average severity
- Trend direction
- Competence level (NOVICE to MASTERED)
- Priority score (0-100)
- Recommendation flag

**Returns:** `IssueMetrics`

**Example:**
```python
from services.coaching_engine import metric_calculation

metrics = metric_calculation(
    IssueType.PIECE_SAFETY,
    detected_issues,
    recent_games
)

print(f"Frequency: {metrics.frequency_per_game:.2f} per game")
print(f"Competence: {metrics.competence_level}")  # NOVICE, DEVELOPING, etc.
print(f"Priority score: {metrics.priority_score}")  # 0-100
```

### 5. `improvement_pct()`

Calculates improvement percentage for an issue across games.

**Input:**
- `issue_type`: Issue to track
- `recent_games`: Recent game history
- `improvement_window`: Number of games to analyze (default 10)

**Processing:**
- Splits games into recent and earlier halves
- Compares issue rates
- Returns -100 to +100 where:
  - Positive = improving
  - Zero = stable
  - Negative = regressing

**Returns:** `float` (-100 to +100)

**Example:**
```python
from services.coaching_engine import improvement_pct

improvement = improvement_pct(IssueType.PIECE_SAFETY, recent_games, 10)

if improvement > 20:
    print("Great progress on piece safety!")
elif improvement < -10:
    print("Piece safety is getting worse")
else:
    print("Stable performance on piece safety")
```

### 6. `competence_detection()`

Assesses player competence level for a specific issue.

**Input:**
- `issue_type`: Issue to assess
- `recent_games`: Game history
- `detected_issues`: Current game issues
- `minimum_sample_size`: Min games for reliable assessment

**Returns:** `CompetenceLevel` enum:
- `MASTERED`: 0% issue rate
- `PROFICIENT`: 0-15% issue rate
- `INTERMEDIATE`: 15-35% issue rate
- `DEVELOPING`: 35-65% issue rate
- `NOVICE`: >65% issue rate

**Example:**
```python
from services.coaching_engine import competence_detection, CompetenceLevel

competence = competence_detection(
    IssueType.PIECE_SAFETY,
    recent_games,
    detected_issues
)

if competence == CompetenceLevel.MASTERED:
    print("Player has mastered piece safety!")
elif competence == CompetenceLevel.NOVICE:
    print("Player needs fundamental training")
```

### 7. `process_game_for_coaching()`

**Main integration point** - orchestrates entire pipeline after game analysis.

**Input:**
- `db`: MongoDB database connection
- `game_id`: Analyzed game ID
- `user_id`: Player ID
- `move_evaluations`: Stockfish move evaluations
- `user_rating`: Player rating
- `user_color`: "white" or "black"
- `time_control`: Time control type (optional)

**Processing:**
1. Detects all issues from the game
2. Aggregates with historical data
3. Generates training prescription
4. Calculates metrics for all issue types
5. Stores coaching summary in database

**Returns:** Dict with:
- `game_id`: The game analyzed
- `user_id`: Player ID
- `detected_issues`: Count of issues found
- `aggregated_issues`: Issue aggregations
- `prescription`: PrescriptionPlan
- `metrics`: Metrics for all issue types
- `improvements`: Improvement percentages
- `generated_at`: Timestamp
- Or `error`: If something failed

**Example:**
```python
from services.coaching_engine import process_game_for_coaching

# Called from analysis_worker.py after Stockfish analysis
result = process_game_for_coaching(
    db=mongo_db,
    game_id="game_123",
    user_id="user_456",
    move_evaluations=stockfish_data["moves"],
    user_rating=1400,
    user_color="white",
    time_control="rapid"
)

print(f"Detected {result['detected_issues']} issues")
print(f"Primary focus: {result['prescription']['primary_issue']}")
```

## Integration with Analysis Worker

The coaching engine is integrated at the end of game analysis in `analysis_worker.py`:

```python
# In analysis_worker.py, around line 2007:

from services.coaching_engine import process_game_for_coaching

coaching_result = process_game_for_coaching(
    db,
    game_id,
    user_id,
    move_evaluations,
    user_rating,
    user_color,
    game.get("time_control", "rapid")
)
```

**Execution sequence:**
1. Stockfish analysis completes
2. Move evaluations enriched with cognitive gaps
3. Coaching engine runs (non-fatal on error)
4. Results stored in `coaching_summaries` collection
5. Game analysis completes

## Data Models

### DetectedIssue
```python
@dataclass
class DetectedIssue:
    issue_type: IssueType          # PIECE_SAFETY, MISSED_TACTIC, etc.
    move_number: int               # Move in game
    move_san: str                  # e.g., "Nxe4"
    severity: IssueSeverity        # CRITICAL, HIGH, MEDIUM, LOW, MINIMAL
    cp_loss: int                   # Centipawns lost
    fen_before: str                # Position before move
    cognitive_gap: Optional[str]   # Gap type from analyzer
    motif_type: Optional[str]      # fork, pin, skewer, etc.
    is_rushing: bool               # Detected time pressure move
    time_remaining_seconds: Optional[int]
    explanation: str               # Why it's an issue
    best_move: Optional[str]       # Better move
    phase: str                     # opening, middlegame, endgame
```

### AggregatedIssue
```python
@dataclass
class AggregatedIssue:
    issue_type: IssueType
    occurrence_count: int          # Times occurred in game
    total_severity_score: float    # Sum of severity weights
    avg_cp_loss: float             # Average cp loss
    recent_games: List[str]        # game_ids with this issue
    trend: str                     # "improving", "regressing", "stable"
    last_occurrence_ago: int       # Number of games
    clean_streak: int              # Consecutive games without
    severity_distribution: Dict    # Count per severity level
```

### PrescriptionPlan
```python
@dataclass
class PrescriptionPlan:
    primary_issue: IssueType       # Issue to focus on
    reasoning: str                 # Why this issue
    training_focus: str            # Training content name
    prerequisites: List[str]       # Things to master first
    training_phase: str            # beginner, intermediate, advanced
    estimated_focus_duration_days: int
    success_metrics: List[str]     # Measurable goals
    coaching_message: str          # Personalized message
```

### IssueMetrics
```python
@dataclass
class IssueMetrics:
    issue_type: IssueType
    frequency_per_game: float      # How often per game
    avg_severity: str              # Average severity name
    avg_cp_loss: float             # Average cp loss
    trend: str                     # Trend direction
    competence_level: CompetenceLevel  # Skill assessment
    recommended_focus: bool        # Should prioritize
    priority_score: float          # 0-100 ranking
```

## Enums

### IssueType
```python
class IssueType(str, Enum):
    RUSHING = "rushing"
    PIECE_SAFETY = "piece_safety"
    MISSED_TACTIC = "missed_tactic"
    KING_SAFETY = "king_safety"
    CALCULATION_DEPTH = "calculation_depth"
    POSITIONAL_ERROR = "positional_error"
    OPENING_KNOWLEDGE = "opening_knowledge"
    ENDGAME_TECHNIQUE = "endgame_technique"
    TIME_MANAGEMENT = "time_management"
    PAWN_STRUCTURE = "pawn_structure"
```

### IssueSeverity
```python
class IssueSeverity(str, Enum):
    CRITICAL = "critical"       # >400cp loss
    HIGH = "high"               # 200-400cp loss
    MEDIUM = "medium"           # 100-200cp loss
    LOW = "low"                 # 30-100cp loss
    MINIMAL = "minimal"         # <30cp loss
```

### CompetenceLevel
```python
class CompetenceLevel(str, Enum):
    NOVICE = "novice"           # <20% correct
    DEVELOPING = "developing"   # 20-50% correct
    INTERMEDIATE = "intermediate" # 50-70% correct
    PROFICIENT = "proficient"   # 70-85% correct
    MASTERED = "mastered"       # >85% correct
```

## Severity Thresholds

```python
SEVERITY_THRESHOLDS = {
    IssueSeverity.CRITICAL: 400,   # >400cp loss
    IssueSeverity.HIGH: 200,       # 200-400cp loss
    IssueSeverity.MEDIUM: 100,     # 100-200cp loss
    IssueSeverity.LOW: 30,         # 30-100cp loss
}
```

## Priority Weights

Issues are ranked by priority for prescription generation:

```python
ISSUE_PRIORITY_WEIGHTS = {
    IssueType.PIECE_SAFETY: 1.0,         # Highest - fundamental
    IssueType.MISSED_TACTIC: 0.95,
    IssueType.KING_SAFETY: 0.9,
    IssueType.RUSHING: 0.85,              # Behavioral
    IssueType.CALCULATION_DEPTH: 0.8,
    IssueType.POSITIONAL_ERROR: 0.7,
    IssueType.TIME_MANAGEMENT: 0.75,
    IssueType.ENDGAME_TECHNIQUE: 0.65,
    IssueType.PAWN_STRUCTURE: 0.6,
    IssueType.OPENING_KNOWLEDGE: 0.55,
}
```

## Database Integration

Results are stored in `coaching_summaries` collection:

```python
db.coaching_summaries.update_one(
    {"game_id": game_id, "user_id": user_id},
    {"$set": coaching_summary},
    upsert=True
)
```

## Error Handling

All functions are wrapped in try/except blocks:
- `detect_issues_from_move()` returns None on error
- `issue_aggregation()` returns empty dict on error
- `prescription_generation()` returns None on error
- `process_game_for_coaching()` logs warning and returns error dict

Non-fatal errors don't stop game analysis - logging shows what failed.

## Testing

Run tests with:
```bash
cd backend
python -m pytest tests/test_coaching_engine.py -v
```

30 comprehensive tests cover:
- Issue detection (8 tests)
- Issue aggregation (4 tests)
- Prescription generation (4 tests)
- Metric calculation (2 tests)
- Improvement tracking (3 tests)
- Competence detection (3 tests)
- Integration workflows (2 tests)
- Edge cases (4 tests)

## Performance

Expected execution times:
- `detect_issues_from_move()`: <1ms per move
- `issue_aggregation()`: 5-10ms
- `prescription_generation()`: 2-5ms
- `metric_calculation()`: 2-5ms
- Full `process_game_for_coaching()`: 20-50ms

Total overhead to game analysis: <100ms for typical 50-move game.

## Future Enhancements

1. Machine learning ranking of prescriptions
2. Multi-issue prescriptions (focus on top 3 issues)
3. Rating-specific training content
4. Success rate tracking for prescriptions
5. Puzzle recommendation integration
6. Time control specific recommendations
