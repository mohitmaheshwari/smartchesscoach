# Chess Coach App - Changelog

## March 5, 2026

### Self-Learning Pattern Recognition System
- **NEW**: Built complete auto-correction system for improving coach accuracy
- **NEW**: 6 backend modules in `/app/backend/services/pattern_learning/`:
  - `auto_correction_service.py` - Main orchestrator
  - `feedback_collector.py` - Structures and stores user feedback
  - `pattern_learner.py` - GPT-4o generates classification rules
  - `rule_validator.py` - Validates rules before activation (Stockfish verification)
  - `rule_executor.py` - Runs learned rules at classification time
  - `learning_db.py` - MongoDB operations for rules, feedback, corrections

- **NEW**: 7 API endpoints for pattern learning:
  - `POST /api/coach/pattern-learning/feedback` - Submit correction feedback
  - `GET /api/coach/pattern-learning/stats` - System statistics
  - `GET /api/coach/pattern-learning/pending-rules` - Rules needing review
  - `POST /api/coach/pattern-learning/approve-rule` - Approve a rule
  - `POST /api/coach/pattern-learning/reject-rule` - Reject a rule
  - `POST /api/coach/pattern-learning/classify` - Test classification
  - `POST /api/coach/pattern-learning/track-accuracy` - Track rule accuracy

- **NEW**: Enhanced feedback modal in CoachPlay.jsx
  - Pattern correction dropdown when "Wrong" is selected
  - Options: Fork, Pin, Skewer, Hanging Piece, Missed Tactic, etc.
  - User explanation helps AI learn the pattern

- **NEW**: `enhanced_classifier.py` - Wrapper that checks learned rules first

### Technical Details
- Uses GPT-4o via Emergent Universal Key (swappable to user's own OpenAI key)
- Auto-approval threshold: 85% confidence
- Cross-user learning: corrections propagate to all similar positions
- Anti-hallucination: LLM only interprets Stockfish data, never invents facts

---

## March 4, 2026 (Previous Session)

### "Play with Coach" Conversational Features
- Added feedback endpoint for beta users
- Proactive opening teaching
- Interactive questions with clickable answers
- Praise for good moves
- Habit-focused coaching (no engine-like suggestions)

### Bug Fixes
- Fixed "Games to Reflect On" not showing
- Fixed puzzle position showing starting FEN
- Added arrows to puzzle screen
- Removed "0 → 0" display issues
- Added rating tooltips

### Core Data Accuracy Fix
- Fixed mistake classifier to use PV for consequence detection
- Correctly identifies pawn forks from engine's principal variation
