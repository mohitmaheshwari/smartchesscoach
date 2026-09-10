# Candidate-Aware Causal Captions — Data Lock

**Date:** 2026-09-10
**Status:** LOCKED AND EXPLICITLY APPROVED; BOUNDED IMPLEMENTATION COMPLETED LOCALLY, NOT DEPLOYED
**Scope:** `docs/candidate_aware_causal_captions_scope.md`
**New aggregate snapshot:** `backend/data/corpus_snapshots/human_candidate_budget_bakeoff_2026-09-10.json`

## 1. Decision summary

1. Use an **adaptive human-policy budget**: include human candidates until 80% cumulative model mass is reached, with a floor of three and cap of eight. The complete root candidate set always contains the played move and stored best move and is capped at ten after authoritative candidates are added.
2. Enrich at most **three featured moments per game**. Keep the deployed ranker unchanged; candidate evidence improves an already selected moment but does not create a new visible ranking formula.
3. Do **not** publish a generic centipawn definition of “another good move.” V1's visible stronger move is the stored best move or a move established by an existing exact authoritative source. Human-plausible inferior moves may appear only as verified comparisons or distractors.
4. Admit only already authorized concrete proof families. Generic counterplay, good-piece/bad-piece, weak-square and long-term-plan claims remain unsupported unless their exact board facts can be stated without the broader positional conclusion.
5. Use the approved compact card: headline, at most two short explanatory sentences, one board action and a separate memory cue. The board, not a paragraph, carries the continuation.
6. Game Review is the first visible consumer. Personalized lessons consume the same contract after it is proven. Play with Coach integration is contract-only and default-off until a preloaded-worker concurrency benchmark exists.
7. Historical enrichment begins with **one explicitly enrolled account and at most ten recent eligible games**. The next pilot is at most ten users and five recent eligible games each, but it is not authorized until the first run reports engine time, storage growth, abstentions and reconciliation.
8. Blinded coach validation requires at least 60 reviewed moments, at least 39/60 strict preferences for the new version, a Wilson 95% lower bound above 50%, and zero critical false claims. Player recognition requires at least 30 paired attempts, a statistically significant exact paired improvement, and no answer leakage.

These locks intentionally favor a small number of complete, replayable explanations over a larger inventory of shallow or unproved captions.

## 2. Evidence identity and privacy

The candidate-budget bakeoff used:

- Maia-2 0.11.0 Rapid;
- pinned model SHA-256 `65aae8465eed5e65df66a24ea7370715579f9e5435098d06fe18bdb1e267e997`;
- the public Maia-2 example test dataset at SHA-256 `cd4defb7213f052eb0c3e78c1af32f40ee67b8cb85b859e890862db31dcb7bd9`;
- 600 deterministic positions, balanced across opening, middlegame and late play and the 900–1199 and 1200–1500 bands;
- zero production reads, production writes, Stockfish runs or LLM calls.

Only aggregates are stored. The snapshot contains no player name, username, game ID, FEN, move, PGN or free text.

The public local dataset contained no eligible 600–899 stratum. That is a coverage limitation, not a reason to invent results. The existing frozen Otter evidence covers its validated 600–1500 runtime population and reports 55.7% top-one and 91.6% top-five accuracy over 3,257 held-out moves. Under-900 candidate recall is therefore monitored separately during Shadow validation. Because human policy never establishes chess truth, lower recall can create silence but cannot authorize a false claim.

Other cited evidence:

- `backend/data/corpus_snapshots/complete_coaching_system_phase0_2026-09-02.json`;
- `docs/hidden_opportunities_shadow_incidence_census_2026_09_06.md`;
- `backend/data/corpus_snapshots/full_game_chess_fact_audit_report_v1_2026-09-03.json`;
- `backend/data/corpus_snapshots/personalized_game_review_quality_v2_2026-09-01.json`;
- Mohit's accepted and rejected literal caption examples in the approved scope and product-review discussion.

## 3. Candidate-budget lock

### Compared candidates

| Policy | Actual move in set | Mean returned mass | Mean candidates |
|---|---:|---:|---:|
| Fixed 3 | 75.83% | 78.41% | 3.00 |
| Fixed 5 | 86.17% | 87.73% | 5.00 |
| Fixed 8 | 93.50% | 93.82% | 8.00 |
| 80% mass, floor 3, cap 8 | **86.33%** | **87.25%** | **4.33** |
| 90% mass, floor 3, cap 10 | 91.67% | 92.46% | 5.84 |

