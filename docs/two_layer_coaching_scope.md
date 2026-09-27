# Two-layer coaching: diagnose the player, drill the pattern

**Status: DRAFT, awaiting Mohit's signoff. No code until then.**
Written 2026-09-28.

Mohit: *"A player is never bad at threat awareness... behaviour detection is the
real story a coach understands, and knowledge... threat awareness, one move
blunders, forks, pins, tactics are sub part of it, which user practises on"* and
*"better detectors would be to detect if player is hearing the coach"*.

---

## 1. The problem, in one number

**326 focus documents have been written. Zero have ever closed as "improved".
Zero as "regressed".** Every one was superseded by a schema bump or a migration,
or closed as unmeasurable.

The reason is a category error. `piece_safety` is the named weakness for 30 of 52
players — because hanging a piece is the common *symptom* of a dozen different
causes. Naming the symptom tells the player nothing and gives us nothing to
measure, so the loop cannot close.

A coach does not say "your weakness is piece safety". A coach says **either**

- *you don't know this pattern yet* (knowledge), **or**
- *you know it and you're not looking* (behaviour)

and then hands over the drill. Forks, pins, hangs and threats are the **drill**,
not the diagnosis.

---

## 2. What the player sees

The card comes first. The schema follows it.

### Same missed forks, two different players

**Knowledge:**

```
  You know what a fork is. Your eye has not learned to look for it.

  Forks come up in your games more often than you take them. The ones you
  miss, you play at your usual speed — so this is not rushing. You are
  not seeing the shape yet.

  Next: positions where a fork is waiting. Find it before you move.
```

**Behaviour:**

```
  You know what a fork is. You are moving before you look.

  Forks come up in your games more often than you take them, and the ones
  you miss you play faster than you normally move. The idea is not the
  problem. Stopping to check is.

  Next: the same positions, but say what you see before you touch a piece.
```

Same detector, same symptom, opposite prescriptions. No counts, no percentages,
short sentences, and the pattern is named rather than a move.

### When it resolves

```
  You are finding forks now that you used to walk past.
```

That sentence has never been said by this product. Saying it once, truthfully,
is the goal of this scope.

---

## 3. The mechanism

```
  UP   (chess -> the player)
       opportunity(P) = the engine's best move is a P-move
       knowledge(P)   = took / opportunities                  a RATE, per player
       behaviour(P)   = the context of the misses             fast? which phase?

  DOWN (the player -> chess)
       knowledge gap  -> puzzles on P                teach the shape
       behaviour gap  -> a habit drill, NOT more P   the scan, the pre-move check

  CLOSE
       re-measure knowledge(P) -> the focus resolves
```

The same detector feeds both layers. Which layer it feeds depends on whether you
read the **rate** or the **circumstances**.

### Proven on forks, on real games

| | engine-gated | loose |
|---|---|---|
| opportunities | **1,384** | 12,013 |
| taken | **51.7%** | 11.2% |
| spread across players | q1 0.38 → q3 0.58 | 0.09 → 0.14 |
| chances per player | median 20 | — |

And the behaviour reading on the same misses: **87.9% were played at normal or
slow pace**, only 12.1% fast. So on forks, for these players, it is a knowledge
gap and not an attention gap — teach the shape, do not drill the scan.

### The trap this scope exists to avoid

**The denominator is the whole architecture.** The loose column above is what
happens when "a fork-shaped move exists" is treated as an opportunity: you
measure your own detector's generosity, get 11.2% with a narrow spread, and it
looks like a finding. It is not. Only "the engine's best move was the fork"
makes it a fact about the player.

I made this exact mistake twice in ten minutes while measuring it.

---

## 4. Which traits are real, and which are not

Stability = the same player's first half of games against their second half.
Anything that fails is game mix wearing a personality.

| axis | stability | verdict |
|---|---|---|
| thinks too long | 0.88 | behaviour |
| clock front-loaded | 0.87 | behaviour |
| error rate | 0.83 | skill baseline, **not** a diagnosis |
| knowledge breadth | 0.77 | knowledge |
| moves fast for them | 0.76 | behaviour |
| plays on when lost | 0.72 | behaviour |
| repeats the same mistake next game | 0.68 | promising, not yet usable |
| notices threats | 0.65 | **weak — this is why it is not a diagnosis** |
| endgame-weighted errors | 0.64 | weak |
| opportunism / punish rate | 0.50 | **weak** |
| tilt (one blunder becomes three) | 0.18 | **not real** |
| "very aggressive" | 0.06 | **not measurable in stored fields** |

And knowledge is **independent of skill** — knowledge vs error rate r = +0.04,
vs blunder rate r = +0.12. So the two layers genuinely separate, and the four
coach-players exist in near-equal numbers:

```
  few ideas + moves quick   10        knows + moves quick    14
  few ideas + thinks long   14        knows + thinks long    10
```

**Two consequences for this scope.** `threat_awareness` is not promoted to a
diagnosis — it is weak, and Mohit is right that it is not a trait. And
`opportunism` at 0.50 must never become a focus, even though a line about it
already ships on the home page; a true statement about someone's games is not a
property of the person.

---

## 5. Is the player even hearing us?

Measured over every focus ever written:

```
  1. told something (a focus with a start date)        54 players
  2. came back and played 3+ games since              39
  3. practised anything since (puzzle or lesson)      29
  4. the named pattern moved?          11 better, 9 worse, 14 flat
```

