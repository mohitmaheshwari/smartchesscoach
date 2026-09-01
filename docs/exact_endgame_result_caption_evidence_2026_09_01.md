# Exact Endgame Result Caption — Evidence Record

**Authorization:** `review:exact_endgame_result_change` → Caption only
**Status:** approved for the enrolled Quality V2 surface behind `EXACT_ENDGAME_REVIEW_ENABLED`
**Not authorized:** technique naming, recurrence, diagnosis, plan, mastery, prescription

## Claim admitted

The caption may say only that one legal move changed an exact win to a draw/loss or an exact draw to a loss, and may name one legal move that preserved the original result.

The claim is not produced by a detector, LLM, Maia, Otter, or a Stockfish score. It is constructed only from a local Fathom/Syzygy response that:

- belongs to the exact normalized FEN;
- has a SHA-256 verified Fathom binary;
- has a SHA-256 verified manifest over every configured `.rtbw`/`.rtbz` file;
- partitions every legal move exactly once into winning, drawing, or losing buckets;
- uses only simple Win/Draw/Loss WDL; `CursedWin` and `BlessedLoss` abstain;
- proves the played move is outside, and the alternative inside, the result-preserving set.

No technique name is inferred from the position. The renderer says only what the exact result did.

## Evidence

- `backend/data/corpus_snapshots/curriculum_endgame_tablebase_2026-08-29.json`: 51 committed eligible positions, 51 stored moves preserving WDL, with response hashes and DTZ evidence.
- `backend/tests/test_exact_endgame_service.py`: all 51 committed positions are legal, uniquely keyed, response-hashed, and keep their stored WDL; parser partition, overlap/incompleteness rejection, exact result-change construction, result-preserving abstention, cursed-WDL abstention, already-lost-position abstention, binary hash rejection, table-manifest hash rejection, contract fingerprint rejection, review-flag isolation, central caption/event consistency, and lesson grading where exact truth overrides a stale authored answer.
- `backend/tests/test_game_review_contracts.py`, `backend/tests/test_game_review_event_adapter.py`, and `backend/tests/test_game_review_shadow_runtime.py`: the exact cause must pass the same typed cause/event boundary as other Quality V2 review claims.

Consolidated runtime gate on 2026-09-01: **210 passed** across exact endgames, Maia/Otter policy, Play with Coach, puzzle shadow metadata, analysis enrichment, review contracts, teaching engines, and rating-aware behavior. Broader non-HTTP control comparison: this branch introduced no regression; the only authorization-sentinel delta is this explicitly listed ID.

## Why the ordinary detector sample bar is not the truth bar here

The Caption-grade detector bar measures the precision of a semantic classifier over sampled positions. This claim has no semantic classifier: its truth is a complete legal-move partition from exact tablebases plus deterministic rendering. Manual review is still required for voice and UX, but cannot strengthen or weaken the underlying WDL result.

## Limitations and rollback

- Only the enrolled Personalized Review + Quality V2 cohort can see it.
- Outside configured tablebase coverage, on missing/corrupt provenance, on incomplete output, or on any schema/fingerprint mismatch, the exact path is silent and the existing review remains unchanged.
- Disable with `EXACT_ENDGAME_REVIEW_ENABLED=false`; no mastery or curriculum state is rewritten.
