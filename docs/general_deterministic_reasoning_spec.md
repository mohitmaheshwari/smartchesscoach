# General deterministic chess reasoning — implementation spec

**Status:** DRAFT v1 — inspection/planning complete; implementation not authorised by this pass.
**Version:** v1 (2026-10-30).
**Scope:** Large, staged research and implementation. No production change proposed for immediate release.

**Implementation update (2026-10-30):** Mohit authorised proceeding with the offline prototype. The first executable slice and its remaining gaps are recorded in [implementation evidence](general_deterministic_reasoning_implementation_2026_10_30.md); [usage](general_deterministic_reasoning_offline.md) describes the actual interface. The research/acceptance/rollout decisions below remain draft.

Companion documents: [repository audit and local evidence](general_deterministic_reasoning_audit_2026_10_30.md), [executable algorithm, schemas and walkthroughs](general_deterministic_reasoning_algorithm.md). Evidence scripts and JSON are in `output/general_reasoning_audit_2026_10_30/`.

## 1. The problem

ChessGuru needs to explain an unfamiliar FEN, with or without a played move, using deterministic chess reasoning. It must cover tactics, quiet choices, defence, structures, exchanges and endgames. An LLM may not invent a chess fact or a causal connection.

The current Why button and captions use different reasoning authorities. The whole `move_reasoning` framework is an admin tool, several proposed components are disconnected, and the available resolvers read narrow single-line consequences. The local baseline returns no explanation on all three supplied/development examples. The audit reproduces semantic validation, promotion ownership, mate-line, score-perspective, and material-settlement defects; passing existing tests does not establish general reasoning quality.

The primary new work is a **general objective generator plus dependency composition and counterexample search**, built on existing legal replay/evidence infrastructure. Merely connecting a principle library, ablation ranker or LLM does not meet the goal.

## 2. The shape — four outcomes

| Result | What a player receives |
|---|---|
| Supported consequence | A concrete outcome, scoped to what was analysed |
| Supported mechanism | A move-to-consequence connection and a transferable teaching point |
| Incomplete hypothesis | Accurate position context; no unsupported explanation of the decision |
| Insufficient evidence | A clear inability to explain, recorded as a coverage failure |

FEN-only returns position context and relevant plans/choices. FEN+move always analyses the played move and compares strong, near-equivalent and relevant natural alternatives. Stable good moves receive neutral explanation or reassessment of a stale flag. Already-losing positions receive appropriate resistance context.

The offline interface is `explain_fen(fen, played_move=None, player_level=1200, history=None, *, config)`.

```text
FEN -> explicit search ledger -> branching legal timelines
    -> board/continuation/route/structure objective seeds
    -> prerequisite joins and composed operations
    -> legal counterexamples, settlement and stability checks
    -> independently verified propositions -> controlled sentences
```

Example product wording supported by the tactical walkthrough: “Nd5 gives your knight a way to take the bishop on e7 with check during the queen exchange. Na4 misses that option.” The prototype must retain its branch scope and avoid claiming the whole line is forced.

No new player page is needed. Later integration extends the current Why experience and the existing caption adapter. The admin trace must show the same result object and search obligations used by players.

## 3. Schema / files touched

All paths below are **future implementation proposals**, not changes made in this pass.

| Existing source | Planned responsibility |
|---|---|
| `backend/services/stored_line_verifier.py:30,96,631` | Extend replay/events into branch-wide identity and accessible persistent snapshots; retain existing consumers through versioned adapters |
| `backend/services/candidate_caption_evidence.py:169,200,257` | Reuse fingerprints, legal branch transport and provenance; support FEN-only and mandatory fresh played score in new requests |
| `backend/stockfish_service.py:231,424` | Expose typed score/search records through an adapter; normalise POV and score bounds without silently changing legacy fields |
| `backend/services/move_reasoning.py:783`, `move_purposes.py:1693`, `move_principles.py:318` | Wrap useful existing concepts as candidate seeds; their outputs do not bypass new acceptance checks |
| `backend/services/ablation.py:179` | Optional diagnostic seed source; no causal shares or intervention-based final ranking |
| `backend/services/why_on_demand.py:326` | Compatibility adapter onto the common engine after offline quality gates |
| `backend/services/framework.py:203`, `caption_pipeline.py:7367` | Final caption consumers of accepted propositions; retire duplicate authority in a staged migration |
| `backend/routes/coach.py:1423`, `admin_reasoning_trace.py:194` | Existing game Why and admin review adapters onto the same result; typed FEN request in this router when integration is approved |
| `frontend/src/components/GameDecryptionV5.jsx:2179` | Render scoped results/alternatives/reassessment; no chess inference in React |
| `backend/analysis_worker.py:1903` | Later background jobs/caching, admission control, provenance and explicit completion state |

Proposed new internal package: `backend/services/reasoning/`, with `contracts`, `search_session`, `timeline_adapter`, `objectives`, `operations`, `investigation`, `claim_verifier`, `selection`, `render`, and a small `explain_fen` orchestrator. These own new jobs, rather than duplicating geometry, piece values or domain names. Exact packaging may shrink after the first vertical slice.

