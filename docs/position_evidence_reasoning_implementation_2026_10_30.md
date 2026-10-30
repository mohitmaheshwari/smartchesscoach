# Position evidence to GPT-6-luna: implementation and measured result

The requested pipeline is coded and has run on the supplied 18...g4 position.
It collects Stockfish lines of at most 15 half-moves, scans every piece before
the move and after each half-move, and explicitly sends that evidence to
`gpt-6-luna`. The current model's explanation quality is still insufficient.
This is a reusable offline experiment; it is not connected to the Why button.

## What the command does

Entry point: `backend/scripts/explain_position_evidence.py`.

1. Validate the starting board and played move, or infer the unique legal move
   from the before/after FEN pair. Reject mismatches before searching.
2. Search the played root, rank alternatives, search the best alternative
   when different and better, and search unrestricted replies after those
   roots where the explicit budget permits. Retain each source separately.
3. Replay the available legal moves, capped at 15 plies including the played
   move. A shorter PV or game end is not padded. Record achieved depths,
   partial searches and stop reasons.
4. Scan every surviving physical piece at the start and after every ply:
   defenders, attackers, pieces it protects or attacks, squares controlled,
   geometric reach, king pins, pawn support and positional candidate evidence.
   Also record captures, promotions, actor, exact material counts and changes
   to unmoved pieces. Identity survives moving, castling and promotion;
   a pawn arriving on a captured knight's square is a different piece.
5. Save full snapshots and an initial state plus lossless deltas for the
   model. No manually chosen reason, caption or case-specific hint is supplied.
6. Only with `--call-model`, ask exactly `gpt-6-luna` for a cited reasoning
   proposal. Save the precise input, prompt, raw response, checks and runtime.

Board relationships come from the existing legal replay. Positional attributes,
including passed-pawn and outpost labels, come from the existing ChessGPT
feature provider. Those labels are candidate evidence, not verified causes of
an evaluation difference. A piece being attacked or undefended is not proof
that it can be profitably captured. The scan does not claim to recognise every
possible chess strength or weakness.

The existing search ledger, replay, feature extractor, piece values and LLM
caller are reused. `explain_fen` remains available. No production route,
caption template, frontend or database schema was changed.

## Run another position

PowerShell, from this worktree. These budgets reproduce the development
allocation; they are experimental inputs, not a production policy.

```powershell
$repo = 'C:\Users\MIISCO\.codex\worktrees\reasoning-review-fixes\smartchesscoach'
$pythonExe = 'C:\Users\MIISCO\smartchesscoach\backend\.venv\Scripts\python.exe'
$engineExe = 'C:\Users\MIISCO\chess-tools\engine\stockfish\stockfish-windows-x86-64-universal.exe'
Set-Location -LiteralPath $repo
New-Item -ItemType Directory -Path 'output/evidence_example' -Force | Out-Null
@'
{
  "engine_path": "set-by-cli",
  "nodes": 8000000,
  "stability_nodes": 8000000,
  "max_queries": 5,
  "max_total_nodes": 40000000,
  "rank_width": 3,
  "root_cap": 3,
  "reply_width": 2,
  "max_plies": 15,
  "max_hypotheses": 80,
  "max_expanded_nodes": 16,
  "hash_mb": 64,
  "equivalence_cp": 30
}
'@ | Set-Content -LiteralPath 'output/evidence_example/config.json' -Encoding UTF8
$runArgs = @(
  'backend/scripts/explain_position_evidence.py',
  '--fen-before', 'r1b2rk1/pp3n2/2p2q1p/2PpNpp1/3P1P2/3B4/P1Q3PP/R4RK1 b - - 0 18',
  '--fen-after', 'r1b2rk1/pp3n2/2p2q1p/2PpNp2/3P1Pp1/3B4/P1Q3PP/R4RK1 w - - 0 19',
  '--config', 'output/evidence_example/config.json',
  '--engine', $engineExe,
  '--depth', '24',
  '--max-plies', '15',
  '--output-dir', 'output/evidence_example/run_01'
)
& $pythonExe @runArgs
```

