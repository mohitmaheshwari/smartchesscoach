# Scope — `clearance_immediate` review queue

Date: 2026-09-25. Signed off by Mohit in-session ("go ahead do it").

## The problem in one line

`clearance` fires on 47% of real games, but a third of those fires are about a
move the player never had the chance to make.

## What was measured

400 analysed games, 310 clearance fires on user blunders of ≥100cp.
`_locate_clearance` walks **every** initiator ply of the stored engine line and
records where it found the motif:

| `clearance_ply_in_line` | fires | share | what the claim would be |
|---|---|---|---|
| 0 | 208 | 67.1% | the move the player got wrong **is** the clearance |
| 2 | 102 | 32.9% | the clearance is two plies further down a line they never reached |

Walking every ply is deliberate and correct — the module's docstring says
refusing to look further loses recall no threshold can buy back. That is right
for **puzzle extraction**. It is wrong for a **caption**: at ply 2 the player's
mistake was the first move, so naming the clearance teaches a move they were
never offered.

Caption grade requires ≥95% independently reviewed semantic precision
(`docs/detector_quality_threshold_lock_2026_08_27.md`). 67.1% is not close, so
`clearance` must not be promoted as currently scoped.

## What changes

Nothing about the detector. One optional argument on the review producer.

1. `_new_proof(...)` takes `fact_gate=None`. When given, a fire whose facts fail
   the gate is dropped. It only ever removes fires; it cannot promote one.
2. New queue `clearance_immediate`, gated on
   `clearance_is_immediate is True`.
3. `clearance_general` is unchanged and stays. Its ply-2 fires are correct
   geometry and remain the right material for puzzle extraction.

No frontend work: `/admin/detector-review/detectors` builds its list from
`_producers()`, so the queue appears on the page automatically.

## What it is for

To produce the one evidence type the quality lock accepts — human rulings on
real fires. Nothing here grants any detector product authority;
`tactic:clearance_with_stored_payoff` has no registry row and stays Shadow.

## Verified before commit

Ran the real producers over 400 games:

```
clearance_general   fires: 88   ply spread {0: 59, 2: 29}
clearance_immediate fires: 59   ply spread {0: 59}

1. every immediate fire is ply 0           : True
2. immediate is a strict subset of general : True
3. general still serves ply-2 fires        : True
gate removes 29 of 88 (33.0%)
```

33.0% removed against an independently measured 32.9% ply-2 share.

**Pool size:** 59, not the 208 quoted earlier. The review queue applies a
`verifier.verified` filter that the raw count did not, which is the stricter and
correct basis. 59 still clears the lock's ≥50 reviewed-fires floor on 400 games,
and the scan limit reaches further than that in production.

`tests/test_detector_quality_gate.py` and `tests/test_detector_gold_corpus.py`:
14 passed, 3 skipped.

## Not in scope

Promotion, registry edits, wiring clearance into any player-facing surface, and
the other six unwired provers.

---

## Revision, same day: two further filters

Reading the surviving 59 as chess rather than as fields showed the ply-0 gate
alone was not enough. Two were clean (`Nxf3+` vacating e5 so the queen's f6–a1
diagonal opens and `Qxa1` wins a rook; `Bd7` clearing c8 so `Rxa8` wins a
knight). One was plainly wrong: `Rxf2` — the rook leaves f1 and the **king**
steps onto the empty square. Nothing got out of anything's way for any purpose;
the lesson is "take the free knight on f2".

Measured across all 59:

| what the follow-up does | |
|---|---|
| quiet — achieves nothing visible | **44.1%** |
| capture | 27.1% |
| check | 27.1% |
| capture + check | 1.7% |

and **10.2%** of follow-ups were the king.

`_blocked_only_by_own_piece` already refuses the king as the *clearing* piece,
stating that "the king stepped aside" is not a lesson a 600–1500 player takes.
The identical argument applies to the king stepping *in*; that case was not
refused.

**Change.** `_locate_clearance` now records `follow_up_is_capture`,
`follow_up_gives_check` and `follow_up_promotes`. Recorded, not gated — the
geometry is a clearance either way and puzzle extraction still wants it. The
queue's `fact_gate` then requires: clearance is immediate, the follow-up is not
the king, and the follow-up does something a caption can point at.

**Result on 400 games:** 59 → **33**, and of those 33 the follow-up is a capture
(48.5%), a check (48.5%) or both (3.0%). **Zero quiet follow-ups, zero kings.**
`clearance_general` unchanged at 88.

**Pool size:** `SCAN_LIMIT` is 20,000 against 16,886 analyses, so the queue
scans the whole corpus. 33 per 400 games projects to **~1,393 fires**, far above
the lock's ≥50 floor.

**Tests:** `test_line_motif_proofs.py` + `test_detector_quality_gate.py` — 32
passed. `test_detector_gold_corpus.py` fails 3 (`coordination`, `prophylaxis`,
`full_detector_audit`) — **verified identical on pristine `origin/working-code`
code**, so pre-existing and unrelated.
