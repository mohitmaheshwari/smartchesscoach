# Player Understanding — Scope

**One line:** stop describing a player by which themes they miss, and start
describing how they actually play — what kind of mistake, how deep, in which
phase, when ahead or behind — then teach against that and check it improved.

Written 2026-09-22. Nothing here is built yet. Awaiting Mohit's signoff.

---

## 0. Existing surfaces audit

Done first, and it changed the shape of this scope twice.

### What already exists for this need

- **`chess_understanding.py`** — six dimensions per player (tactical vision,
  positional sense, opening knowledge, endgame technique, calculation, pattern
  recognition). Reaches the live game review page through
  `/lab/{game_id}/deep-strategy`, fetched by `LabV2.jsx` line 526.
  **Measured 2026-09-22: only 17 of 128 users have a profile**, one last
  updated in April, one built from a single game, one claiming 1,249 games.
  It is built lazily and cached with no expiry — `if cached: return cached` —
  so it never recomputes.

- **`move_observations`** — **526,642 rows**. Already carries `phase`,
  `eval_before`, `eval_after`, `cp_loss`, `ply`, `color`, `severity`,
  `was_critical_moment`, `found_best_in_critical`, `missed_pattern`,
  `tactical_pattern_executed`, `punished_opponent_blunder`,
  `missed_opponent_blunder`, `time_flag`, `opponent_previous`. Sampled 60,000
  rows: every one of those fields is populated, not merely declared.

- **`motif_profile_service.py`** — already two-sided per motif: does the user
  FIND it, keep WALKING INTO it, or MAKE it and then blunder. Live on three
  screens. This is the closest thing we have to the record described here, and
  it works.

- **`behavioral_coaching_layer.py`** — winning-position collapse, rushes when
  winning, post-blunder tilt. `/coach/behavioral-profile` exists. **No
  frontend file references it.** Its fields are set for 16 of 69 profiled
  users (23%).

- **`pattern_decay_service.py`** — recency-weighted scoring with ACTIVE /
  DECLINING / FADING states. The maths for "is this still a problem" is
  already written and used by the Lab page.

- **`concept_test_service.py`** — the 5-puzzle test, written 2026-09-21,
  `TEST_SIZE = 5`, routes registered in `server.py`. The measurement end of
  the loop already exists.

### The three findings that shaped this scope

1. **`chess_understanding` draws from the wrong well.** It builds from
   `player_profiles.top_weaknesses` and decides "simple vs complex" by
   substring matching:
   `if "tactical" in subcat or "complex" in subcat`. Across all 74 player
   profiles the labels that exist are `one_move_blunders` (62),
   `fork_misses` (59), `discovered_attack_misses` (55) — and the string
   `complex` appears **zero** times. That branch has never executed. Meanwhile
   the rich stream sits in `move_observations` with half a million rows.

2. **Three of the six dimensions are not measured at all.** They are
   arithmetic on the others: `endgame = avg * 0.9` ("endgames are usually
   weaker"), `calculation = tactical * 0.95`, `pattern_rec = (tactical +
   positional) / 2`. When the product says a player's endgame is weak, that is
   a formula, not a finding.

3. **Depth is computed and thrown away.** On Mohit's position
   `rn3rk1/pp3ppp/2pb1n2/3qpb2/P1N5/3P1N2/1PP1BPPP/R1BQ1RK1 b`, the fork proof
   returns `replayed_uci: c4e3 d5e6 f3g5 e6e8 e3f5` — it knows the punishment
   lands three moves later. Nothing writes that number down.

### Decision: EXTEND

Do not build a new profile service, a new event store, a new taxonomy or a new
decay model. Repoint `chess_understanding` at `move_observations`, add two
fields to the events we already write, and reuse `pattern_decay_service` for
the record. The genuinely new thing is **two fields and one aggregator**, not
a new system.

---

## 1. What it is

Today the coach can say "you missed a fork." That is a fact about a move.

This makes the coach able to say something about the *player*: that he tends
to leave pieces loose rather than miss tactics; that it happens in the
middlegame rather than the opening; that it happens when he is winning and
relaxes; that the punishments are three moves deep, not one — which is why he
never sees them coming.

Two different players can both "miss forks" and need completely opposite
lessons. One keeps walking into them because he leaves pieces undefended —
that is a piece-safety habit. The other never spots one when it is available —
that is calculation. Right now we call both of them "fork_misses" and
prescribe the same thing.

The new information comes from asking two questions about every mistake that
we currently do not ask:

- **Did he ALLOW it, or MISS it?** Allowing is usually a safety habit.
  Missing is usually calculation. Opposite lessons.
- **How far away was the punishment?** A piece hanging right now is a
  looking failure. A piece lost three moves later to a forcing line is a
  calculation failure. Opposite lessons again.

Then the same record answers whether it is getting better.

---

## 2. What the user sees

### 2a. In the game review, on a mistake

```
  Move 9 ... Nbd7                                    you lost 710cp

  ┌────────────────────────────────────────────────────────────┐
  │  Nothing was hanging when you played this.                 │
  │  The problem arrived three moves later.                    │
  │                                                            │
  │  Your bishop on f5 had nobody defending it, and your       │
  │  queen on d5 sat two squares away from it. A knight on     │
  │  e3 hits both at once. The queen has to run, and the       │
  │  bishop cannot follow.                                     │
  │                                                            │
  │  ▸ Play it out:  Ne3  Qe6  Ng5  Qe8  Nxf5                  │
  │                                                            │
  │  Before you move, look for two of your pieces a single     │
  │  knight could reach at the same time.                      │
  │                                                            │
  │         [ I understand ]        [ Show me again ]          │
  └────────────────────────────────────────────────────────────┘