That saves evidence without loading model credentials or calling a provider.
For the explicit model stage, use a new output folder and append these options
to the arguments before invoking the command:

```powershell
$modelArgs = @(
  '--call-model',
  '--env-file', 'C:\Users\MIISCO\smartchesscoach\.env',
  '--max-output-tokens', '6000',
  '--reasoning-effort', 'low'
)
# Run this instead of the packet-only invocation above, with a new output folder.
& $pythonExe @runArgs @modelArgs
```

An already exported provider configuration also works; omit `--env-file` in
that case. The command never searches for credential files. It refuses to
overwrite a nonempty output folder. `--played-move` accepts a legal SAN/UCI
move as an alternative to `--fen-after`; supplying both checks their agreement.
`--history` accepts JSON with `initial_fen` and `moves` when history is available.

## Output contract

| File | Meaning |
| --- | --- |
| `evidence.json` | Complete saved states, searched branches, events, exact counts, source records and hashes |
| `model_input.json` | The model-facing evidence with shared states and lossless deltas; excludes local configuration paths |
| `model_system.txt` | Exact generic reasoning prompt, when the model is requested |
| `model_response.txt` | Raw provider text, including rejected text |
| `model_result.json` | Parsed proposal, checks, review status and runtime |
| `summary.json` | Search coverage and model status; rejected prose is excluded |

`complete` evidence means the attempted searches returned complete iterations
at the requested depth. It does not mean the tree was exhaustively searched
or every alternative was investigated. `partial` retains what is available.
If no searched continuation is available, the command records an evidence error.

The model can explain or abstain. Reference checks validate shape, state IDs,
branch membership, physical piece IDs at a state or its arrival capture event,
and explicit structured material claims. Invalid responses are `refused` and
remain in the audit files. A structurally valid response is only an
`unreviewed_proposal`; its free-text truth and explanatory relevance are
explicitly unreviewed. The summary labels its text `unreviewed_explanation`.

Exit codes: 0 for saved evidence / a structurally valid proposal; 2 for an
evidence error; 3 for a refused response or provider error. Model errors have
no generated fallback story. Exception messages and credentials are not saved.

## Measured development run

Artifacts are local under `output/position_evidence_pipeline_2026_10_30/`.
The initial real CLI invocation saved `live_run_v1/`; the subsequent model-only
run saved `model_stage_final/` and reused the exact same Stockfish evidence.
Each run records a source freeze. The evidence collector did not change
between these runs. No targeted probe or hand-authored explanation entered
either model request.

After the calls, the generic prompt was clarified to state that an event's
legal-reply count applies to the next move, and to ask for everyday language.
The CLI summary was also corrected to omit rejected prose. Neither change was
followed by another paid model call. The exact prompts and source hashes used
in both recorded calls remain saved alongside those calls.

| Measure | Observed |
| --- | --- |
| Played move | Black 18...g4, inferred as g5g4 from the supplied FEN pair |
| Engine | Stockfish 19, one thread, 64 MiB hash, isolated searches |
| Engine SHA-256 | `45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0` |
| Requested / achieved depth | 24 / 24 in all five searches |
| Requested / actual nodes | 40,000,000 / 16,049,681 |
| Branches / unique states | 3 / 45, starting from 25 pieces |
| Available horizon | 15 plies in every branch |
| Evidence collection time | 42.640 seconds |
| Full evidence file | 2,211,238 bytes |
| Model JSON file / transmitted JSON | 551,165 bytes pretty printed / 232,181 characters compact |
| Latest model call | gpt-6-luna, low effort, 6,000-token output allocation |
| Latest provider usage | 76,521 input + 851 output = 77,372 reported tokens |
| Latest model time | 11.416 seconds, excluding evidence collection |
| Latest mechanical result | Refused: stale piece citations in all three connections |

