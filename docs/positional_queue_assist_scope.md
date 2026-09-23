# Positional Queue Assist — Scope

**Status:** DRAFT, awaiting sign-off. No code until Mohit signs off.
**Date:** 2026-09-23
**Author:** Claude (measurements in this doc were run against prod on 2026-09-23)

---

## Why this, why now

The positional teaching system is finished, correct, and has produced nothing
in fourteen days.

Measured on prod today:

| thing | state |
|---|---|
| `positional_reason_queue` | **240 rows** |
| rows with any `disposition` | **0** |
| `positional_reason_submissions` | **1**, and it is incomplete (`concept_label: null`) |
| that one submission | Mohit's, 2026-09-09 |

The promotion gate, locked in `docs/verified_positional_captions_data_lock.md`,
is `disposition == "eligible_positional"` plus a complete contrastive proof.
Zero of 240 positions have a disposition, so the gate can never pass, so the
positional gold set is empty, so **no positional concept can reach a caption.**

That is not a theory. Two independent measurements today land on the same
place:

- In game `dfa9eed3` (Dok148 vs bhutramohit), `piece_activity` and
  `pawn_structure` fired **zero times** across 52 user moves.
- Across 500 games, of the mistakes no deterministic rule can explain,
  **22.4% are "quiet piece move, no named cause"** — the positional residue.

So the gap the queue exists to close is real and measurable, and the queue is
the only path that closes it.

---

## What is actually blocking it

Nothing is broken. The UI exists (`/admin/positional-reasons`, routed in
`App.js`), the endpoints work, the taxonomy is locked, the data lock is sound
and refuses to invent a centipawn threshold — which is correct.

**It is a typing cost.** To mark one position `eligible_positional`, a human
must write five pieces of prose:

| field | what it asks for |
|---|---|
| `better_move_fact` | what the better move does |
| `played_move_fact` | what the played move does |
| `contrast` | why one beats the other |
| `transferable_lesson` | the rule to carry to another game |
| `concept_label` | a plain-language headline |

All five then pass `voice_warnings()`. One piece of jargon — `fianchetto`,
`prophylaxis`, `zwischenzug` — and the **entire submission is rejected**, not
flagged.

Five written fields times 240 positions, with a hard reject on a single word,
is why this ran once and stopped. The design is right and the unit cost is
wrong.

---

## What this changes, in one sentence

**The machine drafts the four fields from the board; the human accepts,
rejects, or edits.** The disposition stays human. Nothing auto-promotes.

---

## What the reviewer sees (the experience, before any code)

Same page, same queue, same board. The four fields arrive **pre-filled** and
marked as a draft, with the board facts each one came from listed underneath
so a wrong draft is caught by looking, not by trusting.

Three buttons instead of a blank form:

- **Accept** — take the draft as written, set the disposition
- **Edit** — the text is editable; edits are what ship
- **Reject** — mark `not_positional` / `already_decided` / `no_clean_lesson`,
  which also moves the position out of the queue

A reject is as valuable as an accept. Today a position a reviewer looked at
and dismissed is indistinguishable from one nobody opened — both are
`disposition: None`. That alone is worth the change.

---

## Where the drafts come from

The four fields are the exact shape the deterministic rule table already
produces. This is not a new capability; it is pointing an existing one at a
form.

| queue field | comes from |
|---|---|
| `played_move_fact` | what the played move gives away — the `your_move_hangs` family and its siblings |
| `better_move_fact` | what the engine's move does — free material, breaks a pin, rescues the worst piece, takes the square |
| `contrast` | the comparison the rule already computes |
| `transferable_lesson` | the principle attached to that rule |
| `concept_label` | the matching `canonical_concepts()` id, when one matches |

Measured on 3,226 real mistakes across 500 games, that rule table explains
**47.8%** with **0 claims failing an independent board re-check**. So roughly
half the queue can arrive pre-filled; the rest arrive blank and the reviewer
writes them as they do today. **No position is ever blocked by the absence of
a draft.**

---

## Truth rules (non-negotiable, and today's evidence for them)

