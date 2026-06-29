# Activation Hub — Scope

*Status: SIGNED OFF 2026-06-29. Decisions: (1) approved; (2) diagnostic = full 20 puzzles but EXITABLE — user can stop anytime and we still build their profile from whatever they solved (requires incremental/on-exit scoring); (3) hub shown to NEW signups only. Next: pre-code verification of the Wiring-#1 target, then build.*

The problem in one line: **32% of signups are dead on arrival** (no account linked, never played a coached game) because onboarding forces a chess-account link *before* delivering any value. This replaces that account wall with a value-first "activation hub," AND — critically — pipes the cold-start data it gathers into the training engines so a no-account user actually gets **trained**, not just landed.

---

## 0. Existing surfaces audit  →  decision: **EXTEND (reuse heavily) + one thin new surface**

**What already exists and works:**
- **Onboarding.jsx** — 2-step wizard (link account → calibrate). *This is the account wall we're moving past.*
- **Diagnostic (BUILT, WIRED):** `routes/diagnostic.py` + `diagnostic_service.py` + `DiagnosticPuzzles.jsx` — 20 puzzles stratified across the 7 weakness dimensions → **rating estimate + per-category strengths/growth**. Pool sufficient (866 community_puzzles; 145 approved across the 7 types). **BUT its output dead-ends in `diagnostic_sessions` — nothing downstream reads it.**
- **Play-with-Coach (BUILT, account-less):** `coach_play /start` needs no account/games; only gate is free-tier **1 game/day**. PWC games get analyzed → `move_evaluations` + `motif_profile`, same pipeline as imported games.
- **InstantDNA** (`instant_dna_service.py`) — PGN-based instant read, for users who *did* connect.
- **opening_curriculum.json** — teach-a-repertoire (prescribe) path, independent of game data.
- **player_motivation** (just shipped) — self-declared "why are you here."
- **PWC_GAP_ENRICHMENT flag (default OFF)** — would let coach games produce `cognitive_gap` weaknesses.

**Overlap vs differentiation:** almost everything needed EXISTS — the diagnostic, the puzzles, PWC, the curriculum. The gap is **not new capability; it's (a) a landing surface that routes cold users into value, and (b) wiring the cold-start DNA into the training/coach engines that currently only read imported-game data.**

**Decision: EXTEND** — reuse diagnostic + PWC + curriculum + motif as-is; add **one thin new surface** (the activation hub page) and the **wiring** that makes the DNA actually feed training. Do NOT rebuild any diagnostic/puzzle/coach logic.

---

## 1. What it is

After signup, instead of "link your chess account," a new user lands on an **activation hub**: a friendly page that gives instant value — a quick "Chess DNA" puzzle check or a coached game — and asks them to connect their account *later*, framed as their benefit. The hub gathers a cold-start read of the player (rating estimate + weak spots), and that read is **fed into the same training and coaching engines that normally run off imported games** — so a user who never connects an account still gets personalized weakness training and tactics, and gets richer the more they play with the coach. Openings, which can't be read from puzzles, are taught from a curriculum until real game data shows up.

## 2. What the user sees

**The hub (new), shown right after signup instead of the account wall:**
```
  Welcome to ChessGuru 👋
  ─────────────────────────────────────────────
  Let's see how you play — no account needed yet.

   ┌─────────────────────────────────────────┐
   │  ▶  Get your free Chess DNA              │   ← PRIMARY (instant, unlimited)
   │     ~6 quick puzzles · find your level   │
   └─────────────────────────────────────────┘

   ┌─────────────────────────────────────────┐
   │  ♟  Play a game with your coach          │   ← secondary (1 free/day)
   └─────────────────────────────────────────┘

   Already play on Chess.com / Lichess?
   Connect so your coach can analyze your real games →   ← soft, benefit-framed
```

**After the DNA check — the result, AND the payoff:**
```
  Your Chess DNA
  Estimated level: ~900–1050
  Strongest:  Spotting hanging pieces
  Work on:    Seeing tactics (forks, pins)

  → Your coach built you a plan:
     • Train: "Seeing tactics" puzzles      [Start]
     • Learn: a solid opening for your level [Open]
```
The key contract: the "Train / Learn" buttons are **personalized from the DNA**, not generic. A cold user's `/training` and `/home` now speak to *their* weak spots — the same way a game-user's does.

