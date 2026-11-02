# Why queue: Claude studies the positions the button cannot explain — scope

Status: draft for Mohit's sign-off, 2026-11-02. No code until signed.
Parents: `docs/why_differential_scope.md` (the live engine), `docs/why_positional_families_scope.md` (families 1–5).

## The ask, in Mohit's words

"When we click why and it finds no tactics, it should store in a queue which
should run automatically on Claude, local scheduler on this machine, and then
submit the reason back to that position."

## What the player will see at the end

1. Press **Why was this bad?** on a card. The engine finds nothing. Today the
   box says "No single tactic to point at here. The engine simply prefers d4."
   New: the same sentence plus one line: *"The coach will study this one and
   leave the answer here."*
2. Come back later (minutes to hours, depending on when this machine runs the
   queue). The same button now opens a studied answer, in the same box the
   live engine uses, with a small mark that it was studied later:

   > After b3, Qg6 attacks the g2 pawn and nothing guards it. Your queen on d1
   > cannot move to help. d4 opens the queen's road: after d4, taking on g2
   > loses the queen to Bb5+.

   Plain English, no numbers, names the better move, every clause a board fact
   or a played line. Arrows drawn from the claims (g6→g2, d1→d2, b5 check).
3. If the study found no lesson ("this is just a worse position"), the box
   says so honestly and does not invent one.

Nothing a player sees comes straight from the model. See the gate below.

## What already exists and is reused

| piece | where | state |
|---|---|---|
| the live button and its `found: false` exits | `routes/coach.py get_move_why` (1550, 1615, 1626) | live |
| Claude-reason review panel, agree/disagree per row | `/admin/geometry-gaps` claude tab, `routes/admin_claude_reasons.py` | live, rows seeded offline only |
| offline reason format: reason + probes + board verdict | `data/claude_reason_reviews_2026_10_29.json` (60 rows) | my 10-29 run |
| words-layer guards: containment, ownership, verb direction, relation | `services/why_words.py` | live for luna |
| judge method: play the lines, verify every clause | this session's b6 / f3 / b3 probes | manual |

Not reused: the LLM gateway at `host.docker.internal:8000` (nothing listens on
8000 here now; the scripts that used it are 2026-06 era).

## The pieces to build

**1. The queue (prod Mongo, collection `why_queue`).** Written by `get_move_why`
on every `found: false` exit except `engine_choice` and `no_gap` (the move is
the engine's own choice; there is nothing to study). One row per POSITION,
keyed by `fen_before + played_san`, with the list of (game_id, move_number,
side, user_id) that asked. The b6 position sits in nine games; it is studied
once. Fields: fen, played, stored best, class, the account's rating band, what
the live engine already said (differential summary), status
`queued | running | done | held | no_lesson | failed`, timestamps, attempt count.

**2. The worker (this machine).** `scripts/why_queue_worker.py`, run by Windows
Task Scheduler every 15 minutes while the machine is on. Per run:
- pull up to N queued rows (N = 5 to start) over ssh + `docker exec`, the same
  channel every ops query uses today; no new auth surface in v1
- for each row, build the **fact packet** deterministically with the local
  Stockfish 19 and python-chess: MultiPV 5 at depth 20 before the move, 3 after
  it, the best line after the better move, the exchange ledger, attackers and
  defenders of every piece the best reply hits, legal-move counts of the
  mover's pieces (the boxed queen), the differential's own output
- run `claude -p` (Claude Code headless, the CLI installed here) with a fixed
  prompt and the packet. The model must answer in JSON: `claims[]` (each one
  `kind: board_fact | line`, the squares or moves it rests on), `reason`
  (two to four sentences, simple English, no numbers, names the better move),
  or `no_lesson: true` with one line why
- **the gate**: the worker replays every claim. A board fact is checked with
  python-chess (attacks, defenders, legal moves, check). A line claim is played
  out and the engine confirms the swing it asserts (a queen lost, a pawn won).
  Then the existing words-layer guards: containment, ownership, verb direction.
  All pass → `done`. Any fail → `held`, with the failing claim named.
- write the result back to `why_reasons` (keyed like the queue row) and update
  the queue status

**3. Submit back to the position.** `get_move_why` checks `why_reasons` first.
A `done` row returns `found: true, engine: "studied"`, the reason text, the
claims as facts, arrows from the claims. A `queued`/`running` row returns the
"will study" line. A `held` row returns the live `found: false` answer, never
the held text. A `no_lesson` row returns the honest sentence.

**4. Review surface.** `held` rows appear in the existing claude-reasons tab
with the failing claim shown; `done` rows appear there too for spot checks,
with agree/disagree as today. No new page.

**5. The card.** `WhyThisWasBad` learns three states beyond today's two:
will-study, studied (the same answer box with a small mark), no-lesson.

## The rule this bends, and how it is held

Standing rule: *the LLM writes English, never chess.* Here Claude reasons
about the chess. It is allowed only because the gate, not the model, decides
what ships: a claim that cannot be replayed on the board or by the engine is
never shown. The same method produced the b3 answer in this session (the d5
"threat" I first wrote was refuted by playing the line and withdrawn). Every
`done` row also becomes a gold position for the regression set and a
candidate for a new deterministic family, so the queue feeds the engine
rather than replacing it.

## Measurement before any switch is flipped

1. First 30 queued positions: hand-graded by Mohit in the review tab
   (mechanism / thin / misleading / false / no-lesson) **before** anything is
   shown to a player. The worker runs; `done` rows stay `held_for_first_batch`.
2. Gate statistics: how many claims fail, and why (board fact wrong, line does
   not swing, ownership swapped). A gate that passes everything is not a gate.
3. Then auto-publish, with the review tab as the audit trail.

Thresholds (N per run, interval, depth) are read off the first batch, not
chosen first.

## Limits, stated plainly

- Runs only while this machine is on and the scheduler fires. The queue waits;
  nothing breaks. A server-side runner (Agent SDK) is a later variant.
- One study costs a Claude Code run, roughly one to three minutes and the
  tokens of a long prompt. Today the button is pressed a few times a day
  (4 calls since the 04:18 restart), all by Mohit; dedupe by position keeps
  the count down when that grows.
- The answer is not instant. The card says so.
- Opponent moves are included (the route already carries `opponent`); the
  pronouns come from the same flag.
- From Position and Chess960 games currently show no Why button at all
  (`project_v5_generator_ignores_pgn_fen_tag`); that is a separate fix.

## Out of scope for v1

Notifications when an answer lands; proactive queueing of every faulted card
when a game is opened; rewriting stored captions from studied reasons; Play
with Coach surfaces; running on the server.

## Acceptance

- Press Why on 6.b3 in `7727c92c…`: the box says the coach will study it. The
  next scheduler run produces a `done` row whose every claim passed the gate.
  Reload: the box shows the studied answer with its arrows.
- Press Why on a position where Claude says no lesson: the box says so.
- A `held` row never reaches a card; it is visible in the review tab with the
  failing claim.
- The live engine's answers are untouched: `found: true` from the differential
  or the resolver never consults the queue.

## Decisions needed from Mohit

1. **Review-first or auto-publish from day one?** Recommended: review the first
   30, then auto.
2. **Trigger:** only when someone presses Why and gets nothing (recommended for
   v1), or also pre-study every faulted card when a game is opened?
3. **Both sides:** opponent moves too (recommended yes; the route already
   supports it).
