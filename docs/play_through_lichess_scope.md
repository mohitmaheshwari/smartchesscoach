# Play on Lichess, through ChessGuru — Scope

Status: **DRAFT — awaiting Mohit sign-off. No code until signed off.**
Written: 2026-11-25. Audit base: `working-code` @ 502a6856 (live), plus prod reads
and Lichess source reads the same day.

Mohit, 2026-11-25: "chessriro is doing it, why can't we, we should too." Verified:
they are, and we can. This document says what we would build and what it costs.

---

## 0. Existing surfaces audit

| Area | What exists today | Evidence |
|---|---|---|
| Playing on the site | Only against our engine (Play with Coach). A finished coach game is written to `games` with `platform: "coach"`. | `backend/routes/coach_play.py:8539` |
| Playing a real person | Nothing. No seek, challenge, lobby or matchmaking code. | grep over `backend/`, `frontend/src` |
| Lichess play API | Nothing. The only mention of `board:play` in the repo is a comment explaining why we had not built it. | `backend/services/lichess_live_watch.py:34` |
| Lichess OAuth | PKCE flow built and working, but requests `preference:read email:read` only. | `backend/routes/oauth.py:46` |
| A board we could reuse | `react-chessboard@4.6.0` + `chess.js@1.4.0`, already driving `CoachPlayBoard.jsx`. | `frontend/package.json:44,58` |
| Streaming / long-lived connections | **None.** No websocket endpoint, no line-stream consumer anywhere in the backend. | grep for `websocket`, `aiter_lines`, `httpx` streaming over `backend/` |
| Backend process model | One uvicorn process, no `--workers`. In-memory per-user state is possible at this scale, and every deploy destroys it. | `docker/supervisord.conf:15`, `Dockerfile.backend:56` |
| Knowing a Lichess game ended | Shipped today: a 10-second watcher on `users/status` fires the existing sync. Verified live on 5 real game endings. | `services/lichess_live_watch.py`, live at 502a6856 |
| Review of a finished game | Complete. `/game/:gameId` → LabV2 → GameDecryptionV5. | existing route |
| Connected Lichess accounts | **23**, measured live inside the prod container on 2026-11-25. | `lichess_usernames(db)` probe |

### What Lichess actually permits

All verbatim, from Lichess's own sources, read 2026-11-25:

