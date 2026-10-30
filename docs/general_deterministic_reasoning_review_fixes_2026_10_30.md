# Offline reasoning review follow-up — 2026-10-30

This records the first review correction at `6d900d0b`. The later [relevance correction and frozen rerun](general_deterministic_reasoning_relevance_2026_10_30.md) supersedes its defence wording, resource admission, and hypothesis ranking. Its historical examples and counts are retained as that earlier snapshot.

Scope: the user's reproduced prototype review, in the requested order. No route, worker, caption pipeline, database, environment configuration or deployed service was changed. The main checkout was restored to `working-code`, preserving its original three tracked edits. Changes are isolated on `codex/reasoning-review-fixes` in the managed review worktree.

## Tests before fixes

Commit `82ea21e9` adds executable boundary and review regression tests before feature changes. Its first run produced **49 passed, six failed**, reproducing the wrong teaching subject, same-sign mate equivalence, repeated mate name and ambiguous later-move actor. The boundaries cover identities through castling, promotions and en passant; retained relations; gained versus abandoned coverage; dependency timing; altered actors, objects, polarity, strength and evidence; illegal lines/history/input; typed scores and terminal input.

Commit `d6d50367` fixes those six failures: equivalent moves select evidence on the played root, different mate distances compare separately, immediate mate is named once, and later resources name their side and timing. Those original two test files then passed all 55 tests.

The forcing follow-up adds independent legal-certificate validation, numerical evidence binding, search ledger/MultiPV tests, transformed-board discovery tests, and rejection of forged certificates or universal claim strength. This brings the engine-free new tests to **95**. Seven additional tests explicitly opt into a local Stockfish executable.

## Comparative mechanisms

`backend/services/reasoning/forcing.py` contains no FEN, move-name or game-ID lookup.

For checking captures during a queen exchange, it replays the played root and alternative with the same opponent response, enumerates legal queen-capture/queen-capture/recapture routes, and tries an alternative checking capture by the same root piece before the exchange. The verifier independently replays both lines, checks the available/unavailable action and piece identities, confirms both queens are exchanged, and compares the resulting piece counts. It permits a demonstrated exchange, not a claim that the opponent must cooperate.

For prepared checks, it compares coverage from origin and destination and uses a diagnostic null move only to propose checks by the opponent's setup piece. No diagnostic position is admitted as a legal continuation. A candidate must have a common legal waiting move, a finite exact mate-in-two tree after that wait, and a legal capture of the checking piece from the alternative square. The check and alternate capture are searched at both configured budgets with the original mover's score perspective. The verifier independently checks the board relationships, all evasions in the local mate tree, root/FEN/move/POV bindings of both numerical comparisons, and any claimed earlier defensive counterexample. Unchanged protection needed by the mating piece is retained and validated at every intermediate snapshot.

This is deliberately limited: the two families require alternative moves by the same piece; exchange certificates use one queen each; the prepared-check certificate currently closes a local mate-in-two tree. Stronger defences before that tree are searched and reported. Neither family proves that every defender reply reaches the illustrated endpoint or assigns a precise causal fraction of the evaluation gap.

## Reproduced outputs

Same settings as the reviewed prototype: 30,000 base nodes, 120,000 stability nodes, at most 32 engine queries and 2,000,000 requested nodes; root cap 3, reply width 2, 18 plies, 16 expanded investigation nodes, hash 64 MiB, equivalence boundary 30 cp. Stockfish binary SHA-256: `45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0`.

Na4:

> After Black's Bxe2, Na4 still allows Bxd4 Bxd1 Raxd1, exchanging queens. Nd5 instead allows Nxe7+, taking the bishop on e7 with check before that exchange; Na4 has no such checking capture. At that point, Kh8 is the only legal reply. Before taking back, look for a stronger move with check.

Qf8:

> Qf8 adds no cover on f5; Qh7 would let Black's queen cover it. White's Qd7 prepares Qf5+: for example, after Black's a5, Qf5+ Bf6 Qxf6# is mate, with the knight on d5 still protecting f6. After Qh7, the same plan can be met by Qxf5 exf5, trading queens. Black also has an earlier defence: Rc8 avoids this immediate mating line. When a quiet move prepares a check, check which squares your pieces need to cover.

