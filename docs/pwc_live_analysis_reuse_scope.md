# PWC Live-Analysis Reuse — Scope (plain English, what it will be at the end)

> Status: **SIGNED OFF — Mohit 2026-06-11.** Defaults accepted: depth-12 reuse (no new
> Stockfish), regen recent window first. Building behind a default-off flag.
> Scope-first per [[feedback_scope_driven_development]].
> Grounded in a live audit of `bhutramohit@gmail.com`'s last-8 window, not intuition.

## 0. Why this exists (the bug we actually found)

The Home page "Recent Play" card for `bhutramohit@gmail.com` showed **"Eight games, all
losses. Two of eight came down to passive pieces."** Verification against Mongo proved:

- All 8 are **genuine losses** — the count is honest. 4 chess.com + 4 resigned Play-with-Coach games.
- But the **"2 of 8 passive pieces" is an undercount.** The two richest losses in the window —
  a **41-move** and a **16-move** resigned PWC game — contributed **zero** cognitive-gap signal
  (`gaps=[]`, `accuracy` came out 0 and 1). A 41-move resigned loss should be full of weakness signal.

Root cause is **not** a wasteful Stockfish re-run (a tempting assumption). The coach→game
conversion at [`coach_play.py:6583`](../backend/routes/coach_play.py#L6583) already **reuses the
live evals — no second Stockfish pass.** The real defect: it is a hand-rolled minimal copy that
**skips the enrichment step the chess.com import worker runs.** Specifically:

- `cognitive_gap`: line 6687 copies `m.get("cognitive_gap")` off the live move, but the live game
  never writes one back, so it is **always `None`** → every coach move is untagged.
- `is_user_move`: never set on the built move-evaluations at all.
- The chess.com worker, by contrast, runs a gap classifier + intent enrichment
  ([`analysis_worker.py:810-898`](../backend/analysis_worker.py#L810)) before saving.
  Coach games bypass it entirely.

**Blast radius:** every PWC game system-wide contributes **zero** `cognitive_gap` to the Mirror,
the decay model, established-patterns, and missions. PWC is the product's core loop ("your
mistakes become your training material") — and right now PWC mistakes are invisible to the
coaching brain. This also violates [[feedback_one_source_of_truth]]: two analysis paths, two schemas.

(Separately, the "real now, not noise" punchline picks an arbitrary pattern via `next(iter(set))`
at [`game_mirror.py:845`](../backend/services/game_mirror.py#L845) — tracked here as a **companion
fix**, but it is independent of the analysis bug.)

## 1. What it will be at the end

A finished PWC game produces a `game_analyses` doc that is **schema-identical** to an imported
chess.com game: every user move carries `cognitive_gap`, `is_user_move`, `cp_loss`, `best_move`.
The Mirror, decay model, and missions then read PWC games and chess.com games through the **same
detectors with the same taxonomy** — so "2 of 8 passive pieces" counts coach games correctly, and
the numbers are comparable across sources. **No second Stockfish pass is added** (Mohit's
constraint: reuse the live engine work, don't recompute it).

## 2. The depth finding (the one real tradeoff — grounded, not guessed)

| Path | Stockfish depth | Source |
|------|-----------------|--------|
| Live PWC eval (what's stored in the session) | **12** | [`coach_commentary.py:159-162`](../backend/coach_play/coach_commentary.py#L159) |
| chess.com import worker | **18** (`STOCKFISH_DEPTH`) | [`config.py:33`](../backend/config.py#L33) |

So reusing the live evals means deriving coach-game gaps from **depth-12** analysis vs **depth-18**
for imported games. For the 600–1500 audience the dominant gaps are gross (hanging pieces, simple
missed tactics) — depth 12 catches those reliably. The asymmetry mostly affects **subtle**
categories (calculation_depth, pawn_structure), which will be noisier on coach games.

**Decision (recommended): reuse live depth-12 evals + run the canonical enrichment on them.**
This is the cheapest path and honors the "don't re-run Stockfish" constraint. The depth asymmetry
is a documented, accepted tradeoff. **Fallback, only if gap quality proves insufficient in
testing:** a one-time depth-18 pass over **user positions only** (~20–40 per game) at game end —
which is what we're choosing NOT to do unless the cheap path fails.

## 3. In scope

1. **One shared enrichment function**, called by BOTH the import worker and the coach→game
   conversion, that takes move-evaluations and returns them tagged with `cognitive_gap` +
   `is_user_move`. Neither path keeps its own copy. (One source of truth.)
2. **Coach→game conversion** ([`coach_play.py:6583`](../backend/routes/coach_play.py#L6583)) routes
   its built move-evaluations through that shared function before insert. Fixes the empty-gaps bug.
3. **`is_user_move` stamped** on every coach move-evaluation (it already filters to user moves —
   just tag them).
4. **Fix the accuracy calc** for coach games as a consequence (the acc=0 / acc=1 garbage is
   downstream of the missing user-move identification).
5. **Companion fix:** `next(iter(set))` non-determinism in the Mirror listening line — name the
   **top repeated** persisted pattern, not a random one.
6. **Regen path** for the ~existing coach games in the corpus so they retroactively get gaps.

## 4. Out of scope

- Adding any new Stockfish pass to the live game or to conversion (explicitly rejected unless the
  fallback is triggered).
- Re-architecting PWC's live coaching engine (that's [[project_pwc_runs_second_coaching_engine]] —
  a separate, signed-off-pending rewrite).
- Changing the gap taxonomy or the detectors themselves.

## 5. The approach, and the divergence trap we are AVOIDING

There are two ways to fill the gap. We are choosing the second and rejecting the first:

- ❌ **Persist the live `concept_id`** the live coach already computes
  ([`coach_play.py:3045`](../backend/routes/coach_play.py#L3045)). Cheapest, but the live coach uses
  its **own** detectors — coach-game gaps would then come from a *different* detector than chess.com
  gaps, so the Mirror would compare apples to oranges. This is the
  [[project_pwc_runs_second_coaching_engine]] divergence (severity diverges ~50%). **Rejected.**
- ✅ **Run the canonical import-path enrichment** on the live evals. One taxonomy across all games,
  comparable counts, no Stockfish. **Chosen.**

## 6. Rollout (per house pattern)

- Default-OFF env flag gating the new shared-enrichment call in the coach path (A/B → 10% → 100% → delete legacy copy).
- Regen the existing coach games behind the same flag; verify counts before/after on the
  `bhutramohit@gmail.com` window as the canonical fixture.
- Delete the hand-rolled gap/accuracy logic in conversion once the shared path is at 100%.

## 7. Acceptance / how we verify (data-first)

1. Re-run the last-8 audit for `bhutramohit@gmail.com`: the 41-move and 16-move resigned losses
   now carry real `cognitive_gap` tags and a sane accuracy (not 0/1).
2. The Mirror's "N of 8" pattern count rises to reflect the previously-invisible coach-game gaps,
   and the headline pattern is stable across reruns (companion fix).
3. A coach game and a chess.com game of similar shape produce the **same schema** keys on every move.
4. `backend/tests/test_all_flows.py` green; add a regression test asserting coach `game_analyses`
   carry `cognitive_gap` + `is_user_move`.

## 8. Open questions for Mohit

1. **Depth adequacy** — accept depth-12-sourced gaps on coach games (recommended), or require the
   one-time depth-18 user-positions pass for parity with chess.com? Default in this scope: accept 12.
2. **Regen breadth** — regen all historical coach games, or only the recent window the Mirror reads
   (last ~50 by import)? Default: recent window first, full corpus as a follow-up.
