# Scope: Simple-English Captions

**Status:** drafted 2026-06-08 by Claude, delegated by Mohit ("take this without me").
Voice + hit-list approved in chat; this doc is the working reference.

## Goal
Make every user-facing caption readable by a chess player with **basic English**
(the large global "knows chess, weak English" segment) — and clearer for
everyone, including native-English 1200s. **One English version**, same
deterministic pipeline. No translation/i18n (that's a later, separate step that
this *enables*).

## Non-goals
- NOT full i18n / Hinglish / translation (later).
- NOT rewriting templates that are **already simple** (e.g. "Qe2 is a mistake.
  Nf3 was better. It wins the knight on e5." — leave as-is).
- NOT dumbing down to the point teaching is lost — keep the principle ending.

## The rule (caption voice rule #8)
1. **Controlled vocabulary** — common English words + chess terms players know.
   Same word for the same thing every time (always "take", never grab/capture/win
   interchangeably).
2. **No idioms or phrasal verbs** — the #1 barrier for non-natives.
3. **Unpack chess jargon** into plain words (but keep the basic chess terms below).
4. **Short sentences, one idea each. Active voice.** Name the square/piece.
5. **Keep the universal-principle ending** (teaching value > terseness).

## Banned hit-list → replacement
| Banned (idiom / phrasal verb) | Use instead |
|---|---|
| walks into | lets / allows |
| drops (the piece) | loses / leaves open |
| hangs to / hangs your X | leaves your X open / undefended |
| trades off | trades / wins |
| left with | now has / keeps |
| passes up | misses |
| keep the pressure on | make it harder for the opponent |
| turns against you | now you are worse |
| grab / grabbing | take / taking |
| give up | lose |
| comes off the board | is traded |
| joins the game | becomes active |
| for free | for nothing |

| Banned (too-advanced jargon) | Use instead |
|---|---|
| **the exchange** | **"material in the trade" (GENERAL)** — our `is_exchange_losing` is SEE-based (caption_facts.py:4890), fires on ANY losing trade, NOT just rook-for-minor. Do NOT say "rook". |
| with tempo | forces an answer, you gain time |
| strategic / positional | slow / needs planning |
| outpost | a strong safe square |
| initiative | the attack / the pressure |

## KEEP (global chess vocabulary — every chess player learns these)
knight, bishop, rook, queen, king, pawn, check, checkmate/mate, fork, pin,
take, attack, defend, move, castle, open file, square names (e4, f3, …).

## Discipline (mandatory per template — the "exchange" lesson)
- **Verify the detector before rewriting.** Read what the fact/flag actually
  means. The "exchange" near-miss proved blind find-replace ships wrong captions.
  Per [[feedback_query_engine_before_authoring]].
- **Render-test every rewrite** (deterministic pipeline → faithful).
- **No meaning change.** If a simplification would alter what's claimed, or the
  detector is ambiguous, STOP and log it under "Needs Mohit" below.

## Surfaces (in priority order)
1. `backend/data/captions/R12_blunder.json` — central move captions (highest freq)
2. `backend/services/decryption_voice/per_move_caption.py` — capture/check/dev lines
3. `backend/services/v5_llm_narrator.py` — deterministic narrator strings
4. `get_opening_introduction` one-liners (`game_decryption_v5_service.py`)
5. Home / Lab / PWC card prose (`game_mirror.py`, etc.) — later

## Enforcement
- **Blocklist linter** — pre-commit hook flagging any banned phrase in caption
  template files (mirrors the existing `drops about N pawns` hook). Allow-comment
  escape for legitimate quotes (`# allow-idiom`).
- **Readability target** — rendered captions at ~grade ≤ 5 (spot-measured).

## Rollout
- Incremental, highest-frequency first. **Small reviewable commits.**
- Version-bump V5 per batch so re-render surfaces it. Mohit deploys.

## Acceptance
- Every rewritten template render-tested; linter passes; zero detector-meaning
  changes; no item left in "Needs Mohit" unresolved.

## Progress log
- **Batch 1 (v115)** — opening one-liner ideas (`get_opening_introduction`). Done.
- **Batch 2 (v116)** — `per_move_caption` (castle/captures) + R12 ("the exchange"→general, "with tempo"). Done.
- **Batch 3 (v117)** — `opening_book` (fianchetto/cramped/undermine/retreats) + `concept_templates` (hanging/for-free). Done.
- **v133 (2026-07-08)** — follow-up jargon + defeatist-phrase sweep on R12/R_PROMOTED_basic_mistake, partial.
- All render-tested, detector-verified, small commits. Comment/docstring hits skipped.

## Batch 4 (2026-08-03) — corpus-audited, not just claimed-done

Prompted by real user feedback ("captions are too difficult, target
audience is people stuck under 1400 who are still learning"). Rather
than trust this log's "Done" markers, ran a live-production-data audit
first: **55,729 banned-phrase hits across 787,402 stored captions
(~7%)** were actually being served, including in files this log had
already marked Done (R09's castling caption alone was 7,701 hits —
never touched by any prior batch; R12 still had 5 separate live
"grab(s)" instances despite Batch 2 and v133 both claiming it clean).

Full file-by-file discovery audit (via Explore agent, not spot-checks)
found the real scope was far bigger than this doc tracked. Fixed in
this pass:
- `R08_material.json`, `R09_king_safety.json`, `R01_mate.json` — never
  audited before; now clean.
- `R12_blunder.json` — 9 additional leftover instances beyond Batch 2 /
  v133 (kept the pressure on, hangs your, walks into, gave up, grabs x4,
  keeps the pressure on, drop).
- `R_PROMOTED_basic_mistake.json`, `R_PROMOTED_trap_setup.json` (4x
  "walked into", never in any batch) — now clean.
- `backend/data/distilled_templates.json` — the newer Claude-authored
  "distilled" caption system (live since v134) was never written with
  this hit-list in mind. Now clean (7 instances fixed).
- `decryption_voice/concept_templates.py`, `v5_llm_narrator.py`,
  `game_mirror.py` (home/recap cards — item 5 on this doc's own priority
  list, never done), `player_decryption.py`, `truth_line.py`,
  `game_decryption_v5_service.py` (additional inline caption strings
  beyond `get_opening_introduction`, which itself still had 3 leftover
  jargon instances on non-primary opening branches),
  `decryption_voice/middlegame_patterns.py` (the fianchetto detector —
  the *outpost* detector in the same file was already clean, contrary
  to what this doc implied) — all now clean.
- `decryption_voice/opening_book.py` — an 11-instance caption table
  never touched by any batch (every fianchetto-opening caption was
  dirty). Now clean (one opening *name*, "King's Fianchetto Opening",
  intentionally kept — see Needs Mohit).
- `backend/data/traps.json` — ~25 instances, never audited. Now clean
  except 2 intentional "wins the exchange" keeps (see Needs Mohit).
- `backend/data/opening_curriculum.json` (~150 hits) and
  `backend/data/coaching/opening_theory_tree.json` (~58 hits) — by far
  the largest, completely un-audited surfaces (both are live, both
  independently referenced by 40+ files — real sprawl, not a duplicate
  to consolidate away as part of this fix). Reduced by ~65% (134 of 208
  instances fixed via tested, JSON-validated regex passes for the
  common safe patterns — grab/for free/walks into/positional/
  strategic/outpost/principled/cramped/undermine/compensation/with
  tempo/initiative). **~74 instances deliberately left** — see Remaining.

**Corpus-wide re-verification after this batch is required before
declaring victory** — re-run the same production-data audit script and
confirm the hit count actually dropped, then bump `V5_COACHING_VERSION`
and backfill so real users' already-analyzed games pick up the fix
(captions are cached per-move at generation time, not computed live).

## Remaining (next sessions)
- **`opening_curriculum.json` / `opening_theory_tree.json` residual
  (~74 instances)** — overwhelmingly grammatical variants of
  "fianchetto" (verb/noun/adjective forms too varied for a single safe
  regex — e.g. "Fianchetto Bg7" as a terse plan-shorthand, "Fianchetto
  BOTH bishops") plus a handful of "give up"/"gave up" instances that
  need contextual rewriting (not a 1:1 swap — sometimes means "lose",
  sometimes "voluntarily concede", the two need different phrasing).
  Lower priority than everything else in this doc: these are opening-
  lesson pages a user visits per-opening-studied, not per-move captions
  seen on every single game review.
- **Linter** — the existing pre-commit hook scans the WHOLE staged file, so a
  whole-file idiom block can't be enabled until every caption file is clean
  (else it blocks commits to uncleaned files). Decision: build it as a
  **diff-only** guard (scan added lines in `git diff --cached`, like the
  cp-loss rule but diff-scoped) so it blocks *reintroduction* without requiring
  100% pre-existing cleanliness. Build after the audit completes, or as the
  diff-only variant whenever.
- **This is a vocabulary fix, not a teaching-depth fix.** Real user
  feedback (2026-08-03) flagged something bigger than word choice: a
  true beginner needs a coach that starts with simpler *concepts*, not
  the same concept in simpler words. Confirmed only one place in the
  whole caption system has real rating-band content differentiation
  (`caption_pipeline.py:2162-2187`'s post-mistake recovery phrasing).
  This is a separate initiative — needs its own scope doc — see
  [[project_teaching_depth_by_rating_band]] once written.

## Needs Mohit (judgment calls parked here, not guessed)
- **"the exchange" / "wins the exchange" (traps.json:178, 2040;
  opening_book.py's "Caro-Kann Exchange", opening_curriculum.json's
  "Exchange QGD"/"Exchange Variation")** — these are the traditional,
  precise chess sense (a confirmed rook-for-minor-piece trade, or an
  established opening variation *name*), not the vague generic SEE-based
  usage this doc's hit-list originally targeted. Left as-is per the
  "verify the detector before rewriting" discipline below — flagging in
  case Mohit wants these renamed too for consistency.
- **"King's Fianchetto Opening"** (opening_book.py) — a real opening
  name, kept intact same as "Réti Opening" / "Caro-Kann Exchange"
  elsewhere in the same file. Same judgment call as above.
