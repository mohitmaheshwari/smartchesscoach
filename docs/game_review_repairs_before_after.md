# Part one: before and after, Games A–D

Commit **`116fbd90`** — six repairs from
[game_review_repair_and_timeline_scope.md](game_review_repair_and_timeline_scope.md)
revision 3, part one. Held at code-review readiness: **not pushed, not
deployed, no data written.**

Outputs below are verbatim from calling the services on production data
(read-only). "Before" is the HEAD version of both files, "after" is the commit.

---

## The six repairs, before and after

### 1.1 Strengths never showed

| | |
|---|---|
| **before** | `good_moves: []` on **all four games**, including a win and a checkmate |
| **after** | A `[{"move_number": 17, "san": "Ke2"}, {"move_number": 13, "san": "Nxc4"}]` · B `[m49 Bh4, m48 Ke5]` · C `[m30 Rxh2#, m29 Rh6+]` · D `[m50 Bg8, m49 Kf4]` |

Cause: the filter read `e["classification"]`, a key no stored row carries. The
field is `evaluation`. Counted on Game B's 50 rows — 0 with `classification`,
50 with `evaluation` (`best` 26, `blunder` 9, `inaccuracy` 6, `good` 4,
`mistake` 4, `excellent` 1).

Game C's strengths are now `Rxh2#` and `Rh6+` — the mating sequence itself,
which the review previously could not mention.

### 1.2 Mate rendered as centipawns

| | before | after |
|---|---|---|
| Game C m20 | `cp_loss_label: "-1385cp"` | `"lost a forced mate"`, `cost_is_mate: true` |
| Game D m51 | `cp_loss_label: "-9108cp"` | `"lost a forced mate"`, `cost_is_mate: true` |
| Game D context | `"Total material leaked: 99.3 pawns worth"` | `"Material given away: about 8.3 pawns worth; One of these threw away a forced mate"` |
| `_cp_to_pieces(9108)` | `"a queen"` | `"a forced mate"` |

### 1.3 Missing data stated as fact

| | |
|---|---|
| **before** | `"Your opponent played clean — no mistakes to punish."` on Games A and D |
| **after** | `"We have no evaluation of your opponent's moves in this game."` |

Worse than the scope recorded. `_extract_facts` derives `opponent_moves` from
`move_evaluations`, which holds **only the user's moves on 948 of 1,000 sampled
games**. So `opponent_moves` is empty, `opponent_blunders` is empty, and the
old first branch fired on essentially every game. It was not an occasional
mis-fire; it was structurally unavoidable. Three states now: errors offered /
none offered / no opponent evaluation at all.

### 1.4 Empty strings as teaching

Game B's `summary_table`, before — 5 rows, two of them blank:

```
{"mistake": "Bg5 (move 50)", "cp_loss_label": "-646cp", "remedy": ""}
{"mistake": "Bd5 (move 21)", "cp_loss_label": "-580cp", "remedy": ""}
```

After — 3 rows, every remedy real:

```
Qh5+ (move 9)   -704cp   "Bf7+ was better — it wins the rook on a8."
f4 (move 30)    -471cp   "Bd5 was better — it attacks the knight on c4. …"
Bxa8 (move 22)  -350cp   "Bf4 was stronger: it brings a new piece into the game."
```

The dropped mistakes still appear as principle cards above, so nothing is
hidden — only the empty row is gone.

### 1.5 Malformed opener

| | |
|---|---|
| **before** | `"You played the this game and you lost as White."` — all four games |
| **after** | A `"In this game you lost as White."` · B `"…you won as White."` · C `"…you won as Black."` · D `"…you lost as Black."` |

**My first attempt produced `"In this game you you lost as White"`** —
`_result_label` already supplies the pronoun — and the test I had written
(`startswith("In this game you")`) passed anyway. Both the code and the test
are fixed; the test now asserts the whole clause and that `" you you "` never
appears.

### 1.6 Title contradicted diagnosis

| | |
|---|---|
| **before** | Game D m51: title `"King in the corner = mate"` over diagnosis `"it runs into Bxg8, taking your bishop"` |
| **after** | the `title` key is absent on cards whose caption shape is unrecognised |

