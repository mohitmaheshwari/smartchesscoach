# Chess Coach - Data Model Reference

## CRITICAL: Game Analysis Document Structure

```
game_analyses {
  game_id: string,
  user_id: string,
  
  # ===== STOCKFISH DATA (SOURCE OF TRUTH) =====
  stockfish_analysis: {
    accuracy: number,              # e.g., 78.9
    move_evaluations: [            # Array of each move's evaluation
      {
        move_number: number,
        evaluation: string,        # "blunder", "mistake", "inaccuracy", "good", "best"
        played_move: string,
        best_move: string,
        cp_loss: number,
        ...
      }
    ]
  },
  stockfish_failed: boolean,       # True if Stockfish couldn't analyze
  stockfish_error: string,         # Error message if failed
  
  # ===== GPT COMMENTARY (PRESENTATION ONLY) =====
  commentary: [                    # Human-readable explanations
    {
      move_number: number,
      move: string,
      evaluation: string,          # MAY NOT MATCH stockfish_analysis!
      feedback: string,
      ...
    }
  ],
  
  # ===== TOP-LEVEL STATS (MAY BE STALE - DON'T TRUST) =====
  blunders: number,                # May not match stockfish_analysis
  mistakes: number,                # May not match stockfish_analysis
  accuracy: number,                # May not match stockfish_analysis
}
```

## Rules for Querying

### ✅ CORRECT: Get properly analyzed games
```python
db.game_analyses.find({
    "stockfish_analysis.move_evaluations": {"$exists": True, "$not": {"$size": 0}},
    "stockfish_failed": {"$ne": True}
})
```

### ❌ WRONG: Don't use top-level fields
```python
# DON'T DO THIS - top-level fields may be stale
db.game_analyses.find({"move_evaluations": {"$exists": True}})
db.game_analyses.find({"blunders": {"$gt": 0}})
```

### ✅ CORRECT: Count blunders/mistakes
```python
sf = analysis.get("stockfish_analysis", {})
move_evals = sf.get("move_evaluations", [])
blunders = sum(1 for m in move_evals if m.get("evaluation") == "blunder")
mistakes = sum(1 for m in move_evals if m.get("evaluation") == "mistake")
accuracy = sf.get("accuracy", 0)
```

### ❌ WRONG: Don't use top-level counts
```python
# DON'T DO THIS - may be stale/wrong
blunders = analysis.get("blunders", 0)
mistakes = analysis.get("mistakes", 0)
```

## What Makes a Game "Properly Analyzed"

1. `stockfish_analysis.move_evaluations` exists AND has >= 3 items
2. `stockfish_failed` is NOT True
3. `stockfish_analysis.accuracy` > 0

Games with only `commentary` (GPT) but no `stockfish_analysis.move_evaluations` are NOT properly analyzed.
