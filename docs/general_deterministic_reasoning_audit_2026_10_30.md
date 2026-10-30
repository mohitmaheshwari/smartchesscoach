# General deterministic reasoning: repository audit

Inspection date: 2026-10-30. Repository: `C:\Users\MIISCO\smartchesscoach`, branch `working-code`, HEAD `15b84ebabff8e14112436f972b8eaa22abe62b6c`.

This is an inspection and planning pass. No production source, configuration, database, deployment, or existing document was changed. The attachment ends literally at “5. One tactical”; this report includes tactical and quiet examples to satisfy the preceding requirements.

## Evidence boundary

Read root `AGENTS.md`, applicable skill instructions, relevant memory entries, source, fixtures, and existing design documents. No deeper AGENTS file applies to the inspected `backend/`, `frontend/`, or `docs/` paths. The many `_...` worktrees are separate existing work; they were not used as the implementation under audit.

Initial tracked changes were `.claude/settings.local.json`, `backend/services/human_policy_runtime.py`, and `docs/coach_ladder_scope.md`. There were many pre-existing untracked worktrees and artifacts, including `docs/why_engine_framework.md`. They were preserved. New evidence lives only in `output/general_reasoning_audit_2026_10_30/`; the three new documents form this deliverable. No commit or push was performed.

Evidence labels used below:

- **Source verified:** inspected executable code or caller search; no claim about deployed configuration or frequency.
- **Reproduced:** executed a local probe or existing test. Stubbed inputs are identified.
- **Pending:** requires inaccessible data, an authenticated application, production telemetry, or a future implementation.

Local MongoDB at port 27017 responds, but both an unauthenticated collection query and the repository's existing local `backend/.env` configuration returned `OperationFailure`, code 13, authentication required. The configured DB name is `chess_coach`. No credentials were printed, guessed, or changed. Consequently no current collection counts, production captions, queue pressure, stored inaccuracy reversals, or review-ruling frequencies were verified. Ports 27018 and 8001 refused connections in the local port check. This is not evidence that other backend ports or production are unavailable.

The initial sandbox blocks local sockets with Windows error 10013. Read-only engine/tests/localhost checks completed using approved local process permissions. The configured default engine resolves to nonexistent `/usr/games/stockfish` on this Windows checkout; probes explicitly used the already installed Windows binary. No binary was downloaded.

## 1. Actual execution paths

### Imported game to stored analysis and caption

```text
journey_service.py:1430,1474 / routes/games.py:418,445
    -> analysis_queue
analysis_worker.py:566 claim_next_job (atomic find_one_and_update)
    -> process_job -> analyze_game_with_stockfish (1146-1156)
stockfish_service.py:848-857 mover-relative cp_loss
    -> stored PVs for bad moves (934-943), candidate/reply evidence
analysis_worker.py:1295 LLM_CAPTIONS_ENABLED gate
    -> move_purposes.purposes_for / threat_check
    -> llm_caption.build_facts / write_caption
    -> llm_caption + llm_caption_facts on each move (1434-1436,1482-1484)
analysis_worker.py:1903-1988
    -> generate_game_decryption_v5, eagerly when possible
    -> game_analyses upsert (2007-2010)
```

The worker **does eagerly generate V5** now; the old memory note saying V5 is only lazy is stale. Failure retains a lazy fallback (`analysis_worker.py:1994-1996`). The `/api/coach/decryption/v5/{game_id}` handler also reads cached V5, invalidates old versions, and regenerates in a background task (`routes/coach.py:846`, `930-963`, `1237-1257`, `1362-1365`, `1401`).

Within V5, `game_decryption_v5_service.py:4164-4174` calls **`framework.decide`**, not `move_reasoning.reason_about`. `framework.py:236-259` first calls the central `caption_pipeline.build_move_teaching_decision`, then replaces caption text with stored `llm_caption` if present. The cascade still owns its other output. This is a final text-authority distinction, not merely two equivalent names for the same function.

`caption_pipeline.py:7367`, `7418-7426`, `7983-7987` extracts facts and renders the deterministic caption. It directly reuses selected contrastive helpers, for example `q_blocked_a_plan` at `9651-9663`; `caption_facts.py:11311` imports `q_abandoned_own_defender`. Thus **some contrastive reasoning reaches players**, but the whole `move_reasoning` orchestration does not.

### Why button

