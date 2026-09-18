# Coaching build-out plan — tactics, endgames, lessons

Status: DRAFT, awaiting Mohit's sign-off
Measured on production 2026-09-18. Every number below is re-derivable.

---

## 0. Why this document exists

Mohit asked "what is our plan for tier C tactics and endgame techniques and
lessons and everything I was telling you?"

The honest answer is that there wasn't one written down. The Codex
`missed_tactic` architecture, the Codex `endgame_technique` architecture and
the tactics tier scheme (A / B / C) were all discussed in a chat session and
**never written to the repo**. `grep -rn "Tier C" docs/` returns one unrelated
file about piece-safety depth. That is the actual reason this keeps needing to
be re-asked, and it is a direct violation of the scope-driven-development rule
we already agreed: no code starts until `docs/<feature>_scope.md` exists.

So this is the plan on disk. It supersedes anything remembered from chat.

---

## 1. The finding that reorders everything

We do not have a content problem. We do not have a detection problem.
**We have an authorization problem.**

| | measured | source |
|---|---|---|
| user mistakes diagnosed and stored | **71,114** across 6 categories | `game_analyses...move_evaluations[].cognitive_gap` |
| training positions available | **43,000+** | `community_training_positions` |
| endgame lessons authored | **20 lessons / 60 positions** | `data/coaching/endgame_theory_tree.json` |
| endgame principles authored | **17** | `data/theory/endgame_principles.json` |
| registered detectors | **59** | `services/detector_quality._AUTHORIZATIONS` |
| detectors allowed to speak to a player | **~1** | same; the rest are `shadow` or `disabled` |
| **detector claims Mohit has ruled on** | **0** | `detector_claim_rulings` is empty |
| lesson attempts ever, all users, all time | **129** | `learning_sessions.events[].attempt` |
| ...of which piece_safety | **124 (96%)** | same |

The threshold lock (`docs/detector_quality_threshold_lock_2026_08_27.md`) opens
with: *"Promotion is based on independently reviewed semantic examples, not
firing volume, implementation agreement, engine centipawn loss alone."* It then
names our exact kind of evidence as insufficient: *"382/382 sampled
board-geometry checks passed ... but geometry does not prove causal
attribution."*

**Consequence: no amount of further measuring by me can promote a single
detector.** The fork detector measuring 99.2% and discovered-attack measuring
100% are *geometry* precision, which the lock explicitly rejects. The only path
from shadow to a player's screen is Mohit ruling on claims, and that has
happened zero times.

Everything below is sequenced around that fact.

---

## 2. Phase 0 — correct the data we already have (no decisions needed)

**Mate-label backfill.** The mate gate shipped today (`9378f797`) but only
affects newly analysed games. Stored labels still carry what the old code
wrote:

- **5,371** moves should read `missed_tactic`, currently do not
- **2,426** moves should read `king_safety`, currently do not
- **7,797 total, across 55 users**

(Earlier in the session I estimated "~2,300" from a sample. The full population
is 7,797 — a sample that nailed the shape and missed the volume, which is the
third time that has bitten us.)

This matters beyond tidiness: `tactical_oversight` currently holds 5,984 moves
and is the bucket measured at **0.0% agreement** with the precedence spec. It
feeds the picker, active focus, mastery, Progress, and every validation run we
do. We are currently measuring the product against labels we know are wrong.

Procedure is the one used for the cognitive_gap audit (10,085 docs backfilled,
decay recomputed for 61 users): backfill labels from stored `mate_info`, then
recompute decay and active focus for the 55 affected users. No Stockfish re-run
needed — `mate_info` is already populated on 99.4% of mate swings.

*Owner: me. Ready to run.*

---

## 3. Phase 1 — the review sessions (the unlock for everything else)

This is the gate. Until it happens, phases 2 and 3 cannot ship to a user no
matter how much code gets written.

Per detector, **caption grade** needs:

- 50 independently reviewed fires at >=95% semantic precision
- 95% Wilson lower bound >=85%
- 20 true-negative cases
- zero critical false claims

**Plan grade** additionally needs 200 reviewed fires and >=60% recall — that is
a second, later session, not this one. Caption grade is enough to put a
detector's words in front of a player.

`/admin/detector-review` already exists and serves batches of 20 with the
board, the rendered claim and the detector's own evidence. It currently offers
**one** detector (`allowed_mate`, 1,868 fires waiting).

*My job first:* load the queue with the four detectors closest to the bar —
`simple_hang` (96.9% on 260 fires already documented), `left_book` (183 fires),
`fork`, `discovered_attack` — so one sitting earns rulings across four
detectors instead of 50 rulings on one sparse one.

*Mohit's job:* roughly 30–40 minutes per detector. Four detectors is about one
afternoon, and it converts directly into four detectors that may speak.

---

## 4. Phase 2 — tactics

