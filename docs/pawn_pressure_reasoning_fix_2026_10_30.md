# Pawn-pressure composition in the combined offline engine

Authorised fix, 2026-10-30: after inspecting the unused ChessGPT hint on
`15.c4`, Mohit requested, “please fix that and try again.” This extends the
existing [combined offline engine](combined_reasoning_scope.md). It changes
no production route, caption, frontend, model service or database record.

## The missing connection

Input:

```text
r1b2rk1/ppp5/5q1p/3pNpp1/3Pn3/2PB4/P1Q2PPP/R3K2R w KQ - 0 15
```

The played move is `c3c4` (`c4`). The previous combined run selected `f3` as
the best searched alternative but returned `incomplete_hypothesis` and no
explanation. ChessGPT's feature extractor had already flagged the pawn on
f3 attacking Black's knight on e4. Its output was unused because our first
positional composer only joined preparation/recapture patterns.

The existing replay/fact store already provides the root attack and piece
identities. The fix extends `services/reasoning/positional.py`, its independent
verifier and the same renderer/selector. No parallel attack detector, piece
value table or player-facing narrator is created. Upstream code is unchanged.

## What the new certificate establishes

`comparative_piece_pressure` consumes an imported pawn-attack hint only when
exact board facts independently identify one attacked non-pawn, non-king
piece that stays on the same square without a pawn attack after the played
move. Ambiguous multiple-target attribution is left for another composition.

The engine then requires:

1. Both original root comparisons prefer the alternative under the existing
   equivalence policy. The targeted piece moves away in both alternative PVs.
2. Fresh unrestricted opponent searches after both roots complete depth 20.
   The alternative's reply moves the same target; the played move's reply
   retains it. The deeper score comparison must still prefer the alternative.
3. At both existing base/stability allocations, an unrestricted best reply
   moves the target. A matched counterfactual search includes every legal
   reply that leaves that piece on its square, and scores worse for its side.
4. The counterfactual PVs agree on the complete, legally replayed immediate
   pawn-for-piece exchange. Piece, actor, capture and search receipts must
   bind to that precise demonstration. Longer unsupported events are unused.

The independent verifier reconstructs legal boards/events and binds scores,
root restrictions, perspectives, requested allocations, source positions and
search IDs. It checks the purported retreat is legal even when the score
receipt is valid. History-bound node IDs are preserved. Insufficient depth,
budget or projection horizon leaves an incomplete hypothesis.

The reply destination is deliberately not called stable. On this position,
the original stability search chooses `Nc5`; a fresh depth-20 reply search
chooses `Nd6`. The admitted invariant is **the same knight leaves e4**.
The prose names that invariant without asserting a specific destination. It
does not splice either retreat into another PV. The concrete exchange example
has its own full prefix agreement and explicitly counterfactual provenance.
Existing exact-move resource admission rules remain unchanged.

This is conditional search evidence, not an exhaustive proof that the knight
must move or an exact causal allocation of the whole evaluation gap.

## Tests before implementation

The first 18 engine-free pressure tests were committed at `740b5a5e` before
implementation; all 18 failed because the composer was absent. They cover
the real geometry and its colour mirror, invariant replies with different
destinations, unsupported hints, insufficient depth, competitive replies that
ignore the attack, fabricated actors/identities/scores, incomplete restricted
reply sets and missing fact/search receipts.

Commit `15b5ed39` adds real-position integration regressions, history and
short-horizon checks, and a mutation changing a scored retreat to illegal
`e4e8`. That mutation failed before the verifier fix. A further failing
same-destination control removed an unconditional claim that retreat squares
vary. The wording now only states the verified departure invariant.

The broad filename-glob attempt additionally collected the unrelated admin
reasoning-trace route test; collection stopped because `bcrypt` is not
installed locally. The explicit offline suite excludes that application
test. The required `test_all_flows.py` attempt against local port 8001 also
failed with `httpx.ConnectError` because no backend was listening. Neither
application check is counted as passing.

No new shipping score threshold or ranking weight is selected. The existing
30 cp comparison policy, 30k/120k allocations and depth-20 gate are reused.
The six-million-node quality cap and two-million-node reference allocation
remain explicit experimental inputs. The two-million-node total-cap run is
separately retained; a quality result is not claimed to fit that smaller cap
or the eight-second product budget.

## Reproduce

From `backend` in PowerShell:

