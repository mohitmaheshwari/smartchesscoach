# Hidden Opportunities Phase 3A.3 — Runtime Shadow Integration

**Status:** IMPLEMENTED LOCALLY; PLAYER EXPOSURE REMAINS BLOCKED
**Date:** 2026-09-06
**Branch:** `codex/hidden-opportunities-resume-v1`
**Base:** rebased onto `origin/working-code` at `1d4068bb`
**Production reads/writes during implementation:** none
**Fresh engine or model runs:** none

## What is implemented

The canonical `build_verified_hidden_opportunity` composer is now called from
the existing V5 Game Review generation path for both the player and opponent.
It consumes only the stored position, played move, better move, and stored
continuations. It does not run Stockfish, a tablebase, Maia, Otter, or an LLM.

Each evaluated position receives one explicit status:

- `candidate`
- `below_rating_threshold`
- `missing_actor_rating`
- `missing_stored_evidence`
- `invalid_stored_evidence`
- `not_proved`

This prevents a zero-candidate result from being confused with a scan that had
no usable data.

Candidate evidence is stored only under
`game_analyses.game_teaching_plan.hidden_opportunities`. It contains the
canonical proof contract, proof fingerprint, typed diagnostic
`TeachableEvent`, actor, rating band, and selection inputs. It creates no new
collection, player model, mastery record, content identity, or chess-fact
source.

## Deterministic alignment guard

The legacy V5 lookup is keyed by FEN and can collapse repeated positions. The
Hidden Opportunities path does not trust that lookup. It requires an exact
match on:

1. the four-field FEN position key; and
2. the move actually played in that occurrence.

Stored rows are consumed once per review generation. A mismatched or missing
row is counted as missing evidence and cannot produce a proof.

## Why players still see nothing

All four proof families remain Shadow in `detector_quality.py`. Their
`TeachableEvent` requests the Diagnostic surface, has no teaching copy, no
reflection, no plan authority, and cannot be serialized through
`player_dict()`.

The public Game Review projection reconstructs an allow-listed plan and drops
the entire `hidden_opportunities` envelope. A regression test serializes the
full player response and proves that the Shadow key is absent.

No ranking formula is stored. The envelope records
`ranking_formula: null`.

## Read-only incidence measurement

`backend/scripts/report_hidden_opportunity_shadow_incidence.py` scans the
stored player and opponent move-evaluation streams through the same runtime
adapter and emits aggregate counts only. It prints no IDs, positions, moves,
ratings, names, captions, or learner data and performs zero database writes.

Run after this code is present in the backend container:

```bash
cd /app
python backend/scripts/report_hidden_opportunity_shadow_incidence.py --limit 25
python backend/scripts/report_hidden_opportunity_shadow_incidence.py
```

The first command is a smoke census. The second is the complete read-only
population census required before ranking formulas are predeclared.

## Verification

- Focused Shadow/composer/exporter tests: 32 passed.
- Adjacent Review contracts, planner, validation, Phase 8, privacy, and
  Hidden Opportunities tests: 136 passed.
- Repository core live-HTTP flow command was attempted and was inconclusive
  because no backend server was listening locally; it failed before exercising
  an application endpoint.

## Remaining ordered gate

This implementation completes runtime Shadow collection and the measurement
instrument. It does not complete Phase 3A.4 or 3A.5.

1. Deploy this code without changing any proof-family authorization.
2. Run the read-only complete census.
3. Predeclare ranking formulas only where the census gives enough
   within-game disagreements.
4. Freeze independent coach rankings before generating the answer key.
5. Promote only proof families and selection behavior that pass their
   independent gates.
6. Then implement the existing try → hint → reveal → replay → recognition
   interaction and its assisted-versus-independent learning-ledger handoff.

Until those gates pass, the product must not show a Hidden Opportunity merely
because the canonical composer found one.
