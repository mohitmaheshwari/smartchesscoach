# Instant review for Lichess games — Scope

Status: **BUILDING under standing signoff** (Mohit, 2026-11-25: "go ahead, build it").
Audit base: `working-code` @ d604dc22, plus prod reads on 2026-11-24/25.

---

## 0. Existing surfaces audit

| Area | What exists today | Evidence |
|---|---|---|
| Finding new Lichess games | `quick_sync_loop()` polls every **5 minutes**, for up to **100** users | `server.py:271`, `config.py:107`, prod logs: 82 cycles in 6h, 1–2 games each |
| Fetching them | `fetch_recent_lichess_games(username, since)` → `/api/games/user/{u}` | `journey_service.py:226,269` |
| Storing + queueing | `sync_user_games()` writes `games` and inserts into `analysis_queue` | `journey_service.py:1397,1558` |
| Analysing | queue wait median **0.0 min**, work median **1.4 min**; queue holds 1 pending | prod `analysis_queue`, 2026-11-25 |
| Review surface | `/game/:gameId` → LabV2 → GameDecryptionV5 | existing route |
| Notifications | full system incl. push-device registration | `routes/notifications.py:8-15` |
| Lichess OAuth | PKCE flow built; scopes are `preference:read email:read` | `routes/oauth.py:5,46` |
| Playing on Lichess | nothing | grep: no `api/board` anywhere |

**Measured latency today** (lichess, prod, raw rows 2026-11-24): play → imported on the
fast path **5.1 / 8.2 / 9.1 / 12.4 / 22.3 min**; then ~1.4 min to analyse. So a player
waits roughly **7–25 minutes** to see their review.

**Overlap.** Almost everything is built. The only missing piece is *knowing sooner*.

**Rejected designs.**
- *Play on Lichess through ChessGuru* (`board:play`): legal, but any coaching surface
  during a live game is cheating, and Lichess auto-marks **our users** as engine cheaters
  by referer domain, on a randomised delay that defeats testing. See
  `memory/project_lichess_board_api_forbids_in_game_coaching.md`. Out.
- *OAuth `challenge:read` + `/api/stream/event`*: sub-second push, but needs every
  existing user to re-authorise. With 0 new users in 30 days and 73 of 82 one-and-done,
  nobody is coming back to click "reconnect". Out of V1, kept as V2 for fresh sign-ups.

**Decision: EXTEND.** Keep every existing path. Add one watcher that fires the existing
sync the moment a game ends, instead of waiting up to five minutes for the next poll.

---

## 1. What it is

When you finish a game on Lichess — on lichess.org, in their app, anywhere — ChessGuru
notices within about ten seconds, pulls the game, and analyses it. By the time you have
stopped being annoyed about losing, your review is already waiting. You do nothing
differently: you keep playing where you always play, and you never connect anything new.

## 2. What the user sees

Nothing during the game. That is deliberate — see the rejected designs above.

In V1 nothing announces itself either (see out of scope). The change is that the
review is **already waiting** when they next open ChessGuru, instead of sitting
7-25 minutes behind them. The surface this unlocks, once a delivery channel
exists, is:

```
┌────────────────────────────────────────────┐
│  Your game is ready                        │
│  You lost to Arjun_90 · 25 min rapid       │
│                                            │
│  The game turned on move 23.               │
│  [ See what happened ]                     │
└────────────────────────────────────────────┘
```

Tapping it opens the existing review at `/game/:gameId`. No new review surface is built.

## 3. In scope (V1)

- A watcher loop that polls `GET /api/users/status?ids=…&withGameIds=true` (no auth, 100
  ids per call, Lichess sanctions once per 5s) for every user with a `lichess_username`.
- On a watched user's `playingId` disappearing (game over), immediately call the existing
  `sync_user_games()` for that user. **No new import, storage or queue code.**
- Raise the `quick_sync_loop` user cap from 100 to cover all connected users (136 today).
- A `User-Agent` naming the site, per Lichess's requirement. No user identity in it.
- Env flag to turn the watcher off without a deploy.

## 4. Explicitly out of scope (V1)

- Playing on Lichess (`board:play`) — rejected above, permanently.
- Any coaching surface during a live game — forbidden; must never be built for Lichess.
- OAuth scope upgrade and `/api/stream/event` — V2, for new sign-ups only.
- `GET /api/stream/games/by-oauth-origin` (the Chessbook-style firehose) — needs Lichess
  to add our origin to a hardcoded allowlist. Worth asking; not a V1 dependency.
- Email delivery. Requires a new topic in `moments_topic_registry` under the mandatory
  Email → Page Contract. Separate scope.
- Chess.com. Its API has no equivalent live-status endpoint; unchanged at 5-minute polling.
- Web push notifications (device registration exists, no sender is wired).
- **Any notification at all.** Cut during the build: firing on *analysis complete*
  means editing `analysis_worker.py`, the one file the stale PR #1 touches, and
  open question 1 below is whether an in-app row reaches anyone. V1 therefore
  shortens the wait; it does not announce the result.

## 5. Success criteria

- Median play → analysed for Lichess games drops from the measured **7–25 min** to
  **under 4 minutes**, measured the same way as the 2026-11-25 baseline in this doc.
- Zero duplicate `games` rows: `platform_game_id` + `user_id` stays unique (2,094 of
  2,094 today).
- No increase in Lichess 429s; the watcher makes at most 12 calls/minute total.
- Behavioural, and the one that actually matters: of users who get a notification within
  4 minutes, the share who open the review **the same day**. No target set yet — there is
  no baseline, so V1 establishes it.

## 6. Open questions

- **Does a notification reach anyone who isn't on the site?** Unresolved. In-app rows are
  invisible to someone who never visits, and that is most users. Unblocking step: ship V1,
  then measure same-day open rate; if it is ~0, the next build is the delivery channel
  (email under the contract), not more detection.
- **Do private Lichess accounts break the no-auth path?** `users/status` and game export
  are public-only. Unverified. Unblocking step: count connected users whose games 404.
- **Is 10s polling the right interval?** Lichess sanctions 5s. Starting at 10s as the
  cheaper default; revisit if detection lag is still visible.

## 7. Pre-code requirements

- [x] Latency baseline measured and written down (section 0) — so the win is provable.
- [x] Open PR check: PR #1 is stale (base `main`, last touched 2026-03-29) and touches
      `analysis_worker.py`; this build does not edit that file.
- [x] Fair-play position verified from Lichess source and policy, and recorded in memory.
- [x] Confirmed no duplicate-import bug exists (hypothesis tested and rejected).
- [x] Standing signoff for small features within an agreed direction.