The latest model-only harness used a 60-second transport timeout and no
retries. This was a test override, not a change to the shared caller. The CLI
uses the existing caller's timeout and retry policy. Its earlier medium-effort
model call took 64.973 seconds; the run does not establish how many SDK retries
occurred. Timings from the reused model stage and original engine stage are
separate measurements, not a newly measured combined request.

The three saved lines are:

```text
B1 played: g4 Rae1 Nxe5 fxe5 Qg6 Rf4 Be6 g3 h5 Ref1 Kg7 a4 Rf7 Qf2 Raf8
B2 alternative: Nxe5 fxe5 Qf7 g3 f4 gxf4 gxf4 Kh1 Kh8 Rg1 Bf5 Bxf5 Qxf5 Qxf5 Rxf5
B3 played, fresh reply search: g4 g3 h5 h4 gxh3 Qh2 b6 Rac1 Nxe5 dxe5 Qg6 Qxh3 Bd7 Rfe1 bxc5
```

The fixed-root scores were -45 cp for g4 and -9 cp for Nxe5, both Black POV.
Root ranking returned Nxe5 at 0 cp; the unrestricted reply searches returned
-35 and -3 cp respectively. These are different recorded searches. The reply
search after g4 selected g3, while the root PV selected Rae1; neither branch
is labelled forced or silently merged with the other.

Useful evidence is present: White's e5 knight initially has d4/f4 pawn support
and is attacked by Black's f6 queen/f7 knight. The g5 pawn loses f4 control
after g4. In B1, fxe5 removes the f4 pawn from that square and Rf4 follows.
The e5 occupant after the exchange is a pawn with a new passed-pawn candidate
label, not the original knight. Those relationships are scanned independently
of what the model chooses to say.

## What the model got wrong

The latest draft is preserved verbatim, rather than repaired into a success:

- It cited White's e5 knight at N4, although that knight was captured at N3.
- It cited White's captured h-pawn at N36, well after the capture event, and
  Black's queen at N30, a state after that queen had already been captured.
- It described B2's final material as level while its own structured claim
  correctly reported -100 cp in White material balance. Black still has six
  pawns against five. The reference checker does not establish free-text
  entailment, so this prose contradiction is a separate manual finding.
- Its assessment says g3 lets White capture the f5 pawn, which the supplied
  played continuations do not demonstrate. Its final explanation emphasises
  the h-pawn exchange rather than establishing why it accounts for the gap.

The first medium-effort draft originally failed a reference rule that was too
strict: a state immediately after a capture legitimately supports citing the
piece just captured. Tests were committed before correcting that generic
arrival-event rule. Rechecking the unchanged first response now passes its
references, but its timing explanation still does not establish the principal
cost of g4. Passing references does not make it coaching-correct.

The latest stale references remain rejected. No rule was relaxed to accept
pieces at later unrelated states, and no hand-written chess explanation was
substituted for either draft.

## Validation and limits

Contract tests were committed before the implementation and before fixes for
newly discovered boundaries. They cover all-piece scans, changed relationships
on unmoved pieces, castling/en-passant/promotion identity, exact material,
legal FEN pairs, short/terminal lines, the 15-ply cap, partial budgets/depth,
source binding, lossless reconstruction, malformed responses, stale and
cross-branch citations, explicit model calls and provider failures. The final
offline suite passed **210 tests** (35 new contracts and 175 existing tests) in
36.66 seconds. The live Stockfish integration test passed **1 test** against
the actual CLI artifact. All 45 real states were additionally reconstructed
exactly from the compact model view. The model adapter tests were rerun after
the final prompt clarification; see `model_adapter_final.log`.

The required core HTTP flow suite was attempted against localhost:8001 and
could not connect to a running backend (`httpx.ConnectError`). It is not a
passing end-to-end result. No production rollout, held-out quality benchmark
or eight-second latency claim is made.

This completes the requested offline evidence-to-model implementation. It does
not establish that GPT-6-luna reliably selects the relevant explanation. The
saved failure is the measured outcome; fresh-position evaluation and improving
that reasoning remain necessary before showing these drafts to players.
