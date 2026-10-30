# Correcting the c4 explanation: follow the lost support

Mohit's correction identifies the relevant chain: the pawn on c3 protects
d4, and d4 protects White's knight on e5. The previous f3 caption described
a real pawn attack on Black's knight, but failed to explain what c4 broke.
Calling that an adequate explanation of this mistake was wrong. The earlier
tests checked facts and a selected feature family, not the required relevance.

## Verified chess account

Before c4, c3 is d4's only defender, and d4 is the e5 knight's only defender.
Black's queen on f6 already attacks e5. Playing c4 abandons d4's protection.
Black's c5 attacks that now-undefended pawn. After
`c4 c5 cxd5 cxd4`, the d4 pawn is captured and the knight on e5 is undefended
against the queen. This is the root-connected mechanism the previous caption
missed.

Mohit's complete line `c4 c5 cxd5 cxd4 f4 gxf4 Nf3 Nc3` is legal. At f4,
White replaces the knight's lost defender with the f-pawn; gxf4 removes that
replacement. Nf3 moves the exposed knight away. Black's later Nc3 is protected
by the black pawn now on d4. Those support relationships were independently
replayed and saved in `support_walk.json`.

The saved depth-20 best-reply line agrees through Nf3, but chooses Re8 next.
The lower-node base PV chooses Nc4 immediately after cxd4, while stability and
depth 20 choose f4 first. Therefore the engine's central account ends at the
defender's capture on ply 4, where all three searches agree. It does not call
Nf3 or Nc3 forced, and does not splice a later event into a different PV.

## Correction to the existing engine

The new `comparative_support_chain` composition derives its roles from our
canonical boards, identities and existing `coverage_abandoned`, `attacks_piece`,
`captures` and `reaches` facts. ChessGPT's placement hint identifies a candidate
piece to investigate; it does not certify the support chain. The source code
contains no fixture FEN, move name or square lookup.

The composition checks:

- The played pawn abandons the last defender of another friendly pawn.
- That pawn is itself the candidate minor piece's only defender.
- The alternative preserves both support edges at the root.
- The opponent's first reply attacks the abandoned pawn; the same enemy piece
  captures it later in the primary line, exposing the original minor piece.
- Every narrated move through the capture agrees between base, stability and
  a completed unrestricted depth-20 reply search. Both original root comparisons
  and the deeper unrestricted score comparison must retain the preference.

The independent verifier rebuilds legal events and support relationships and
checks exact actor, identity, timing, score and search receipts. It checks the
claimed exposed attackers from the resulting board. A missing defender,
another remaining defender, a substituted piece, an avoided line or insufficient
search evidence prevents this certificate from becoming teaching.

This account is investigated before the generic best-move pawn-pressure
account. If a concrete played-move support-loss hypothesis is incomplete, it
cannot be replaced by the incidental alternative feature. Existing immediate
material and forcing explanations retain their priority.

This is still conditional engine evidence, not an exhaustive proof of every
possible defence or an exact attribution of the whole centipawn gap.

## Tests and scope

Commit `2f429f0e` added the first 18 failing tests before implementation.
They cover the mirrored position, identity and timing substitutions, false
exposure, missing origin/capture/search receipts, restricted references and
insufficient depth or PV agreement. Commit `19e695ca` adds the corrected
real-position regression and controls for extra defenders and a completed
best reply avoiding the support loss.

All **175 offline reasoning tests passed**. This includes the earlier pressure
tests, which remain tests of a true alternative feature rather than proof that
it is the right explanation of c4. The application core-flow attempt still
fails to connect to the absent local backend on port 8001; application E2E is
not counted as passing.

The work extends the authorised offline engine. It adds no production route,
caption path, LLM service, database write or shipping threshold. Existing
30k/120k root allocations, completed-depth-20 gates and explicit experimental
quality budgets remain in force. The placement provider and its permission
provenance are unchanged. This reviewed case is not held-out evaluation.

Evidence directory: `output/combined_reasoning_2026_10_30/c4_support_audit/`.
The main checkout stays on `working-code` with the user's tracked edits intact.

## Final measured output

> With c4, the pawn leaves c3 and stops defending d4. The pawn on d4 is the only
> defender of White's knight on e5. Black's c5 attacks that undefended pawn.
> After c4 c5 cxd5 cxd4, that pawn is gone and the knight on e5 is undefended
> against Black's queen on f6. f3 keeps the pawn on c3 defending d4 and the
> pawn on d4 defending e5. Before pushing a pawn, check what it protects and
> what depends on that protection.

The full frozen matrix passed **7 integration tests across 12 engine requests
in 168.61 seconds**, with unchanged source hashes. Existing Nxe5, Na4, Qf8,
equivalent-move subject, mate-distance and immediate-rook-capture behaviour
retained their results. Qc2 remains unexplained. c4 now selects the support
chain, not the pawn-pressure feature; its repeat is identical outside runtime.

A final wording check required the renderer to name both defending pawns
explicitly. Both colour variants failed the ambiguous wording before its fix
(`da4d853a`). All **175 engine-free tests passed in 13.88 seconds** afterwards.
Three fresh frozen engine calls then reran c4, its repeat and the limited-budget
case. All seven integration assertion functions passed against those final
outputs and the retained unaffected outputs. This last check is three new
engine calls, not another fresh execution of all twelve. Both source freezes
remained unchanged during their runs.

| Final request | Result | Seconds | Executed queries |
|---|---|---:|---:|
| c4, total cap 6M | Supported loss-of-support mechanism | 10.185 | 9 |
| c4 repeat, total cap 6M | Identical outside runtime | 9.550 | 9 |
| c4, total cap 2M | Incomplete; required reference allocation unavailable | 11.477 | 18 |

The quality request reserves 4,480,000 nodes and actually searches 2,025,569
nodes. Base/stability allocations remain 30k/120k; unrestricted references
have an explicit allocation of up to 2M each and must complete depth 20.
No depth or score gate was weakened. Runtime remains above the eight-second
product budget, and the two-million-node total-cap request still abstains.

The serialized final artifacts were replayed and their facts and selected
dependencies reverified, including the exact c3-pawn / d4-pawn / e5-knight
identities. This checks proof consistency; the relevance correction comes from
the verified causal relationship identified by Mohit, not a test-count metric.

Evidence under the directory above:

- `support_walk.json`: all eight supplied moves, defenders and attackers by ply.
- `unit_tests_final.log`: the final 175-test run.
- `source_freeze.json`, `completion.json`, `engine_tests.log` and
  `engine_tests_frozen/combined_engine0/*.json`: full frozen matrix.
- `final/source_freeze.json`, `completion.json`, `c4*.json`,
  `artifact_audit.json`: final explicit-pawn wording, repeat and low-budget run.
- `core_flows.log`: unavailable local application check.

Final c4 artifact SHA256:
`446f1f5596c606a3a63448ea7c6353ea9a851d1384dc4ef5fbe60af0406e5ba2`.
Stockfish binary SHA256:
`45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0`.

Voice check: the explanation names the squares and pieces, describes actual
support loss, does not call the knight lost or a retreat forced, and ends with
a transferable habit. It stays in the same offline renderer. No production
caption or application E2E claim follows from these results.
