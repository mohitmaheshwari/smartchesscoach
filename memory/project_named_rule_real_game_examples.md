---
name: named-rule-real-game-examples
description: Surface real-game positions where a named rule (Rule of the Square, Opposition, Pawn Fork, etc.) actually fired, as concrete teaching examples bound to the rule. Pool source = the user's own games + community game pool. Closes the gap between "learn the rule abstractly" and "see it in a game you actually played."
metadata:
  type: project
---

Mohit (2026-05-17) framed this while reviewing the END_RULE_OF_SQUARE Phase 2 audit. The detector fires on real positions where the rule was missed; those positions are gold for teaching — a 1200 sees the rule abstractly AND in a position someone actually played.

## The idea

For every named V5 principle / shape pattern (28 principles + 24 shapes), the detector's per-fire output is a candidate teaching example. Surface those positions in the teaching UI alongside the abstract rule.

Two sources:
1. **The user's own games.** "You missed Rule of the Square in your game vs Walloo21" — strongest because the player remembers the game.
2. **Community pool.** When the user's own games don't have a fire for a rule, pull from the broader corpus. Anonymise opponent names.

## Why this matters

- `[[sub1500-memory-anchors]]` — 1200-1500 players remember named principles + geometric shapes, not move sequences. Real positions anchor the rule to a visual.
- Closes the loop between detector → caption → teaching. Right now the detector fires inside game review only. The same fire could feed a "show me a real example of this rule" surface.
- Scales: every Phase 3-5 endgame principle automatically populates new teaching examples.

## How to apply (future implementation)

When implementing:
1. **Reuse existing per-fire audit scripts** as the data source. They already enumerate every fire in the corpus with FEN + evidence.
2. **Filter by pedagogical purity.** Same filter that gates the V5 caption (e.g., the eval-bracket Pass 4 filter on RULE_OF_SQUARE). The teaching example must be a clean fire.
3. **De-duplicate.** Within a rule, prefer ~3-5 representative examples per difficulty tier; don't dump 50.
4. **Tag by user.** Each user has "your own examples" (from their games) + "community examples" (from others'). UI surfaces own first.
5. **Wire to `endgames.json` vocabulary.** Same rule name in Play-with-Coach lesson library, V5 captions, and these examples. One vocabulary across surfaces (`[[no-parallel-surfaces]]`).

## Where it fits in the backlog

- **Prerequisite:** Phase 2-5 of [[endgame-principles-backlog]] complete (detectors fire reliably and audited).
- **Adjacent:** [[pattern-skill-tracking]] — once we record per-user applied/missed counts, we can show "you missed Rule of the Square 3 times — here are your examples."
- **UI:** Slot into the teaching screen for each named rule. New surface, not retrofitting existing ones.

## Open questions

- Difficulty tiering: should "your own" examples be shown chronologically (most recent first) or by clarity (cleanest geometry first)? Probably clarity for teaching, recency for "see your progress."
- Community example sourcing: stratify by rating? A 1200's example of Rule of the Square should come from a similar-rated game, not a GM endgame.
- Anonymisation: opponent username shown or hidden? Probably hidden for community pool ("a player rated 1180 missed this") to avoid social weirdness.
