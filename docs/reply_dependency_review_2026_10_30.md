# Run-4 response: generic reply deletion and score cleanup

The review's generality and model-quality conclusions are supported by the
recorded results. The three position-driven families remain narrow, and the
evidence-to-GPT experiment failed to establish relevant, reliable reasoning.
Its original files remain preserved. It is retired as the reasoning direction;
the evidence collector remains reusable, and a model belongs after a verified
account has been selected.

This change adds a general **search dependency locator**, removes all five raw
engine-score strings, and measures the locator on disclosed diagnostic inputs.
It does not add a new motif family or claim new automatic teaching coverage.

## What changed

`services/reasoning/counterfactual.py` extends the existing offline search tools:

- Accept a FEN and played move, plus an optional legal continuation to reach a
  later decision. Validate the entire prefix before creating an engine session.
- Search that actual node without restrictions. Nominate its best searched
  reply automatically, or accept an explicit legal move for a diagnostic probe.
- Search again, allowing **every legal move except that one**. Save both
  searches, depths, typed scores, replacement reply and the exact allowed set.
- Express the difference from the actor's perspective at the investigated
  node, including Black-to-move cases. Scores remain diagnostic JSON.
- Reuse SearchSession, canonical legal replay, identities and event facts.
  Retain the original root move and its relationship changes in each timeline.
- Preserve incomplete depths/budgets, search reversals and mate scores. Never
  turn mate scores into synthetic centipawn differences or an empty allowed
  set into an unrestricted search.
- Reject a dependency interpretation if the excluded move was not selected
  by the unrestricted baseline. Its best line remains available without that
  move; a changed score is search variation, not proof of dependence.

All outputs say `mechanism_established: false` and have `coaching: null`.
They locate decisions worth investigating. The board-mechanism connection,
comparison against adequate alternatives and teaching selection remain required.
A positive delta is not an allocation of the original move's evaluation gap.
The operator excludes the move **at the investigated ply**, not every future
use of that move or square.

The public entry point is `locate_reply_dependency`. The CLI is
`backend/scripts/probe_reply_dependencies.py`. It accepts arbitrary legal input
without FEN, square, pawn-push or piece-type rules. The ordinary `explain_fen`
teaching selection does **not** automatically consume these measurements yet.
Wiring it directly into lesson selection would incorrectly promote a locator
into an explanation.

The piece-pressure pawn-takes-piece gate was left intact. No provider or
vendored file, production route, caption pipeline or frontend was changed.
There were no LLM calls, production data writes or deployments.

## Real engine measurements

Local artifacts: `output/reply_dependency_review_2026_10_30/`.
The source export and reviewer results under the main checkout were read only.

`run_v1/` contains 14 fresh CLI investigations at depth 20: the eight existing
pressure misses, Nxe5/c4 development controls, the proposed immediate Rf4
consequence, and one seeded example from each of the three most frequent
pressure groups. Config: 2M/8M nodes per query, four-query/20M requested-node
cap per case, Threads=1, Hash=64 MiB, the same Stockfish 19 binary as before.
All 56 queries reached depth 20. Actual total: 45,779,188 nodes; case runtime
median 9.92 seconds, total 153.16 seconds. These are locator costs, excluding
the existing explanation pipeline. An offline test run overlapped part of
this run, so these are not clean shipping-latency measurements.

Both allocations ended at the same depth with identical results in these
cases. This is not independent evidence from a deeper search. No new shipping
threshold or signal-to-caption rule is locked by this experiment.

| Disclosed case | Excluded immediate move | Actor score drop, cp | Current interpretation |
| --- | --- | ---: | --- |
| corpus_00, Bd3 | d6 | -4 | Search reversal; investigate alternatives |
| corpus_01, exd4 | Qxd4 | 32 | Positive dependency candidate |
| corpus_02, Rac1 | d3+ | 119 | Positive dependency candidate |
| corpus_03, O-O-O | h6 | -4 | Search reversal; investigate alternatives |
| corpus_04, Re1 | O-O | 2 | Tiny search difference; no teaching claim |
| corpus_05, Nc3 | dxe4 | 62 | Locates the pawn capture, not a story about kicking a knight |
| corpus_06, Nb4 | Rxb4 | -133 | Substantial search reversal; baseline is unreliable here |
| corpus_07, Bf4 | e5 | 110 | Positive dependency candidate |
| Development Nxe5 | Nxe5 | 160 | Locates the recapture decision |
| Development c4 | c5 | 102 | Locates the attack on the pawn chain |
| g4 later-node control | Rf4 | 19 | Baseline chose Kh1; no dependency support |
| Frequency group d5 | exd4 | 77 | Positive dependency candidate |
| Frequency group e5 | Nxc4 | 290 | Positive dependency candidate |
| Frequency group h6 | dxc4 | 634 | Positive dependency candidate |