- Board tag, [lichess-api.yaml](https://raw.githubusercontent.com/lichess-org/api/master/doc/specs/lichess-api.yaml):
  *"Play on Lichess with physical boards and third-party clients. Works with normal
  Lichess accounts. Engine play or assistance is forbidden."*
- Board restrictions, same file: *"Engine assistance, or any kind of outside help, is
  forbidden"* and *"Time controls: Rapid, Classical and Correspondence only. For direct
  challenges, games vs AI, and bulk pairing, Blitz is also possible."*

So a third-party client is a **supported** use, not a tolerated one. The enforcement is
a runtime setting, `boardApiBadRefererRegex`, described in code as *"Board API: referer
domains that use engine, as a regex"*, default `"-"` (matches nothing); its production
value is not public
([BoardReport.scala](https://raw.githubusercontent.com/lichess-org/lila/master/modules/bot/src/main/BoardReport.scala)).
A match publishes `BoardApiMark`, which `modules/mod/.../Env.scala` subscribes to with
`api.autoEngine(...)` → `userRepo.setEngine` — a **full engine mark on our user**, plus a
mod note reading `"Board API: <our domain>"`, auto-processed cheat reports and rating
refunds to their opponents
([Env.scala](https://raw.githubusercontent.com/lichess-org/lila/master/modules/mod/src/main/Env.scala),
[ModApi.scala](https://raw.githubusercontent.com/lichess-org/lila/master/modules/mod/src/main/ModApi.scala)).
It is checked once per game at ply `5 + (createdAt.toSeconds % 20)`, then fires after a
randomised delay that is **longest for the weakest players** (base 24 minutes under 1800,
0 above 2500). It is built to be invisible to A/B testing.

**Read that twice: the penalty does not land on us. It lands on the player.** An account
they have had for years, marked as a cheat, because of a panel we drew.

### What Chessiro actually ships

From their own blog, [introducing-play](https://chessiro.com/blog/introducing-play):
*"Play is powered by Lichess. Sign in to Chessiro, connect your Lichess account, choose
Play Online, and Chessiro will use Lichess to find your opponent while you play on
Chessiro's board."* Time controls *"start at 10+0"* and go up to 60+0 — exactly the
Rapid-and-slower restriction. Their framing is *"Play First, Review After."* They show
**no coaching during the game.** Their separate bot mode is their own Maia, not Lichess.

### Overlap and differentiation

**Overlap.** The board, the game record, the analysis queue, the review page, the Lichess
OAuth flow and the priority logic that puts a just-finished game at the front of the queue
all exist and are reused unchanged.

**Genuine differentiation — and it is not the playing.** Lichess already runs the game
better than we will. What we add is that the game *ends inside the coaching product*. The
player does not have to remember to come back; they are already here, and the review opens
on the last move. That is the one thing our funnel has never had.

**What this obsoletes.** [docs/play_on_site_scope.md](play_on_site_scope.md) (draft
2026-11-02, never signed) proposed player-vs-player on our own server. Its own stated
risk was *"plain play here would be a worse Lichess"*, and its unanswerable problem was an
empty lobby — 8 people other than Mohit opened a page in 30 days. Playing through Lichess
is the version of that idea that has opponents. **If this document is signed, the 11-02
draft should be closed as superseded, not built.**

**Decision: EXTEND.** One new live surface, every existing surface after the last move
reused as-is.

---

## 1. What it is

You start a game on ChessGuru. We find you a real opponent on Lichess — a real person, a
real rated game on your real Lichess account — and you play it on our board. While the
game is running we tell you nothing about the position, because Lichess forbids it and
because a player who gets help is not playing. The moment the game ends, your review is
already open on the move where it turned. You never leave the site, and you never have to
remember to come back.

---

## 2. What the user sees

**Starting a game** (`/play/online`)

```
┌──────────────────────────────────────────────┐
│  Play a real opponent                        │
│                                              │
│  [ 10 | 0 ]    [ 10 | 5 ]    [ 15 | 10 ]     │
│                                              │
│  Rated on Lichess. Your Lichess rating       │
│  counts, win or lose.                        │
│                                              │
│  Playing as bhutramohit  ·  1834 rapid       │
└──────────────────────────────────────────────┘
```

**While the game is live** — bare board, plus a visibly sealed review panel:

```
┌──────────────────────────────────────────────┐
│  Arjun_90          1823            9:41      │
│                                              │
│            [    the board    ]               │
│                                              │
│  You               1780           10:02      │
│  [ Offer draw ]  [ Resign ]      ● connected │
├──────────────────────────────────────────────┤
│  🔒  Your review opens when this game ends.  │
│                                              │
│  No help while you play — that is the rule   │
│  on Lichess, and it is the only way the       │
│  game tells us anything true about you.       │
└──────────────────────────────────────────────┘
```

Nothing engine-derived is sent to the browser while the game is playable. Not hidden,
not greyed out, not in a collapsed panel — **not sent**.

**The moment the last move is played**, the panel unseals in place:

```
├──────────────────────────────────────────────┤
│  You lost. The game turned on move 23.       │
│                                              │
│  Your knight on f5 had nowhere to go after   │
│  g4, and you had seen that square before.    │
│                                              │
│  [ See what happened ]   [ Play again ]      │
└──────────────────────────────────────────────┘
```

The headline waits for real analysis rather than guessing — if Stockfish has not finished
yet it reads "Reading your game…" and fills in, typically inside two minutes (measured
work time 1.4 min median, 78s observed 2026-11-25).

---

## 3. In scope (V1)

- **`/play/online`**: pick one of 10+0, 10+5, 15+10; create a Lichess seek; wait for a
  pairing. Rapid only — the safest reading of the Board API restriction, and the same set
  Chessiro offers.
- **A live board** on our site driving a real Lichess game: our moves posted to Lichess,
  their moves and clocks streamed back, clock display, draw offer, resign, opponent info,
  and an honest connection indicator.
- **OAuth scope upgrade to include `board:play`**, with a one-time "reconnect your Lichess
  account" prompt for the 23 already-connected users. Existing scopes keep working for
  import; a user who declines keeps everything they have today and simply cannot play here.
- **A sealed review panel** that receives no position data until Lichess reports the game
  is over, then opens in place on the finished game.
- **A hard structural guarantee that no engine output can reach a live game.** Not a
  feature flag — a flag that flips the wrong way marks real accounts as cheats. The
  guarantee is enforced on the server, in the one place that serves coaching data, keyed on
  the game's own state: `playable == true` means the endpoint returns nothing. With a test
  that fails if any coaching route can return a body for a playable game.
- **A `User-Agent` and referer that identify us honestly**, so that if we ever do break the
  rule Lichess can find us — and so we never look like a client trying to hide.

## 4. Explicitly out of scope (V1)

- **Any in-game coaching, hint, evaluation, arrow, best move, opening name, or "you are
  worse in this line".** Permanently out for live Lichess games, not deferred. The
  spec's words are *"any kind of outside help"*, and we do not get to decide how broadly
  Lichess reads that.
- Blitz and Bullet. The spec allows Blitz for direct challenges only, not pool seeks;
  adding it means two different rules in one UI for a marginal gain. Revisit after V1.
- Friend challenges and a shareable game link. Wanted, but each is a separate Lichess
  endpoint and its own state machine.
- Playing our Maia bots through Lichess. We host Maia ourselves already; routing it
  through Lichess buys nothing and lands in bot-account territory.
- Tournaments, arenas, correspondence games, takebacks, berserk.
- Rematch as a Lichess rematch. "Play again" in V1 starts a fresh seek.
- Chat with the opponent. Moderation we cannot staff.
- Mobile layout beyond "it works at phone width".
- Replacing Play with Coach. It stays exactly as it is; that is where coaching during a
  game is legal, because we are the opponent.

## 5. Success criteria

The point is never the playing. So the criteria measure what happens *after* the last move.

- **Primary, behavioural:** of games played through our board, the share where the player
  opens the review **in the same session**, versus the baseline for games played on
  lichess.org and picked up by the watcher. The watcher shipped today establishes that
  baseline; no target is set because no baseline exists yet. If play-through does not beat
  it, this feature has no reason to exist and should be removed, not iterated.
- **Zero engine marks.** Any ChessGuru user receiving a Lichess engine mark during this
  build is a stop-everything event: pull the surface the same day, then diagnose.
- A game started on `/play/online` reaches a real opponent within 60s at 10+0, or tells the
  player plainly that nobody is available.
- No game is ever lost to our infrastructure: a deploy, a restart or a dropped stream
  mid-game must leave the player able to finish on lichess.org with their clock intact.
- Review open to within 2 minutes of the last move (today: 1.4 min median analysis work).

## 6. Open questions

- **Does a sealed panel reading "no help while you play" itself count as outside help?**
  I believe plainly not — it contains no information about the position. Not verified with
  Lichess. **Unblocking step:** ask `contact@lichess.org` before shipping, and quote the
  exact panel text in the email. Their answer is also the moment to ask whether showing
  the opening *name* is acceptable, since that is the first thing we will want.
- **What happens to a live game when we deploy?** One uvicorn process, no `--workers`
  (`docker/supervisord.conf:15`), and every deploy restarts it — so any in-memory stream
  state dies mid-game. **Unblocking step:** decide before coding whether the stream is
  resumable from Lichess's own state on restart (it should be: their event stream replays
  current games), and prove it by deploying during a test game.
- **Will the 23 existing users reconnect?** Honestly, probably not: 73 of 82 were
  one-and-done. **Unblocking step:** none that precedes the build. Accept that V1's real
  audience is Mohit plus new sign-ups, and do not size the build on 23 users converting.
- **Is 10+0 Rapid?** The spec names the categories but does not map clock times to them,
  and the FAQ page refuses automated fetches. Chessiro ships 10+0, which is evidence but
  not authority. **Unblocking step:** confirm from `lichess.org/faq#time-controls` by hand
  before the time-control list is final.
- **Does our own `/play-with-coach` coaching leak into a Lichess game by sharing a route?**
  Must be answered by reading the coaching routes, not assumed. **Unblocking step:** part
  of pre-code requirements below.

## 7. Pre-code requirements

- [ ] **Mohit signs off on this document.** Nothing else in this list matters first.
- [ ] Email to `contact@lichess.org` sent, quoting the in-game panel text verbatim, asking
      (a) whether a sealed panel is acceptable, (b) whether the opening name is, and
      (c) to be added to `GameStreamByOauthOrigin.allowedClients`. A reply is **not** a
      blocker for a bare board; it is a blocker for anything beyond it.
- [ ] Every backend route that can return coaching, caption, evaluation or arrow data is
      enumerated, and the single chokepoint that will carry the `playable` guard is
      identified by `file:line`. If there is no single chokepoint, building one is the
      first task, not the last.
- [ ] The failing test is written **before** the feature: a test that asserts no coaching
      route returns a body for a game Lichess reports as playable. It must fail on today's
      code for the right reason.
- [ ] 10+0's category confirmed by hand from the Lichess FAQ.
- [ ] A Lichess OAuth app registered with `board:play`, and the consent screen read and
      screenshotted — the user sees what we ask for, and we should know what that says.
- [ ] Decision recorded on whether `docs/play_on_site_scope.md` is closed as superseded.

---

## Appendix: what I got wrong, recorded on purpose

Earlier on 2026-11-25 I told Mohit that playing through Lichess was effectively closed to
us because Lichess "auto-marks our users as engine cheaters by referer domain". That was
wrong in the part that mattered. The spec explicitly supports third-party clients; the
referer regex targets *domains that provide engine help*, not third-party domains as such;
and Chessiro ships the feature in the open. The correct constraint is narrower and
sharper: **no engine-derived help may reach a live Lichess game**, on pain of a mark
against the player, not against us. The memory note
`project_lichess_board_api_forbids_in_game_coaching.md` overstated this and must be
corrected to say exactly that.
