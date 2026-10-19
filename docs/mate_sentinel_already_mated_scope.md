# You cannot walk into a mate you are already in

**Status:** scope, 2026-10-19
**Defect:** `backend/services/severity.py:127`

## What is wrong

`classify_severity` carries an escape hatch:

```python
walked_into_mate = (user_post_eval_cp is not None
                    and user_post_eval_cp <= -MATE_SENTINEL_CP)
if walked_into_mate:
    tier = "blunder"
```

It reads only the position *after* the move. A player who is already being
mated has a post-move eval below the sentinel on **every** legal move, so
every move they make is forced to `blunder` no matter how small the
centipawn loss. "Walked into" names a transition, and the code never checks
that one happened.

The hatch was added for a real case (`fb_a9ac9f02affa`): stored `cp_loss`
is small while the eval is a mate, because the player genuinely stepped
into a mating net. That case is correct and stays. Only the already-mated
case is wrong.

## Measured, on production data

Sample of 1,200 analysed games, user moves whose card says `blunder` and
whose post-move eval is a mate score:

| | moves | |
|---|---|---|
| genuinely walked into mate | 405 | correct, keep |
| **already being mated before the move** | **568** | **false** |

That is **0.47 false blunders per game**, roughly 9,200 across the 19,424
stored analyses. On 392 of the 568, the pipeline's own
`severity_practical` already says `good`; the practical classifier knows,
and the displayed severity ignores it.

It is not an endgame problem: 282 of the 568 are at eight or more pieces,
115 at six or seven, 171 at five or fewer.

### Independent adjudication

At five pieces or fewer the Syzygy tables settle the result outright. Over
2,500 games, every criticism card in that range was judged against them:
**0 of 33 earned criticisms** would be lost by treating result-preserving
moves as uncriticised, while 380 of 385 unwarranted ones disappear. The
tables are the permitted adjudicator under the detector quality lock, so
this is proof rather than a precision estimate — for the 171 cards in
range. The remaining 397 share the same mechanism and the same fix.

## The fix

`walked_into_mate` requires a transition: not mated before, mated after.
`user_pre_eval_cp` is optional and, when absent, behaviour is exactly as
today — so every existing caller and the test guarding `fb_a9ac9f02affa`
keep passing unchanged.

Three files: the rule in `severity.py`, the pass-through in
`caption_pipeline._compute_severity_for_move`, and the caller in
`game_decryption_v5_service`, which already holds `eval_before` beside the
`eval_after` it passes today.

## Explicitly not in scope

- **Tablebase in production.** The server has no tables and no probe
  binary, and the box is already killing workers for memory. The tables
  adjudicate offline; they do not need to ship.
- **An eval gate at five pieces or fewer.** Superseded. It would have
  reached 171 of 568 cards and needed a threshold chosen by hand; this
  reaches all of them and reuses the sentinel already defined.
- **Criticism of a losing player generally.** 24.3% of all criticism cards
  fire when the mover is behind before and after. At eight or more pieces
  a 300-centipawn deficit is not a lost game for a 600-1500 player, so
  that criticism is legitimate coaching and silencing it would remove
  teaching. Only the mate case is provably false.
- **Silencing anything.** Coverage is first-class. A corrected card keeps
  its caption; it stops being labelled a major blunder.

## How it will be verified

1. Unit tests, each a positive and a negative control: the
   `fb_a9ac9f02affa` case still classifies `blunder`; an already-mated
   player's small-loss move no longer does; a `None` pre-eval is unchanged.
2. Re-render a corpus sample through the real path and diff severities per
   card, confirming the only movement is out of `blunder` on already-mated
   moves.
3. Re-run the tablebase adjudication over the re-rendered cards at five
   pieces or fewer: earned criticisms must still be criticised.
4. Version bump so stored cards re-render, and confirm the regen
   supervisor is actually running — a bump reaches nobody while it is dead.