```text
GameDecryptionV5.jsx:2683 isFaultedCard, either side
    -> WhyThisWasBad (2179), fetch with SAN and opponent flag (2187-2189)
GET /api/coach/why/{game_id}/{move_number} (routes/coach.py:1423)
    -> authorise ownership (1451-1456)
    -> select stored user/opponent evaluation (1478-1499)
    -> asyncio.to_thread(_run) (1562)
    -> new StockfishEngine, Threads=1, default Hash=128 MiB (1518)
    -> 8 root candidates, depth 18 (1520-1521)
    -> fresh played continuation, depth 18, up to 12 plies (1532-1538)
    -> why_on_demand.explain (1545), using stored cp_loss
        -> _mate_from_score
        -> punishment_resolver.resolve_received
        -> resolve_missed for a sufficiently close alternative
        -> deterministic _phrase or no answer
    -> text/arrows or found:false; no explanation persistence here
```

The frontend prints `result.text` (`GameDecryptionV5.jsx:2250`) and otherwise “We can’t show a clear reason here” (`2230-2237`). This request never calls `why_words.write`, `move_principles.separating_themes`, `ablation.attribute`, or `move_reasoning.reason_about`.

### Admin and review tools

- `server.py:732-734` registers `admin_reasoning_trace`. Its `_trace_payload` calls `reason_about(move)` **without a Probe or candidate set** (`admin_reasoning_trace.py:200-204`). Pasted FEN mode separately gets a best move and two lines (`102-140`). Therefore the displayed trace is the actual framework report, but not a trace of the Why button, and its deeper stability probe is unavailable by default.
- `server.py:707-720` registers `admin_positional_reasons`, `admin_detector_review`, and `admin_claude_reasons`. The positional and Claude queues store candidate authoring/reviewer evidence; their module contracts explicitly exclude player influence. `admin_detector_review.py:1905` uses `resolve_both`; its producer path is useful for review, not the player Why caller.
- Review labels are development material, not proof. A module named “proof” or “verified” is not itself evidence of exhaustive branch coverage.

## 2. Reuse inventory and disconnected components

| Component | Verified capability | Boundary / disposition |
|---|---|---|
| `stored_line_verifier.py:30-152,631-775` | Legal replay, stable root-based piece IDs, captures, promotion type, castling rook identity, en-passant capture square, per-ply check/reply counts, relationship/line changes | **Extend this**, rather than invent a second timeline. Currently a supplied single line, not explanatory branching search. |
| `stored_line_verifier.py:365-431` | Bounded material minimax over captures/checks/promotions, all evasions in check, stand pat otherwise | Reuse as a bounded tactical diagnostic. Depth 4 and omitted quiet moves prevent general soundness/proof claims. |
| `candidate_caption_evidence.py:125-165,169-246,257-325` | Played and best roots mandatory; replayed branches, fingerprints, provenance, separate CP/mate fields; missing branches via restricted engine search; rejects bound scores | Extend its transport primitives. Its current API requires played+best and may reuse scoreless/stale stored branches; cannot directly implement FEN-only/fresh-comparison requirements. |
| `line_motif_geometry.py:116` | Full legal line walk and geometry primitives | Reuse geometry, not its motifs as a complete general inference engine. |
| `move_reasoning.py:450-469,783-879` | Six registered questions, differential checks, named challenges, rejection reporting, bounded Probe abstraction | Only whole-framework caller found in runtime source is admin trace. Useful scaffolding, but not a general hypothesis generator or branch verifier. |
| `contrastive_reasoner.py:51,173,408` | Specific blocked-plan and abandoned-defender reasoning | Individual helpers have player callers; orchestration `reason()` is not the canonical player engine. Preserve reviewed concepts as candidate producers, with new verification. |
| `move_principles.py:309-315,337-409` | Four pure principles and theme separation across supplied good moves | Caller search finds no runtime service/route consumer. “Mobility” is geometric (`93-114`), despite earlier prose calling it legal. Pins need separate treatment. |
| `ablation.py:73-95,179-195,247-296` | Apply externally supplied teleport/pass/remove probes; fresh process evaluator; excludes a reconstruction of best | No automatic hypothesis enumerator or runtime consumer found. Its `share` and `leader` must not become causal attribution or teaching rank. |
| `move_purposes.py:1693-1770` | Many tactical/quiet purpose seeds, plus plans for moves actually played | Runtime caption caller exists. Several seeds use attack/cheapest-attacker heuristics (`191-207`), so seed status must differ from accepted reasoning. |
| `why_words.py:62,294-340` | Optional LLM phrasing of resolver slots, token/relation guard | Default off; no runtime caller found. Do not describe all narration as unwired: **caption narration is wired behind a different flag**. |
| `framework.py:203-260` | Final caption decision and stored LLM override | Preserve as the product adapter. A new common reasoning result should eventually feed both it and Why. |

