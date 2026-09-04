# Human Chess Intelligence — Chronological Split Data Lock

**Status:** LOCKED FROM PRODUCTION DATA  
**Date:** 2026-08-31  
**Raw evidence:** `backend/data/corpus_snapshots/human_chess_split_selection_2026-08-31.json`  
**Corpus:** `backend/data/corpus_snapshots/human_chess_research_2026-08-31.json`

## Decision 1 — move-policy and clock evaluation

**VALUE:** at least 10 earlier games, followed by the player's final 5 eligible games as the chronological evaluation window. Clock experiments use only the 24 users whose complete evaluation window passes the independent clock-alignment verifier.

**EVIDENCE:**

- 30 users and 150 future games remain, containing 3,609 current observations and a median 140 observations per user.
- All 5 evaluation games are clock-qualified for 24 users.
- The 5+3 candidate adds only 3 users, while reducing future observations from 3,609 to 2,193 and median named events from 12 to 6.
- The 20+5 candidate has the same evaluation length and median evidence as 10+5 but loses one user, so it is dominated for a pretrained move-policy comparison.

**REJECTED CANDIDATES:**

- 5 earlier + 3 future: broader by 3 users, but the evaluation window is materially thinner and one quarter of users has no named future event.
- 20 earlier + 5 future: no evaluation-evidence gain over 10+5 and one fewer user.
- 30 earlier + 10 future: excellent for weakness stability, but unnecessarily narrows the primary move-policy and clock cohort.

## Decision 2 — future-weakness prediction

**VALUE:** at least 30 earlier games, followed by the player's final 10 eligible games.

**EVIDENCE:**

- 28 users and 280 future games remain, containing 6,719 observations, 935 mistakes, and 709 named events.
- The median future window contains 30 named events and 5 distinct named topics, compared with 12 named events under either 5-game evaluation candidate.
- It retains 23 users with at least one named future event—only one fewer than 10+5—while providing 2.5 times the median named evidence.
- This track predicts a distribution of future weaknesses, so the denser target window matters more than the two-user difference.

**REJECTED CANDIDATES:**

- 5 earlier + 3 future: only 242 named events; median 6 per user and p25 zero.
- 10 earlier + 5 future: 24 users with named evidence, but median 12 events is too sparse for a stable top-three weakness target.
- 20 earlier + 5 future: loses a user relative to 10+5 without increasing evaluation evidence.

## Measurement method

The manifest was generated read-only from production `games` and `game_analyses`. Eligibility required an external Chess.com/Lichess game, rating 600–1500, a trusted play date, a valid mainline PGN, and already-stored Stockfish move evidence. Exact duplicate PGNs were removed. Each candidate used the last N eligible games per player; no future game entered earlier history.

Evaluation game IDs were then joined read-only to `move_observations` with `schema_version >= 16`. The raw artifact records totals and per-user distributions. No `$sample`, production write, model inference, LLM call, or Stockfish re-analysis was used.

This lock selects evaluation windows only. It does not lock model thresholds, soundness bands, puzzle difficulty formulas, complexity formulas, caption rollout gates, or detector promotion.
