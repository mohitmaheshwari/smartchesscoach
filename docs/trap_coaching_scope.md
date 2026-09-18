# Trap coaching — scope

**Status: DRAFT, awaiting Mohit's signoff. No code starts until he says go.**

Mohit, 2026-09-18:

> "we are not stockfish evaluation, chess.com doesn't tell you traps, we do and
> that's why we are important, we tell you how to save from traps, we tell you
> how to setup traps, in the game analysis sir, that's what we are"

This scope is about making that true in the product, not about inventing it.
Almost all of it already exists.

---

## 0. Existing surfaces audit

Done first, because the answer changed what this document proposes.

### What already exists

**The caption machinery is built, wired, and shipping.** Three rules, fifteen
authored variants, real selection logic:

| Rule | What it does | Wired? |
|---|---|---|
| `R_PROMOTED_trap_setup` | fires when a move completes a named trap's setup — includes a `victim_warning` variant | yes |
| `R_PROMOTED_trap_defense` | fires when the user plays a move that is IN the trap line | yes |
| `R_PROMOTED_trap_punisher` | fires when the user executes a step of the trap as the setter | yes |

The warning text is authored and good:

> `{move_san} — watch out, you're now in {trap_name} territory. The punisher
> will play {trap_next_expected_move} next.`

And it renders real captions today:

> "Nxe5 — you set up the Petroff Marshall Trap. The most famous beginner trap
> in the Petroff — copying white's moves…"

**The trap data exists and is sound.** `data/traps.json` holds 55 traps across
28 openings, with `setup_moves`, `trap_line` (per-move explanations),
`how_to_avoid`, `key_squares`, `tactical_theme`, `trap_color`, `result_type`.
All 55 setup lines and all 55 trap lines were verified to play out legally on a
real board (2026-09-18). The authoring is honest — the Traxler entry says
outright that it "does not force one reply or promise an automatic win."

A further 21 `trap_type` nodes live in the opening curriculum tree.

### What does NOT exist, despite a document saying it does

`docs/TRAP_OPENING_WIRING_COMPLETE.md` (2026-07-09) is headed **"Status: LIVE"**
and describes a five-stage loop: detect → evidence in coach_memory → puzzles
extracted → coach message → drills. Measured 2026-09-18:

| Claimed stage | Reality |
|---|---|
| caption on the board | **67 cards** of 73,972 (0.09%) — the only stage that works |
| evidence in `coach_memory.learning.skills["trap_detection"]` | **0** of 126 memories |
| trap puzzles extracted | **0** of 25,076 and **0** of 43,915 |
| trap drills attempted | **0** |
| trap events in `pattern_events` / `learning_sessions` / `user_active_focus` | **0** |

One stage of five carries data. The rest is a wiring claim, not a feature.

### Reach, measured on 1,500 real games

| | |
|---|---|
| games entering a trap line by **move order** | 77 (5.1%) |
| games reaching a trap position by **position match** | 105 (7.0%) |
| ...and blundering within 4 plies of it | 12 (0.8%) |

Position-matching finds 36% more than move-order matching, because players
transpose. It also survives the case that broke opening naming on Mohit's own
Rousseau Gambit card, where the recognizer returns `None` the moment Black
deviates — which is exactly the move the lesson is about.

### The depth problem

55 traps across 28 openings is **2.0 per opening**, and 18 of the 28 have
exactly one. The gap sits where the volume is:

| Opening | Traps | Games |
|---|---|---|
| Italian Game | 7 | 118 |
| Scotch Game | **1** | 145 (across variations) |
| Englund Gambit | **1** | 95 |

Our single Scotch "trap" is the Mieses Variation, tagged `opening_plan` — not a
trap at all. The trap club players actually fall into is missing:
`1.e4 e5 2.Nf3 Nc6 3.d4 exd4 4.Bc4 Bc5 5.c3 dxc3?! 6.Bxf7+! Kxf7 7.Qd5+`,
verified at +90 for White and winning the c5 bishop, with Black's best at the
branch point being `Nf6` (−6, equal).

### The pattern underneath the names

Across 46,867 user moves there are **330 piece captures on f7/f2, of which 65
(20%) are blunders of 150cp or worse**. The same square carries Mohit's own
flagged `Bxf7+`, the Blackburne Shilling hit, and the Scotch Gambit trap above.
One in five of these sacrifices is a mistake, and no named trap covers most of
them.

### Decision: EXTEND

Not a new feature. Three jobs on things that already exist:

1. **Feed it** — the machinery is data-starved (55 traps → 67 cards).
2. **Match better** — position, not move order.
3. **Finish the wiring, or stop claiming it** — four of five stages are empty.

A fourth job is genuinely new and is argued for in section 3: a shape detector
for f7/f2 sacrifices, because named traps are a finite list and the shape is not.

---

## 1. What it is

When a player walks into a known trap, we name it and tell them how to get out.
When they are the one setting it, we tell them that too. This is the thing
neither Stockfish nor chess.com does: an engine says "−379"; we say "this is
the Fried Liver, f7 is attacked twice, and the way out is d5."

