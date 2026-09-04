# Human Chess Intelligence — Stage 4 Caption Protocol

Date: 2026-08-31

## Outcome

Stage 4 turns Game Review from a move verdict into a verified coaching explanation:

1. what changed on the board;
2. why the played move failed or what the better move accomplished;
3. whether this is connected to verified prior evidence about this player;
4. one transferable action for the next game.

It does not add a second caption engine. `services.caption_pipeline.build_move_teaching_decision` remains the authority for both Game Review and Play with Coach.

## Current call graph and disposition

| Surface | Current source | Stage 4 disposition |
| --- | --- | --- |
| Game Review primary move text | `MoveTeachingDecision.text.caption`, stored as `move.caption` | Keep as the only primary caption |
| Game Review habit line | `MoveTeachingDecision.teaching_meta.principle_cue` | Keep as the transferable instruction |
| Play with Coach V5 feedback | Same central decision, with live-session context | Keep; consume the same structured explanation contract |
| `/coach/decryption/per-move` fallback | Stored `caption_llm`, decryption moments, then deterministic caption | Compatibility fallback only; it must not outrank a fresh `move.caption` |
| Game Moments explanations | Concept candidate narrator | Keep as a separate summary surface; it must not mutate the primary move caption |
| Legacy V5 narrative enhancer | `narrative` field | Retired from primary display; no new Stage 4 behavior may depend on it |

## Non-negotiable invariants

- A personal statement may frame a verified chess explanation; it may never replace it.
- Personal claims require eligible stored evidence. No evidence means no personal claim.
- The final composed caption is verified after every enrichment, including personalization.
- A failed verification removes the unsupported enrichment and falls back to verified board text.
- Captions never translate centipawn loss into material lost.
- A mistake caption names a concrete failure or honestly says that the mechanism is not yet known.
- The same structured decision is available to Game Review and Play with Coach.

## Structured explanation contract

Each `MoveTeachingDecision` returns:

- `board_explanation`: verified move-specific chess explanation;
- `player_connection`: optional evidence-backed link to the player's history;
- `transferable_instruction`: short habit or scan to use next time;
- `confidence`: `verified`, `limited`, or `silent`;
- `provenance`: rule and evidence-family identifiers, never user-facing statistics;
- `personal_evidence`: evidence kind and eligibility marker, without raw private history.

The rendered caption remains plain coach language. The structure exists so UI, audits, and future learning measurement do not parse prose.

## Gold corpus

The existing `gold_captions` collection is the starting source, not a new competing store.

- 946 stored reviews reduce to 467 unique positions after `(game_id, move_number, move_san)` deduplication.
- For duplicate reviews, prefer a verified correction over an earlier version, then the newest review.
- Exclude rows without board/engine evidence from truth scoring.
- Reclassify positions by a clean, engine-grounded situation rather than trusting broad legacy gap labels.
- Keep the easy-English corpus as a voice reference only; it is not position truth.

The first audit strata are the situations already supported by deterministic facts: mate allowed/missed, one-move material loss, walked-into tactic, missed free material, opening deviation, and endgame technique. Positional residue remains explicitly unclassified until it has a verifier.

## Rubric

Hard gate:

- board claim true;
- stated line legal;
- better move is supported by stored engine evidence;
- personal connection has eligible stored evidence.

Quality dimensions, measured separately:

- causal failure is explained;
- purpose of the better move is explained;
- language is understandable to a 600–1500 player;
- transferable instruction is present and specific;
- caption does not repeat itself;
- personal connection helps rather than distracts.

No combined score can compensate for a false board or personal claim.

## Reviewer protocol

- Reviewers see the board, played move, engine continuation, and two anonymized captions.
- Source labels, author, rule name, and system/gold identity stay hidden.
- Reviewers grade truth first, then usefulness and clarity.
- Disagreements on truth go to an independent board verifier; preference disagreements stay preference data.
- Manual coach review is an external final-stage input, not simulated during implementation.

## Rollout

1. Generate the structured explanation in shadow while preserving current visible text.
2. Compare current and Stage 4 output on the locked corpus and production-shaped samples.
3. Reject any variant with a verified false claim.
4. Lock coverage/preference thresholds from observed distributions, not intuition.
5. Enable for internal accounts, then a small cohort, with immediate flag rollback.

The measured pre-change baseline is 230 WHY failures among 2,446 sampled mistake/blunder captions (9.4%). This is a baseline, not a release threshold.