The original v1 record labelled all 11 positive differences as
`positive_at_all_allocations`. Its Rf4 result exposed the missing baseline-choice
guard. A failing test was committed before adding that generic guard.
`guard_reanalysis.json` applies the corrected logic to the same saved searches,
without changing their scores: ten positive candidates, three reversals, and
one unused-choice rejection. The original v1 files were not rewritten.

`controls_depth24/` repeats the three controls at depth 24, with one 8M-node
allocation and a two-query/16M cap. All six queries reached depth 24:

| Control | Drop, cp | Interpretation |
| --- | ---: | --- |
| Nxe5 recapture | 125 | Positive dependency persists |
| c4 / ...c5 | 176 | Positive dependency persists |
| Immediate Rf4 at the later g4 node | 8 | Baseline still chooses Kh1; not evidence for an Rf4 cause |

`negative_control_guarded/` then makes a **fresh** depth-24 call with the guard
in place. It reproduces the raw 8 cp difference and returns
`excluded_move_not_baseline_choice`. Its source freeze is unchanged.
All three run folders record unchanged sources during their calls and
`model_called: false`. Together these folders contain 64 fresh engine queries;
the reanalysis is separate and does not count as additional engine validation.

The independent judge's small Rf4 difference has the opposite sign. This
disagreement is preserved. The baseline's retained Kh1 line is sufficient to
reject an immediate-Rf4 dependency interpretation in our own output. Neither
result establishes the principal reason for the root g4 inaccuracy.

## Frequency-based investigation order

The existing exported scan contains 4,442 pressure-shape matches. Recounting it
reproduces the review: d5 399, e5 396, h6 283, d4 239, h3 237. Piece targets are
bishops 1,746, knights 1,716, queens 785 and rooks 195.

The three additional examples were selected from d5/e5/h6, one each, using
seed 20261030 after sorting by game ID and move number. The selection and full
counts are in `selection.json`; the search inputs contain only the FEN, played
move and necessary explicit diagnostic prefix/exclusion. Expected moves,
scores, family names and coaching reasons are not inputs to the locator.

These are exposed development diagnostics. They are not a held-out benchmark,
a generality rate, or evidence that the three largest groups now have lessons.
They identify where further deterministic connection work has the highest
observed volume. No new family has been written from these three examples.

## Five score strings fixed

Re-rendering the 33 frozen run-4 results through the changed renderer gives
exactly five changed texts: `codex_g4`, `dev_qf8`, `ho05`, `ho08`, `ho21`.
Raw engine-score strings: **5 before, 0 after**. The other 28 texts are
unchanged. This is a render audit of saved evidence, not a fresh full-corpus
engine rerun. Full before/after texts are in `render_audit.json`.

Root-capture score-comparison sentences are omitted. The Qf8 defence sentence
is also omitted: the receipt stores a numerical score but has no verified
plain-English cost. It is not replaced with relief language. Both the
remaining unit-test Rc8/score lock and the live integration assertion were
updated to the requested voice contract. Structured scores remain available
to the verifier and diagnostic tools.

## Running the locator

A manifest is a JSON list such as:

```json
[
  {"id": "example", "fen": "<legal FEN>", "played_move": "<SAN or UCI>"}
]
```

Optional `continuation` supplies legal moves **after** the played move to
reach a later node; optional `exclude_move` nominates a move at that node.
The default nominates the deepest usable unrestricted choice. Config uses
the existing explicit `ReasoningConfig` schema, including node/query caps.

```powershell
python backend/scripts/probe_reply_dependencies.py `
  --manifest output/reply_dependency_review_2026_10_30/manifest.json `
  --config output/reply_dependency_review_2026_10_30/config.json `
  --engine C:/Users/MIISCO/chess-tools/engine/stockfish/stockfish-windows-x86-64-universal.exe `
  --depth 20 `
  --output-dir output/reply_dependency_review_2026_10_30/new_run
```

The output folder must be new or empty. Saved inputs strip unrelated metadata;
every result retains source searches, legal timelines, score POV and runtime.
Partial results stay partial and do not supply a measured drop. No model key
is loaded or required.

## Validation and remaining gap

The final offline suite passes **224 tests**, including 14 new reply-deletion
contracts. Tests were committed before the implementation, and the baseline-
choice regression failed before its fix. The contracts cover both actor/score
perspectives, exact root restriction, incomplete searches, mates, only-legal
replies, invalid prefixes, reversals and unused nominated moves.

The live integration run passed **10 tests** in 107.71 seconds: eight existing
regressions over fresh Stockfish searches and two audits of the actual new CLI
artifacts. The core HTTP flow suite
was attempted against localhost:8001 and failed to connect; it is not a passing
application end-to-end check.

There are **zero new automatically taught mechanisms** in this delivery.
The reusable locator and its rejection conditions are now implemented and
measured beyond one position. The remaining step is to connect a robust
dependency to the changed board relationships and adequate alternatives,
then verify the resulting lesson. Neither a reference-valid LLM draft nor
a positive deletion score is allowed to stand in for that step.
