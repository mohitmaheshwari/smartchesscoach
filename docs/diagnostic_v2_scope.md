# Diagnostic V2 — Scope Document

**Status:** AWAITING SIGNOFF
**Author:** Claude (research + scope)
**Date:** 2026-07-19
**Scope:** Redesign `/diagnostic` from "engine-move matching" to "chess understanding measurement"

---

## 0. Existing Surfaces Audit

**Path: EXTEND** — we keep the same diagnostic route/UX flow, but replace the grading logic and UI.

**What exists (verified prod):**
- `DiagnosticPuzzles.jsx` at `/diagnostic`, 20-puzzle flow, routed from `ActivationHub.jsx`
- Backend: `routes/diagnostic.py`, `diagnostic_service.py`, binary grading ("best move vs. user move")
- Storage: `diagnostic_sessions` collection (14 in prod), `community_puzzles` (5.1k approved)
- **Lichess puzzle collection: 4.1M imported**, already indexed by theme/rating/popularity
- Existing serving precedent: `coaching_puzzle_service._get_lichess_puzzles()` + `WEAKNESS_TO_PUZZLE_THEMES` map

**Grading bug:** current `_check_move()` requires exact SAN match to `best_move_san`. Consequences:
- Winning move that isn't THE stored move → FAIL (false negative)
- Blunder and safe move both score "1 miss" → indistinguishable
- No concept-specific profiling; binary "correct/wrong" only
- Difficulty weighting computed but ignored by `_rating_estimate()`

**Puzzle pool issue:** own `community_puzzles` by category are skewed:
- piece_safety: 1.3k (healthy)
- missed_tactic: 1.6k (healthy)
- piece_activity: 24 (unusable)
- pawn_structure: 4 (unusable)

---

## 1. What It Is

A diagnostic that measures **chess understanding**, not engine-move compliance. Instead of "did you play the best move?", it asks:
- "Do you see pieces under attack?" (piece safety)
- "Do you see your opponent's threat?" (threat response)
- "Can you find a two-move sequence?" (calculation depth)
- "Can you hold a winning position?" (winning technique)

25 puzzles across 10 concepts (forks, pins, mate patterns, defense, threats, calculation, endgame, opening, safety, conversion), calibrated and multi-move where depth matters. Grading is consequence-based: did the move *win*, *hold*, or *lose* — not whether it matched the canonical line. Result is a per-concept profile (Solid/Developing/Missing) that seeds coaching focus.

---

## 2. What the User Sees

### During diagnostic:

```
┌─────────────────────────────────────────────────┐
│  [●●○] [●○○] [◐○○] [○●○] [○○○] [○○○] [○○○] [○○○] [○○○] [○○○]
│  fork   pins   mate  threat safe  calc  endg open  conv
│
│  Puzzle 7 of 25: Forks (tier 2 of 3)
│
│  [CHESS BOARD — Piece colors match user, side-to-move]
│
│  Make your move...
│
│  [Below board, after move submitted]:
│  ✓ Correct — Nxd5 wins the knight (that fork you spotted)
│  or
│  ◐ Partial — Bd3 keeps your advantage, but Nc7 forked both pieces
│  or
│  ✗ Wrong — After Nc7, your knight is still attacked, mate next move
│
│ [Concept progress bar at bottom shows current/remaining in this concept]
└─────────────────────────────────────────────────┘
```

Tone: clinical assessment, no encouragement/discouragement, explain the consequence.

### After diagnostic (results screen):

```
┌──────────────────────────────────────────────────┐
│  Your Chess DNA
│
│  Estimated rating: 1,050–1,250
│
│  ┌───────────────────────────────────────────┐
│  │ Solid ✓ — Fork                        ✓✓◐ │
│  │ Solid ✓ — Mate patterns             ✓✓✓ │
│  ├───────────────────────────────────────────┤
│  │ Developing ◐ — Threat response       ✓◐✗ │
│  │ Developing ◐ — Defense               ✓◐◐ │
│  ├───────────────────────────────────────────┤
│  │ Missing ✗ — Endgame technique        ◐✗✗ │
│  │ Missing ✗ — Calculation depth        ✗✗✗ │
│  └───────────────────────────────────────────┘
│
│  🎯 YOUR FOCUS AREA
│  "You spotted tactics well, but three times your piece was
│   hanging and got captured. Games at your level are decided
│   here — let's drill piece safety."
│
│  [Start Training] → /training/pattern/piece_safety
│
│  [Learn Endgame] → endgame lesson (if endgame was weakest)
└──────────────────────────────────────────────────┘
```

---

## 3. In Scope (V1)

**Concepts to test (10 total, 25 puzzles):**
- [ ] Piece safety (offense) — take the hanging piece (3 puzzles, tiers 800/1200/1600)
- [ ] Piece safety (defense) — save your attacked piece (3 puzzles)
- [ ] Forks — knight/bishop attacking two pieces (2 puzzles)
- [ ] Pins & skewers — line pieces through multiple targets (2 puzzles)
- [ ] Mate patterns — mateIn1, back-rank mate (3 puzzles)
- [ ] Threat response — opponent just attacked; parry it (3 puzzles)
- [ ] Calculation depth — find 2-3 move forced sequences (3 puzzles)
- [ ] Endgame technique — K+P opposition, promotion races (3 puzzles)
- [ ] Opening principles — don't grab poison pawns, develop (2 puzzles)
- [ ] Winning technique — you're up material; simplify, don't lose it (1-2 puzzles)

