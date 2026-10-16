# Refactoring the caption layer — analysis before any code

> Status: **DRAFT for Mohit's sign-off.** No refactor starts until he agrees §2
> and §7. Written 2026-10-12 after he asked for "a proper analysis first, so
> that we don't lose anything that we have already done, but make it better, so
> we don't fuck up."

## 0. The short version

The caption layer works and is in nobody's head. It is organised **by producer**
— each rule carries its own facts, its own words, its own checks — rather than
**by decision**, where one place decides what a card says and everything else
supplies evidence. Every improvement is therefore additive, and additions cannot
see each other.

**The fix is not a rewrite.** The code holds years of hard-won corrections that a
rewrite would silently drop (§3). The route is strangulation behind a
byte-identical snapshot, and that method is already proven in this repo (§4).

## 1. What we would actually be touching

Measured by walking imports from the two review entry points
(`game_decryption_v5_service`, `caption_pipeline`):

| | modules | lines |
|---|---|---|
| whole services tree | 374 | 195,721 |
| **reachable from the caption path** | **166** | **104,837** |
| not reachable from it | 232 | 90,884 |
| immediate blast radius (depth 1) | 58 | — |

The 232 are not dead — they serve PWC, admin, training and other routes. They
are simply **out of scope**, and saying so halves the risk before any code moves.

Two limits of that count, stated rather than hidden: static imports
**over-report** anything imported and unused, and **under-report** anything
reached by a runtime string lookup. The second is why the behaviour snapshot
in §4 matters more than this graph does.

## 2. THE DECISION Mohit is being asked to make

Adopt **one decision point** for what a card says.

- producers stop writing text; they return candidate evidence
- one function ranks the candidates and writes the card
- verification happens at that boundary, so nothing can append below the check

Everything in §5 follows from this. If he disagrees, the rest does not matter.

## 3. What must not be lost — the expensive knowledge

These are real corrections found the hard way, each currently encoded in a
comment or a guard somewhere in the 166 modules. A rewrite loses them and they
get re-found on live cards. **Any refactor must carry a test for each before the
code it protects is moved.**

- `mate_info` is **white-relative**, and mate-in-0 means the player *delivered*
  mate. Both cost real bugs.
- **En-passant captures are invisible to `piece_at`** on the destination square.
  This has bitten at least twice.
- **Arrow colours invert by side.** `_line_sequence_arrows` reads the side off
  the board handed to it, and the user-side caller hands in a board where the
  opponent moves. 113 cards drew the opponent's win in the player's colours.
- **Material is counted from BEFORE the played move.** Counting from after it
  turns an even recapture into a loss — documented in `_story_swing`, and
  reintroduced in new code on 2026-10-12 anyway.
- **`board.attackers()` is pseudo-legal.** A pinned attacker counts. Any claim
  that a piece is attacked needs a legal move to prove it.
- **The word cap cuts at the last sentence boundary**, so the sentence it drops
  is always the last one — which is usually the recommendation.
- **`_enforce_word_cap` runs at stage 9**, above six stages that still append.
- **Opening detectors are fed a user-only move history**, so book lines never
  match. The fix is `games.pgn`.
- **`cp_loss` is 6000+ on delivered checkmates** (sign flip on terminal
  positions).
- **A caption appended below the `TextSurface` assignment never reaches a card.**

This list is not complete. Building it out — grepping the 166 modules for
guard comments and turning each into a test — **is itself the first work item**,
before anything is moved.

## 4. The safety net, which already exists

`backend/scripts/snapshot_captions.py` captures a byte-identical baseline of
caption output across pinned games: text, rule name, arrows, highlight squares,
severity surfaces, caption tier, teaching anchors, principle ids, decisiveness
fields. Sorted for deterministic diff. Baselines from the last refactor are
still on disk (`baseline_v99.json`, `pwc_baseline_pwc_v100.json`).

Its own docstring says it was built "to verify the v100 caption-pipeline
extraction does NOT change any user-visible output."

**So this repo has already done one caption-pipeline refactor safely, and the
method is proven here.** We reuse it rather than invent one.

Two cautions from 2026-10-12, both learned the expensive way:

- **Snapshot before touching anything**, and diff per row, not in aggregate. A
  previous refactor passed its tests while four en-passant rows silently lost
  their payoff.
- **Pin the corpus to a file.** The container reads the live production
  database and the candidate set moves while you measure; four separate figures
  for one effect came out of that in a single session.

## 5. The order of work

Each step ends with a byte-identical snapshot diff. A step that changes output
is either reverted or has its change explained row by row and signed off.

1. **Write the guard tests** (§3). Nothing moves until the expensive knowledge
   is executable.
2. **One canonical implementation per chess concept.** Today there are **89**
   files implementing "is this piece hanging" and **38** computing material. The
   same bug — an available capture counted as a lost piece, with no recapture —
   exists in at least three of them, including the production
   `TAC_HANGING_PIECE`. One implementation, everyone calls it.
3. **Producers return evidence instead of text.** One at a time, lowest-traffic
   first. 31 places currently assign the caption.
4. **One decision point** ranks candidates and writes the card.
5. **Move verification to that boundary.**

Steps 1 and 2 are worth doing **even if Mohit rejects §2**: they remove a live
class of false claims and cost nothing structurally.

## 6. What this is expected to fix

Measured on Mohit's own 838 analysed games, these are consequences of the
current shape rather than of any one rule:

- a card contradicting itself — 660 of his real mistakes were described as
  "playable" because a fallback overruled the engine's verdict (fixed 2026-10-12)
- facts dying in transit — `best_move_why` is derived on 58% of positional cards
  and reaches the caption on 21%; `line_loss_san` is computed and has zero readers
- arrows absent where the verdict already knows the line — 42% of tactical cards
- the same chess written repeatedly, with the same error each time (§5.2)

## 7. Risks, and what we do about each

| risk | mitigation |
|---|---|
| a runtime-string import the graph missed | the snapshot covers behaviour, not imports |
| the snapshot passes while meaning changes | diff **per row**; aggregate equality hid a real loss before |
| half-migrated state ships | each step is independently shippable and snapshot-clean |
| the peer session edits the same files | boundaries agreed per step; `caption_pipeline.py` is contended |
| a guard test encodes today's bug as correct | each §3 test cites the incident that produced it |
| scope creep into the 232 out-of-scope modules | §1 is the fence; anything outside needs its own scope |

## 8. What I would not do

**Rewrite from scratch.** 104,837 reachable lines encode the corrections in §3
and many more not yet catalogued. The failure mode is not "the rewrite is
wrong" — it is that it looks right, ships, and re-finds every one of those bugs
on Mohit's cards.

**Refactor and improve in the same step.** Each step either preserves output
byte-for-byte or changes it deliberately with the diff explained. Never both.