Caller audit command, scoped to the actual checkout's runtime source:

```powershell
rg -n 'why_on_demand|punishment_resolver|contrastive_reasoner|move_reasoning|move_principles|why_words|services.ablation|from .*ablation' backend/routes backend/services backend/analysis_worker.py backend/server.py --glob '*.py'
```

No-match findings apply to this inspected source tree, not reflection/dynamic imports in unknown deployments.

## 3. Reproduced defects and limitations

Counterexamples are saved in `probe_results.json` and `boundary_results.json`, with executable probes beside them. They establish function behavior, not incident prevalence.

| Finding | Evidence and result | Scope |
|---|---|---|
| Played score absent outside top candidates | `why_on_demand.py:252-262` cannot read mate transitions unless played SAN is in candidates. The route refreshes its PV but never its score. Real depth-18 runs omit **Na4 and e4**, and both return no answer. | Confirmed coverage limitation; not “played move is never analysed.” Its continuation is searched. |
| Received-mate line duplicates the reply | `_mate_from_score` stores the whole played continuation in `Punishment.line` (`why_on_demand.py:280-283`); `explain` prepends the reply again (`364-366`). Legal Fool's Mate input returns `g4 Qh4# Qh4#`; full replay fails on the last entry. | Reproduced with explicit truthful mate-score input. Existing arrow walk quietly stops at the illegal suffix. |
| Promotion assigned to wrong side | `punishment_resolver.py:559-560` accepts any `=` in the line. From `7k/P6p/8/8/8/8/8/K7 w - - 0 1`, `Kb1 Kg7 a8=Q` is legal. Resolver says **their** pawn promotes; it is White's pawn. | Reproduced full `explain` result; underpromotion would also invalidate the unconditional “queen” wording. |
| Narration accepts contradictory meaning | `why_words.py:249-277`, `_CONVEYS` at `130-143`. Both “Qxd4 wins your knight” and “Qxd4 does not win your knight” return validator success. “Your knight wins Qxd4” also passes. | Synthetic resolver facts isolate semantic validation, with no LLM call. `llm_caption.py:315-340` has only token containment and formatting checks. |
| Chosen retreat becomes “only” retreat | `why_words.py:217-219` maps a single observed `retreat_san` to `the_only_square_it_can_go_to`. Resolver never establishes uniqueness (`punishment_resolver.py:513-556`). | Reproduced fact packet with `Nf3`. Currently unwired narrator, still unsafe to reuse as accepted IR. |
| Attack heuristic overstates necessity | `_must_move` uses counts/relative piece value (`207-244`). In `7k/6pp/8/8/3b4/8/8/QK2R3 w - - 0 1` it says Qa1 must move, while **Re8#** is legal mate. | Board-verified helper counterexample. Does not establish a returned TRAPPED caption for this position. |
| Material settlement differs between paths | On existing `test_stored_line_verifier.py:136-164` fixtures, `_line_material_gain` returns **+400**, while the canonical bounded continuation settlement returns **0**. These are the rook-recovery and check-before-recovery cases. | Reproduced helper divergence; not an exhaustive claim about either verifier or production miss rate. Both use bounded search. |
| Admin pasted-FEN score perspective is wrong | Adapter methods return White POV (`stockfish_service.py:244,342`); admin code treats the played score as opponent POV (`admin_reasoning_trace.py:133-136`). With White scores best=100, played=40, expected loss=60, actual=140; Black best=-100, played=-40 gives actual=0, expected=60. | Executed the real function AST with explicit mocked adapter scores; route import is blocked by missing bcrypt. `Probe.evaluate` also promises side-to-move but returns the adapter's White score (`move_reasoning.py:165-173`); no current evaluate consumer found. |
| Recommendation boundary disagrees with severity | `CLOSENESS_CP` is 30, but `gap > CLOSENESS_CP` (`why_on_demand.py:446-449`) accepts gap=30; severity already calls 30 an inaccuracy. | Real selector with stubbed mechanism/scores reproduces acceptance. This is an inclusive-boundary defect, not a fresh chess evaluation of Nf6. |

