# Why-Now Coach Layer (Verified Concept Coach) — Scope

**Status:** Draft for sign-off. No code until Mohit approves the build order.
**Date:** 2026-06-18
**Goal:** close the 23-vs-53 caption gap — answer *"why THIS move in THIS position,"* not "what Nf3 is" — while staying deterministic, board-verifiable, cheap (no runtime LLM), and explainable.

## First principle (non-negotiable)

> **Retrieval does not remove hallucination — it moves hallucination into the detectors.**

A concept library is a set of *claims*. Every claim lies if not board/engine-verified. We proved this all session: "attacks e5" lied when Black's pawn was on c5; "open file" lied on a half-open file; "free" lied on a defended piece. Therefore **every detector ships with its own verifier, authored FIRST.** The retrieval/assembly plumbing is the easy 10%; the verified detectors are the hard, valuable 90%.

**Corollary:** 20 detectors × high accuracy × high frequency beats 10,000 pretty snippets × weak verification. We start at ~20, prove lift, then scale — never 10k up front (that's a regression machine).

## ★★ LOCKED ARCHITECTURE (2026-06-18) — the selector is the keystone

Settled after a long design pass. The score gap to gold (23→53) is **four distinct deficits masquerading as one number** — do NOT expect one subsystem to absorb it, and **measure each increment on the blind harness** (the components are NOT guaranteed additive; selection + calibration interact, and fixing selection can unmask calibration errors verbosity was hiding):

| Component | Est. lift | Priority |
|---|---|---|
| **Lesson selector** (kills verbosity; say ONE thing) | 23 → ~35–42 | **1** |
| **Cross-move state** ("still missing the same pawn") | +3–6 | 2 |
| **Detector calibration framework** | +4–8 | 3 |
| **PV-intention layer** | (folded in) | 4 |
| **Positional depth** | remaining | 5 |

**1. The lesson selector is the biggest single lever** — our slot-composer scored 24% *because it had no selector and emitted 8 facts*. Gold wins by saying ONE thing. Two scores, not one:
- `urgency_score` — engine-grounded, verifiable (hang/tactic/material/king-safety).
- `teaching_value_score` — pedagogical (gold often picks the most *teachable* thing, not the most urgent — e.g. "develop + castle" while ignoring a 0.2 pawn).
- Weighted by **LEVEL = rating** (reliable + available NOW; beginner→teaching dominates, advanced→urgency). Per-user *weakness* weighting is **Phase 4** (gated on the cognitive_gap audit — that data is ~2% today; see [[project_focus_loop_gate0_cognitive_gap]]).

**2. The one substrate — the aligned-corpus-table.** Built from the whole-game gold:
`position → {active detector firings} → gold caption → gold's chosen lesson`. It powers three things at once:
- **Selector training** — learn the **CONDITIONAL** choice (*given concepts {free-pawn, develop, castle} present, which did gold pick?*), NOT the marginal frequency ("development 43%" = what's common, not what's chosen under competition). The #127-vs-#128 dataset.
- **Detector calibration** — firing distributions; "where does gold *start* saying passive" (calibrate thresholds from the distribution, never guessed — the threshold-before-distribution sin).
- **False-positive mining** — *detector fired but gold stayed silent* = prime false-positive (the structural fix for the open-file/safe-square/attacks-e5 bug pattern; gold = silent oracle).
- **Positional residual = a shrinking work-queue**: gold captions with **zero** relevant firings = the "decompose next" backlog + a live metric (% gold unexplained). "Irreducibly positional" is *not-yet-decomposed*, not a wall — decompose until marginal ROI < the next-priority work.

**Known dependency risk:** mapping gold caption → one lesson label is a hidden classifier — validate it (held-out check), or the selector learns from noisy labels.

**3. Measurement-infra BEFORE more detectors.** Every detector auto-reports fires_per_1000 / distribution / false-pos+neg samples / judge-disagreement. Calibrate features (mobility-delta "passive", attacker-delta "trade calms attack", structure-diff "pawn shape") from 100k-position distributions + where gold agrees — not guessed thresholds.

**Roadmap:** P1 = verified detectors + PV-intention + rating-weighted selector (can already beat today's 23). P2 = distribution-calibrated ranking. P3 = cognitive_gap audit. P4 = personalized (weakness-weighted) selection.
**~50–100 verified detectors + ~20 lesson types + 1 selector + game-state layer** — NOT 10,000 detectors.

## ⚠️ CRITICAL: most of this ALREADY EXISTS — reuse, don't rebuild (single-source)

A code survey (2026-06-18) found the proposed architecture is **substantially already built**, just not wired to the no-LLM path we've been improving. Building a new detector set would VIOLATE [[feedback_single_source_of_truth]] — the lesson of this very session.

| Layer | Already exists as | Status |
|---|---|---|
| Verified concept **detectors** | **`caption_facts.py`** — "the canonical chess-semantics layer; facts are the gold." Emits board-verified `attacker_count`/`defender_count`/`effective_attackers_on_target`, `hanging`/`undefended`, `fork`/`pin`/`discovered_attack`, `castle`/`king_safety`/`enemy_king_square`, `passed_pawn`, `recapture`, `development`, `tempo`, full `best_move` tactic layer. Has a tactic-shape **detector registry**. | **REUSE** |
| Urgency **ranking** | **`caption_priority_resolver.py`** — "collapses 9 branches into ONE decision; facts are gold, LLM only verbalizes." | **REUSE** |
| Compose / serve | **`caption_pipeline.py`** — facts → resolve → render (the central layer). | **REUSE** |
| First principle | Already locked as `renderer_never_computes_chess_meaning` ("facts are gold; renderer/LLM only verbalizes") == "retrieval moves hallucination into the detectors." | already law |

**The actual gap:** the **distilled (no-LLM) renderer** (`distilled_caption_service.py`, what we've been baking) has **0** references to `caption_facts` — it's a parallel move-TYPE-template path. That is precisely why it's generic and loses 23-vs-53: it ignores the rich, already-verified, position-specific facts that `caption_facts` computes.

**Revised build (single-source-compliant, much smaller):**
1. Make the distilled snippet renderer **consume `caption_facts`** (reuse the canonical verified facts) instead of move-type templates.
2. **Rank via `caption_priority_resolver`** (reuse).
3. Distil easy-English **snippets keyed to caption_facts' fact keys** (the proven distillation method).
4. **EXTEND `caption_facts` only for genuinely thin concepts** (the mining showed `center`/`open_file` are weakly covered) — add them INTO the canonical layer + its verifier, never a parallel module.

The "build 15 detectors" framing below is SUPERSEDED by this: ~most detectors already exist in `caption_facts`; the work is wiring + snippets + a couple of gap concepts. This is smaller, higher-confidence, and single-source-correct.

## Pipeline (endorsed)

```
Position
  ↓
Engine / PV truth            (Stockfish eval + top 3-5 ply continuation = ground truth)
  ↓
Verified concept detectors   (each: board verifier (+PV verifier) + negative tests + confidence)
  ↓
Urgency ranking              ("why NOW" — the most urgent true reason wins)
  ↓
Safe snippet assembly        (compose 2-3 approved snippets for the top-ranked concepts)
  ↓
Optional personalization     (the moat — gated on cognitive_gap accuracy being audited first)
```

Explicitly **NOT** `concept library → retrieve a nice explanation` (too dangerous — unverified).

## What a detector MUST have (the contract)

Each detector is a small module that, given (fen_before, played_move, pv_after_played, pv_after_best, eval), returns `fired: bool, confidence: float, slots: {...}` and is paired with:
1. **board verifier** — re-derives the claim from the board independently (defense in depth; don't trust the detector's own computation).
2. **engine/PV verifier** — when the claim depends on a line (tactic, plan, punishment), confirm it in the PV.
3. **negative tests** — positions where it must NOT fire (e.g. "attacks e5" must not fire with no enemy pawn on e5; "open file" must not fire on a half-open file).
4. **approved snippet** — the easy-English fragment (distilled from gold, the proven method), one per detector.
5. **confidence score** — used by ranking + a floor below which the detector abstains.

A detector with a failing/absent verifier does not ship. (This is the `verify-detectors-first` discipline + the existing user-games detector loop.)

## First batch — ~15 detectors, ORDERED BY MINED FREQUENCY (data-first)

Source: `scripts/mine_gold_concepts.py` over the 866-caption corpus (% = share of captions touching the concept; the Opus extraction pass agreed). **The data reordered the intuition list — build top-down:**

| # | Detector | mined freq | verifiable | note vs original intuition |
|---|---|---|---|---|
| 1 | king-safety / can-castle / should-castle | **21%** | yes | top concept — build first |
| 2 | center control / center tension | **18%** | yes | |
| 3 | immediate tactic / check in PV | **18%** | yes | "check" is huge; pair with tactic-in-PV |
| 4 | attack-square actually attacked | **16%** | yes | the moved piece truly hits the named target |
| 5 | hanging piece + defended-piece-NOT-free | **12%** | yes | kills the "free on defended" lie |
| 6 | recapture / trade-keeps-material-even | **9%** | yes | |
| 7 | **move attacked piece to safety** | **8%** | yes | **PROMOTED — mining surfaced this; wasn't in the 15** |
| 8 | tempo / queen chased / queen out early | **7%** | yes/partial | |
| 9 | **add-a-defender / count attackers vs defenders** | **6%** | yes | **PROMOTED — the core material-safety check** |
| 10 | development / behind in development | **6%** | yes | |
| 11 | piece improves to active square | 5% | partial | |
| 12 | gain space | 4.5% | partial | |

**DEMOTED (your list ranked these, but the data says they're rare → defer to batch 2):**
open-vs-half-open file **(1.2%)**, same-piece-moved-twice **(0.5%)**, pin (0.4%), pawn-break (0.4%), fork (0.1%), passed-pawn (0.1%), mate (0%). They matter *when they occur* and stay board-verifiable — just low-frequency, so lower ROI for the first batch.

Each lands with verifier + negative tests + snippet + confidence.

## Urgency ranking ("why now")

When several detectors fire, rank by urgency and surface the top 1-3:
`immediate tactic > hanging/defended-material > king exposed > center tension / pawn break > development/tempo > positional improvement`.
The caption leads with the most urgent TRUE reason — that is the "why now."

## Example assembled caption (the artifact)

Move `Nf3`, detectors fire: {development, attacks-e5 (verified: Black pawn on e5, Nf3 attacks it), can-castle-next (PV shows O-O)}.
> "Nf3 brings your knight out and hits the pawn on e5. It also gets you ready to castle next. Getting pieces out early and castling keeps your king safe."

Every clause traces to a fired+verified detector. No clause without a detector.

## Personalization (the moat — last, and gated)

ChessGuru knows the student's weaknesses (`cognitive_gap`) — gold can't. Personalize the *emphasis* ("you've missed development lately, so getting pieces out matters here"). **BUT** cognitive_gap detection is currently ~2% and unaudited — personalizing on bad gap data is worse than none. **Prerequisite: audit cognitive_gap accuracy before this layer ships.**

## PROOF-SLICE RESULT (2026-06-18) — caption_facts wiring does NOT close the gap

Wired the distilled renderer to consume `caption_facts` for the capture/material concept (names the real defender from `effective_defenders_on_target`, with the net-material guard). Re-ran the blind harness:

- **No lift: 22-53 (was 23-53), 0 board-lies.** The wiring is correct + safe (won 11:dxc4, 17:exd6, 21:Rxe4) — but the aggregate didn't move.
- **Why:** the 23-53 gap is NOT on captures (where caption_facts is rich, ~10 moves) — it's on **quiet/opening moves** where gold wins by (a) **naming the engine's slightly-better move** (Nf3, Be3) and (b) being clearer/more specific. `caption_facts` is *thin* on quiet moves (returns just `best_move_san` + a count), so consuming it doesn't help where the gap lives.
- **Located the ceiling precisely:** quiet-move "why-now" = name-the-better-move tastefully + explain the plan. That is LLM-shaped, not facts-shaped. The cheap deterministic levers left are narrow (e.g. a careful "better-move" mention, risky to do without sounding preachy on equal moves).
- **Decision:** do NOT scale the caption_facts wiring expecting the gap to close. It improves tactical captions (keep it), but closing the quiet-move gap likely needs a cheap LLM (the hybrid from the earlier rethink) — re-open that trade-off rather than building more deterministic detectors for quiet moves.

## Build order & acceptance

1. **Mine gold** → ranked concept frequency + board-verifiability flag (data-first; decides the batch).
2. **Build the ~15 detectors** (verifier-first), lead with why-now + PV-intention.
3. **Compose + rank** → assemble verified snippets.
4. **Measure on the comparison harness** (blind A/B vs easy-English Opus gold + board verifier).
   **Acceptance: lift the demo game from 23 → ~35-40+ system wins with 0 board-verified lies.** Do NOT scale past ~20 detectors until the harness proves the lift.
5. Personalization — after the cognitive_gap audit.

## Out of scope (rejected / deferred)
- **Neural "tiny specialist models"** — rejected: breaks determinism/verifiability/cheapness. Realize "specialists" as deterministic detector modules, not ML.
- **Good-move counterfactuals** — deferred: unverifiable speculation. Counterfactuals only for MISTAKES (the engine punishment line is the verifiable counterfactual).
- **10k-50k concept library** — deferred until ~20 verified detectors prove lift.

## Names
**Verified Concept Coach** (internal/engineering) · **Why-Now Coach Layer** (product) — the value is *why this move matters now*, not what the move is.

## Ties to existing work
[[project_user_games_gold_detector_loop]] (detectors assert engine-confirmed facts), [[project_move_classification_taxonomy]] (the 15-cat classifier), [[project_focus_loop_gate0_cognitive_gap]] (gap data — audit first), `narrator_claim_verifier` (extend per claim type), `distill-caption-template` (snippet distillation), `verify-detectors-first`.
