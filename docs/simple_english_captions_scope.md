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
- All render-tested, detector-verified, small commits. Comment/docstring hits skipped.

## Remaining (next sessions)
- **Complete the audit** of lower-frequency caption files not yet swept:
  `decryption_voice/middlegame_patterns.py` (the real "outpost" caption),
  endgame modules, `game_mirror.py` (home/recap cards), and the V5 per-pattern
  builders in `game_decryption_v5_service.py` (lines ~188-2283 have
  strategic/positional/initiative/outpost/"trades off" in *some* captions —
  needs comment-vs-caption triage like batch 3).
- **Linter** — the existing pre-commit hook scans the WHOLE staged file, so a
  whole-file idiom block can't be enabled until every caption file is clean
  (else it blocks commits to uncleaned files). Decision: build it as a
  **diff-only** guard (scan added lines in `git diff --cached`, like the
  cp-loss rule but diff-scoped) so it blocks *reintroduction* without requiring
  100% pre-existing cleanliness. Build after the audit completes, or as the
  diff-only variant whenever.

## Needs Mohit (judgment calls parked here, not guessed)
- _(none so far — no meaning-change/ambiguous-detector cases hit; the "exchange"
  one was resolved by checking the SEE detector.)_
