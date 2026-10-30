# Combined reasoning: implemented offline, 2026-10-30

ChessGuru's existing reasoning engine now accepts positional candidates from
ChessGPT and can compose a verified preparation/recapture explanation. Our
search ledger, typed scores, legal replay, piece identities, independent
verification, teaching selection and controlled renderer remain the core.
The production Why route is unchanged. This implements the authorised
[scope](combined_reasoning_scope.md) and [spec](combined_reasoning_spec.md).

## What was incorporated

Only `chessgpt/features.py`, unchanged from upstream revision
`b7ea991854f926250036105f152894881e7820a2`, is vendored. Its SHA256 is
`cbf257583293c0f1f1a2981b0b90381b5495b63d6d46dd71bc600214a8e86a65`.
The user's explicit confirmation of the author's permission is recorded in
`backend/vendor/chessgpt/PROVENANCE.json` and `NOTICE.md`. No broader upstream
licence is asserted. The upstream search wrapper, calibration weights,
prompts and model providers are not incorporated.

`positional.py` evaluates our already searched boards. Each feature snapshot
records the FEN, board-node ID, timeline ID, ply, side to move, provider
revision and hashes. Values are explicitly raw upstream feature units from
White's perspective. Differences suggest investigations; they do not assign
centipawns or a causal percentage to a feature. A zero fitted upstream weight
does not discard concrete candidate evidence.

The first composition joins actual identities and legal actions: an immediate
capture permits a minor-piece recapture; the alternative attacks that defender
first; a searched retreat changes which piece takes back after the same
capture. No fixture FEN, game ID, SAN name or square selects the composition.
The feature hint alone cannot admit the explanation.

`positional_verify.py` independently checks the placement and every dependency.
It requires pawn support, no current enemy attackers and a carefully scoped
claim about existing enemy pawns on adjacent files advancing toward the square.
Root comparisons must agree at both allocations. Both unrestricted opponent
reference searches must complete depth 20 and retain the narrated prefixes.
Matched recapture comparisons must favour the original recapturing piece.
The alternative recapturer must also have been a legal option in the original
position. Every intervening move in a longer demonstration is retained and
verified. Unreached depth, missing receipts or changed replies leave the
hypothesis incomplete.

These checks establish a conditional, engine-supported account. They do not
prove every possible defence, permanent pawn immunity or an exact allocation
of the evaluation gap to one positional feature.

## Concrete result: Nxe5

Input before Black's `Nxe5`:

```text
r1bq1rk1/ppp5/2n1p2p/3pBpp1/2PPn3/2PB1N2/P1Q2PPP/R3K2R b KQ - 1 12
```

Actual combined output:

> After Black's Nxe5, White can play Nxe5, placing the knight in the centre on
> e5. That knight is protected by the pawn on d4, and no Black piece attacks
> it at that point. No Black pawn currently on an adjacent file can chase it
> away by advancing. In the compared line, g4 instead attacks the defending
> knight on f3 first. After Nd2 Nxe5 dxe5, White has a pawn on e5 instead.
> Before an exchange, check which piece would take back.

Our baseline, given the same six-million-node total cap, abstains here. The
combined engine selects `comparative_recapture` with `supported_mechanism`.
Its fresh unrestricted depth-20 replies retain `Nxe5` after the played move
and `Nd2 Nxe5 dxe5` after `g4`. The separate 30k/120k root comparisons prefer
`g4` by 202/146 centipawns from Black's perspective. At the original recapture
decision, matched 30k/120k searches prefer White's `Nxe5` to `dxe5` by 151/153
centipawns. These are recorded search comparisons, not material counts or an
exact causal decomposition. This is a reviewed development position.

## Frozen validation

The final matrix ran against an unchanged source snapshot: exit code 0,
**5 integration tests passed in 124.57 seconds**. It executed nine requests
covering baseline/combined/repeated Nxe5 and six other disclosed positions.
The table reports individual request wall time, not a service latency target.

| Request | Result | Seconds | Engine queries |
|---|---|---:|---:|
| Nxe5, provider off, same total cap | Abstention | 12.989 | 20 |
| Nxe5, combined | Verified recapture mechanism | 12.298 | 13 |
| Na4, combined | Existing checking-capture contrast retained | 15.878 | 26 |
| Qf8, combined | Existing coverage/threat chain and Rc8 score retained | 15.537 | 25 |
| Nf3, combined | Played move's castling contribution retained | 18.562 | 32 |
| Qa2, combined | Mate in one versus mate in six retained | 5.077 | 8 |
| Rook contrast, combined | Immediate rook capture selected | 10.742 | 17 |
| Qc2, combined | Abstention | 16.481 | 27 |
| Nxe5 repeat, combined | Identical outside runtime fields | 13.429 | 13 |

