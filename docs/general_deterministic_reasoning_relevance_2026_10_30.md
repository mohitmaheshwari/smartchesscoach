# Relevance correction and frozen review rerun — 2026-10-30

The user's second independent review established the distinction this pass addresses: a proposition can be board-true while being a poor explanation of the decision. This is an offline correction on `codex/reasoning-review-fixes`; it changes no product route, caption pipeline, database or deployment.

## Policy chosen before the 12-case rerun

The reviewed failures supplied three candidate policies:

1. The prior mechanism-first shortlist: a conditional checking-threat certificate precedes a direct root capture. In ho05 this selected f2 coverage over Rxc2's immediate rook capture despite the original root scores of +244 and -369 for White.
2. Root-action contrast tied to both root score gaps first, then conditional certificates, then later events supported against an unrestricted depth-20 best reply.
3. Clip events only to the two existing root PVs' common prefix. Stored ho02 agrees for 17 plies across the base/stability searches, yet the review's depth-20 line omits its lesson. This candidate cannot fix that reported failure.

Policy 2 is the experimental choice. The discriminating data are the supplied failures, the stored ho02 agreement of 17 plies, and ho05's measured 613cp root gap. A fresh development run of the disclosed ho05 regression selects the root capture and the original numerical comparison. It uses 17 physical queries, 780,000 requested nodes and takes 14.94 seconds in the standalone run. These data justify addressing the direct choice before the conditional coverage account; they do not calibrate a general teaching-quality rank. No new centipawn cutoff, material-value table or weighted ranking formula was introduced. The existing 30cp equivalence setting remains unchanged.

## Admission and provenance

Exact root actions (including an immediate capture or clearing a castling square) are checked as root facts. An immediate capture contrast additionally binds both root score pairs, the played root leaving that target on the board, and the alternative taking it. The controlled wording says “takes,” with the numerical engine comparison stated separately. It makes no claim that the captured piece accounts for a precise fraction of the evaluation change or remains won after every reply.

Later ordinary consequences and optional opponent resources must come from the primary stability line, within its agreement with the base search, and within their agreement with a fresh unrestricted opponent search reaching depth 20. A forced opponent root cannot supply a coaching resource. The reference query spends only the remaining original query/node allocation; if it cannot run or reaches the node cap before depth 20, later teaching is withheld. Rejected claims and reasons remain visible in `teaching_admission` and `resource_admission`.

The Na4/Qf8 certificate frames remain explicit conditional legal variations. They are not represented as the opponent's depth-20 main line. Their independent finite proof and two numerical checks still apply. A named earlier defence now carries its bound typed engine score and the branch prefix; the Rc8 integration assertion no longer requires the name to appear. The numeric score is not presented as captured material.

Every rendered chess sentence has a `sentence_admission` receipt with proposition/search IDs, source purpose, root restrictions and admission reason. General teaching principles and numerical comparisons have separate receipts. Board verification and teaching admission remain separate judgments.

## Development verification before freezing

The new relevance tests reproduce the forced bishop-sacrifice resource, out-of-agreement events, an unfinished depth target and the rook-capture contrast. Mutation checks reject invented gaps, scores and branch identities. The review runner strips best-move labels, cp_loss, categories and game IDs from the inputs passed to the engine.

- All 113 engine-free package tests passed in 6.36 seconds before freezing.
- Eight opt-in integration tests passed in 132.50 seconds across seven development requests, including repeated Na4, the disclosed rook-capture case and the original fixes. Nf3 contains no Black e4 resource; ho05 contains no f2 account. The final defence sentence subsequently gained its explicit branch prefix; unit tests cover that controlled rendering change.
- No positive control from a different independently sourced game is claimed. Symmetry tests remain geometry checks, not evidence of generalisation.

## Frozen rerun protocol

`backend/scripts/review_reasoning_policy.py` copies the user's supplied manifest byte-for-byte, saves a filtered request manifest, and freezes source/config/engine/input hashes before execution. It refuses to overwrite an existing freeze or completed run, checks the hashes before and after running, and performs a separate fresh single-thread depth-20 root audit. Audit cost is reported separately from pipeline latency and its original budgets.

All 12 cases have now been disclosed in the review, and ho05 is an explicit regression fixture. The run is therefore a frozen rerun of the reviewed set, not a new untouched evaluation. No policy change will follow inspection of those results in this pass. Raw selection counts will not be reported as coaching usefulness.

The run's local evidence is under `output/relevance_review_2026_10_30/frozen_review/`. `freeze.json` binds the copied original manifest, config and engine hash. The final `review_report.json` records `freeze_unchanged: true`. Frozen source digest: `af5fe7216c18677db2fc0050ba14221df570029a30ba9a348b2a4d5bbc794a34`. Runtime policy commit: `e9378dfd`; named-defence correction: `25c4f87f`. Only documentation changed after execution began.

## Completed 12-case results

**Six selected consequences, six incomplete accounts, zero invalid propositions.** No comparative certificate was selected on this set. Two of the selected consequences are the new direct rook-capture contrasts. These are raw outcome counts, not six proven useful comparative explanations.

