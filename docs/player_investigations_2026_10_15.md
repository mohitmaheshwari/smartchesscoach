# Three investigations — user_8b599930d7ef, read-only

Run 2026-10-15 against live production, nothing written. Window: the player's
**100 most recent analysed games**, 2026-09-08 to 2026-10-14 (lichess 87,
coach 9, chess.com 4). 2,986 of his moves examined, 90,048 legal moves across
those positions.

Headline: **one hypothesis survives, one is refuted, one is unanswerable for
this player.** Every count below reconciles, and each section states what it
cannot support.

---

## H1 — Missed mates: SUPPORTED

With the denominator, which is the part the earlier report lacked:

| | Positions |
|---|---|
| a mate-in-1 existed | **29** |
| he delivered it | 20 |
| he did not | **9** |
| sum | 29 ✓ |

**Conversion rate 69% (20 of 29).** Every one of the nine had exactly one
mating move available.

**Uncertainty, stated:** a clock reading survives on **1 of the 9**, so no
time-pressure explanation is possible for the other eight. On the one we can
see he had 389s left and spent 4s. Also note two of the nine are consecutive
moves in the same game (moves 40 and 41), so the nine are not nine independent
occasions.

Traceable positions — FEN is before his move:

| Game | Move | He played | Mate was | cp_loss | FEN |
|---|---|---|---|---|---|
| `ad652319` | 40 | Re4+ | Rd4# | 0 | `8/3R2Qp/1p4p1/4R2r/6kq/8/5PP1/6K1 w - - 9 40` |
| `ad652319` | 41 | Rxh4 | Rd5# | 0 | `8/3R2Qp/1p4p1/6kr/4R2q/8/5PP1/6K1 w - - 11 41` |
| `45f946c3` | 21 | Bd7+ | Qd7# | 0 | `r1b4k/p4Bp1/1pK4p/4p3/8/3q2b1/PPn5/RNB4R b - - 1 21` |
| `66ac48e5` | 21 | Bd5 | Rc8# | 580 | `rn2kb1r/2R1p2p/p3B1p1/5p2/3pn3/7N/1PP2PPP/2B1K2R w Kkq - 0 21` |
| `0f24e0b6` | 61 | Be6+ | h7# | 10 | `6k1/6P1/5K1P/5B2/8/8/8/8 w - - 1 61` |
| `8a9eddd2` | 27 | Rxd7+ | Rxg6# | 450 | `r2r3k/p2p2Rp/1p4p1/4Bp2/1P6/5P2/P5PP/5RK1 w - - 2 27` |
| `c7f3400f` | 34 | Be5+ | Qxc8# | 0 | `1kb3QB/p4p2/8/8/P3P2p/3r4/3N1P2/2R3K1 w - - 2 34` |
| `coach_cf7d6a6d` | 17 | axb5 | Qd1# | 0 | `r1bqk2r/1p3p1p/p3p1nb/1NP5/4R1p1/6P1/PPP2P1P/K5NR b kq - 0 17` |
| `coach_cf7d6a6d` | 24 | Bxe4 | Qxa2# | 0 | `r3k2r/1p6/2b1p1p1/qpP5/4N3/6P1/PPPb1P1P/K7 b kq - 1 24` |

A pattern worth a human eye: in six of the nine he played **a check that was
not the mate** (Re4+, Bd7+, Be6+, Rxd7+, Be5+, and Rxh4 taking a queen). He is
not failing to look for forcing moves — he is taking the first forcing move he
sees. That is a hypothesis about *how* he searches, not a measurement, and it
is exactly the sort of thing only an asked question settles.

---

## H2 — Capture consequences: REFUTED, two independent ways

The earlier report said 13% of his captures lose material on the recapture and
called it "a habit cp_loss cannot see". With a denominator and a second look,
that does not hold.

**Reconciled counts.** Of 744 captures he played:

| | Captures |
|---|---|
| no recapture available | 392 |
| won material on the trade | 53 |
| even trade | 204 |
| **lost material on the recapture** | **95** |
| sum | 744 ✓ |

27% of the 352 recapturable captures — which is where the first report stopped.

**Refutation 1: the opportunity denominator.** A losing capture was *available*
in **1,817 of his 2,986 positions (61%)**, and he played one 95 times.

| | |
|---|---|
| his share of moves that were losing captures | 3.18% |
| share of all legal moves that were | 4.10% |
| **preference ratio** | **0.78×** |

He picks losing captures **less** often than they occur. That is the opposite
of a habit. This is the same error as the earlier "aggressive attacker from 74%
forward moves" claim: a raw share with no denominator.

**Refutation 2: the engine clears most of them.** Of the 95, **53 have
cp_loss < 50**. I first argued that made them an invisible habit, then that
those positions were already decided. Both were wrong, and I checked both:

- The recaptures are genuinely legal — verified move by move on the board for
  the five worst cases (`Kxd5`/`Nxd5`, `Qxd2+`, `Qxh3`, `Qxf2+`, `Qxd5` all
  legal). So the heuristic is not misfiring.
- The positions were **not** already decided: of the 53, 49% were within ±300cp
  and 38% clearly better; only 2% already lost and 4% already winning.
  `mate_info` on 3 of 53.

Which leaves the engine's own verdict, searching far deeper than my two-ply
look: these moves are fine. A capture that is recaptured is an *exchange*, and
the material comes back or the compensation is real. My two-ply heuristic
cannot see that; Stockfish can.

**What survives.** 42 of the 95 cost 50cp or more (median `eval_before` ≈ −3cp,
i.e. balanced positions). That is 42 genuinely costly losing-captures in 2,986
moves — **1.4%** — at a below-base-rate preference. Not a signature weakness.
**I withdraw H2.**

---

## H3 — Clock: UNANSWERABLE for this player

A clock reading survives on only **309 of his 2,986 moves (10%)**, against ~82%
population-wide. He plays lichess almost exclusively in this window, and the
clock is not reaching his observation rows.

| Clock left | Moves | Mean cp lost | Blunder rate |
|---|---|---|---|
| over 3 min | 210 | 53.4 | 6% |
| 1–3 min | 66 | 82.7 | 14% |
| 30–60 s | **10** | 132.2 | 30% |
| under 30 s | **23** | 34.5 | 4% |
| sum | 309 ✓ | | |

Only the top two rows are readable. **The earlier claim that "30–60s is the
danger band" rested on ten moves and is withdrawn.** The under-30s row cannot
be read as a strength either: by then a game is usually decided or being
flagged, so that population is not comparable.

The one statement the data supports: with 1–3 minutes left he loses about half
again as much per move as with over 3 minutes, on 66 moves against 210. That is
suggestive and no more.

His own pace, from 297 readings: median **5s** per move, p75 10s, p90 21s,
p99 66s.

---

## The `time_flag` correction — you were right, and I was wrong twice over

I said the flag fires on 0.4% of moves and therefore "the threshold was never
calibrated; the signal is there and the switch is off." That was a firing rate
mistaken for a defect, which is the inverse of the rule I keep citing about
never picking a threshold before seeing the distribution.

**The distribution.** Across all 501,863 observations with a reading:

| Time spent | Moves | Share |
|---|---|---|
| 0–1 s | 51,099 | 10.2% |
| 1–2 s | 91,961 | 18.3% |
| 2–5 s | 153,988 | 30.7% |
| 5–10 s | 100,713 | 20.1% |
| 10–30 s | 84,697 | 16.9% |
| 30–60 s | 15,047 | 3.0% |
| 60–120 s | 3,521 | 0.7% |
| over 120 s | 837 | 0.2% |

So **59.2% of all moves take under five seconds** — fast moving is the norm,
not an anomaly.

**And the flag is not measuring that.** `_classify_time_flag` is deliberately
narrow, and its docstring already records the calibration work I claimed was
missing: it was rewritten on 2026-09-26 because the old `impulsive_critical`
test was *vacuous* (true on 11,984 of 11,984 fires) and used an absolute
3-second cut when the corpus median is 3.4s, so 14.6% of fires told players
they rushed a move they had actually thought about longer than usual. It now
gates on mistakes only, tests speed **relative to that player's own pace in
that game**, and skips positions where they were already losing by 400cp.

It also states the conclusion I should have read before writing mine:

> "mistakes are LESS rushed than ordinary moves — 13.2% of mistakes are snap
> decisions against 23.5% of all moves — and NOT ONE player makes their
> mistakes faster than their usual pace… It is not evidence that a player is
> impulsive, and nothing should aggregate it into that claim."

0.56% is what a correctly narrow flag looks like. **No recalibration is
warranted, and the "calibrate time_flag" item should come off the priority
list.**

---

## What I would tell this player

One thing, with its positions attached: **when you find a check, you stop
looking.** In six of nine positions where mate was available in one move, he
played a different check. Conversion is 20 of 29, so the skill is there; the
search stops early. The nine FENs above are the lesson material.

Nothing about captures. Nothing about the clock — we do not have his clock.

## What this changes in the profile definition

- Opportunity denominators are not a nicety. They refuted H2 outright and they
  are what makes H1 a finding rather than a count.
- Two-ply board heuristics must defer to the engine on *whether* a move is bad.
  Mine disagreed with Stockfish 53 times and was wrong 53 times.
- Clock coverage is per-player, not global. 82% population-wide hid 10% for
  this player.