Game B m9 shows the same repair: caption `"Qh5+ lets g6 attack the queen on
h5"` — the verb `lets` is not in the title map, so the card now goes out
headerless rather than wearing a template title written for a different body.

Game A m11 keeps its title, correctly: the caption opens `"b4 runs into…"`,
which *is* in the map, so `"Runs into the reply"` still matches its own text.

---

## Deliberately unchanged

The turning point is still `max(cp_loss)`. Scope §1 says §2.4 replaces it and
part one keeps current behaviour; two guard tests pin that, so Game C still
reports move 20 and Game D still reports move 51. **The disagreement between
the two services on Game D (move 4 vs move 51) therefore persists** — it is a
part-two item, not an oversight.

---

## Test results, actual

```
backend/tests/test_game_coach_review_repairs.py
  34 passed in 0.29s
```

Eight related suites, baseline established by restoring the HEAD versions of
both services into the container and re-running:

```
BEFORE (HEAD code, 8 suites)     96 passed, 28 skipped in 5.04s
AFTER  (this commit, 9 suites)  130 passed, 28 skipped in 2.37s
```

130 = the same 96 plus the 34 new. **No regressions.** Suites:
`test_coach_review_api`, `test_adaptive_decryption_v5`, `test_game_moments`,
`test_game_review_contracts`, `test_coach_selected_review_service`,
`test_caption_mate_branch_truth`, `test_forced_mate_caption_promotion`,
`test_coaching_model`, plus the new file.

The pre-commit caption guard passed: *"no bespoke caption prose outside the
central layer."*

---

## Blockers

**None for this commit.** It is a pure-function change over
`move_evaluations`, writes nothing, and both suites are green against a
measured baseline.

One environment limitation, not a blocker on the code:

- **`test_all_flows.py` cannot run here.** It is an HTTP E2E suite against
  `http://localhost:8001/api` and dies at its first request. Verified it never
  reaches either changed module (`"did it reach game_coach_review? False"`), so
  it is neither a regression nor a meaningful gate without a live API. It
  should still be run wherever the API is up, before deploy.

## Optional improvements, deliberately not done

Kept out to hold the scope fixed. None is required for review.

1. **`_cp_to_pieces` thresholds are unexamined** — 900/500/300/100 map to
   queen/rook/piece/pawn and I did not check them against a distribution. Only
   the mate branch was touched.
2. **`"3.5 pawns of material gone on that move"`** (Game A) is arithmetically
   right for 352cp but reaches the player as a number, which the published-text
   rule discourages. Out of scope here; it is wording, not correctness.
3. **The title map has six verbs** (`runs into`, `allows`, `hangs to`,
   `loses to`, `drops the exchange`, `leaves your`). Repair 1.6 makes an
   unmatched caption headerless, which is safe but means many cards now carry
   no title. Widening the map would restore headers — but it needs the caption
   corpus measured first, not guesses.
4. **`MATE_SENTINEL_CP = 9000` is a judgement**, not a measured threshold. It
   is safe because real material swings do not reach 90 pawns, but it is
   defined in two files and should become one shared constant if anything else
   needs it.
5. **The opponent-evidence state could be filled**, not just named.
   `move_observations.missed_opponent_blunder` / `punished_opponent_blunder`
   hold real data (Game B: 7 missed, 1 punished), but `compute_game_summary`
   does not take `move_observations` and adding a parameter would widen the
   scope. Part two's timeline is where that belongs.

## For the reviewer

The commit is `116fbd90` on `feat/band-aware-lesson-question`, three files:

```
backend/services/game_coach_review.py            +90 −11
backend/services/game_coach_summary.py           +53 −1
backend/tests/test_game_coach_review_repairs.py  +280 (new)
```

Nothing else is staged — the worktree holds unrelated untracked scripts that
were deliberately left out.

---

# Revision after Codex's review of `116fbd90`

Commit **`047a334a`**. All three findings were within repair 1.2. Timeline
untouched, no data written, no deploy.

## P1 — mate transitions now carry direction

`"lost a forced mate"` was printed for every mate row. Both of the reviewer's
counterexamples are now covered:

| Case | Before | After |
|---|---|---|
| `mate_info {before: null, after: -3}`, White to play — he **allowed** a mate, never had one | `lost a forced mate` | **`allowed a forced mate`** |
| `mate_info {before: 3, after: 13}` — he **still has** a forced mate, just slower | `lost a forced mate` | **`still had a forced mate`**, `mate_cost_the_player: false` |

New `services/mate_state.py` derives the transition from `mate_info` plus
`user_color`: gave up / allowed / still had / escaped / delivered / turned
yours into theirs / involved-but-unknown, with `costs_the_player()` so a
consumer cannot render KEPT, ESCAPED or DELIVERED as a loss.

**Why `mate_info` and not the eval sign.** I verified the convention rather
than assuming it. Over 300 production games ending in checkmate, the last row
carrying `mate_info`:

| | before | after | games |
|---|---|---|---|
| white won | +1 | 0 | 89 |
| black won | −1 | 0 | 50 |
| white lost | — | −1 | 72 |
| black lost | — | +1 | 79 |

Consistent every time: **white-relative, signed, 0 = delivered.**

The evaluations are *not* usable for direction. In the same games black winners
show a positive final eval **and** black losers also show a positive final
eval — user-relative and white-relative cannot both hold, so the stored sign is
inconsistent across rows. Game C confirms it from the other side: its raw m20
`eval_before` is **−9970**, while `game_coach_summary` (which sign-flips for
black) reported **+9970** for the same row. So evals are used only as a
magnitude hint for *whether* a mate is involved, never for whose.

Verified on the two real cases, both **black** players — the risky direction:

```
Game C m20  mate_info {before: -3, after: None}  -> gave up a forced mate
Game D m51  mate_info {before: None, after: 16}  -> allowed a forced mate
```

## P1 — no material claim from cp_loss

| | |
|---|---|
| **before** | `"Material given away: about 3.5 pawns worth"` from `cp_loss` alone |
| **after** | `"Evaluation lost across these moves: 352 centipawns"` |

Game D's line, end to end: `"Total material leaked: 99.3 pawns worth"` →
**`"Evaluation lost across these moves: 827 centipawns; One of these involved a
forced mate"`**.

The reviewer is right that this is the existing rule in
`memory/feedback_cp_loss_is_not_material.md`. My wording had also slipped the
pre-commit hook on a technicality — it blocks *"gives up about N pawns"* and I
wrote *"given away … pawns worth"*. `_material_leaked_line` is renamed
`_blunder_cost_line` and reports centipawns, the honest unit.

## P2 — mate detected below the cutoff, and one shared test

The partition was `cp_loss >= 9000`, so a 9970 → 8585 row (cp_loss 1,385, a
mate thrown away) went through as 13.8 pawns — and that is also how the two
repaired consumers came to disagree about the same row. Both now call
`mate_state.is_mate_related`, which checks `mate_info` and both evaluations,
not just the delta. `_extract_facts` stamps `mate_related` onto every user and
opponent row, and the cost line applies the shared test itself.

**A real bug my first attempt at this fix still had:** trusting the stamp alone
left the helper wrong when called directly with raw rows — precisely how the
reviewer reproduced it. My own new test caught it before this commit.

`MATE_SENTINEL_CP` is now defined once, in `mate_state`.

## Tests, actual

```
backend/tests/test_mate_state_and_cost_wording.py   49 new
backend/tests/test_game_coach_review_repairs.py     updated for the rename
  both files:                                       83 passed in 0.75s

ten suites (8 pre-existing + 2 new):  179 passed, 28 skipped in 4.96s
baseline, 8 pre-existing suites:       96 passed, 28 skipped
```

179 = 96 + 83. The baseline figure matches the reviewer's independent run.

The new file covers: both of the reviewer's counterexamples verbatim;
all seven transitions in **both colours**; the 3.5-pawns case; the 1,385
under-cutoff case; a mixed blunder list; and two **public-summary**
regressions rather than helper-only ones, as the review asked.

## Still outstanding before deploy

Unchanged, and not addressed by this commit:

- **Live API and browser smoke.** `test_all_flows.py` needs an API this
  environment does not have, and the 28 skipped tests are live-API tests — they
  are not evidence those routes pass.
- The reviewer's note that the before/after document lives on the branch head
  rather than inside the reviewed code commit still holds; this section is in
  the same document, one commit later.