| Case | Frozen output | Independent depth-20 audit / limit |
|---|---|---|
| ho00 | Re1, then Re7 attacking c7 | Ply-3 event survives both the fresh opponent depth-20 search and the independent root PV |
| ho01 | Abstains | No supported account; root ranking agrees on Kd8 |
| ho02 | Abstains | Previous later event withheld because opponent verification was unavailable after the 32-query cap |
| ho03 | Abstains | Still no account; 120k root choice Rb8 differs from depth-20 Bg7 |
| ho04 | Abstains | Previous later event withheld because opponent verification was unavailable after the 32-query cap |
| ho05 | Rxc2 takes the rook; Re1 leaves it there; original deeper-search gap 6.13 | Depth-20 root also chooses Rxc2; no f2 story or Rf1 relief claim |
| ho06 | Abstains | Prior Rxg7+ event lies beyond the base/stability agreement; independent root PV uses Qh7, avoiding that capture |
| ho07 | d3, then dxe4 | Ply-3 capture survives both depth-20 references |
| ho08 | Rxc2 takes the rook; Qa3 leaves it there; original deeper-search gap 1.55 | Depth-20 root also chooses Rxc2 |
| ho09 | Abstains | No supported account; root ranking agrees on Nd4 |
| ho10 | Bg7 clears f8 for castling | Exact root fact, still an incomplete comparative lesson. Root depth-20 prefers Bxd5; pipeline scores Bg7 +22 and Bxd5 +21, nearly equal |
| ho11 | Na7+, then Nb5 attacking the king on c7 | That event survives the depth-20 reply after Na7+, but independent root depth-20 chooses Qa4. Following another check still does not establish the decision's most useful lesson |

The audit finds three root-name disagreements: ho03, ho10 and ho11. A different best-move name alone does not establish a large quality difference. In ho11 the original pipeline has Na7+ +919 and Qa4 +892; a fresh search after Na7+ reaches +990, while the separate depth-20 root search scores Qa4 +1007. Those latter searches have different roots/depth horizons, so their 17cp difference is diagnostic, not a matched comparison proving inferiority or equivalence. The choice and quality of the lesson remain unresolved.

There are three completed opponent-depth-20 admission searches (ho00, ho07 and ho11). ho02, ho04, ho06 and ho10 reach the 32-query cap first, so their later events cannot use that verification. For ho06, the existing root agreement already rejects the proposed capture. This is a concrete scheduling limit: optional investigations consume queries before relevance verification. The silence in ho02/ho04 is not represented as a fresh engine refutation. No policy was changed or rerun after these results were inspected.

Across the selected text, the separate root audit records two later sentences retained in its PV, three exact root-action sentences, and one sentence belonging to a different root (ho11). It does not grade the root fact in ho10, or the check in ho11, as a complete comparative explanation. There is no independent usefulness grade and no new-game generalisation claim.

Pipeline latency: **10.06–35.79 seconds, mean 19.11, median 17.78**. All twelve exceed eight seconds. Queries range from 11 to 32, with at most 2,000,000 requested nodes. The depth-20 root audit ran separately and is excluded from those pipeline times. The original node/query budgets were not raised. Independent root searches and raw score details are saved in `review_report.json`; all full pipeline evidence is in `pipeline/case_*.json`.

The corrected development text for the named defence is now: “After Qf8 Qd7 Rc8, the engine score is -10.95 from Black's side.” The original threat certificate is retained as a conditional account. Nf3's optional resource receipts reject six forced-root propositions, two non-primary branches and four events beyond base/stability agreement; none reaches its text.

What this pass establishes: the reported misleading defence wording is removed, the forced-root resource is blocked, the ho05 contrast is corrected, and the known late/avoidable accounts are withheld. It does not solve general quiet comparison, root-ranking reliability, useful selection among several near-equal plans, query scheduling or the eight-second product budget. The next experiment needs fresh positions after those policies are designed; this disclosed set remains regression material.

Reproduce with the two separate modes (from the repository root), using a new output folder for any future experiment rather than overwriting this freeze:

```powershell
python backend/scripts/review_reasoning_policy.py --manifest '<original manifest path>' --config '<config path>' --engine '<local Stockfish path>' --output-dir '<new review folder>' --freeze
python backend/scripts/review_reasoning_policy.py --manifest '<original manifest path>' --config '<config path>' --engine '<local Stockfish path>' --output-dir '<new review folder>' --run
```

## Broader verification

The existing relevant replay, Why, narration, material, ownership and move-reasoning suites plus all engine-free package tests produced **384 passed, one failed in 44.54 seconds**. The sole failure remains `test_the_generic_lesson_still_applies_when_we_did_not_recommend_it`: expected `distilled:good_space`, received `facts:traps_piece`. The user independently bisected that existing caption behavior to `1832467e`; this offline change does not modify it. The broad run overlapped the frozen pipeline run, so neither elapsed time is a production performance benchmark.

The required `python tests/test_all_flows.py`, explicitly pointed at `http://127.0.0.1:8001`, again failed at its first HTTP request with `httpx.ConnectError: All connection attempts failed`. No application flow is counted as passing and no deployed API was substituted. The Windows-incompatible `/app/...` test omitted from the prior broad run remains outside this run as well.

Voice audit: moves and squares are explicit; named defence scores are separate from actual captured pieces; the transferable habit remains last. There is no new production coaching path. Main checkout verification still reports `working-code` and the original three tracked edits.
