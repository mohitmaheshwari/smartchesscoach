---
name: surface-teaching-gold-proactively
description: When a corpus scan or detector run produces data, the next step is to classify it as teaching gold (missed/played/lucky/warning) and surface the gold games — not stop at the count.
metadata:
  type: feedback
---

When a corpus scan or detector run produces data, the immediate next step is to **classify each fire as teaching gold and surface the gold games to Mohit**. Don't stop at the count.

**Why:** ChessGuru's whole purpose is teaching, not analysis-for-its-own-sake. A scan that says "10 Légal fires across 9 games" is research. A scan that says "you missed Légal in 7 of these 7 games — here are the FENs, want me to seed them into pattern training?" is product. Mohit called this out 2026-05-18 after the scan_legal_geometry.py run — I gave him a count and stopped; he asked plainly: "are you not capable of flagging games that have some gold teaching for the guys?" That's the gap.

**How to apply:** For every detector / scanner / audit that produces a list of fires:

1. **Classify each fire by teaching role:**
   - **GOLD:** user had the opportunity, missed it. Highest teaching value.
   - **CELEBRATION:** user had it and played it. Use sparingly for confidence-building.
   - **LUCKY:** opponent had it against user, missed it. "Here's what could have happened to you."
   - **WARNING:** opponent had it and played it. "Here's how you actually lost."
   - **N/A:** neither side had the user as participant (only relevant when scanning community/historical games).

2. **Output the gold pool, not just the count.** Each gold entry has: game_id, fire-ply, FEN_before, named pattern, what was played, what was best, engine swing, opponent, result.

3. **Connect it to the existing teaching surfaces:**
   - Lab page Coach's Pick — gold games should rank highest for review.
   - Pattern Training puzzles — gold positions are auto-extracted via [[v5-lazy-generation]] / puzzle_extraction_service.
   - Clickable rule pages ([[clickable-rule-names]]) — show the user's OWN gold games as the rule's examples, not generic ones.
   - Play-with-Coach onboarding ("here's a position from your game where Légal geometry was on the board — try it now").

4. **Always include this breakdown in scanner output by default.** A scanner that only prints fire counts is incomplete. The `scan_legal_geometry.py` v2 (2026-05-18) added the teaching-gold breakdown to its stdout summary — this is the template every future detector scanner should follow.

**The general pattern:** every research artifact should be one query away from a product surface. If I can produce a count, I can produce a ranked list. If I can produce a ranked list, I can produce a "here are the 5 most teachable moments in your last 100 games" summary. Stop one level shy of that, and the product never benefits.

Companion: [[vision-match-before-ship]] (verify end-to-end vision elements are present), [[no-hollow-coverage]] (coverage % up while teaching is empty = accounting trick), [[named-rule-real-game-examples]] (real-game positions bound to named rules — this is the surface gold should feed into).
