# CCT tag misalignment — root cause confirmed, implementation plan

**Date:** 2026-10-14 · Investigation read-only. Nothing modified.

---

## 1. Root cause — proven arithmetically

**Two index spaces, joined as if they were one.**

`services/cct_detector.tag_moves_with_cct` numbers plies across the whole game
but emits only user moves:

```python
ply = 0
for node in game.mainline():
    if board.turn == user_color_bool:
        out.append({"ply": ply, ...})     # user moves only
    board.push(move); ply += 1            # counts EVERY halfmove
```

So keys are `{0,2,4,…}` when the user is White and `{1,3,5,…}` when Black.

`analysis_worker.py:1322` joins them by list position:

```python
tagged_by_ply = {t["ply"]: t for t in tagged_user_moves}
for i, me in enumerate(move_evaluations):
    t = tagged_by_ply.get(i)
```

**`move_evaluations` is user-only — measured: 8,585 user rows, 0 opponent
rows.** So `i` counts user moves while the keys count halfmoves, and the tag
fetched at index `i` describes **user move `⌊i/2⌋`**.

### The fingerprint — 28,120 rows, zero exceptions

| colour | index parity | tagged | untagged |
|---|---|---|---|
| white | even `i` | **7,516** | 0 |
| white | odd `i` | 0 | **7,283** |
| black | even `i` | 0 | **6,754** |
| black | odd `i` | **6,567** | 0 |

A perfect parity split in both colours. Black never receives a tag at `i=0`;
White's `i=0` is the only row correct by coincidence (`ply 0` *is* the first
user move) — and of 468 White games with a tag there, **all 468 agree**.

**Disagreement:** White 34.4%, Black 36.0% — equal magnitude, because the
offset grows identically for both; only the tagged parity differs.

### This was found three months ago and scoped as a local workaround

`services/move_observation_deriver.py:424`:

```python
# Real was_capture + was_forcing (SAN is source of truth; the
# analyzer's cct_is_capture / cct_forcing flags are unreliable —
# both were caught mislabeling ~13% of Parth's moves on 2026-07-02).
was_capture = _san_indicates_capture(san)
```

The symptom was measured, a correct workaround was applied **in one function**,
and the join was never fixed. `_classify_register` is in the same file, ~200
lines away, still reading the raw fields. The ~13% matches my `cct_is_check`
figure of 13.3%; `cct_is_capture` is worse at 35.1%.

**SAN is a valid substitute** — it agrees with board truth on **9,304 / 9,304**
moves for both check and capture. So the 2026-07-02 workaround is sound; it was
simply never generalised.

---

## 2. Affected fields and consumers

### Affected — all seven merged tags

`cct_is_check` · `cct_is_capture` · `cct_creates_threat` · `cct_forcing` ·
`cct_had_forcing_options` · `cct_best_was_forcing` ·
`cct_played_forcing_when_best_was_forcing`

### NOT affected — important for scoping

**`compute_cct_aggregate(tagged_user_moves)`** (`analysis_worker.py:1338`)
consumes the tagged list **directly** and never passes through the join.
So game-level `cct_score`, `cct_correct` and `cct_decisions` are **sound**. Do
not touch them, and do not re-run analysis on their account.

### Consumers, by exposure

| consumer | reads | status |
|---|---|---|
| `move_observation_deriver._classify_register` | raw `cct_forcing`, `cct_had_forcing_options`, `cct_best_was_forcing` | **BROKEN** — writes `decision_register` |
| `move_observation_deriver` subtype path (line ~424) | SAN, not the tags | **safe** since 2026-07-02 |
| `services/cognitive_gap_subtypes.py` | SAN, not the tags | **safe** |
| `services/data_freshness.py` | mentions `cct_creates_threat` | **verify** — monitoring vs logic, 1 line to check |
| `scripts/e2e_verify_mohit.py` | `decision_register` | script only, not user-facing |

### Blast radius on shipped coaching: none

`cognitive_gap`, `cp_loss`, `pattern_decay`, the focus picker and
`caption_pipeline` do **not** read `decision_register` or the raw CCT tags.
**No player has been shown a wrong sentence because of this.** The damage is
confined to a dimension that was never wired to a surface — which is why it
survived three months.

---

## 3. Does history need recomputation?

**Yes for `decision_register`, no for anything else.**

| data | rows | verdict |
|---|---|---|
| `move_observations.decision_register` | 224,801 populated | **recompute** — 56.2% of verdicts change |
| other `move_observations` fields | 630,349 | unaffected (SAN/board/clock-derived) |
| `cct_*` on `move_evaluations` | ~11% of rows carry tags | leave; stop reading them |
| `cct_score` / `cct_correct` aggregate | per game | **keep** — never went through the join |

**Recomputation is cheap: no Stockfish required.** The deriver already has
`fen_before` and `move_uci` on every row and already imports `chess`. This is a
re-derive, not a re-analysis.

**One reconciliation to do first (5 minutes, not an audit):** ~11% of
`move_evaluations` rows carry CCT tags in a 300-game sample, yet 35.7% of
`move_observations` have a non-null `decision_register`. Those do not obviously
agree. Count `decision_register` by `schema_version` before the backfill so the
repair scope is known rather than assumed.

---

## 4. The smallest safe fix

**Two changes. The first repairs the data; the second stops producing the
defect.**

### Fix A — make `_classify_register` independent of the join *(the one that matters)*

In `move_observation_deriver`, compute forcing-ness from the row's own position
instead of reading the merged tags — the pattern already used 200 lines above:

```python
# before: trusts the merged tags
user_played_forcing = bool(mv.get("cct_forcing"))
had_forcing_options = bool(mv.get("cct_had_forcing_options"))

# after: from this row's own board, as the subtype path already does
board = chess.Board(fen_before)
move  = chess.Move.from_uci(move_uci)
user_played_forcing = board.gives_check(move) or board.is_capture(move)
had_forcing_options = any(board.is_capture(m) or board.gives_check(m)
                          for m in board.legal_moves)
```

**Why this first:** it removes the join from the dependency chain entirely, so
the field becomes correct by construction and history can be repaired by
re-deriving — no engine, no re-analysis.

**`cct_best_was_forcing` cannot be rebuilt this way** — it needs the engine's
best move. Either read `best_move_uci` from the same row and recompute
forcing-ness from the board (preferred — the row has it), or leave
`decision_register` as `None` until Fix B lands. **Do not keep reading the
merged value.**

### Fix B — repair the join at source

```python
# analysis_worker.py:1322
tagged_by_ply = {t["ply"]: t for t in tagged_user_moves}
for i, me in enumerate(move_evaluations):
    t = tagged_by_ply.get(i)
```

becomes a positional zip, because both lists are user-only and in game order:

```python
for t, me in zip(tagged_user_moves, move_evaluations):
```

or, safer against future shape changes, match on the move itself
(`me["move_uci"] == t["uci"]`) and log a warning on mismatch rather than
silently mis-tagging.

**Fix B alone is not sufficient** — it only corrects games analysed after it
ships. Existing rows stay wrong until re-analysed, which costs Stockfish time.
Fix A makes the repair free.

---

## 5. Regression tests

Each must **fail before the fix**. A test that passes either way is decoration.

| # | test | asserts | fails today? |
|---|---|---|---|
| 1 | `test_black_game_tags_land_on_the_right_move` | for a Black game, the tag at user move *n* describes user move *n* | **yes** — today no Black row is correct |
| 2 | `test_white_game_past_the_first_move` | same for White at user move 3+ | **yes** — only `i=0` is correct |
| 3 | `test_tags_are_not_confined_to_one_index_parity` | both parities carry tags | **yes** — the exact fingerprint above |
| 4 | `test_register_matches_board_truth` | over ≥500 rows, recomputed check/capture equals stored, ≤0.5% disagreement | **yes** — 35.1% today |
| 5 | `test_forcing_is_computed_from_the_board_not_the_tags` | source contract: `_classify_register` does not read `cct_*` | **yes** |
| 6 | `test_cct_aggregate_is_unchanged` | `cct_score`/`cct_correct` identical before and after | **no — must pass both sides.** Guards against "fixing" the aggregate, which was never broken |

Test 6 is the one I would most want: the aggregate is correct today and a
careless fix could change it.

---

## 6. Historical repair strategy

**Step 1 — scope.** Count `decision_register` and CCT-tag presence grouped by
`schema_version`. Resolves the 11% vs 35.7% question and gives the true row
count.

**Step 2 — snapshot.** Fingerprint `decision_register` value counts and a fixed
sample of row ids before touching anything, so the diff is per-row and not just
a total. *(The corpus-snapshot discipline: tests passed once while rows silently
lost their payload.)*

**Step 3 — bump `SCHEMA_VERSION` to 21.** Mandatory, not cosmetic. The backfill
skips rows already at the current version; the v20 comment records that without
a bump the corrected rule would have reached only **12,333 of 16,723** rows.

**Step 4 — dry-run the backfill** over a pinned 500-game sample. Expect
`decision_register` to change on ~50% of registered moves and the field-level
disagreement to fall to ~0%.

**Step 5 — apply**, then re-run the reconciliation probe as the acceptance
gate: `is_check`, `is_capture` and `had_forcing_options` disagreement must each
be **≤0.5%**, and the parity fingerprint must be gone.

**Step 6 — then** Fix B, so new analyses stop writing misaligned tags. Order
matters: A+backfill makes the data correct now; B prevents recurrence.

**Rollback:** `decision_register` has no user-facing consumer, so a bad
backfill cannot reach a player. Reverting is re-running the previous deriver
version.

---

## 7. What this does and does not unblock

**Unblocks:** a trustworthy `decision_register` across ~225k moves — "you had a
forcing option and played quiet" becomes sayable, which is the one process
measure the product has at scale.

**Does not unblock:** `cct_best_was_forcing` remains engine-dependent, so
"the best move was forcing" needs its own verification pass even after this.

**Independent of all of it:** the clock fields. 501,863 timed moves from PGN
`%clk`, never routed through this join. **If the homepage needs a decision
signal before this work lands, it is the clock — and that is unaffected either
way.**

---

## 8. Sequence

1. Scope by `schema_version` *(minutes)*
2. Write tests 1–6; confirm 1–5 fail and 6 passes *(short)*
3. Fix A in `move_observation_deriver` *(small, contained)*
4. Snapshot → bump to 21 → dry-run on a pinned sample → apply *(the bulk)*
5. Acceptance gate: reconciliation ≤0.5%, fingerprint gone
6. Fix B in `analysis_worker` + the mismatch warning *(small)*
7. Check `data_freshness.py`'s use of `cct_creates_threat` *(1 line)*

Steps 1–3 are where the judgement is. Step 4 is mechanical but needs the
snapshot. I would not merge 3 without 2 proven to fail first.
