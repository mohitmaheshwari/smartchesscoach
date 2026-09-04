# Human Chess Intelligence — Stage 0 Evidence Report

**Status:** COMPLETE  
**Date:** 2026-08-31  
**Production writes:** none  
**Stockfish runs:** none

## What Stage 0 established

The research now has a reproducible, privacy-minimized chronological corpus rather than a collection of live queries. The artifact contains opaque user/game IDs, dates, ratings, time-control provenance, clock qualification, split cutoffs, and hashes. It does not contain PGNs, player names, email addresses, credentials, or generated coaching claims.

Artifacts:

- `backend/data/corpus_snapshots/human_chess_research_2026-08-31.json`
- `backend/data/corpus_snapshots/human_chess_split_selection_2026-08-31.json`
- `docs/human_chess_split_data_lock_2026-08-31.md`
- `backend/scripts/build_human_chess_research_manifest.py`

## Pre-code audit

**PASS.** The locked scope contains literal player-facing examples; headlines are chess ideas rather than SAN reports; no research threshold was gut-locked; the success metric includes retention and real-game transfer; deferred product work remained deferred; and Mohit explicitly approved the scope and spec.

## Recovered production provenance

The producer of `games.human_model` was not present in the local `working-code` tree, but was found as two committed changes on `feat/human-model-phase0` and in the deployed repository:

- `fca5b321` — Phase 0 prerequisite producer and tests;
- `2532616c` — correct player/opponent clock de-interleaving helpers.

The exact final producer and test blobs were recovered locally. Their Git blob hashes match commit `2532616c`:

- producer: `0ae9508512b3eb6658aa3a64dc7bef9565b48c60`;
- tests: `54956c7025866665f4a0d2dee35e132753627c04`.

This preserves the semantics of `human_model_prereq.v1`; it does not silently rewrite the historical schema.

## Current production corpus

The frozen eligible population contains:

- **8,241** external Chess.com/Lichess games;
- **40** players in the product's 600–1500 range;
- a median **76** eligible games per player;
- **7,905** clock-qualified games (95.9%);
- **157** exact duplicate PGNs removed;
- **662** games excluded because stored move analysis was absent;
- **5,200** analyzed external games outside the target rating range;
- **257** Play-with-Coach/non-external games excluded.

The ordered eligible-record digest is:

`b63cd4911ab1ce8f1993e2fde9a71c68311e15a2a59cb25a9941a07efd0b73a5`

The complete file reproduced byte-for-byte on a second production run with SHA-256:

`8622fa1cde8d6457fe1b7509482363ce18ea601fd5055050995c223be5163d30`

## Clock honesty finding

The historical v1 producer extracts `%clk` tags as a flat list. That is valid only when every mainline move is annotated and no variation contributes an extra clock tag. Otherwise one missing or extra tag shifts the player/opponent de-interleaving and silently assigns clocks to the wrong moves.

The manifest therefore independently parses the mainline with python-chess and qualifies clock evidence only when:

1. every mainline ply has a clock;
2. the mainline parser has no PGN error; and
3. the mainline clock sequence exactly equals the historical v1 producer sequence.

Games failing this test remain eligible for non-clock Maia/Otter evaluation but cannot enter a clock-conditioned claim.

The source audit also found multiple older clock parsers in `rating_service.py`, `time_analysis_service.py`, `instant_dna_service.py`, and `move_time_analyzer.py`. Stage 0 did not add another product parser. A later consolidation must keep `services/pgn_clock_parser.py` as the move-observation authority or explicitly migrate it under a separate signed scope.

## The 16 apparent mismatches

The first report showed 8,225 stored prerequisite matches out of 8,241 eligible games. A field-level audit found **zero value mismatches**. All 16 are newer games where `human_model` is entirely missing; 13 contain recoverable clocks and all 16 contain recoverable ratings.

This is a write-gap, not corrupt historical evidence. The research manifest derives them deterministically from the committed v1 producer and records `stored_prerequisite_status: missing`. Product ingestion should eventually call the canonical producer, but that runtime change is not required for the offline bake-off and was not smuggled into Stage 0.

## Split decisions

Two chronological windows are locked because the tasks need different target density:

- **Move-policy and clock:** at least 10 earlier games, final 5 games for evaluation; 30 users total, with 24 fully clock-qualified evaluation users.
- **Future-weakness prediction:** at least 30 earlier games, final 10 games for evaluation; 28 users, 6,719 future observations, 935 mistakes, and 709 named events.

The detailed candidate comparison and rejected alternatives are in `docs/human_chess_split_data_lock_2026-08-31.md`.

## Verification

- 25 focused tests pass.
- Recovered producer/test blobs match their deployed commit exactly.
- Manifest record hash recomputes locally.
- Privacy assertions confirm no raw PGN, name, or email field is present.
- `git diff --check` passes on the Stage 0 files.
- Two identical production runs produced byte-identical artifacts.

## Next authorized step

Stage 1 builds isolated offline adapters and records license, weight, version, latency, and legal-move behavior for:

1. the simple rating/time-control frequency baseline;
2. Maia-2;
3. Otter without clock/history ablations;
4. Otter with only independently qualified clock/history evidence;
5. Fathom/Syzygy content verification.

No model is connected to a route, caption, puzzle, mastery record, or player-facing feature during Stage 1.
