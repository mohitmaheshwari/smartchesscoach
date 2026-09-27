# Detector census and promotion strategy

Measured on production 2026-09-27. Every number here came from the registry or
from `move_observations`, not from a count of files.

---

## 1. The census

### Registered detectors: 66

| grade | n | reaches |
|---|---|---|
| plan | 5 | a focus **and** captions |
| caption | 7 | captions only |
| shadow | 49 | nobody |
| disabled | 5 | blocked on purpose |
| **promoted** | **12** | |
| **not promoted** | **54** | |

### But 66 is not the whole population

| population | n | note |
|---|---|---|
| registered with a grade | 66 | the table above |
| gap subtypes that FIRE but have **no id at all** | 15 | 26,700 fires across 56 users |
| detector/prover modules with no id | 17 | **9 have zero product callers** — dead code |

So the real count of things that behave like a detector is roughly **98**, and
**12 of them reach a user.**

### The 12 promoted, with what they actually fire on

| id | grade | fires | users |
|---|---|---|---|
| `gap:piece_safety:destination_safety_exact` | plan | 4,908 | 56 |
| `gap:king_safety:ignored_king_attack` | plan | 3,332 | 57 |
| `gap:missed_tactic:missed_skewer` | plan | 1,015 | 52 |
| `gap:missed_tactic:missed_fork` | plan | 862 | 49 |
| `gap:time_management:clock_damage_exact` | plan | see below | 8 hold it |
| `gap:piece_safety:simple_hang` | caption | 2,246 | 54 |
| `tactic:free_piece_exact` | caption | — | — |
| `tactic:fork_with_stored_payoff` | caption | — | — |
| `tactic:aligned_with_stored_payoff` | caption | — | — |
| `tactic:forced_mate_exact` | caption | — | — |
| `review:verified_single_game_cause` | caption | — | — |
| `review:exact_endgame_result_change` | caption | — | — |

`clock_damage_exact` shows no subtype fires because its evidence is not a
subtype: it is timeout losses plus two time flags.

---

## 2. Behavioural: 1 of 66

| | |
|---|---|
| promoted behavioural | **1** — `gap:time_management:clock_damage_exact` |
| behavioural, scored, but **cannot** be promoted | 2 — `threat_awareness`, `punish_blunders` |
| behavioural-ish but unregistered | 3 — the `tactical_oversight:*` subtypes |
| everything else | board geometry, concepts, curriculum |

Its per-move evidence, after the re-derive:

| flag | fires | users | role |
|---|---|---|---|
| `time_pressure_blunder` | 1,229 | 33 | scores the topic |
| `slow_paralysis` | 306 | 27 | scores the topic |
| `snap_decision` | 1,256 | 49 | explains a move only, never scores |

Why `threat_awareness` and `punish_blunders` are stuck: they have no `gap:` id,
so the plan gate drops them — and they are scored `(1 − rate) × 100 × prior`,
capped at 150, while count-based topics are unbounded. Two barriers, both fixable.

---

## 3. The 54 not promoted, by what they actually are

| namespace | n | what they are | can they be promoted? |
|---|---|---|---|
| `concept` | 24 | concept detectors | **No, and worse — see §7.** These 24 fire ZERO times. A different, unregistered set of 14 fires 278,000 times, always on good moves. |
| `curriculum` | 7 | exact opening/trap/endgame matchers | Yes, but they serve lessons, not focuses |
| `gap` | 6 | weakness subtypes | 2 measured and refused, 4 open |
| `review` | 4 | causal-proof family | Yes — caption surface |
| `tactic` | 3 | exact tactic + payoff | Yes — one was reverted after a false claim |
| `shape` | 3 | free_piece / pin / skewer executed | Yes |
| `principle` | 3 | caption principles | Yes |
| `brain` | 3 | legacy | Probably delete |
| `legacy_endgame` | 1 | superseded | Delete |

**So "move all 54 to promoted" is not the right goal.** 24 of them cannot
diagnose anything by construction, and 5 are disabled deliberately. The
realistic promotable population is about **25**.

### The better goal

> Empty the shadow tier. Every detector gets a verdict — **promoted, rebuilt, or
> deleted.** Nothing sits in shadow indefinitely.

Shadow is currently where detectors go to be forgotten: 49 of them, some for
months, with no owner and no date.

---

## 4. The plan, in the order that reaches users fastest

### Tier A — promote the 5 named subtypes that already fire (1–2 days)

These have a *named* claim, so each one is testable. Volume and reach:

| candidate | fires | users |
|---|---|---|
| `gap:king_safety:weakened_shelter` | 859 | 50 |
| `gap:endgame_technique:passed_pawn_ignored` | 668 | 42 |
| `gap:piece_safety:threat_ignored` | 582 | 52 |
| `gap:king_safety:king_in_center` | 350 | 37 |
| `gap:endgame_technique:passive_king_in_endgame` | 61 | 18 |

Each needs the same four steps, which have now been run four times and work:

1. **Promise check** — compute the literal claim on the board, count false fires.
2. **Negative control** — run the same check over all positions, not just fires.
   Without it a high rate means nothing.
3. **Topic-change test** — would promoting it change anyone's focus? Run this
   *first*; it is cheap and it has twice said "nobody".
4. **Packet** — record the numbers in the authorization's own `limitations`.

Expect some of these to fail. `missed_pin` (81.1%) and
`missed_discovered_attack` (35.3%) both failed and were correctly refused.

### Tier B — the behavioural expansion (2–3 days) ← biggest remaining win

`threat_awareness` (12,222 rows, 58 users) and `punish_blunders` (6,841 rows,
58 users) are the two largest behavioural signals in the product and neither can
be chosen. Two things to fix:

1. mint a `gap:` id for each, backed by a promise check;
2. make rate-based and count-based scores commensurable — today a rate topic
   caps at 150 while a count topic is unbounded, so a rate topic can only win
   for a player with very little evidence.

This is the only remaining change that could move a large number of users, and
it is behavioural, which is where the coaching value is.

### Tier C — rebuild the generic buckets (1–2 weeks)

26,700 fires with no provable claim. They cannot be promoted; they have to be
**classified** first.

| bucket | fires | users |
|---|---|---|
| `missed_generic_tactic` | 7,035 | 56 |
| `small_slip` | 5,948 | 56 |
| `tactical_seq_loss` | 3,616 | 56 |
| `unverified_hint` | 3,158 | 55 |
| `generic_endgame_slip` | 2,963 | 49 |

`missed_generic_tactic` is already shown to decompose cleanly — 0.0% quiet
moves against 84.2% in the engine-approved control, and free material provable
by SEE in 23.0% against a 3.2% baseline. The others have not been looked at.

### Tier D — wire or delete the code-only modules (2–3 days)

17 detector modules have no id. **9 have zero product callers** — they are dead
code and should be deleted unless someone can name the caller they are waiting
for. Six (`interference`, `advanced_pawn`, `xray_attack`, `deflection`,
`clearance`, `attraction`) were measured at high recall and are imported only by
measurement scripts.

### Tier E — concept detectors: see §7, it is not what this said

An earlier version of this section said "24 concept detectors that only
congratulate — 1,639 applied against 5 wrong". That was from a stale note and is
wrong twice over. §7 has the measured version.

---

## 5. What I would not do

**Promote on volume.** Every high-volume candidate left is a generic bucket.
Promoting one would put an unprovable claim in front of a player, which is the
one thing the grading system exists to prevent.

**Promote for the count.** Measured 2026-09-26: of the precise detectors still
in shadow, **not one** would change any user's focus topic — `missed_pin` at
1,299 fires and 81.1% precision included. Promoting them would move the "12
promoted" number and nothing else.

---

## 6. Where the 12 came from, for calibration

Five were promoted in the last two days, each on its own measurement, and two
candidates measured at the same time were refused. That is roughly the rate to
expect: **two or three promotions a week, with a third of candidates failing.**
A plan that promises 54 in a sprint is not describing this work.


---

## 7. Concept detectors, measured properly (correcting §4 and Tier E)

### What they are

They live in `services/concept_detectors/` (20 modules, 24 registered ids) and
ask a different question from the gap detectors: not *"what went wrong?"* but
*"did the player apply a named chess idea correctly?"* — castling early, a rook
to an open file, king centralisation, the Lucena position, avoiding the Fried
Liver. Their results are recorded through `coach_memory.record_skill_attempt`,
so they feed a **skill/mastery** model, not the weakness-focus loop.

### Three populations that can never meet

```
  the registry holds        concept:concept_rook_open_file       24 ids, 0 fires
  observations produce      observation_concept:rook_on_open_file  14 names, 278,005 fires
```

Different prefix AND different spelling. Overlap between the registered names
and the stored ones: **zero**. So the 24 registered ids govern nothing, and all
278,005 fires fall to the unknown default — shadow — and are stripped from the
plan surface. Nothing reaches a player either way.

### They never fire on a bad move

| move quality when a concept fires | share |
|---|---|
| best | 81.8% |
| good | 9.9% |
| excellent | 6.3% |
| brilliant | 2.0% |
| **mistake or blunder** | **0.0%** |

Against a corpus where 45.3% of moves are best and 13.5% are mistakes or
blunders. Across 278,005 fires, not one is on a move that went wrong. They
cannot diagnose, by construction.

### So they are an IMPROVEMENT signal, not a diagnosis signal — and that is
### worth having, but the data does not currently show any improvement

`/api/progress/improvement-proof` already exists and measures improvement
**subtractively** — mistakes going down, from cognitive gaps, pattern decay and
thinking scores. Concepts would give the additive half: *"you do this now, and
you did not before."* Different sentence, and the better one at this scale.

Measured, though, there is nothing to say yet:

```
  concept rate per move, first half of a player's games vs second half
      47 users with 30+ games:   7 improved, 2 declined, 38 FLAT
      median change +2%

  per concept, 568 user-and-concept pairs:
      62.3% flat, 21.1% up, 15.5% down

  the biggest movers are the most GAME-DEPENDENT concepts, and they move
  symmetrically -- winning_attack 16 up / 20 down. You cannot execute a
  winning attack the position never offers, so that is game mix, not learning.

  and with a clean denominator -- every game offers castling:
      king_safety_castling   9 up,  8 down, 28 flat,  median -0.01
      knight_development     3 up,  5 down, 37 flat,  median -0.04
      center_control         6 up,  8 down, 31 flat,  median -0.03
```

**Symmetric even where the denominator is unambiguous.** These players are not
measurably improving at these habits.

That is not a broken metric. It is the correct reading, and it is the most
useful thing on this page: **nothing has coached them yet.** The focus loop only
started naming behavioural topics yesterday, and the product is not live. So
this is the BASELINE — the control group a later claim gets proved against.

### What building it would take

1. **Register the 14-name vocabulary** so it can reach a surface at all. All
   278,005 fires are ungoverned today.
2. **Drop `found_best_move`** — 36% of all fires and a restatement of move
   accuracy, which `player_profiles` already tracks.
3. **Opportunity denominators**, or restrict the surface to the habit concepts
   where the denominator is "every game". Without them the page reports game
   mix as progress, which is the one thing an improvement surface must not do.
4. **Expect it to be quiet.** Today it would have something to say for roughly
   one player in five, and for the rest it would correctly say "not yet".