It runs inside game review, on the move where it matters, and it does not need
the player to have asked.

---

## 2. What the user sees

**A. You are walking into one** (the warning — the highest-value case):

```
  Move 5   Bc5
  ┌────────────────────────────────────────────────────┐
  │  You're in Fried Liver territory.                  │
  │                                                    │
  │  Your f7 square is attacked twice — by the bishop  │
  │  on c4 and the knight on g5. The punisher plays    │
  │  Nxf7 next.                                        │
  │                                                    │
  │  The way out: d5, blocking the bishop before the   │
  │  knight can land.                    [board arrows]│
  └────────────────────────────────────────────────────┘
```

**B. You fell into one** (after the fact):

```
  Move 6   dxc3
  ┌────────────────────────────────────────────────────┐
  │  This is the Scotch Gambit trap.                   │
  │                                                    │
  │  Taking the second pawn lets Bxf7+ drag your king  │
  │  out: Kxf7, then Qd5+ forks your king and the      │
  │  bishop on c5.                                     │
  │                                                    │
  │  Nf6 kept the game level.                          │
  └────────────────────────────────────────────────────┘
```

**C. You set one** (kept from the existing `trap_punisher` rule, unchanged):

> "Nxe5 — you set up the Petroff Marshall Trap."

---

## 3. In scope (V1)

- **Position matching** replaces move-order matching for trap entry. Measured
  +36% reach on the same 55 traps.
- **Trap library expansion**, prioritised by `user games ÷ traps we hold` —
  Scotch and Englund first, not alphabetically.
- **Every new trap engine-verified before it ships**: setup line legal, trap
  line legal, and the stated payoff confirmed by the engine. The Scotch line
  above took seconds to verify; there is no excuse for an unverified trap.
- **The f7/f2 sacrifice shape detector** — a piece sacrifice on f7/f2 that
  legal exchange truth says loses material and that has no forcing follow-up.
  Covers the 65 blunders above, named trap or not.
- **One honest decision on the dead loop**: either wire evidence/puzzles/drills,
  or delete the claim from `TRAP_OPENING_WIRING_COMPLETE.md`. A document that
  says LIVE over four empty stages is worse than no document.

## 4. Explicitly out of scope (V1)

- **Trap drills and puzzle extraction.** They are in the July doc as done; they
  are not. V1 does not build them — it stops claiming them.
- **Setting traps as a plan** ("play this to trap your opponent"). We describe a
  trap the player already set; we do not yet coach them to aim for one.
- **Opening repertoire changes.** Naming a trap is not recommending a line.
- **Rewriting the three caption rules.** They work. V1 feeds them.
- **The `None`-on-deviation recognizer bug.** Real (it broke the Rousseau card)
  but it is an opening-naming defect, tracked separately.

## 5. Success criteria

Behaviour, not activation:

- **Trap captions rise from 67 cards (0.09%) to ≥1% of review cards**, driven by
  data and position matching, not by loosening any gate.
- **Zero unverified trap claims ship.** Every trap in the library passes the
  engine check, as an automated test, not a one-off script.
- **The f7 shape detector fires on ≥50 of the 65 measured blunders**, with no
  false fire on a sacrifice the engine approves of.
- **A player who saw a trap warning meets the same trap later and avoids it.**
  This is the only criterion that measures teaching rather than output, and it
  needs the evidence stage — which is why the dead-loop decision is in scope.

## 6. Open questions

**Who authors the traps?**
*Why unresolved:* it is content work, not engineering — plausibly Farhan's
highest-value contribution, well above ruling on geometry gaps.
*Unblocking step:* Mohit decides. If Farhan, he needs an authoring surface;
`/admin/geometry-gaps` is the template and took under a day.

**How many traps is enough?**
*Why unresolved:* no threshold should be picked before the distribution is
seen. 55 gives 0.09% of cards; the relationship between library size and reach
has not been measured.
*Unblocking step:* plot fires against library size on the existing 55 before
choosing a target.

**Warn before, or explain after?**
*Why unresolved:* the warning is 7% reachable and the punishment 0.8%, but a
warning on a move the player then plays correctly may read as noise.
*Unblocking step:* render both on stored games and read fifty of each.

**Wire the dead loop, or delete the claim?**
*Why unresolved:* it is Mohit's call whether trap drills are a product
direction or an abandoned one.
*Unblocking step:* one decision, this week, either way.

## 7. Pre-code requirements

1. Mohit signs off on this document.
2. The dead-loop question is answered — wire or delete.
3. The trap verifier exists as a test, so no unverified trap can be added later.
4. The library-size-versus-reach curve is measured before any target is set.
5. An authoring owner is named.

---

*Section 0 measurements were taken 2026-09-18 against production data: 73,972
review cards, 46,867 user moves, 1,500 games with PGNs, 126 coach memories.
Every figure in this document is reproducible from those queries.*