Three completely different failures, currently invisible as one:

| stage that fails | what it actually means | what to do |
|---|---|---|
| never came back (15) | re-engagement, nothing to do with chess | not a coaching fix |
| came back, never practised (10) | the ask was wrong, too hard, or unseen | change the ask |
| practised, nothing moved | **the diagnosis was wrong** | change the diagnosis |
| practised, it moved | say so, loudly | the thing never yet said |

Without this, "the coaching failed" and "he never heard it" are the same row in
the database. Every input already exists: focus start date, games since,
practice events since, and the pattern's rate either side.

---

## 6. In scope

1. **An opportunity gate as a shared service.** One way to ask "was P the right
   move here", used by every pattern, so no detector invents its own
   denominator.
2. **Knowledge rates per pattern per player**, from that gate. Starting with the
   four patterns that have both a shape detector and engine truth: **fork, pin,
   skewer, free_piece.**
3. **The behaviour reading** on the misses: pace against the player's own, and
   phase. Only the axes that passed §4.
4. **The diagnosis**, as the pairing of the two, rendered as §2's card.
5. **The drill split** — knowledge sends you to puzzles on P, behaviour sends
   you to a habit drill. Never the same prescription for both.
6. **The landing funnel** from §5, recomputed per analysed game, as a
   first-class record rather than a script someone ran once.

## 7. Out of scope, and why

- **Aggression, calculation depth, "plays without a plan".** All three are real
  coaching ideas and none is measurable from stored fields — aggression failed
  twice, at 0.23 and 0.06. They need new detection, scoped separately.
- **The six unwired provers** (`interference`, `xray_attack`, `deflection`,
  `clearance`, `attraction`, `advanced_pawn`). Each is another knowledge axis
  and each is already written at high recall — but they wait until the gate
  works for four patterns. **Note for the census doc: these are not
  housekeeping, which is how I filed them.**
- **The concept vocabulary.** 278,005 ungoverned fires in a namespace that can
  never match the registry. It is the *improvement* surface, and it has nothing
  to show until this loop has been running a month.
- **Retiring the symptom topics.** `piece_safety` and the rest keep working as
  they are until the diagnosis is proven on at least one pattern. Nothing is
  taken away first.

## 8. What would say this failed

**The honest one:** a player is diagnosed knowledge-gap on forks, does the fork
puzzles, plays twenty more games, and his engine-gated fork take-rate does not
move. That means the diagnosis is not actionable, and it is measurable per
player from data we already store.

**The subtler one:** the take-rate moves for everyone, including players we never
diagnosed. That would mean we measured ordinary improvement and called it
coaching. The un-diagnosed players are the control group, and they must be kept.

**The flat check:** if the four quadrants collapse — if nearly every player lands
in one — the two axes are not separating anybody and the diagnosis is theatre.
Today they are 10 / 14 / 14 / 10, so they do separate now.

## 9. Sequence

1. the opportunity gate + knowledge rates for one pattern (fork), measured, no UI
2. the landing funnel, because it is independent and it tells us whether
   anything that follows is arriving
3. the behaviour reading and the diagnosis pairing
4. the card
5. the drill split
6. then, and only then, the other three patterns

Step 1 is the one that can fail cheaply. It has now been RUN — see §10.

---

## 10. Step 1, already measured: the grain has to change

The go/no-go was whether the engine-gated rate is stable per player. Run before
asking for signoff, so the signoff is informed.

**Per pattern it is NOT a trait.** Fork take-rate, same player's first half of
games against their second:

```
  bar 10 chances   48 players   r = +0.41
  bar 20 chances   39 players   r = +0.33
  bar 30 chances   30 players   r = +0.57
```

Non-monotonic. A real trait's correlation climbs steadily as the sample grows;
bouncing means noise. And there is a plain reason: about fifteen chances per half
at a take-rate near one half has a standard error of roughly 0.13, which would
flatten even a strong underlying trait.

**Pooled across every tactical shape it IS a trait**, and unmistakably:

```
  bar  20 chances   54 players   r = +0.70   spread 0.22
  bar  40 chances   53 players   r = +0.72   spread 0.21
  bar  60 chances   50 players   r = +0.71   spread 0.20
  bar 100 chances   46 players   r = +0.73   spread 0.18
```

50,251 opportunities across 57 players, 67.0% taken. Flat at every bar, which is
what a real trait does.

### So the diagnosis and the drill sit at different grains

```
  DIAGNOSE pooled      "you are not seeing tactical shapes yet"
  DRILL per pattern    forks, because that is where your misses are
  MEASURE pooled       because the per-pattern rate is too thin to trust
```

This is a correction to §3 and §6, and it matters: telling a player "you don't
know forks" off fifteen samples would be a confident claim built on noise. The
person-level claim is pooled; the pattern is only how we choose the exercise.

### And a coverage problem found in the same run

The pooled 50,251 came from **two** patterns only:

```
  free_piece   26,522
  fork         23,729
  pin               0
  skewer            0
```

`detect_pin` and `detect_skewer` never once had the engine's best move match
their executing move. Either they do not emit one or their shape is almost never
the best move. §6 claimed four patterns; **two of them do not work with this
gate**, and that must be established before they are counted.