Settings: base/stability allocations 30k/120k nodes; rank width 4; root cap 3;
reply width 2; timeline horizon 18; max hypotheses 80; max expanded nodes 16;
hash 64 MiB; existing equivalence tolerance 30 cp; max queries 32. Combined
mode explicitly uses feature horizon 4 and up to two million nodes per
depth-20 reference. The total cap is six million for Nxe5 requests and two
million elsewhere. These are experimental allocations, not shipping defaults.
Combined Nxe5 requested 4,780,000 nodes and used 2,525,778 actual engine nodes.
All requests stayed within their explicit query and requested-node caps.

Stockfish 19 binary SHA256:
`45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0`.

The engine-free package suite passed **131 tests** after the longer-route
boundary fixes. A subsequent metadata assertion/update passed all **18
combined engine-free tests**, then the final frozen engine matrix above ran.
The initial nine tests were committed before implementation at `231c4df2`
and failed without the new module. Additional tests, including two failing
longer-route boundaries, were committed at `8457e77a` before their fixes.
Coverage includes mirroring, actor and identity substitution, pawn challenges,
wrong score perspective, restricted reply searches, missing receipts,
unreached depth, explicit budgets and disabled-provider compatibility.

An additional audit deserialized the final saved artifacts, legally replayed
**122 timelines**, reverified **5,134 accepted propositions**, and checked all
seven selected explanations' dependencies against their saved search records.
It found no rejected accepted fact or selected dependency, and the source
snapshot still matched. These counts measure internal consistency; they are
not independent evidence of teaching usefulness or broad chess coverage.

The required application core-flow check was attempted against
`http://127.0.0.1:8001`. It stopped at the first request with
`httpx.ConnectError: All connection attempts failed` because no local backend
was listening. Application E2E is **unverified**, not counted as passing.

## Reproduction and evidence

From the worktree's `backend` directory in PowerShell:

```powershell
$reasoningTests = (Get-ChildItem tests/test_reasoning*.py |
    Where-Object { $_.Name -notlike '*integration*' -and
        $_.Name -ne 'test_reasoning_trace_is_the_engines_own_account.py' }).FullName
python -m pytest -q @reasoningTests

$env:CHESSGURU_TEST_STOCKFISH = 'C:\Users\MIISCO\chess-tools\engine\stockfish\stockfish-windows-x86-64-universal.exe'
python -m pytest -q -s tests/test_reasoning_combined_integration.py
```

The existing `scripts/benchmark_reasoning.py` also accepts explicit
`--positional-features --feature-plies 4 --verification-nodes 2000000`.
Its sealed mode includes the combined settings and vendored source/provenance
in the required hashes. Passing the frozen matrix does not make it an unseen
evaluation: all its positions are disclosed development/regression cases.

Local evidence is under `output/combined_reasoning_2026_10_30/`:

- `integration_final_freeze.json`: exact source/test/vendor hashes before run;
  SHA256 `8855717eef76687c54c795406e3cd7ce12c83f582af30fda01bcff69d57647ec`.
- `integration_final_completion.json`: test exit code and unchanged-freeze check.
- `engine_tests_final.log` and `engine_tests_final/combined_engine0/*.json`:
  outputs, typed scores, search ledger, provenance and sentence receipts.
- `saved_artifact_audit_final.json`: independent saved-artifact rechecks.
- `core_flows.log`: the unavailable local API check.

The large experimental `output/` directory is not part of the source commit.
The executable test fixtures and this report are committed for reproduction.
The main checkout remains on `working-code` with the user's three tracked
edits preserved.

## Remaining work before a player integration

The eight-second Why-button budget is unmet on every combined case here except
the mate example. Qc2 remains unexplained. The first composition covers one
family; additional positional features remain candidate diagnostics until a
verified explanation can use them. This work does not add LLM narration or
change production captions, routes, database records or frontend behaviour.

The next quality gate is to freeze this policy and evaluate fresh positions,
grade relevance separately from board truth, then reduce latency against the
same evidence contract. A product adapter and rollout are later work under
the scope. No conclusion about millions of positions or player learning
follows from this reviewed regression set.