The selected adaptive policy preserves essentially the same observed move coverage as fixed five while evaluating 13.4% fewer human candidates. Fixed eight adds 84.8% more candidates than the selected policy for 7.17 percentage points of observed move coverage, but there is no evidence that those tail moves add a distinct teachable idea. The 90%-mass policy adds 34.9% more candidates for the same unproved tail benefit.

Post-warmup Maia inference on CPU measured 16.48 ms mean and 19.95 ms p90 per position. This is model latency only and does not authorize a historical engine backfill size.

### Locked construction order

The bounded root set is constructed deterministically:

1. played move;
2. stored Stockfish best move;
3. up to two moves from an already authorized exact source, when applicable;
4. human-policy moves in probability order until the 80% target is reached, subject to the three-move floor, eight-human-move cap and ten-total-move cap.

Duplicate moves consume no slot. When authoritative moves fill the total cap, they displace the lowest-ranked human-policy tail. Otter is preferred only with legal verified history; Maia-2 is the no-history fallback. A missing or rejected model leaves played, best and authoritative candidates intact.

One restricted root analysis evaluates the candidate set. The job must not start one independent engine process per candidate.

### Rejected alternatives

- Fixed top one: measured Otter coverage is only 55.7%; it cannot represent the moves a player is likely to consider.
- Fixed top five: nearly the same coverage as the selected policy, but spends a slot in positions whose distribution is already concentrated.
- Fixed top eight: higher recall, but no measured increase in unique teaching value and materially more branch work.
- Unbounded cumulative mass: impossible to budget and unsafe for analysis-queue latency.
- Showing the candidate list to the player: rejected; it recreates an engine report.

## 4. Featured-moment count and ranking

The full Shadow census scanned 14,356 analyses and found 6,148 complete candidates in 4,141 games:

`1:2842, 2:845, 3:294, 4:99, 5:40, 6:13, 7:5, 8:2, 9:1`.

Games with three or fewer candidates account for 3,981/4,141, or **96.14%**, of candidate-bearing games. A three-moment cap therefore changes only the densest 3.86% while preventing a tactical game from becoming an every-move report.

### Lock

- Maximum featured moments per game: **three**.
- The first moment may be expanded; later moments stay in the move timeline until selected.
- Candidate-aware evidence does not alter the current visible ranking formula in V1.
- Hidden Opportunities and other Shadow events remain Shadow until their own blinded ranking and promotion evidence passes.
- When more than three already-visible events qualify, preserve the deployed selection order and record what was suppressed.

The independent within-game ranking packet had only one comparable game and two candidates. That cannot select or tune a new formula. Candidate completeness is therefore improved without pretending the missing importance labels exist.

## 5. Soundness and cause-family lock

The proposed 25cp same-WDL “sound and findable” band passed engine research but never received the required blinded coach authorization. Centipawn proximity also does not prove that two moves teach the same idea.

### V1 visible rule

- The primary stronger try is the stored best move, an exact tablebase result-preserving move, or an already authorized canonical opening/trap decision.
- A human-policy move may be explained as a tempting comparison only when its legal branch and concrete consequence are independently verified.
- “Another good choice” remains hidden in V1 unless the move has exact result authority. Generic non-best-move soundness stays Shadow.
- Human probabilities can order review work; they cannot label a move good, bad, accurate, intended or understood.

### Admitted cause families

Only the current surface-authorized forms of these families may speak:

- legal material or exchange consequence;
- verified line cause, including mate direction and concrete material opportunity;
- exact endgame result;
- authorized opening or trap identity and move-order fact;
- authorized Hidden Opportunity proof family on a surface where its grade permits it.

The census found only five board-transformation candidates in 552,901 positions. That is insufficient to authorize broad positional language. V1 may still state exact primitive facts—queens came off, the queen remained, a piece became attacked, a file opened—without upgrading them into unsupported claims about counterplay or long-term strategy.

### Rejected alternatives

- A permanent 25cp/50cp/100cp “good move” band.
- Maia/Otter probability as correctness.
- Geometry presence as a causal explanation; prior evidence found it in 21/24 opportunities and 58/76 non-opportunities.
- Promoting Shadow families to avoid silence.

## 6. Reading and board-interaction lock

Mohit rejected the dense five-sentence Re1 explanation and approved the literal compact review shape in the scope. The user-visible contract is therefore structural:

1. a plain-language headline;
2. sentence one: the played consequence or hidden possibility;
3. sentence two: the stronger idea and its concrete purpose;
4. one **Compare the two ideas** or **Show the idea** board action;
5. one separate **Remember** cue.