**Puzzle sourcing:**
- [ ] Build offline `diagnostic_pool` (500 curated Lichess puzzles)
- [ ] Quality gates: popularity ≥90, single-idea (multipv confirms ≥150cp gap to 2nd move)
- [ ] 3 rating tiers per concept (~800/1200/1600 ±100)
- [ ] Reuse `coaching_puzzle_service._get_lichess_puzzles()` + theme maps

**Grading logic (consequence-based, not move-matching):**
- [ ] Precompute multipv + baselines for all 500 puzzles (offline script)
- [ ] At attempt time: one fast Stockfish eval (depth 12-14) of position after user's move
- [ ] 3-tier verdict: UNDERSTOOD (solution or equiv, ≤50cp loss) / PARTIAL (50-200cp loss, eval sign holds) / MISSING (loses eval or allows threats)
- [ ] Multi-move lines: user must find each solution move sequentially, auto-play opponent replies
- [ ] Consistency gate: concepts never judged on 1 puzzle; 2/2 UNDERSTOOD = solid, 1/1 ties include adaptive 3rd puzzle
- [ ] Difficulty staircase within concepts: UNDERSTOOD → up tier, MISSING → down tier
- [ ] Reuse cp-loss thresholds from `realtime_coaching_feedback._classify_move_quality` (single source of truth)

**Output format:**
- [ ] Per-concept record: level (Solid/Developing/Missing), (✓/◐/✗) dots, highest tier passed
- [ ] Rating estimate via puzzle-rating staircase (replace accuracy bins)
- [ ] Headline gap (worst-performing concept by priority: defense > threat > forks > ...)
- [ ] Summary line explaining the gap
- [ ] Blunder rate (committed hangs) flagged separately to `coach_memory`
- [ ] Wire through existing `update_weakness_tracking` + `/training/pattern/{gap}` pipeline unchanged

**UI:**
- [ ] During: concept-grouped progress (10 chips, 2-3 dots each, current highlighted)
- [ ] Per-puzzle feedback: verdict + one-sentence why, no jargon, name the square
- [ ] Results: vertical bar chart per concept (not radar), level chips, verdict dots
- [ ] CTA: "Start training" → `/training/pattern/{weakness}`

---

## 4. Explicitly Out of Scope (V1)

- "Why" proof questions (tap-choice about the move's purpose) — deferred; cheap to add post-V1
- Radar chart or other viz — bars are more honest; no false precision
- Difficulty progression visual — kept simple; staircase is internal logic only
- PWC personality/voice tuning based on diagnostic results — defer to V2
- Mobile responsive redesign — keep current page structure
- Social/leaderboard tie-in — diagnostic is assessment, not gamification
- Opening-specific lessons (e.g., "learned Fried Liver trap") — diagnostic seeds it, training pathway teaches it
- Lichess OAuth / live puzzle sync — static curated pool from existing import, no live API

---

## 5. Success Criteria

- "Consequence-based grading" verified: a winning move not matching engine's top line scores UNDERSTOOD, not FAIL
- Diagnostic can be completed in 20–30 min with multi-move puzzles included
- Per-concept profile matches manual chess review of same user (spot-check 2-3 profiles vs. their real games)
- Rating estimate is within ±200 of their actual rating in half of new-user diagnostics
- Concept-level verdicts (Solid vs. Missing) correlate with their weakness_tracking / actual game mistakes
- Results flow through to `/training/pattern/{gap}` with no manual wiring — training sees same gap keys

---

## 6. Open Questions

1. **Adaptive third-puzzle frequency**: How strict on the consistency gate? (a) only on 1-of-2 splits, (b) also on PARTIAL-heavy 1–1–◐ patterns? Recommend (a) to keep ~25 target.
2. **Blunder thresholding**: When does a MISSING move count as "committed a blunder"? (a) only illegal/hanging, (b) any ✗ that puts opponent on a mate line? Recommend (a) for clarity.
3. **Endgame lesson wiring**: When endgame is headline gap, should CTA link to `/endgames/{lesson}`? Or keep single `/training/pattern/endgame_technique` training path? Recommend the latter for MVP.
4. **Offline pool refresh frequency**: How often rebuild the 500-puzzle pool from Lichess? (a) once per deployment, (b) monthly, (c) on-demand when pool shrinks? Recommend (a) for predictability.

---

## 7. Pre-Code Requirements

Hard gates — each must be true before the first line of code is written:

- [ ] **Mohit has signed off on this scope document** (explicit "locked", "ship it", "yes proceed")
- [ ] **Concept prioritization locked** (order for "headline gap" selection confirmed)
- [ ] **Grading thresholds locked** (cp-loss boundaries for PARTIAL vs. MISSING per rating band, reuse from coaching or define fresh)
- [ ] **UI wireframe approved** (concept chips, verdict format during/after)
- [ ] **Lichess puzzle collection verified** in prod Mongo (spot-check: theme counts, rating distribution, multi-move line format)
- [ ] **Offline pool curation script drafted** (identify which Lichess puzzles qualify + expected count per concept)
- [ ] **Consequence-based grading logic pseudocoded** (multipv baseline usage, eval classification, multi-move walk-through)

---

*After signoff: write offline pool script → build diagnostic_v2 backend → update DiagnosticPuzzles.jsx + results screen → integration test vs. real diagnostic flow.*
