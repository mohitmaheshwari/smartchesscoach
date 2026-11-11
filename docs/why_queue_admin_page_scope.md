# Why queue admin page — scope

Mohit, 2026-11-11: "I want a page on admin to show up positions that have been
set up for queue; if Claude has processed them then Claude's caption there, if
not processed then To Be processed or something, gameId and the position with
board." Signed by that request under his standing sign-off for small features.

## 0. Existing surfaces audit

- `/admin/geometry-gaps`, Claude tab (`routes/admin_claude_reasons.py`): serves
  ONE study at a time for Agree/Disagree, and only studies that are waiting
  (`held_for_review`, `held`). It never shows a queued, running, published,
  rejected or no-lesson position, and shows no list, no game ids, no request
  history.
- `/admin/llm-cost`: shows the queue's spend, not its positions.
- Nothing lists `why_queue`.

Decision: **PARALLEL**, a read-only list page. Ruling stays in the
geometry-gaps tab; the list links there. No overlap in what each page does.

## 1. What it is

One page listing every position the Why button sent to the coach to study,
newest first: the board, the move, the games it came from, and either the
coach's explanation or a plain "To be processed".

## 2. What the user sees

```
Why queue — 5 positions                                   [Refresh]
Studied by Claude on Mohit's PC every 15 minutes. Rule them on Geometry gaps → Claude.

┌──────────────┐  6.e5 (opponent's move)          Waiting for your review
│   board      │  Engine prefers c3 · graded mistake
│ red e4→e5    │  Asked 2× · last 11 Nov 13:31
│ green c2→c3  │  Games: 2d86e1f9 move 6  (link)
└──────────────┘  Claude: "After e5, you can answer d5. Your pawn on d5 attacks
                  their bishop on c4. ..."   gate passed · $0.12 · claude-opus-5-5

┌──────────────┐  18...Rf7 (player's move)        To be processed
│   board      │  Engine prefers Kg7
└──────────────┘  Games: game_48c2… move 18
```

## 3. In scope (V1)

- `GET /api/admin/why-queue/positions` (owner admin only): every queue row
  joined with its study; played and better move as from/to squares.
- Page `/admin/why-queue`: one row per position with a view-only board
  (played move red arrow, better move green), status in plain words, game ids
  linking to `/game/:id`, ask count and last asked time, Claude's text when a
  study exists, gate result, cost, model.
- Status words: To be processed (queued) · Being processed (running) ·
  Waiting for your review · Failed the check · Published · Rejected ·
  No single lesson · Processed, no study saved · Failed.

## 4. Explicitly out of scope (V1)

- Ruling (Agree/Disagree) on this page: stays in the geometry-gaps tab.
- Re-queueing, deleting or editing a study.
- Paging/filters: 5 rows today; capped at 500 on the server.
- The 59 Oct-30 `claude_reason_reviews` rows: they are not the queue.

## 5. Success criteria

- Mohit can answer "is my click in the queue, and what did Claude say" from
  this page alone, without asking me to query the database.

## 6. Open questions

None blocking.

## 7. Pre-code requirements

- Request + standing sign-off: yes (2026-11-11).