`ExplanationResult` contains context, candidates, objectives, accepted/rejected/incomplete hypotheses, node/event relations, propositions with evidence references, supporting lines/counterexamples, completed/unresolved search obligations, teaching selection, controlled text, and reproducibility/runtime metadata. See algorithm §§1–3 and 8 for typed fields and invariants.

## 4. New facts / data the system needs

- Branch-wide piece lineage, exact legal actions, per-move geometry deltas and persistent enabling facts, derived from existing replay.
- Rule-defined action prerequisites and objective predicates, including routes, pawn breaks, entry squares, duties and exchange transformations.
- Fresh typed played/root scores, score bounds, actual searched replies, retained common-depth MultiPV snapshots, node counts and search identity.
- A development manifest linking reviewed examples to their source game and original evidence limits. Existing reviewed positions are seeds, not unquestioned gold.
- Independent labels for factual correctness, explanatory support, usefulness, outcome status and degree of necessity. No labels derived from engine prose.
- A sealed evaluation manifest from **different games** and sufficiently different position families, including quiet positions and good/equivalent moves. No inspected example or reviewed snapshot becomes held-out data.
- Measurements of Python and child-engine RSS, total query CPU/nodes, latency distribution, failures, cache hits, and useful coverage by stratum.

No current local DB counts or production rate claims are available: local Mongo requires authentication. Offline fixtures suffice to begin the design/prototype, but representative evaluation and production capacity need additional approved data access. No credential changes are part of this plan.

## 5. Gating — preventing plausible stories from becoming facts

1. **Always search played:** reserve its query budget before optional objectives; absent ranking is never absent analysis.
2. **Typed truth levels:** exact rule fact, searched continuation conclusion, repeatedly supported positional hypothesis, exhaustive result only with an actual complete proof/rule certificate.
3. **Decision connection:** every accepted mechanism has a verified root-specific dependency and a useful downstream consequence. Feature lists alone fail.
4. **Refutation first:** adversarial replies, natural alternatives, quiet defences, sacrifices, ordering changes and search instability can reject or narrow a claim.
5. **No false necessity:** exact legal reply count, only reply avoiding an outcome, and best defence found are distinct contracts.
6. **No edited-board attribution:** intervention deltas may suggest legal queries; cannot allocate CP or establish a cause.
7. **Independent final verifier:** actor, direction, identity, timing, polarity and quantifier checked against evidence. Controlled critical claims; no arbitrary LLM rewriting in prototype.
8. **Truthful completion:** budget cutoffs, score bounds, unresolved exchanges and missing branches remain visible. No “verified” flag from a legal prefix alone.
9. **One reasoning authority:** Why and captions eventually consume the same accepted result. Shadow outputs are isolated experiments, never a second silent player-facing writer.

## 6. Test strategy

**Phase 1: stateless probes.** Retain the audit scripts/JSON. Exercise actual engine adapters and independent legal replay with pinned configuration, including both supplied FENs and the quiet opening fixture. The 302 passing existing tests are a baseline, not acceptance of the new core. Repair-route tests requiring bcrypt are currently unavailable.

**Phase 2: boundary and metamorphic checks.** Piece moves/captures, standard castling's two identities, promotions/underpromotions, EP, pins, king escapes, quiet defences, safe sacrifices, alternative recaptures, repeated searches/order independence, mirrored colors/POV, optional history, terminal positions, malformed/illegal inputs, interrupted/bound scores and budget exhaustion. A transformed position has its own verified legality; do not assume arbitrary board rotations preserve pawn/castling rules.

**Phase 3: development experiment.** Use reviewed positions from the existing gold/corpus sources and multiple games across tactics, quiet middlegames, pawn structures, exchanges, endgames, good moves, equivalent choices and already-losing positions. Reanalyse rather than inherit old labels. Instrument **before** judging quality. Compare baseline, new generator without interventions, and optional intervention-seeded investigation on the same development positions.

Report separately:

| Metric | Required accounting |
|---|---|
| Factual correctness | Correct checked propositions / all emitted propositions, with board/rule contradictions listed |
| Explanatory support | Supported decision-to-outcome links / all asserted links; branch scope and necessity overclaims separate |
| Coaching usefulness | Blinded reviewer rating for the selected point and plain-English output, independently of engine score |
| Coverage | Every input in denominator; counts for all four statuses and useful-supported explanation rate |
| Operational cost | p50/p95/max latency, CPU/nodes/query count, Python+child memory, timeouts/failures by stratum |

Also report **correct AND useful supported explanations / all eligible inputs** and per-stratum results. This prevents high precision achieved by excessive abstention. Report material-only coverage separately from supported mechanisms, and tactical/quiet coverage separately. A confidence interval and exact denominator accompany each rate; game-level resampling avoids pretending correlated moves are independent.