The collapsed explanation may contain no more than two sentences and 32 words. The memory cue may contain no more than 18 words. SAN move strings do not count as prose sentences. If the complete truthful explanation does not fit, detail moves to the board sequence or the expanded comparison; the system must not truncate a condition that changes the chess truth.

Replay length is not fixed to four stored plies. It ends only after the claimed payoff, defense or recapture is settled. The UI reveals one move at a time and may collapse continuation after six plies, but the verifier must evaluate the full required settlement.

Static reflection choices remain a fallback only. Position-relative choices must each be legal-board compatible and must not reveal the correct move before the player commits.

## 7. First consumers and failure behavior

### Rollout order

1. Game Review: visible to one explicitly enrolled validation account after migration dry-run.
2. Personalized lessons: same reason bundle and replay contract after Game Review truth and UX pass.
3. Play with Coach: schema integration and Shadow instrumentation only.

Live Play with Coach model inference is not in the first visible rollout. The production container does not currently mount the model artifacts, and no preloaded-worker concurrency envelope exists. Normal play must remain legal and responsive if every model call fails.

### Fallbacks

- no model: played + best + exact-source candidates;
- no new engine evidence: existing stored explanation;
- incomplete branch: no featured moment;
- unsupported cause: quiet move comparison only, never invented WHY;
- rejected provenance/fingerprint: ignore the enrichment packet;
- exact ending unavailable: no exact result claim;
- page read: never starts an engine or model process.

## 8. Historical cohort and migration lock

The full corpus has 14,356 analysed games in the candidate census; 4,141 contained a complete Shadow opportunity. Model latency does not measure Stockfish branch cost, so a broad backfill cannot be authorized yet.

### Locked first run

- one explicitly enrolled account;
- at most ten most-recent eligible analysed games;
- at most three selected positions per game;
- dry-run before apply;
- immutable original analysis;
- resumable enrichment keyed by input fingerprint;
- reconciliation states: current, newly enriched, changed, unsupported, rejected, failed and stale.

### Conditional second pilot

At most ten users with at least five analysed games, and at most five recent eligible games per user. This pilot remains blocked until the first run reports:

- selected positions and unique root candidates;
- model and engine wall time, p50 and p95;
- peak worker memory;
- stored bytes per position;
- abstention and failure reasons;
- deterministic rerun equality;
- zero page-read engine/model starts.

Any larger backfill requires a new measured cohort lock. The old `teachable_move_headroom.py` output is not versioned and its current implementation would retain raw identifiers and FENs, so it is not accepted as migration evidence.

## 9. Validation thresholds

### Chess truth

- zero critical actor, color, direction, legality, mate, material, exchange, recapture, promotion, x-ray and truncated-payoff failures;
- 100% legal replay;
- 100% identity and provenance validation;
- no page-read engine or model process.

Any critical false claim fails the release regardless of average score.

### Blinded coach preference

Use at least 60 moments stratified across rating band, phase, actor and every admitted cause family with enough natural population. A reviewer sees legacy and candidate-aware versions with mapping hidden.

Pass requires:

- at least **39 of 60** strict preferences for candidate-aware, excluding ties;
- Wilson 95% lower bound above 50%;
- no cause family with a majority preferring legacy when that family has at least ten reviewed examples;
- zero critical false claims.

At 60 reviews, 36/60 is a visually appealing 60% but its confidence interval includes chance. The 39/60 threshold crosses the statistical discrimination cliff and is therefore selected. Requiring 42/60 would add confidence but has no product evidence establishing 70% as the necessary effect.

### Player recognition

Use at least 30 paired, first-attempt records. Ask the position-relative question before reveal, then a structurally equivalent non-identical recognition item after the comparison.

Pass requires:

- exact paired test at `p < 0.05`;
- post-comparison correct rate with Wilson 95% lower bound above 50%;
- no answer leakage;
- assistance, reveal and replay recorded separately.

Viewing, replaying or answering correctly never changes an organic-game transfer verdict.

## 10. What this lock authorizes

After explicit approval, implementation may:

- correct exchange accounting and freeze the adversarial regressions;
- add the candidate-evidence contract as an extension of the existing canonical decision;
- add offline/new-analysis enrichment with the selected candidate policy;
- enrich no more than the locked historical validation cohort;
- compose the compact Game Review card and board comparison;
- generate position-relative lesson choices from verified facts;
- add Shadow PWC consumption without visible model latency;
- build the migration, reach, truth, preference and recognition gates.

It does not authorize broad rollout, a new ranker, a generic non-best soundness band, new positional detector claims, a full historical backfill or production deployment.
