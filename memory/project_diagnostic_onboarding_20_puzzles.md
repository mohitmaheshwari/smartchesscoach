---
name: diagnostic-onboarding-20-puzzles
description: Onboarding for sub-800 / no-history users — a 20-puzzle diagnostic drawn from the community_puzzles pool that ends with a meaningful assessment of the user's chess understanding (rating estimate + per-principle strengths/weaknesses).
metadata:
  type: project
---

**Onboarding design (locked by Mohit 2026-05-19):** new users with no analyzed games go through a **20-puzzle diagnostic**, not a generic "welcome to ChessGuru" tour. Each puzzle tests a chess concept. The output is a real DIAGNOSIS — approximate rating + which principles they understand vs which they struggle with. This becomes the seed for everything else (Coach's Pick, Pattern Training, etc.).

**Why this shape:** Mohit's framing — "if you can analyze their games, that's good otherwise meanwhile we will take them to the puzzle from community and see how good are they." The 20 puzzles substitute for game history. Better than asking the user to self-rate (most are wrong) and better than starting them at a generic baseline.

**How to apply:** Build a new diagnostic flow with these requirements:

1. **Puzzle source:** `community_puzzles` collection (161 docs as of 2026-05-19). Each puzzle is FEN + best_move_san + issue_type + difficulty. Already extracted from real games via puzzle_extraction_service.

2. **Selection rule:** 20 puzzles spread across categories — pin / fork / hanging-piece / discovered-attack / mate-in-1 / mate-in-2 / endgame-king-walk / opening-development / etc. Pull 2-3 per category, ascending difficulty within category. Aim for a mix that probes BOTH tactical recognition AND positional understanding.

3. **UX:** one puzzle at a time, no time pressure (per [[no-gamification]]), no "X% correct" gamification mid-flow. Just "next puzzle." After move attempt: show whether it was correct, brief one-line explanation, move to next.

4. **Output (the actual product value):** a diagnostic readout. Something like:
   - "You're approximately rated 950-1100 based on tactical pattern recognition."
   - "Strengths: hanging-piece detection, basic forks."
   - "Areas to grow: pin recognition, calculation depth beyond 2 ply, endgame king activity."
   - "Your improvement plan starts here..."
   This becomes the SEED for their dashboard recommendations.

5. **Re-running:** after the user has 10+ analyzed games, the diagnostic regenerates from real data and supersedes the puzzle-based estimate.

**What this is NOT:**
- NOT gamified ("Get 80% to advance!") — per [[no-gamification]]
- NOT a rating tournament — it's a diagnostic, not a competitive thing
- NOT a one-time barrier ("solve these to access the app") — should feel like a useful tool, not a gate

**Companion:** [[sub1500-memory-anchors]] (the puzzle picks should anchor to the named principles we already use), [[product-vision]], [[no-gamification]].