**Phase 4: freeze, then untouched evaluation.** Freeze generator, rules, wording, equivalence policy, budgets, ranking and acceptance thresholds on development data. Hash configuration, code and the held-out manifest before running. Reviewers see position/moves/evidence, blinded to engine family and proposed output when authoring gold. Use Mohit/Parth review for usefulness and independent chess verification for contested factual/support claims. Do not repeatedly tune against the held-out set; after a failure, return to development and reserve new untouched games for the next generalisation claim.

## 7. Risk + rollback

Principal risks: objective search explosion, tactical horizon errors, quiet feature correlation mistaken for explanation, proof-strength inflation, score/identity drift across adapters, and background memory competing with analysis jobs.

Offline prototype has no player blast radius and no deployment dependency. Product integration ships behind proposed `CHESSGURU_REASONING_ENGINE_ENABLED=false`, with shadow persistence under a separate versioned field. Keep existing captions/Why behavior until the new authority is deliberately selected. Disable the flag to roll back immediately; keep audit evidence and caches versioned, never overwrite Stockfish source facts. No deployment or environment variable was changed in this pass.

Use bounded admission control for background and on-demand explanation jobs, request deduplication, explicit cancellation and process cleanup. Determine concurrency from measured whole-process RSS and CPU headroom, not the current 64 MiB hash or worker estimate alone. A wall-clock safety timeout returns incomplete evidence; the deterministic algorithm normally stops on node/query budgets.

## 8. What this spec does NOT cover

- Exhaustive proof of arbitrary chess outcomes or one unique exact cause for every evaluation difference.
- Guessing historical intentions/repetition from FEN, training a chess language model, or a catalogue of position-specific stories.
- Fluent unrestricted LLM rewriting, new player pages, wholesale caption replacement before offline validation, or automatic production backfills.
- Altering production settings, sending email, deployment, schema migration or current reviewed documents in this pass.

## 9. Implementation order

1. **M1 — reproducible baseline and repository audit:** this pass supplies source/caller map, local engine manifest, three actual-helper examples, counterexamples and existing-test results. Remaining M1 work is representative development export, whole-process capacity measurement and a sealed unseen manifest; local authentication currently blocks data checks. Proposed commit: `docs(reasoning): record current paths and reproducible baseline`.
2. **M2 — offline vertical slice:** contracts/search adapter -> extend canonical timelines -> mandatory root comparison -> board/continuation/quiet objective enumeration -> prerequisite dependency joins -> ENABLE/PREVENT/PRESERVE/PREPARE/SEQUENCE/TRANSFORM -> legal challenge searches -> independent proposition verifier -> controlled frames. Include a tactical **and a quiet** end-to-end path from the first slice. Proposed commits split by these reviewable responsibilities. No API/product rollout in M2.
3. **M3 — generalisation experiment:** run stratified development ablations, compare teaching selection/budget candidates, adjudicate causal support, freeze the configuration, then run the sealed evaluation once. Publish denominators and counterexamples, including abstentions. Do not proceed merely because aggregate accuracy is high while quiet coverage is poor.
4. **M4 — integration only after M3 meets frozen gates:** existing Why adapter first, admin trace from the same result, then caption adapter and bounded background caching. Ship default-off. Mohit + Parth A/B for one week with flag on; then 10% rollout and monitor for one week; then 100%; delete the replaced authority after two clean weeks at 100%. Each promotion requires review of actual correctness/coverage/cost evidence. Keep rollout size/timing adjustable only through a reviewed plan revision.

The forecast bottleneck is **finding and validating quiet objectives under counterplay**, not sentence fluency. A second risk is expensive counterexample search. Measure both in M2 before committing to synchronous product budgets.

## 10. Decisions / Open questions for Mohit

These are review items for a later implementation sign-off, not requests that block this completed planning pass.

- **Data:** provide an authorised readable local export or working local DB access for representative development and game-level split creation. No need for access to production credentials in this document.
- **Product budget:** how much latency is acceptable for an on-demand answer versus a background answer? Measure candidate search policies against that target before locking a number.
- **Acceptance:** set factual/support/usefulness/coverage floors **per tactical and quiet stratum**, using development results before sealed evaluation. Board/rule contradictions in mandatory regressions must be resolved, not averaged away.
- **Partial support:** confirm the proposed separate `supported_consequence` output, with scoped wording, is useful enough for the player surface while mechanism coverage improves.
- **Ranking and equivalence:** compare the draft lexicographic teaching selector with a Pareto shortlist, and fixed-small/fixed-large/adaptive search budgets on development data. Measure output usefulness, false criticism of equivalent choices, coverage and cost. No formula, CP window or production concurrency is locked here.
- **Authority migration:** approve extending existing Why/framework adapters onto one common core, with caption adoption after offline and Why validation. Retiring duplicate authority is part of integration, not an indefinite parallel system.

The `lock-via-data` skill requires measured discriminating data before thresholds/formulas are fixed. The unavailable DB and absent new-core benchmark mean those locks remain explicitly open; the small diagnostic node budgets in the audit are not shipping defaults. Before implementation, follow the repository's scope/pre-code requirements with this evidence attached.
