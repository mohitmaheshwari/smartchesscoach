# Chain builder: c4 and new-position experiment

The offline chain builder generated the user-supplied c4 support chain from
replayed board relations. Its first new-position test did **not** establish a
correct reason on any of four fresh positions. One produced plausible but
unverified bishop-related candidates; a deeper opponent search changed its
first reply. This is a failed initial transfer test, not evidence of a general
explanation engine.

## Implementation

`services/reasoning/chain_builder.py` derives identity-aware facts from the
existing canonical replay: lost support, gained attack, capture and exposure.
It links facts through the same physical pieces and time to enumerate maximal
candidate paths. It has no FEN, pawn, knight, square or game-specific guard.
At present all chains must begin with support lost on the played move, so this
is a limited first grammar, not a general mechanism finder. It emits every
candidate without ranking and never returns coaching text or a verified label.

`services/reasoning/chain_challenge.py` checks that the candidate is reproduced
from canonical replay, sources bind to the played root and unrestricted reply,
searches reach the requested depth, candidate facts lie within agreement of
the played-root and reply lines, and the root relation is preserved in the
searched alternative. Even a candidate passing those checks remains explicitly
unreviewed. The module does not establish causal relevance, compare all good
defences, prove compensation, or independently verify every relation.

`scripts/run_chain_candidates.py` runs the played root, unrestricted opponent
reply and root ranking through the existing isolated SearchSession, builds
legal timelines, then saves candidates, challenges, exact searches and source
hashes. It never calls an LLM. The production Why and caption paths do not
consume these outputs.

## c4 development position

Fresh Stockfish 19 searches, depth 20, 2M nodes per query, three queries;
all achieved depth 20. Runtime was 13.06 seconds, with 3,775,328 actual
nodes. The opponent line began `c4 c5 cxd5 cxd4 f4`. The builder produced one
candidate, with the searched alternative `f3` preserving the root support:

1. c4: the pawn from c3 stops defending the pawn on d4.
2. ...c5: the black pawn attacks d4.
3. ...cxd4: that pawn captures the pawn on d4 in this line.
4. The removed d4 pawn no longer defends the knight on e5.
5. The knight is undefended and attacked by the queen on f6.

The search-source and line-agreement checks pass when applied to this saved
run. It remains `candidate_needs_review`, not an automatically verified
mechanism. The user and the independent previous review had already identified
and checked this exact development example, so it is not evidence of transfer.

## Six exploratory positions

Six further FENs were randomly selected from the existing 4,442 pressure-shape
export, one per game, excluding earlier sample, frequency examples, and known
regression game IDs. Seed 20261031; manifest SHA-256
`cdb1279fa31a5a8ea965bc9912b347f8d180178f693973d48e47cd717504c65c`.
The original builder was committed before running them. All six first runs
were partial at the 2M-node budget; 18 candidates were generated. After one
case had been inspected, the provenance/agreement challenger was added, so
its later evaluation of these six is exploratory, not a sealed test.

A separate 8M-node-per-query repeat reached depth 20 on all six: 19 candidates
in total, six passed the limited mechanical checks in two positions and 13
were incomplete. **No candidate was automatically verified.** The higher
budget changes search results; source and results from both runs are preserved.
Wall times on this contended local machine were 11.8–27.1 seconds per case.
The six candidates that passed need independent relevance/defence review;
their count is not a correctness score.

## Four fresh positions after the complete policy was frozen

Commit `f4994b40` fixed the candidate generation and challenge policy before
selection of four further game-separated positions, excluding the six above
and the known prior samples. Seed 20261101; manifest SHA-256
`b615ba496acdb7538b9fa8636896233841c36aef6c538bf32667aa064e219255`.
These are fresh to this policy, but all come from the pressure-shape export;
four cases cannot estimate general chess performance. No independent human
grading has yet been performed. All runs kept their source freeze unchanged.

| Case | Search | Candidates | Result |
| --- | --- | ---: | --- |
| fresh_00: Bxd5 | Partial: played-root search depth 18 | 0 | No candidate. The reply line includes Nxd5 and later Qxg5. |
| fresh_01: ...Nd4 | Complete at depth 20 | 3 | All incomplete: the searched alternative does not preserve the root relation. |
| fresh_02: Bg5 | Complete at depth 20 | 4 | Two incomplete; two pass only the mechanical checks and need review. |
| fresh_03: ...h6 | Complete at depth 20 | 0 | No candidate. |

No correct, relevant explanation is established on these four. This is a
conservative result: `candidate_needs_review` is not a claim that a candidate
is right, and no candidate text is shown as an answer to a player.

### The fresh Bg5 case

FEN before: `r1bqk2r/pppp1ppp/2n2n2/2b5/2B1P3/2N2N2/PP3PPP/R1BQK2R w KQkq - 1 7`.
The two mechanically admitted candidates both say the bishop formerly on c1
lost support when it moved to g5 and Black's ...h6 attacks it. The depth-20
line continues `Bg5 h6 Bh4`; the bishop retreats. Those board facts do not
establish why Bg5 missed the stronger opportunity.

Independent fresh-process depth-22 searches gave `e5` +105 cp for White,
`Bg5` -26 cp, and selected `...d6` as the immediate reply after Bg5 rather
than the earlier `...h6`. The e5 line begins `e5 Ng4 Bxf7+ Kxf7 Ng5+ Kf8
Qxg4`. These results demonstrate the need to investigate the alternative and
the reply stability; they do not by themselves prove a unique explanation.
The current checker did not detect the depth-22 reply change. The candidate
must not be presented as the reason.

## Validation, limits, and files

- Seven chain-builder unit cases passed after failing before implementation;
  four challenger tests also passed after failing before implementation.
- The complete relevant engine-free reasoning suite passed **235 tests**.
- A separate core HTTP suite was attempted but localhost:8001 was unavailable;
  no application end-to-end pass is claimed.
- The `fresh_final/` and exploratory run folders contain source-freeze hashes,
  per-position legal timelines, candidate facts, search receipts and runtime.
  `fresh_02_judge.json` contains the independent deeper searches. The prior
  c4/six challenger results were applied after those saved runs, without new
  searches, in `posthoc_search_challenges.json`.
- The earlier 6M total cap and 24M higher-budget cap are explicit offline
  experiment settings, not production thresholds. Timings are contended and
  are not an 8-second Why-button claim.

The next research problem is to explain *why a candidate matters to the choice*
and challenge it against alternative replies and compensation. Simply
discarding every moving piece that loses support would remove plausible cases
as well as the fresh Bg5 noise; that change needs measured tests. Extending the
primitive grammar beyond initial support loss is also necessary for captures,
missed forcing resources and quiet positions where no such loss occurs.
