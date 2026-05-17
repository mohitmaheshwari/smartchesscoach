---
name: We are a coach, not a board narrator
description: Cross-cutting product principle. Every player-facing string must have teaching context, not just reading context. Applies to captions, decryption, play-with-coach, postgame, plateau breaker — everywhere the player reads our words.
type: feedback
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
**Product positioning rule.** This product's category is **chess coaching**. Chess.com / lichess / Chessbase already do board description, move classification, and engine-fact reporting. Players use ChessGuru when they want a coach.

That means **every player-facing string must have a teaching tone — not a reading tone.**

The user's exact framing on 2026-05-08 after the voice sweep:
> "That should honestly become a core product principle across: captions, decryption, play-with-coach, postgame review, plateau breaker. Everywhere."

## Surfaces this rule governs

  - per-move captions (Path B, decryption_voice/per_move_caption.py)
  - critical-moment narratives (decryption_voice/decryption.py + concept_dispatcher templates)
  - V5CoachingCard "why_best_is_better" / "narrative" content
  - CoachPlaySidebar.TeachingMoment / coach commentary during Play with Coach
  - postgame review explanations
  - plateau-breaker / coaching loop messages
  - puzzle-feedback text (incl. punishment-puzzle MVP)
  - opening lessons / endgame lessons / trap warnings

If a string reaches the player, it follows this rule.

## The mechanical version of the rule

**List a square only when it contains something interesting.**

A square in a caption is interesting only when an enemy piece (≥minor) sits on it. If the listed squares are empty, the caption is annotation-talk — engine output dressed up. Replace the square list with meaning-language ("fights for the centre", "wakes up the bishop", "asks Black a question", "starts to crack their structure").

Examples of the rule's effect:

| Before (annotation rhythm) | After (coach voice) |
|---|---|
| "Pushes to d4. Hits c5 and e5 now." (when c5/e5 are empty) | "Pushes to d4 — fights for the centre. Now your pieces have room." |
| "Knight to d4. Covers c6 and e6." | "Knight to d4 — strong central square. Both sides want this; you got it first." |
| "Pawn to b4. Bites at a5 and c5." | "Pawn to b4 — gains ground on the queenside. Starts to crack their structure." |
| "Pawn to e3. Holds d4 and f4." | "Pawn to e3 — quiet support move. Builds a solid base." |

The user's distillation:
> "Humans don't naturally say 'controls c5 and e5' unless there's actually tension there. They say 'fights for the centre', 'opens the bishop', 'asks Black a question', 'wins space', 'now they have to react'. That's chess meaning."

## Forbidden meta-commentary phrasings

Delete on sight. These sound like annotation software trying to sound intelligent.

  - "Quiet move —" (then more text) — drop "Quiet move —"
  - "useful move" / "small but useful"
  - "covers squares" (without naming what's there)
  - "controls the column / file / diagonal" (without naming target)
  - "tests their pawn structure"
  - "claims central space" (alone)
  - "active diagonal" / "fresh diagonal" (alone)
  - "repositions" / "redeployment"
  - "to a better spot"
  - "solid setup" (as a tail)
  - "reasonable move"
  - "develops smoothly"

Each of these has a teaching-tone replacement that says what the move actually accomplishes.

## How to apply

When writing or auditing any coaching text:

  1. Re-read project_coach_voice.md for tone.
  2. Re-read this memo for the structural rule (squares only when interesting).
  3. Ask: "Would this caption make sense to a 1200 player WITHOUT them looking at the board?" If it's just listing coordinates, no.
  4. Ask: "Does this sentence answer 'why should the player care?' or just 'what square changed?'?" If the latter, rewrite.
  5. Coverage % is necessary but not sufficient. A caption can be 100% factually correct, pass the 1200-test (concept + concrete consequence), AND still fail the coach-voice test if it leads with empty geometry.

## Why this memo exists

During the 1200-test sweep on 2026-05-08, captions drifted into **stenographer mode** — concrete and verifiable, but reading like a chess engine output. User caught it: "we are chess coach category, why are we not behind teaching really."

Two waves of voice rewrites later, the user's verdict (verbatim):
> "This is now genuinely differentiated from normal chess annotations. The important breakthrough is not 'better wording'. It's that the system now understands: coaching language ≠ move description. That's the hard part most chess products never cross."

This memo encodes that breakthrough so it stays load-bearing across surfaces and across future drift.