## 3. In scope (V1)

- **Activation hub page**, shown to new users in place of the account wall; account-link demoted to a soft, benefit-framed option.
- **Diagnostic** as the primary action — the **full 20-puzzle** run, but **exitable at any point**. The user can stop early and we **still build their profile from whatever they solved**. This requires **incremental / on-exit scoring** — the existing diagnostic only scores at full completion ([diagnostic.py:261](backend/routes/diagnostic.py#L261)), so V1 adds: score the partial `attempts` on exit, persist a (rougher) diagnosis, and feed it to Wiring #1. Each solved puzzle nudges the profile.
- **Wiring #1 — Diagnostic → weakness profile (THE core of "train them"):** the diagnosis's top growth-areas are written into the same weakness signal the training recommender reads, so cold-user `/training` + `/home` personalize off it. (Exact store verified pre-code, §7.)
- **Wiring #2 — PWC gap-enrichment ON (second cold-start source):** flip `PWC_GAP_ENRICHMENT` (env flag, `config.py:16`; gated live at `coach_play.py:6814`) so every coached game produces `cognitive_gap` weaknesses, + run `regen_coach_game_gaps.py --apply` to backfill existing coach games. Mechanism is ready (flag + regen script + test exist). Coach games then feed the same weakness pipeline as imported games — so a cold user's profile gets richer the more they play the coach. NOTE: the flag is **global** (enriches all users' coach games, not just cold-start) — a net positive but broader than the hub; gaps ride the classifier that already has the king_safety fix.
- **PWC** offered as the secondary value path (account-less, 1 free/day).
- **Capture `player_motivation`** on the hub (reuse the shipped field).
- **Soft account-link** entry that drops them into the existing link flow when they choose it.

## 4. Explicitly out of scope (V1) — acknowledged, deferred with reasons

- **Openings for cold users (diagnose→prescribe switch).** Puzzles can't reveal a repertoire. V2: prescribe from `opening_curriculum` for their level + learn their real openings from PWC games. Deferred because it's a separate teaching flow, not the activation core.
- **Adaptive difficulty branching** in the teaser (V1 uses the existing fixed stratified selection).
- **Replacing/merging the diagnostic when real games later arrive** (the diagnostic spec already says game data supersedes after 10+ analyses — V1 doesn't touch that handoff).
- **Any per-persona coaching-tone adaptation** (still deferred from the motivation work).

## 5. Success criteria

- **Dead-on-arrival drops:** the "no account AND no coached game" rate falls from **32%** toward **<15%** for cohorts that hit the hub.
- **Cold users get *personalized* training:** ≥X% of hub-completers land on a `/training` recommendation **derived from their DNA** (verifiably their weak category, not a generic default). If the DNA still dead-ends, V1 failed regardless of nice puzzles.
- (Set X at launch from the first cohort; not a vanity "they saw the page.")

## 6. Open questions

- **RESOLVED — hub trigger:** NEW signups only (existing un-activated users deferred).
- **RESOLVED — length:** full 20, exitable; partial run still builds the profile.
- **Q: Exact weakness store the training recommender reads** (the Wiring #1 target). *Unblock: verify in code pre-code (§7) — what does `/training` / lab-coach-pick consume for a user with no games? (running now)*
- **Q: Does the soft link-ask interrupt or just sit there?** *Recommend: non-blocking, always dismissible.*

## 7. Pre-code requirements

- Mohit **signs off** this scope.
- **Verify the wiring target:** read what the training recommender + `/home` actually consume as the weakness signal for a no-game user — that's where the diagnosis must be written. (If it's `cognitive_gap_history` / `player_profiles` / a decay store, confirm the shape.)
- **Teaser length** locked (§6).
- **Hub trigger / routing point** chosen (§6).
- Confirm the diagnostic cold-serve endpoint serves a brand-new user end-to-end (start → score → result).
- **Wiring #2 ops:** flipping `PWC_GAP_ENRICHMENT=true` is a **server-side env change** (Mohit's deploy), and `regen_coach_game_gaps.py --apply` is a **prod data op** — both are part of shipping V1, sequenced like the other backfills. Spot-check enriched gaps for accuracy before the full regen (the king_safety fix is in the classifier).
