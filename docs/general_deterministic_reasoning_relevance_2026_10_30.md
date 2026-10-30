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

- Engine-free package tests: results recorded below after completion.
- Eight opt-in integration tests passed in 132.50 seconds across seven development requests, including repeated Na4, the disclosed rook-capture case and the original fixes. Nf3 contains no Black e4 resource; ho05 contains no f2 account. The final defence sentence subsequently gained its explicit branch prefix; unit tests cover that controlled rendering change.
- No positive control from a different independently sourced game is claimed. Symmetry tests remain geometry checks, not evidence of generalisation.

## Frozen rerun protocol

`backend/scripts/review_reasoning_policy.py` copies the user's supplied manifest byte-for-byte, saves a filtered request manifest, and freezes source/config/engine/input hashes before execution. It refuses to overwrite an existing freeze or completed run, checks the hashes before and after running, and performs a separate fresh single-thread depth-20 root audit. Audit cost is reported separately from pipeline latency and its original budgets.

All 12 cases have now been disclosed in the review, and ho05 is an explicit regression fixture. The run is therefore a frozen rerun of the reviewed set, not a new untouched evaluation. No policy change will follow inspection of those results in this pass. Raw selection counts will not be reported as coaching usefulness.

The run's local evidence is under `output/relevance_review_2026_10_30/frozen_review/`. Final results and remaining failures will be appended after completion.