The material resolver also has a hard six-ply consequence window (`punishment_resolver.py:64,196,409`) despite a twelve-ply requested PV. This can omit later consequences; its current production undercount frequency was **not** measured. A legal PV and a quiet-on-the-last-square test do not establish that other captures, checks, quiet defences, or sacrifices have been resolved.

The Why path does not reclassify a stored inaccuracy after refreshing search (`routes/coach.py:1545-1550`): fresh continuations/candidates and stored `cp_loss` can disagree. No stored-flag reversal was verified against local Mongo. This is a source-confirmed missing check, not a claimed production event.

## 4. Local verification results

Engine: **Stockfish 19**, SHA-256 `45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0`; Python 3.11.9; python-chess 1.11.2. Binary: `C:\Users\MIISCO\chess-tools\engine\stockfish\stockfish-windows-x86-64-universal.exe`.

Two different experiments were kept separate:

```powershell
# Run from the repository root; only output/ evidence files are written.
python output\general_reasoning_audit_2026_10_30\baseline_probe.py
python output\general_reasoning_audit_2026_10_30\probe.py
python output\general_reasoning_audit_2026_10_30\boundary_probe.py
```

1. **Current Why helper baseline:** actual `StockfishEngine.get_candidate_lines`, `get_principal_variation`, and `explain`, 8 candidates/depth 18/Threads 1/Hash 128, fresh process per FEN. No HTTP/auth/database; `cp_loss=None`, because no stored loss was available. Qf8, Na4, and quiet e4 each returned `None`; runtimes **9.055 s, 7.150 s, 5.722 s**. This is three development examples, not a coverage estimate. See `baseline_results.json`.
2. **Controlled investigation:** fresh process per query, Threads 1, Hash 64, node budgets 150,000 and 600,000. Record completed unbounded score/PV iterations; an interrupted aspiration bound is not an exact result. MultiPV uses the last complete common-depth snapshot with distinct roots. This correction is necessary: naive “last exact value per rank” can combine different depths and duplicate roots. See `probe.py:analyse` and `probe_results.json`.

Selected single-root results, consistently from the original mover's perspective:

| Decision | 150k nodes | 600k nodes | Interpretation |
|---|---|---|---|
| Black Qf8 | -1069 cp | mate against Black in 10 | Material-looking shallow score becomes a mate score. Keep types distinct. |
| Black Qh7 | -860 cp | -858 cp | Already losing; better resistance found, not a saving move. |
| White Na4 | +43 cp | +29 cp | Gives up the large advantage found after Nd5. |
| White Nd5 | +350 cp | +410 cp | Stable qualitative tactical opportunity; score amount changes. |
| White e4, quiet fixture | -21 cp | -25 cp | Inferior under these searches; no exact allocation to one feature. |
| White Nf3, quiet fixture | +28 cp | +29 cp | Bg2 is also near-equivalent (+31 cp at 150k). |

The repeated 150k-node Nd5 query returned identical score/PV/depth/nodes. This establishes reproducibility for that local configuration/query, not universal reproducibility across engines or hardware. Nineteen recorded investigation queries took 27.75 s in aggregate, excluding the repeat and real-helper baseline. Individual query times were 0.780–2.911 s. Maximum **sampled child-engine RSS** was 320,516,096 bytes (~305.7 MiB), with Hash=64 MiB. This is not peak Python-plus-engine memory or a production capacity benchmark; sampling may miss peaks.

Existing test runs, no new `backend/tests` files:

```text
python -m pytest -q -p no:cacheprovider
  tests/test_why_on_demand.py
  tests/test_material_gain_survives_the_recapture.py
  tests/test_punishment_claims_answer_to_the_line.py
  tests/test_move_reasoning_framework.py
  tests/test_move_principles_separate.py
  tests/test_ablation_judges_the_cause.py
  tests/test_why_words_cannot_add_chess.py
  tests/test_we_never_prescribe_a_move_we_would_fault.py
=> 202 passed in 6.15s

python -m pytest -q -p no:cacheprovider
  tests/test_stored_line_verifier.py tests/test_candidate_caption_evidence.py
  tests/test_mate_is_read_from_the_score.py
  tests/test_pronouns_follow_whose_move_it_is.py tests/test_left_it_loose.py
  tests/test_pushed_past_the_support.py tests/test_self_removal_caption_voice.py
=> 100 passed in 3.57s
```

