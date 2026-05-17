---
name: Situational personality — the next coaching-voice frontier
description: Coach captions should adapt their tone to game state. Calm in quiet positions; urgent in tactical ones; punishment when missed; survival when worse. NOT YET BUILT — this memo captures the design rules so when the work starts, the frame is already set.
type: project
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
## Status

Not yet implemented. Captured as the **next design leap** identified by the user on 2026-05-08, after the structural voice sweep landed.

User's exact framing:
> "The next leap is probably NOT better wording. The next leap is situational personality. Different coaching energy depending on position context. Right now captions are semantically improved but eventually they should become emotionally aware of game state. That's where ChessGuru becomes dangerous. Because chess.com explains moves. A coach understands what phase the student is psychologically in."

## The seven tones

Each tone fires when specific game-state conditions are mechanically verifiable. Tone affects voice/cadence/word choice — not the underlying chess facts.

| Tone | Fires when | Voice signature |
|---|---|---|
| **Calm positional** | Quiet middle of game, no tactics flagged, eval near 0, no recent mistakes | Measured. "Steady move." "Holding the structure." "Building slowly." |
| **Urgent tactical** | Position has check available, capture available, hanging piece on board, mate threat within 3 plies | Sharp. Short sentences. "Now. Take the bishop." "Mate in two — find it." |
| **Punishment** | Opp just blundered (≥300cp swing in user's favour), user has clear win | Decisive. "Free piece. Take it." "Now press." |
| **Missed momentum** | User had a clear winning move recently and didn't play it; eval still positive but smaller | Honest, not soft. "You had bigger. Bxe5 won the queen — your move keeps you up but slows the kill." |
| **Looks active but weakens** | User's move LOOKS forcing (check / capture / threat) but actually drops material or king safety | Cautionary. "That check feels good — but it costs the knight." |
| **Conversion** | User is decisively winning (eval ≥ +500), needs to convert | Steady, confidence-building. "You're up a piece. Trade pieces, not pawns." |
| **Survival** | User is decisively worse (eval ≤ -300), needs resources | Resilient, honest. "Losing — but their king's exposed too. Look for tricks." |

## The hard guardrail — narrative words require state evidence

Words that imply narrative awareness CANNOT fire without verified game-state evidence backing them. Wrong firing destroys trust instantly.

**Forbidden without state evidence:**

  - "finally" — implies the player has been delaying. Requires session-level state ("first central pawn move after N quiet moves").
  - "calmly" — implies the player is under pressure. Requires opp-attack signal.
  - "desperately" — implies the player is losing. Requires eval ≤ -X.
  - "too slow" — implies a tempo problem. Requires opp tempo signal (initiative tracker).
  - "in time" — implies a race. Requires racing pawns or king-hunt context.
  - "before it's too late" — same.
  - "wakes up" / "comes alive" — implies the piece was passive. Requires piece-activity history.
  - "courageous" / "brave" / "bold" — implies risk acknowledgement. Requires verified material/positional risk.
  - "still has a chance" — implies the player is losing. Requires eval signal.
  - "everyone's been there" — empathy without specifics is patronising. Requires the move to actually be a common-pattern miss.

User's framing of the guardrail:
> "If wrongly fired, they destroy trust instantly. So your instinct there was correct: don't hallucinate emotional context without state evidence."

## Implementation rule when this work begins

Each tone-firing detector must:

  1. Verify ALL preconditions for that tone mechanically (eval thresholds, ply windows, piece-activity history, etc.)
  2. Fail-closed: if any precondition is uncertain or unverifiable, fall back to neutral coach voice
  3. Be auditable like the existing detector set — verifiable claims, no hallucinated narrative

The same audit infrastructure (mock_correctness_audit) extends naturally: per-tone verifier + 1200-test still applies.

## What this is NOT

  - NOT another caption rewrite layer. The current captions are right; this layer adapts how they're delivered.
  - NOT LLM-generated tone. We have deterministic state — derive deterministic tone.
  - NOT applied universally. Many moves stay in calm-positional. Tone shifts only when state warrants.

## When to start

When the user signals readiness. This memo captures the design so we don't have to re-derive it. Until then, the structural voice work (feedback_teaching_not_reading.md) is the load-bearing rule and stays the active focus.