```powershell
$reasoningTests = (Get-ChildItem tests/test_reasoning*.py |
    Where-Object { $_.Name -notlike '*integration*' -and
        $_.Name -ne 'test_reasoning_trace_is_the_engines_own_account.py' }).FullName
python -m pytest -q @reasoningTests

$env:CHESSGURU_TEST_STOCKFISH = 'C:\Users\MIISCO\chess-tools\engine\stockfish\stockfish-windows-x86-64-universal.exe'
python -m pytest -q -s tests/test_reasoning_combined_integration.py
```

Local evidence is saved in `output/combined_reasoning_2026_10_30/c4_fix/`.
Source/test/vendor hashes are recorded before the engine matrix and compared
again afterwards. All positions are disclosed development/regression cases;
this is not an unseen evaluation or a claim of general positional coverage.

## Measured result

The full frozen matrix passed **7 Stockfish integration tests across 12
requests in 203.60 seconds**, with the source snapshot unchanged. Nxe5, Na4,
Qf8, Nf3, mate distance and the immediate-rook-capture contrast retained their
previous behaviour. Qc2 still abstains. The new c4 quality run and repeat both
selected `comparative_piece_pressure`; the limited-budget run abstained.

After the final wording-only correction, all **154 offline reasoning tests**
passed, including **23 pressure tests**. Three fresh frozen engine calls
reran c4, its repeat and the limited-budget case. The same seven regression
assertion functions passed against those final outputs and the retained
unaffected matrix outputs. This final step is three new engine calls, not a
second fresh execution of all twelve. Its source snapshot also stayed fixed.

Final engine output:

> f3 uses the pawn on f3 to attack Black's knight on e4; c4 leaves that knight
> without a pawn attack. The best replies found after f3 move that knight
> away. Leaving it there is worse for Black in both comparisons: for example,
> f3 c5 fxe4 fxe4 exchanges White's pawn for that knight. Check whether a pawn
> can challenge an active enemy piece before starting another plan.

| Final request | Result | Seconds | Executed engine queries |
|---|---|---:|---:|
| c4, total cap 6M | Supported pressure mechanism | 14.327 | 13 |
| c4 repeat, total cap 6M | Identical outside runtime fields | 13.546 | 13 |
| c4, total cap 2M | Incomplete; required reference allocation unavailable | 13.040 | 18 |

The quality request reserved **4,780,000 nodes** and actually searched
**2,325,739 nodes**. Both unrestricted references completed depth 20. From
White's perspective, they score f3 at -0.01 and c4 at -1.33. The original
120k root comparisons remain +0.14 and -1.75 respectively. Different search
settings give different evaluations; the preference survives both checks.
At matched 30k/120k reply allocations after f3, leaving the knight on e4 is
66/73 centipawns worse for Black than moving it. The example c5 fxe4 fxe4 is
the best searched **restricted counterfactual**, not Black's best reply to f3.
No percentage of the root gap is attributed to that exchange.

An additional saved-artifact audit replayed **151 legal timelines**, rechecked
**6,110 accepted facts** and all selected dependency graphs across the retained
regressions plus the three final outputs. No accepted claim failed. Those are
internal consistency checks, not an independent teaching-quality evaluation.

Final c4 artifact: `wording_final/c4.json`, SHA256
`f1246ff620b397e09f3a5384a0972224df0511bab92a96f1e085c631797dad92`.
Additional records under the evidence directory:

- `unit_tests_final_wording.log`: 154 passed in 14.01 seconds.
- `integration_freeze.json`, `integration_completion.json` and
  `engine_tests_frozen.log`: the full twelve-request matrix and unchanged hashes.
- `wording_final/source_freeze.json`, `completion.json`, `c4*.json` and
  `artifact_audit.json`: final wording runs, repeatability and saved-proof audit.
- `core_flows.log` and `unit_tests.log`: the unavailable application checks.

Voice audit: square and piece names replace positional jargon; the pawn-for-
knight statement is backed by actual captures; the text makes no forced-reply
or evaluation-as-material claim; the transferable habit remains last. It uses
the existing offline renderer and does not bypass the production caption path.

The eight-second product budget remains unmet. This fix turns one previously
unused feature family into checked teaching; it does not make every ChessGPT
feature usable or solve general positional explanation. The main checkout
remains on `working-code` with the user's three tracked edits preserved.
