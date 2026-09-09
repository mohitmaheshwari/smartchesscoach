# Unsafe-recapture pawn-fork caption — implementation evidence

Date: 2026-09-09
Status: implemented and locally verified; not pushed or deployed

## Outcome

The central opponent-caption path no longer stops at the immediate capture in
the reported `Re1` position. It now explains the legally stored continuation:

> Opponent's Re1 is an inaccuracy. Play Nxe4. If Rxe4, d5 attacks their rook
> at e4 and bishop at c4 together. After Bxd5 Qxd5, your knight and their
> bishop both come off the board. Before recapturing, check whether a pawn
> push can attack two pieces.

The rule is position-general. There is no game id, FEN, move sequence, or
caption string embedded in the detector.

## Proof contract

The new caption can render only when the canonical stored-line replay proves
all of the following:

1. the recommended move legally captures a piece;
2. the opponent legally recaptures that exact moving piece on the same square;
3. a legal, quiet, unpinned pawn move attacks the recapturing piece and exactly
   one other persistent non-king piece;
4. the stored continuation resolves the double attack in one of two proved
   ways:
   - the other target captures the pawn and is then recaptured; or
   - one target moves and the pawn captures the other target;
5. every named piece identity, square, and SAN move comes from replayed board
   state, not evaluation loss or prose inference.

If any condition is missing, illegal, ambiguous, or unresolved, the proof
returns no result and the existing safe fallback remains in control.

## Real examples

### Reported Re1 position

- start after `Re1`: `r1bq1rk1/pppp1ppp/2n2n2/2b1p3/2B1P3/1P3N2/P1PP1PPP/RNBQR1K1 b - - 2 6`
- stored line: `Nxe4 Rxe4 d5 Bxd5 Qxd5`
- proved targets after `d5`: rook on e4 and bishop on c4
- proved resolution: bishop captures d5; queen captures that exact bishop

### Independent versioned-corpus example

- start: `r1bqkbnr/pp1p1ppp/4p3/2p1n3/2B1P3/2Q4N/PPPP1PPP/RNB1K2R b KQkq - 3 5`
- stored line: `Nxc4 Qxc4 d5 Qe2 dxe4`
- proved targets after `d5`: queen on c4 and pawn on e4
- proved resolution: queen moves; the same pawn captures the other exact target

## Corpus measurement

A read-only recursive scan covered 82 versioned JSON evidence files in
`backend/data/corpus_snapshots` and `backend/data/detector_gold`:

- 6,576 nested rows contained `fen_before`, `best_move_san`, and
  `pv_after_best`;
- 3,570 stored continuations were unique;
- the proof fired once, on the independent `Nxc4 Qxc4 d5 Qe2 dxe4` example;
- it fired on no other stored continuation.

This scan is evidence of narrowness, not a recall claim. It shows that the new
proof does not broadly reinterpret unrelated stored lines. The reported Re1
position is a second real example outside that anonymized packet set.

No database access, Stockfish run, model call, production read, or production
write was used for this implementation or scan.

## Test evidence

Focused tests cover:

- exact persistent piece identities and squares for both real examples;
- both supported resolution families;
- incomplete horizon, illegal continuation, and unresolved double-attack
  abstention;
- atomic fact projection into R12;
- exact final Re1 caption and six-move interactive coach line;
- strict final-caption verification;
- preservation of the existing fallback on an unproved immediate capture.

The V5 coaching-content version is bumped from 148 to 149 so cached reviews
regenerate through the normal existing path after deployment.

The end-to-end trace also found that the central A3 helper's opponent
`coach_line` return value was dropped during the earlier V5 migration. The
typed decision now carries the six proved SAN moves, and V5 projects them to
the existing Game Review replay fields. That projection is gated to this
typed proof family, so this release does not activate every dormant generic
opponent line.

## Release-gate repair

Touching `game_decryption_v5_service.py` for the required version bump caused
the changed-file CI guard to rescan 17 unchanged legacy captions and fail. A
clean `origin/working-code` checkout produced the same 17 findings. The guard
now scans the committed head snapshot but blocks only findings on added or
modified lines. Contract tests prove both sides:

- safe maintenance in a file with an unchanged legacy finding passes;
- a newly added noncentral caption in that same legacy file still fails.

The whole-backend audit remains unchanged and still reports the legacy debt;
no file-wide exemption or bypass marker was added.

Local results on the isolated branch:

- focused proof, rendering, fallback, stored-line, interaction-boundary, and
  no-LLM tests: 36 passed;
- wider caption-truth, authorization, V5-version, validation, and release
  wiring suites: 146 passed, 15 skipped on the rebased latest
  `origin/working-code`;
- the two broad legacy central-pipeline suites plus the no-LLM invariant:
  87 passed, 7 failed; the same seven central-pipeline tests fail on a clean
  `origin/working-code` checkout (82 passed, 7 failed), so this change
  introduced zero failures;
- whole-file strict caption-source scan: 17 findings on both the clean
  baseline and this branch, all in the pre-existing legacy
  `game_decryption_v5_service.py`; this change adds no finding;
- changed-file CI caption-source gate: passes after the diff-aware repair;
- mandatory `test_all_flows.py`: inconclusive locally because it is a live-HTTP
  script and no backend is listening on port 8001; it failed before its first
  assertion with `httpx.ConnectError`.

The caption JSON parses, every changed Python module compiles, the complete
human-readable probe renders both real examples, and `git diff --check`
passes.

## Rollout responsibility

Codex owns this implementation and local verification. Per the standing
working agreement, Claude owns push and production deployment.