Supply: `missed_tactic` **11,824** today, plus **5,371** arriving from the
Phase 0 backfill. This is the second-largest category we have.

**Tier B — fork, discovered attack.** Geometry measured at 99.2% and 100%.
These are genuinely close and are the right first candidates for Phase 1
review. Expected outcome: caption grade, then wired into review captions and
the lesson question spec.

**Tier C — pin, skewer. Do not promise these.** Measured precision **10.4%**
and **6.0%**. That is not a detector needing review; it is a detector needing
rebuilding. Reviewing them would waste a review session proving they are bad.
The honest plan is: rebuild pin/skewer detection against engine-verified ground
truth first, re-measure, and only then queue them. I would not put a date on
this until Tier B has been through review, because Tier B will teach us what
the review bar actually rejects.

**Known content gap:** `data/theory/tactical_patterns.json` holds 17 pattern
keys (knight_fork, skewer, deflection, pin_to_king ...) with **zero stored
positions between them**. Authoring lesson text against those keys produces
content no player can reach. Positions first, text second.

---

## 5. Phase 3 — endgames

Supply: `endgame_technique` **7,915** diagnosed mistakes. Content authored: 20
lessons / 60 positions in the theory tree, plus 17 principles. The endgame
lesson path **already works** — `endgame_theory_service.v1` has served 4 real
attempts (active_rook, lucena, key_squares). That is the proof that a second
category beyond piece_safety can be served end to end.

### Mohit's eight principles, against what exists

| principle | status |
|---|---|
| Staircase / ladder mate | authored — `basic_mates/rook_mate`, `queen_mate` |
| Push the passed pawn | authored — `passed_pawn_creation`, `outside_passed_pawn` |
| **Two connected passed pawns win** | **GAP — nothing authored** |
| Activate your king | authored — `king_activity_endgame`, `king_centralization` |
| Cut off the opponent's king | authored — `rook_endgame_cut_off_king` |
| Opposite-colour bishops are drawish | authored — `opposite_bishops_draw` |
| Rook behind the passed pawn | authored — `rook_behind_passed_pawn` |
| Queen vs pawn on the 7th | authored — `queen_endgame_checks`, `stop_promotion` |

**Seven of eight already exist as content.** The endgame problem is not
authoring. It is that the principles are matched by "material count + piece
configuration" and almost none of that matching has been through review, so the
claims stay in shadow. Same gate as everything else.

One real authoring task: connected passed pawns.

### Syzygy tablebase — worth doing, worth not overselling

`SYZYGY_MAX_MEN=0` and `SYZYGY_PATH` is unset in production, so every probe
returns `disabled`. Turning it on gives us *provable* endgame claims — win /
draw / loss as fact rather than as an engine opinion — which is the strongest
possible evidence for a review session.

But only **12.6%** of our stored endgame moves have <=7 pieces on the board. So
this is a precision instrument for one position in eight, not a general fix for
`endgame_technique`. Do it because it makes a slice of claims unfalsifiable,
not because it moves the headline number.

---

## 6. Phase 4 — lessons

129 attempts ever. 124 piece_safety, 4 endgame, 2 geometry, 2 destination
safety. The lesson engine is not broken — it is wired to one category.

The blocker is not the engine and not supply (`king_safety` 17,248,
`missed_tactic` 11,824 are both bigger than what piece_safety trains on). It is
that `lesson_question_spec` has seven categories with questions but only
`piece_safety` has an `any_safe` grader; the rest are `single_best` and need a
stored best move per position. Wiring a second cognitive-gap category
end-to-end is the unit of work here, and endgame already proved the shape.

**Deliberately deferred:** teaching the destination-safety grader to judge pawn
and king moves. It is a real correctness gap (30–60% of legal moves are
unjudgeable) but that surface has been answered twice in the product's
lifetime. Revisit when the lesson path carries traffic.

---

## 7. Sequence

1. **Phase 0 backfill** — me, ready now, no decisions
2. **Load the review queue with 4 detectors** — me, a few hours
3. **Review session** — Mohit, about one afternoon, yields 4 detectors that may speak
4. **Tier B wiring** — me, after their grades land
5. **Syzygy on + connected-passed-pawns authoring** — me, parallel to 3–4
6. **Second lesson category wired end-to-end** — me, after Tier B proves the path
7. **Tier C rebuild (pin/skewer)** — not scheduled; needs Tier B's lessons first

The single most important line in this document: **step 3 is not optional and
cannot be delegated to me.** Steps 4, 6 and most of 5 are blocked behind it.

---

## 8. What I am NOT proposing

- Not authoring more lesson text before positions exist for it
- Not promoting anything on geometry precision — the lock forbids it, and it is
  the exact failure mode that put king_safety at 75.4%
- Not rebuilding pin/skewer before Tier B has been through review
- Not measuring harder as a substitute for review. There is no such path.