Qh7 is resistance in an already losing position. The quoted local mate follows the legal waiting example a5; it is not mate-in-two against Rc8 or every Black response. The alternative capture trades queens; it does not win White's queen for free.

Equivalent good Nf3:

> Nf3 moves the knight off g1, making room to castle. The compared moves are close in these searches. Later in this line, Black plays e4, attacking the knight on f3. Check the opponent's threats while getting the king to safety.

Qa2 versus Qa8#:

> Qa8# is checkmate. The engine finds mate in 6 after Qa2, but this choice finishes immediately. Before choosing a move, check for mate.

The White e4 case also explicitly labels the later resource as Black's e4. Its quiet comparative reason remains incomplete: clearing f1 explains a benefit of Bg2, not the full reason White's e4 is inferior.

## Actual verification

- **95 engine-free new tests pass in 6.24 seconds**. The first 89 were included in the broad run below; the final six add certificate/claim-strength mutation checks.
- **Seven opt-in Stockfish tests pass in 102.69 seconds** on the final verifier across six requests (five unique positions plus repeated Na4). Both Na4 outputs match in every field outside runtime. All six results have the same source hashes, zero invalid propositions, and stay within requested node/query budgets.
- The broader replay, Why, narration, material, ownership, move-reasoning and new-package run produced **360 passed, one failed in 17.00 seconds**. The failure is `test_mistake_why_and_coherence.py::test_the_generic_lesson_still_applies_when_we_did_not_recommend_it`, expecting `distilled:good_space` but receiving `facts:traps_piece`. Running that exact test on the restored `working-code` checkout reproduces the same failure. No caption behavior was changed to satisfy it.
- An earlier collection attempt included `test_why_better_append_guard.py`, which hardcodes `/app/backend/data/captions/R12_blunder.json`. That path does not exist on this Windows host; this file was excluded from the completed broad run and is not counted as passing.
- Required `python tests/test_all_flows.py`, with `REACT_APP_BACKEND_URL=http://127.0.0.1:8001`, stops at the first request with `httpx.ConnectError: All connection attempts failed`. No local backend is running. It is not a passing application test.
- Voice audit: concrete moves/squares, explicit side/timing, no evaluation-as-material claim, and an explicit transferable habit at the end. The renderer remains offline; caller search finds only the two CLI scripts and tests importing the package.

Real-engine test invocation from `backend`:

```powershell
$env:CHESSGURU_TEST_STOCKFISH='C:\path\to\stockfish.exe'
python -m pytest tests/test_reasoning_engine_integration.py -q -s --basetemp=../output/reasoning_review_2026_10_30/final_engine_tests
```

Full per-case evidence is local under `output/reasoning_review_2026_10_30/final_engine_tests/reasoning_engine_regressions0/`, with a compact `review_summary.json` in the review output folder. The integration test writes equivalent evidence to pytest's temporary directory when no basetemp is specified. The separate quiet rerun is under `output/reasoning_review_2026_10_30/quiet_remaining/` with its input manifest in the parent folder. These output files are local artifacts, not committed fixtures. Regression inputs and executable checks are committed in the test files.

## Coverage and runtime still limit this prototype

The reviewed pawn-structure, endgame and exchange cases remain incomplete, with no selected teaching point. The supplied Nc6/bishop-pair position selects a later pawn attack after f5 as a `supported_consequence`, with `comparative_cause_not_established`; it does not explain the bishop-pair decision. That selection is not counted as solving quiet comparative reasoning. No held-out games were opened and no generalisation or independent coaching-quality rate is claimed.

The six final engine integration requests took 4.93–21.19 seconds each, 8–32 physical queries, and 510,000–1,290,000 requested nodes. The two forcing regressions took 21.19 seconds (Na4) and 15.27 seconds (Qf8) in that run. Earlier standalone runs took 18.36 and 15.15 seconds. Sampled engine RSS stayed near 320.5 MB; parent memory grew while pytest retained all six full result graphs. These observations confirm background-only feasibility under the current implementation. They do not meet the existing eight-second Why-button budget.

Remaining work: general quiet comparative mechanisms, wider forcing coverage, independent usefulness grading, frozen-policy evaluation on different games, and capacity/latency work before product integration. No push, merge or deployment was performed.