```

The sentence that matters is the first one: **"nothing was hanging when you
played this."** That is what makes it a new lesson rather than a repeat of
"you hung a piece."

### 2b. In the player's profile — the record

```
  HOW YOU LOSE MATERIAL                      last 40 games

  Pieces left loose                  ●●●●●●●○○○   struggling
     23 times · mostly middlegame · usually punished 2-3 moves later

  Spotting tactics when they are there   ●●●○○○○○○○   you are good
     found 31 of 44 · you are better at this than most at your rating

  Holding on when ahead              ●●●●●○○○○○   watch this
     11 of your 23 loose pieces happened while you were winning
```

Three separate facts, not one "weakness" list. The middle line is a
*strength*, said plainly — the current system has no way to tell a player he
is good at something.

### 2c. After the review — the test

Unchanged. The existing 5-puzzle test fires against the concept that was just
taught. That part is already built.

---

## 3. In scope (V1)

1. **Two new fields on every detector event we already write:**
   - `allowed_or_missed` — did the player allow this, or fail to find it
   - `punishment_depth` — which ply of the line the material actually changed
     hands (1 = immediately, 3 = two moves later, and so on)

2. **Run the existing proofs down `pv_after_played`** — the engine's
   refutation of the move actually played. No new engine work: measured
   2026-09-22, this line is stored for **90% of 100-199cp mistakes and 97% of
   200cp+ blunders**. The fork proof already fires correctly when handed it.

3. **Repoint `chess_understanding` at `move_observations`** — phase,
   eval_before (winning / level / losing), and the two new fields. Delete the
   substring matching.

4. **Delete the three invented dimensions** (`endgame = avg * 0.9`,
   `calculation = tactical * 0.95`, `pattern_rec = average`). A dimension we
   cannot measure is reported as "not enough evidence yet", never as a number.

5. **Recompute on a schedule, not once and never again.** Remove the
   permanent cache.

6. **One record per concept** using `pattern_decay_service`: struggling /
   solid / strong / one-off. Strength must be expressible, not only weakness.

7. **The review card in 2a**, for mistakes where the punishment is deeper
   than one move.

8. **The fourth quadrant: "your opponent gave you something and you did not
   take it."** Opponent moves carry full engine truth — `cp_loss`,
   `best_move`, `pv_after_played` on every stored row. Measured on 400 games:
   301 opponent blunders of 200cp or more. With this, the diagnosis is
   genuinely two-sided the way Mohit described it — allowed / missed /
   punished / found — from stored data, with no new engine work.

---

## 4. Explicitly out of scope (V1)

- **Re-analysing the 5,578 pre-June games.** Opponent moves are stored in
  `stockfish_analysis.opponent_move_evaluations` and have been since Mohit's
  fix in June 2026 — 86% of June analyses, 99-100% every month since, 10,835
  of 16,413 overall. The only gap is games analysed before that fix. Whether
  those are worth re-running is a separate decision with its own cost, and is
  not part of V1.

  **Correction, 2026-09-22.** An earlier draft of this document said
  `game_analyses` holds zero opponent moves and that adding them would double
  analysis cost. Both claims were wrong. They came from reading
  `move_evaluations` alone, never checking for a second field, and then
  sampling 400 analyses — which, because the collection reads oldest-first,
  landed almost entirely in the one period where the number really is zero.
  The sample confirmed the error instead of catching it. Mohit knew the fix
  existed and said so; the data agreed with him.
- **Raising `pv_length` from 4.** One number in `stockfish_service.py` that
  would help every depth-aware detector at once — but it changes analysis cost
  for every game and needs its own measurement. Noted, not done here.
- **New detectors.** V1 adds no new chess detection. If it needs a new
  detector to be interesting, the premise is wrong.
- **A new page.** 2b lives on an existing profile surface. No new route.
- **Time-pressure diagnosis.** `time_flag` exists and is tempting. Out, to
  keep V1 to one idea.

---

## 5. Success criteria

1. **Coverage:** the two new fields are set on at least 90% of mistakes of
   100cp or more, across 400 analysed games. Below that, the diagnosis is
   built on a minority and V1 has failed.
2. **The split is real:** across those events, neither "allowed" nor "missed"
   is below 15%. If one side is near zero we have built a relabelled version
   of what we already had.
3. **Depth is real:** at least 20% of punishments land later than ply 1. If
   almost everything is immediate, the distinction Mohit is asking for does
   not exist in our data and we should say so rather than ship it.
4. **Profiles exist:** every user with 10 or more analysed games has a current
   profile — 56 users today, against 17 now.
5. **It changes a prescription:** for at least 20 users, the concept picked to
   teach differs from what the current system would have picked. If the plan
   never changes, the diagnosis is decoration.

---

## 6. Open questions

**Q1. Is `punished_opponent_blunder` trustworthy?**
It is set on 2.4% of moves and `missed_opponent_blunder` on 1.8% — but
`game_analyses` stores no opponent moves, so something is deriving these
another way. *Unresolved because:* the writer has not been traced.
*Unblocking step:* find what writes it and on what evidence, before V1 uses it
as the positional half of the diagnosis.

**Q2. What counts as "winning" for the winning-vs-losing cut?**
`eval_before` is there, but +200cp at 800 rating is not the same situation as
+200cp at 1500. *Unresolved because:* no threshold has been read off a
distribution. *Unblocking step:* histogram `eval_before` at the moment of
mistakes, per rating band, before picking any number.

**Q3. Does "allowed" need the player to have had a choice?**
If every legal move loses the piece, the player did not allow anything — the
position was already lost. *Unresolved because:* it needs a rule.
*Unblocking step:* Mohit rules on whether a forced loss counts as a mistake at
all.

**Q4. Is 40 games the right window for the record in 2b?**
*Unresolved because:* the decay model uses games-back, not a fixed window.
*Unblocking step:* decide whether 2b shows decay state or a raw count.

---

## 7. Pre-code requirements

Hard gates. None of this starts until all are true.

1. Mohit has signed off on this document.
2. Q1 answered — we know what writes the two opponent flags.
3. Q3 answered — the rule for a forced loss is written down.
4. Q2 has a histogram behind it, not a guessed threshold.
5. The two new fields have names agreed and a version bump planned, so old
   events are distinguishable from new ones.
6. A baseline is captured first: what the current system prescribes for the
   same 20 users, so criterion 5 can be measured against something.

---

## Appendix — every number in this document

Measured against the production database, 2026-09-22.

| Claim | Value |
|---|---|
| `move_observations` rows | 526,642 |
| users total / with a chess_understanding profile | 128 / 17 |
| users with 10+ analysed games | 56 |
| `complex` substring hits across 74 player profiles | 0 |
| game analyses total | 16,413 |
| ...with `opponent_move_evaluations` | 10,835 (66%) |
| opponent coverage, May 2026 | 0% |
| opponent coverage, June 2026 onward | 86%, then 99-100% |
| opponent blunders 200cp+ (400 games) | 301 |
| refutation line stored, 100-199cp mistakes | 89.9% |
| refutation line stored, 200cp+ blunders | 96.8% |
| refutation line length | 4 plies |
| phase split (60k moves) | opening 46% / middle 39% / end 15% |
| game state split | winning 26% / level 50% / losing 23% |
| `behavioral_coaching_layer` frontend consumers | 0 |
