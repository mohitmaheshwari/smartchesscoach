---
name: recent-play-story-rewrite
description: "Backlog. Retire the multi-game LLM \"story\" aggregate on HomePage Recent Play. Replace prose with principle-name + process-habit + mini-board. The current surface violates sub1500_memory_anchors and feedback_teaching_not_reading in its entire design."
metadata: 
  node_type: memory
  type: project
  originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---

The `_aggregate_verdict()` composer in `backend/services/game_mirror.py`
produces text like:

  "Eight games — 3 wins, 4 losses, 1 draw. Six of eight turned on
   missed tactics. Move 17: Ng4 was quiet when Nxd7 was the tactic.
   Hung pieces also turned up in four of eight. Look at forcing
   moves first — checks, captures, threats — before the quiet ones.
   Second time opening drift have shown up — these are real now,
   not noise."

Every "N of M" violates [[sub1500-memory-anchors]] (game-count framing
forbidden). The "real now, not noise" closer is [[teaching-not-reading]]
meta-talk. "Move 17: Ng4 was quiet" anchors on a game number with no
visual, also forbidden. Plus a grammar bug ("have" → "has").

Picked Option C from the 2026-05-13 design conversation: rewrite the
prose AND simplify the layout.

**Why:** The current Recent Play story is wall-of-text serif-italic
prose that violates 3+ locked memory rules at once. Surface needs
redesign, not patches. Per [[v5-caption-rewrite-no-patches]] discipline.

**How to apply:**
  1. Retire `_aggregate_verdict()` text output from HomePage.
  2. Keep the data backend computes: window outcomes, top pattern,
     critical position. Drop the prose composition.
  3. Replace HomePage rendering with:
     - Result summary chip (3W/4L/1D — counts of outcomes are fine,
       counts of patterns are not)
     - Pattern NAME alone as a chip ("Missed Tactic", "Hanging Piece")
       — the memory anchor sub-1500 players retain
     - One process-habit line per pattern (≤12 words: e.g.
       "Checks, captures, threats — scan them first")
     - Mini-board of the worst position from this window (the
       existing critical_fen) — visual anchor, no game number needed
  4. NO "N of M". NO "Second time X has shown up." NO "Move 17 in
     game Y." NO "real now, not noise."
  5. Visual: drop serif italic + giant quote block. Use the same
     compact card style as Pattern of the Day.

Code locations:
  - `backend/services/game_mirror.py` lines 758-869 (_aggregate_verdict)
  - `backend/services/game_mirror.py` lines 125-135 (_pattern_observation)
  - `frontend/src/pages/HomePage.jsx` lines 295-300 (story render)

Out of scope for the current session per user direction 2026-05-13.
Pick this up when next opening up Home/Mirror work.
