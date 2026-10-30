# Offline reasoning prototype

Implemented 2026-10-30 under the [approved offline scope](general_deterministic_reasoning_scope.md). This is the first executable slice of the [algorithm](general_deterministic_reasoning_algorithm.md), rather than a production integration or a demonstrated general chess coach.

## Run one position

From the repository root, save an explicit experimental configuration JSON. The smaller development experiment used:

```json
{
  "nodes": 30000,
  "stability_nodes": 120000,
  "max_queries": 32,
  "max_total_nodes": 2000000,
  "rank_width": 4,
  "root_cap": 3,
  "reply_width": 2,
  "max_plies": 18,
  "max_hypotheses": 80,
  "max_expanded_nodes": 16,
  "hash_mb": 64,
  "equivalence_cp": 30
}
```

These are exploratory settings, not shipping defaults or newly locked thresholds. The 30 cp comparison uses the existing canonical inaccuracy floor as a diagnostic boundary, with strict `<` equivalence; it remains configurable for calibration. The node budget caps requested allocations. UCI searches can slightly overshoot their requested node count; actual consumption is recorded separately.

```powershell
python backend/scripts/explain_position.py `
  --fen 'r4rk1/ppp1bppp/5n2/4p3/1PPq2b1/P1N5/1B1PBPPP/R2QR1K1 w - - 0 13' `
  --played Na4 `
  --engine 'C:\path\to\stockfish.exe' `
  --config experiment.json `
  --output output/reasoning/position.json
```

Omit `--played` for position-only mode. Alternatively use `--input request.json`, whose fields are `fen`, optional `played_move`, `player_level`, and `history`. History is an object containing `initial_fen` and a legal `moves` list. It must reproduce the supplied FEN. History from a midgame root is marked a provided segment, not a complete repetition history.

The Python interface is:

```python
from services.reasoning import ReasoningConfig, explain_fen

result = explain_fen(fen, played_move, config=ReasoningConfig(**settings))
```

Illegal input raises `ValueError`. Terminal positions need no engine process. Normal requests return the four outcome classes from the spec, explicit search limits and unknowns, candidate scores, legal timelines, accepted/rejected/incomplete hypotheses, verified propositions, a teaching point where supported, and controlled text.

## What is implemented

- Fresh Stockfish processes, single-thread search, completed common-depth MultiPV iterations, separately typed mate/CP scores, recorded bounds and a shared query/node ledger.
- Played-root analysis before optional alternatives, including played moves absent from ranking. Compared roots get independent searches at both configured budgets.
- Equivalent choices select teaching evidence on the played root. Mate distances remain distinct coaching decisions, including mate in one versus a slower mate.
- Full rule/history-aware query identity, binary/config/source hashes, engine options, and runtime/memory instrumentation.
- Branch views over the canonical stored-line replay, with retained relationship snapshots, piece lineage, castling's rook movement, en passant and promotion type changes.
- Finite objective generation and prerequisite joins: captures/checks, opened lines, same-piece routes to concrete targets, castling preparation, maintained coverage, pawn transformations and candidate prevention of observed resources.
- Adaptive AND/OR investigation of castling and entry-square objectives, with legal own actions, adequate searched opponent replies, forcing resources, explicit omissions and unknown horizons.
- Independent checks for proposition actors, identities, timing, polarity, quantifiers, board relations and composed event/route dependencies.
- Comparative forcing certificates: an available checking capture changes a demonstrated queen exchange; or changed coverage answers a prepared check. A diagnostic pass only proposes a check. Acceptance requires a legal waiting-move witness, a closed local mate tree, legal alternate capture, two numerical searches, and independent dependency validation. Earlier defensive choices remain explicitly outside that local mate proof.
- Rejection of universal interpretations when a legal branch supplies a counterexample. A true but incidental capture cannot become the selected teaching point without a root-dependent link.
- Controlled sentence frames. No LLM, network provider, MongoDB, product route, caption override, or worker invocation is involved.

`stored_line_verifier` received additive public `root_piece_ids` and `relationship_snapshot` helpers. Existing replay IDs and output contracts remain compatible. No existing resolver bug was patched through a parallel product path.

## Current limits

The core can demonstrate consequences and a few exact or conditional comparative mechanisms, including immediate mate, checking captures during a queen exchange, and coverage against a prepared checking threat. These are limited families, not a general solution to forcing chess. A witnessed capture is never promoted to a material win merely because it appears in a PV. The output explicitly leaves settlement and unsearched defences unresolved. Defensive responsibility and persistent pawn-structure benefits remain incomplete unless supported; missing resources in a PV do not prove prevention.

The current objective-policy search supports castling and concrete piece-entry routes. The larger algorithm's full pawn-break/structural policy search, general quiet defensive objectives, competing-account adjudication and measured teaching selection are further work. Most searched accounts remain `supported_consequence`, not a proven comparative mechanism. Player level is recorded but critical chess facts and frames do not yet vary by rating.

The experimental shortlist is deterministic but uncalibrated. Best-SAN equality is not the stability test; comparative score classes are checked at both budgets. Differences between near-equivalent plans are described neutrally. A result can have useful exact facts while lacking a selected explanation; abstention is included in reports.

Engine memory is sampled, not a guaranteed OS peak. Parent CPU and sampled child CPU are separate. External NNUE files are not independently certified by the prototype; engine defaults and binary hash are recorded. A production reproducibility manifest must pin externally resolved network/tablebase files too.

## Run a development experiment

```json
{
  "split": "development",
  "cases": [
    {"id": "example", "stratum": "quiet", "fen": "...", "played_move": "..."}
  ]
}
```

```powershell
python backend/scripts/benchmark_reasoning.py `
  --manifest development.json --config experiment.json `
  --engine 'C:\path\to\stockfish.exe' --output-dir output/reasoning/development