Initial collection including `test_reasoning_trace_is_the_engines_own_account.py` failed: importing its auth dependencies requires unavailable `bcrypt`. It was not counted as passing. The 302 passing tests exercise their existing assertions; several tests use mocks or permissive checks and do not exclude the counterexamples above. No backend code changed, so the live-server `test_all_flows.py` mandate for backend changes was not triggered.

## 5. Capacity and determinism

- Engine adapter defaults are Threads=1 and Hash=128 MiB (`stockfish_service.py:176,193-195`); its shutdown already has quit/close recovery (`217-228`). Do not report the historical process leak in its comments as a currently reproduced leak.
- Each Why call creates its own engine in `asyncio.to_thread`; the inspected handler has no shared admission limit, per-user deduplication, or cached reasoning result. The warm engine pool's lock (`engine_pool.py:31`) belongs to a different hot coaching path and does not guard Why.
- `docker/supervisord.conf:28` defines five analysis processes. `docker-compose.yml:333-378` also defines a replicable worker service with a 2 GiB memory limit. Active deployment composition and replica count are unknown; do not add these counts and call it the live process count.
- Caption LLM fan-out is separately bounded at four calls (`analysis_worker.py:1421`), not a global Stockfish or explanation budget.
- `docker-compose.prod.yml:129-141` contains OOM priority and memory configuration. Its incident comments are historical reports, not evidence of today's RSS or OOM events. `scripts/worker_capacity_probe.sh:19-20` uses a 400 MB worker estimate; the local engine measurement shows why full-process measurement is needed before adding explanation concurrency.
- One thread alone is insufficient pinning: binary/NNUE/options, hash reset/process policy, search order, node limits, history, bounds, and tie-breaking also matter. Existing Why shares one process across candidate and played queries; the proposed reproducibility contract records that explicitly or isolates queries.

## 6. Architectural assessment

**Verdict: NO — this checkout does not already contain the requested general FEN explanation engine.** It contains substantial reusable evidence transport and single-line facts, a tactical consequence resolver, hand-authored purpose/question families, and several product/review adapters.

Recommended direction: **extend the canonical replay/evidence infrastructure with one offline hypothesis-and-query core**, then integrate it into the existing Why and caption adapters. This is larger than wiring `move_reasoning` into Why. Two narrower alternatives are (a) repair and extend the existing tactical resolver only, which leaves quiet generalisation unmet, or (b) wire the principle selector/ablation ranker, which is smaller but still lacks explanatory composition and reliable refutation. Neither alternative meets the whole goal.

Keep Stockfish as search/evaluation authority. Keep exact rules, searched evidence, and hypotheses distinct. A timeline is necessary evidence storage; it is not the inference algorithm. The executable proposal is in [the algorithm](general_deterministic_reasoning_algorithm.md).

Three changes to the prior documents are essential:

1. `differential_why_engine_scope.md` says a shared fact cannot be a reason and proposes ranking edited-board recovery as a share of loss. **Shared background facts may be indispensable premises**, and edited-board score changes do not causally allocate the original gap. Keep the decision-specific dependency, not only changed facts.
2. `why_engine_framework.md` says quiet backward search has no anchor without interventions. **Legal pawn breaks, entry/route opportunities, castle prerequisites, exchange transformations, and observed future actions supply anchors directly**. Interventions are an optional suggestion source.
3. Requiring the same theme across every good move (`move_principles.py:349-353`) can erase legitimate different plans. Compare plans within near-equivalent classes; explain them neutrally, and criticise only a supported disadvantage versus the played choice.

Existing reviewed gold, `backend/data/detector_gold/personalized_review_ten_game_gold_v1.json`, and the hidden-opportunities corpus/annotations are **development material**. Their original scope and evidence limits remain attached. The blind packet under `_blind_label_packet` was not opened as evaluation data. No untouched evaluation set was selected or scored in this pass.

Next artifact: [implementation spec](general_deterministic_reasoning_spec.md). All proposed thresholds, ranking alternatives, and rollout choices remain draft pending development measurement and review.
