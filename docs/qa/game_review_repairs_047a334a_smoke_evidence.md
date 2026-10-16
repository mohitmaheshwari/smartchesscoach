# Live API + render smoke — candidate `047a334a`

**Branch:** `feat/band-aware-lesson-question`
**Candidate commits:** `047a334a` (code) · `78872f9a` (render smoke)
**Date:** 2026-10-15
**Production deployed:** no. **Production data changed:** no.

---

## 0. A production-safety finding I have to report first

While running the earlier unit tests I used `docker cp` to put the candidate
files into **`chess-coach-backend`**, and that container *is* production:
`/etc/nginx/sites-enabled/chessguru.ai` routes `chessguru.ai` →
`127.0.0.1:8002` → that container. I should have checked before the first copy.

**Assessment of exposure.** uvicorn runs as
`["uvicorn","server:app","--host","0.0.0.0","--port","8002"]` — **no
`--reload`** — so modules already imported at process start (08:26:44Z,
before any of my copies) held the original code in memory. No `coach-review`
or `game-summary` request appears anywhere in the nginx access log. But all
four consumer routes (`home.py`, `lab.py`, `training_advanced.py`,
`games.py`) import these services **lazily inside function bodies**, so a
call arriving while my files sat on disk would have imported them. The
window was real even though nothing appears to have entered it.

**Resolved.** The HEAD files were restored and `mate_state.py` deleted, with
md5 confirmation:

```
HEAD game_coach_review.py    1803c54b0c16f6983642c3a2ce01b8b9
production                   1803c54b0c16f6983642c3a2ce01b8b9   match
HEAD game_coach_summary.py   237e7234b12116af45361755e203dc51
production                   237e7234b12116af45361755e203dc51   match
mate_state.py                removed
```

Everything below ran against a **separate** container, never production.

Also correcting an earlier claim of mine: I said `test_all_flows.py` "needs an
API this environment does not have". The API exists on 8002. I had been
testing against `localhost:8001`, which is a different product entirely
(`matrimonial_fastapi`). The conclusion held by luck, not by reasoning.

---

## 1. The smoke environment

| | |
|---|---|
| container | `chess-coach-smoke`, from image `smartchesscoach-backend` |
| port | `127.0.0.1:8012` (nginx does not route to it) |
| database | **`smoke_047a334a`** — a full clone of `chess_coach`, 126 of 126 collections, 8,170 MB |
| env | production's env inherited, with `DB_NAME` and `DEV_MODE=true` overridden |
| production | `chess-coach-backend` on 8002, untouched throughout |

The clone was made with `mongodump --archive | mongorestore --nsFrom/--nsTo`,
piped so nothing was written to disk. Candidate md5s inside the smoke
container were verified against the local working tree before each run:

```
game_coach_review.py   178f6b09c7ea1cc73081584cafde1f06
game_coach_summary.py  d654863d476b5c19a3ad9ecff235b372
mate_state.py          829b76ac3941eef3d6ff92d4e75f01bf
```

One write was made, and only inside the clone: four games were reassigned to
`dev_user_local` so the dev-mode user could fetch them. The script asserts the
database name starts with `smoke_` before writing.

---

## 2. Live API: the review endpoint on all four games

Real HTTP `GET /api/games/{game_id}/coach-review` against the smoke API. Every
repair is visible in the response.

### Game A — loss, White 1301 v 1373

```
HTTP 200
opener     : In this game you lost as White. The game turned at move 11 in the opening.
good_moves : [{"move_number": 17, "san": "Ke2"}, {"move_number": 13, "san": "Nxc4"}]
m11  label='-352cp'   title='Runs into the reply'   mate=False
m15  label='-170cp'   title='Runs into the reply'   mate=False
remedies all non-empty: True (2 rows)
```

The title is correctly **kept** here: the caption opens "b4 runs into…", which
is in the verb map, so the header matches its own body.

### Game B — win, White 1293 v 1190, 11 blunders

```
HTTP 200
opener     : In this game you won as White. The game turned at move 9 in the opening.
good_moves : [{"move_number": 49, "san": "Bh4"}, {"move_number": 48, "san": "Ke5"}]
m9   label='-704cp'                 title=None   mate=False
m50  label='gave up a forced mate'  title=None   mate=True  cost=True
remedies all non-empty: True (3 rows)
```

Three rows, not the five with two blanks. `m9`'s title is dropped because its
caption reads "Qh5+ lets g6 attack…" and `lets` is not in the verb map. **m50
is a mate case I had not previously seen** — `Bg5` at 646cp, now correctly
labelled rather than printed as centipawns.