A draft that is plausible and wrong is worse than a blank field, because a
reviewer under time pressure will accept it.

1. **Every drafted fact must name a board fact that can be re-checked**, and
   those facts are shown to the reviewer next to the text.
2. **A draft never sets the disposition.** Only a human does. The data lock is
   unchanged.
3. **Drafts are stored as drafts** (`draft_source`, `draft_accepted_unedited`)
   so we can measure later how often an unedited draft turned out to be wrong.
4. **No draft may claim a move belongs to the wrong side.** Today a gold
   caption told a Black player "e5 claims central space" when e5 was White's
   move and Black had no e-pawn. Whose move each ply is must be explicit in
   the fact bundle.
5. **If the rule table has no reason, the fields stay empty.** Silence beats
   invention. The 52.2% with no deterministic reason get a blank form, exactly
   as now.

Today produced three concrete reminders of why rule 1 exists, all mine:
"e5 claims central space" (opponent's move sold as the player's benefit),
"d4 pushes the knight around" (the c3 pawn covers d4, so it cannot go there),
and "the knight has nowhere to go" firing on every position because after our
move it is the opponent's turn and the mobility filter matched nothing.
Deterministic does not mean correct. It means checkable.

---

## Where it lives + what already exists

| piece | state |
|---|---|
| `positional_reason_queue` (240 rows) | exists |
| `services/positional_reason_learning.py` — `normalize_submission`, `canonical_concepts`, `voice_warnings` | exists, unchanged |
| `routes/admin_positional_reasons.py` — next / submit / similar / concepts | exists, one additive field on the `next` payload |
| `frontend/src/pages/AdminPositionalReasons.jsx` | exists, gains pre-filled fields + accept/edit/reject |
| the rule table (`explain()` + `verify()`) | prototyped and measured today, needs promoting from a scratch script to a service |
| `docs/verified_positional_captions_data_lock.md` | unchanged — this scope does not touch a single locked decision |

---

## Acceptance bar (how we know it worked, not vibes)

Measured, not felt:

1. **Throughput.** Positions dispositioned per hour of review, before vs
   after. Today's baseline is 1 submission in 14 days.
2. **Draft quality.** Of accepted drafts, the share accepted **unedited**. If
   that is low the drafts are noise and should be turned off.
3. **Draft correctness.** Every accepted draft re-checked against the board by
   the same verifier used on captions. **Target: 0 board-false claims.** Any
   failure stops the rollout.
4. **The thing that actually matters.** Once ~40 positions are
   `eligible_positional`, re-run the unexplained-mistake measurement. The
   22.4% "quiet positional, no named cause" should fall. If it does not, the
   queue was not the bottleneck and we learned that cheaply.

---

## Out of scope (this pass)

- Any change to the promotion gate or the data lock.
- Auto-promotion of any kind. A concept still becomes teachable only through
  the existing human disposition.
- Rewriting the jargon filter. It stays a hard reject; the drafts simply avoid
  jargon because the rule table's vocabulary is already plain.
- The other three dissection axes (tactics coverage, behaviour surfacing,
  clock capture). They are tracked separately; see below.

---

## Companion findings, filed here so they are not lost

These came out of the same investigation and are **not** part of this scope:

- **Time control is one flag away.** `journey_service.py:168` sends
  `"clocks": "false"` to Lichess, so no game has per-move clocks. The parser
  already exists (`backfill_human_model_prerequisites.py` —
  `parse_clocks_seconds`, `player_clock_series`) and has never had data.
  Flipping it only helps games imported afterwards.
- **Behaviour is computed and unsurfaced.** `thinking_scores` holds per-game
  habit scores — game `dfa9eed3` has overall 78.7, `threat_awareness` 42.3
  with ten named examples. None of it appears on the game.
- **Adjacent cards contradict each other.** In `dfa9eed3`, m15 says "Qa4 traps
  the bishop on a3", the next card calls the reply "a calm move that keeps
  their position solid", and the card after says the bishop was taken. Cards
  are evaluated in isolation.
