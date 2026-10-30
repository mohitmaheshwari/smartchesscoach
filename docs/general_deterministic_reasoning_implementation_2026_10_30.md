# Offline reasoning — implementation evidence, 2026-10-30

Authorisation: Mohit's “okay, move ahead” after the repository-grounded plan. Scope: first offline vertical slice; no production integration. [Usage and current limits](general_deterministic_reasoning_offline.md), [scope](general_deterministic_reasoning_scope.md), [original algorithm](general_deterministic_reasoning_algorithm.md).

## Implemented path

`scripts/explain_position.py` -> `services.reasoning.explain_fen` -> isolated budgeted search -> canonical replay and retained snapshots -> objective/prerequisite joins -> legal reply and adaptive route investigation -> independent proposition/dependency checks -> controlled rendering.

The runtime package contains contracts, search, timeline views, objective generation, investigation, verification, rendering and orchestration. `stored_line_verifier.py` gains public snapshot/root-identity helpers; its existing replay contracts are unchanged. Caller search finds the new package only in the two offline scripts. No route, worker, caption path, environment setting, database or deployed app was changed.

No FEN, game ID, Na4/Qf8 name or fixture lookup is embedded in the reasoning package. The only source-game-ID handling is the benchmark's evaluation-split provenance check.

## Existing tests and boundary verification

- **302 existing relevant tests passed in 10.63 s**, including canonical replay, candidate evidence, Why, material/recapture, move reasoning, principles, ablation, narration validation and ownership regressions. No new test file was committed.
- **75 direct boundary assertions passed** during implementation: valid and altered proposition actors/objects/negation/strength/timing, Na4/Nd5 sequence joining, correct f5 coverage transitions, castling rook identity, en passant identity/square, underpromotion actor/type, illegal lines, history mismatch, invalid boards/moves, CP/mate distinctions and mandatory played search under a one-query cap.
- Further direct checks verified composed-dependency timing rejection and queenside preparation through the rook's b1 path.
- The required `python tests/test_all_flows.py` was attempted against **localhost:8001**, explicitly overriding the backend URL. It failed at its first HTTP request with `httpx.ConnectError: All connection attempts failed`. The suite is not counted as passing. Production was not used as a fallback.

## Final development experiment

Manifest: `output/general_reasoning_audit_2026_10_30/prototype/development_manifest.json`. Configuration: sibling `development_config.json`. Full report: `prototype/development_final/report.json`. Every case is development data from inspected/reviewed examples; none is held out.

| Case | Result | Observed behavior |
|---|---|---|
| Na4 / Nd5 | Supported consequence | Nd5's later knight capture on e7 with check, Kh8 as the only legal reply at that node; other Black branches retained |
| Quiet e4 | Supported consequence | Bg2 clears a castling prerequisite; a concrete ...e4 attack on Nf3 is shown as an opponent resource |
| Quiet good Nf3 | Supported consequence | Nf3/Bg2 are close; output is neutral rather than calling the played move bad |
| Qf8 | Incomplete hypothesis | No invented abandonment of f5; incidental later rook capture is withheld as the teaching point |
| Attacked-queen fixture | Supported mechanism | A legal immediate mate is checked exactly; no inference that the attacked queen must retreat |
| Reviewed pawn-structure case | Incomplete hypothesis | True but incidental captures cannot substitute for the missing root-to-benefit connection |
| Reviewed endgame case | Incomplete hypothesis | No supported teaching point within the configured investigation |
| Reviewed exchange case | Incomplete hypothesis | No assertion that a knight is free or that an arbitrary later capture explains the choice |

Counts: **3 supported consequences, 1 supported mechanism, 4 incomplete hypotheses, 0 runtime/input errors**. Four of eight cases have a selected scoped account. This is descriptive development outcome coverage, **not** a measured useful-explanation or generalisation rate. Factual correctness, explanatory support and usefulness remain explicitly `not_reviewed` in the report pending independent grading.

The final outputs contain **4,268 mechanically accepted propositions and zero rejected propositions**. These are correlated board/event facts, not 4,268 independent explanation-quality tests. The important coverage result is still four incomplete decisions; it is not hidden by the proposition count.

The stronger dependency gate changed the development outcome from seven selected accounts to four: Qf8, the pawn case and the exchange case had attractive true continuation events, but no supported link making them the teaching point for the root choice. This is a meaningful limitation of the first inference slice and the next development target.

## Reproducibility, FEN-only and cost

`prototype/repeat_check.json` records comparison of the final Na4 result and a fresh identical request: **all structured fields matched after excluding runtime fields**. All eight final results record the same source-hash set. Queries use a fresh single-thread engine process, explicit budgets/options, and a hashed binary.

`prototype/fen_only.json` verifies the quiet FEN-only request: no played move was supplied, a scoped castling-preparation account was returned, and no criticism of an invented decision was added.

Development configuration: 30k base nodes, 120k stability nodes, 32 physical queries maximum, 2M requested-node allocation cap, 3 candidate roots, 2 ranked replies, 18 projected plies, 16 adaptive expanded nodes and 64 MiB hash. The 30 cp strict comparison boundary is an explicit diagnostic setting inherited from the canonical inaccuracy floor, not a new shipping lock.

Observed final-batch p50 wall time: **14.920 s**; nearest-rank p95/max: **24.243 s**. Sampled maximum child RSS: **320,512,000 bytes**; parent RSS: **52,936,704 bytes**; combined child+parent sample: **373,342,208 bytes**. Some engine verification ran concurrently, so these are local development observations, not a production latency/capacity claim. UCI actual node consumption can slightly exceed its requested allocation and is reported separately.

## Next gate

The next work is to investigate root-specific pawn breaks, structural transformations, defensive responsibilities and endgame objectives, rather than add fluent narration to the current partial coverage. The existing bounded material settlement remains available, but the new prototype deliberately does not call a captured piece a material win without a closed settlement/search obligation.

An independent reviewer should grade the selected and incomplete cases before teaching selection or equivalence policies are locked. Then freeze the implementation/configuration and evaluate different, untouched games. The benchmark checks frozen code/config/engine hashes and game/position separation for a sealed run. No such evaluation was performed here, and no claim of readiness for player integration is made.

Voice check: controlled frames name pieces, squares and concrete actions; no evaluation-to-material translation; transferable habit last. This is an explicitly authorised offline experiment. Eventual player output must enter the existing Why/framework adapters, rather than becoming a parallel runtime caption writer.