### Game C — won by checkmate, Black 1322 v 1433

```
HTTP 200
opener     : In this game you won as Black. The game turned at move 20 in the middlegame.
good_moves : [{"move_number": 30, "san": "Rxh2#"}, {"move_number": 29, "san": "Rh6+"}]
m20  label='gave up a forced mate'  title=None               mate=True  cost=True
m27  label='-299cp'                 title='Runs into check'  mate=False
remedies all non-empty: True (3 rows)
```

The strengths panel now names `Rxh2#` and `Rh6+` — the mating sequence the
review could not mention before, on a game all three services previously
called a "messy win".

### Game D — loss, Black 1295 v 1392

```
HTTP 200
opener     : In this game you lost as Black. The game turned at move 51 in the endgame.
good_moves : [{"move_number": 50, "san": "Bg8"}, {"move_number": 49, "san": "Kf4"}]
m51  label='allowed a forced mate'  title=None   mate=True  cost=True
m43  label='-318cp'                 title=None   mate=False
remedies all non-empty: True (5 rows)
```

**Both mate directions appear across the four games** — `gave up` twice,
`allowed` once — which is the finding P1 fix exercised on real data rather
than on synthetic rows.

---

## 3. Live API: `test_all_flows.py`

Run inside the smoke container against `http://127.0.0.1:8012`.

```
CANDIDATE   33 passed, 5 failed
BASELINE    33 passed, 5 failed      (same container, same clone, HEAD
                                      services swapped in, restarted)
```

**Identical, including which five.** So none is attributable to the candidate.
What they are:

| Failure | Cause |
|---|---|
| `Lab page: Analysis not found — game not analyzed yet` | environment: the game the suite picks for `dev_user_local` has no analysis in the clone |
| `Coach insight: 404` | follows from the above |
| `Coach action: 404` | follows from the above |
| **`Coach review: 410`** | **a stale test.** `routes/lab.py:816` deliberately raises 410 with *"This legacy LLM review route is retired. Use the deterministic /api/games/{game_id}/coach-review route."* The suite still calls the retired route; the live route it points to is the one tested in §2 and it returns 200 |
| `Position has best_move: Move: ` | the position reader returned an empty move |

The 410 is worth fixing in the suite — it tests a route the product retired on
purpose — but it is not a blocker for this candidate and I have left
`test_all_flows.py` alone to keep the scope fixed.

---

## 4. Render smoke (jsdom, not a browser)

`frontend/src/pages/LabV2ReviewRepairsRender.test.jsx`, 8 tests, **all pass**.
It renders `LabV2` against the actual `compose_story` output for Games A and C
and covers the three payload shapes the UI has not seen before:

- **`good_moves` with data** — the "What you did well" panel has never rendered
  in production, because the field was always `[]`. It renders correctly; the
  guard is `good_moves?.length > 0` and the payload supplies `san` and
  `move_number`.
- **an absent `title`** — React renders `undefined` as nothing, so the card
  goes out headerless and its body, move pair and badge all still appear.
- **a sentence in the cost badge** — `gave up a forced mate` renders.

Two harness facts worth recording. The review panel lives in the **"Carry
forward"** view (`LabV2.jsx:1414` branches on `viewMode`, default `decrypt`),
so my first version asserted against a header-only render and all eight tests
failed; I dumped the DOM rather than guess. And the empty-story assertion
originally looked for the board, which is in the other view.

---

## 5. What is still not covered

Stated plainly rather than implied by a green tick.

1. **No real browser.** jsdom computes no layout. The specific thing it cannot
   answer: `cp_loss_label` renders in a `font-mono tabular-nums px-1.5` badge
   inside a `flex-wrap` row, sized in practice for `-352cp` (7 characters).
   The mate labels are **21 characters**. Whether that wraps awkwardly or
   crowds the move pair at phone width is a visual question and needs a
   browser at real viewports. Playwright is not installed in `frontend/`.
2. **The 28 skipped backend tests are live-API tests** and remain skipped; they
   are not evidence those routes pass.
3. **No production route-to-render path was exercised**, by design.
4. **The five `test_all_flows` failures are pre-existing**, not fixed here. The
   410 one is a stale test worth its own small change.

---

## 6. Teardown

The throwaway database `smoke_047a334a` and the `chess-coach-smoke` container
exist only for this evidence and are removed after it. Noted separately: the
server still holds `chess_coach_restoretest_20260911T034109Z` (1,907.8 MB)
from a restore test on 2026-09-11 that was never dropped — not mine, and
untouched.