```

The runner writes full per-case evidence, an interruption-safe progress file, outcome counts with every input in the denominator, strata, rejected claims, latency and sampled memory. Mechanical proposition validation is **not** reported as human factual correctness, explanatory quality or coaching usefulness. Those fields remain `not_reviewed` until independently graded.

Sealed evaluation additionally requires matching frozen config, code and binary hashes, the frozen development manifest, and source game IDs proving the game sets do not overlap. Exact position overlap is rejected. Family-level similarity and reviewer blindness still require a review protocol; the code cannot manufacture an untouched set. No held-out set was opened or evaluated during implementation.

## Verification and next gate

The original implementation reported 302 existing tests and uncommitted direct boundary checks. The review follow-up commits executable tests: 95 engine-free boundary/search/forcing regressions and seven opt-in local Stockfish integration tests. The first tests-only commit preceded the reviewed fixes. See the [follow-up evidence](general_deterministic_reasoning_review_fixes_2026_10_30.md) for the actual commands, baseline failures and scope limits.

From `backend`, run the engine-free suites with:

```powershell
python -m pytest tests/test_reasoning_boundaries.py tests/test_reasoning_review_regressions.py tests/test_reasoning_forcing.py tests/test_reasoning_search_contracts.py -q
```

For the real-engine tests, explicitly set `CHESSGURU_TEST_STOCKFISH` to a local executable, then run `python -m pytest tests/test_reasoning_engine_integration.py -q -s`. Without that variable they skip. These tests use the original 30k/120k budgets, check complete output repeatability outside runtime, and save per-case JSON in pytest's temporary directory. They access no API or database.

The repository-mandated `tests/test_all_flows.py` was attempted with `REACT_APP_BACKEND_URL=http://127.0.0.1:8001`. It stopped at the first request with `httpx.ConnectError`; no local server was listening. No deployed application was used as a substitute. The [implementation evidence](general_deterministic_reasoning_implementation_2026_10_30.md) records actual development outputs and the remaining quality gate.

Before any player integration: independently grade the development outputs, improve incomplete mechanisms and quiet coverage, calibrate/freeze search/selection policy, evaluate separate untouched games, and review capacity. The existing Why and caption routes remain the eventual adapters for the same engine.
