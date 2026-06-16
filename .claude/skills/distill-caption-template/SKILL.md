---
name: distill-caption-template
description: Build a gold-grade caption template for ONE mistake situation by DISTILLING it from Claude gold (not hand-authoring), with strict engine-grounded slots + an independent board-verifier, graded on "verified-AND-gold-match >= 85%". Use when raising a category/situation's caption quality (e.g. piece_safety, missed_tactic) toward gold. Supersedes hand-editing R12_blunder.json predicates for the WHY — proven 2026-06-16 that hand-editing REGRESSES (41%->36%) while distillation + strict slots + verifier reaches 63% verified-true on the first pass with 0 false claims. Trigger when the user says "get <category> to 85%", "improve the captions for <situation>", "distill a template", or "make detector <X> gold-grade".
---

# Distill a caption template from gold (the verified loop)

The lesson from 2026-06-16: the legacy R12 cascade is a tangle of fallback fillers with
gates that don't obey their docs — hand-editing it caused collateral damage and REGRESSED
the score. The replacement is ONE distilled template per situation, deterministic slots, and
a board-verifier. **Quality comes from Claude (offline, once); truth comes from the verifier
(runtime); cost stays near-zero (no runtime LLM).**

## The bar — TWO metrics, and TRUTH is the one that ships
1. **VERIFIED-TRUTH (the shippable bar, primary):** every claim is TRUE on the board (independent
   verifier passes). **This is the bar that gates shipping** — a learner must never see a false claim.
   `right-or-silent`: unverifiable claim -> abstain that clause. **piece_safety hit 11/11 verified-true.**
2. **GOLD-MATCH (a noisy quality-tracker, secondary):** does it MATCH the gold lesson (LLM judge).
   Do NOT treat 85%-match as the gate — it is gated by THREE things that are NOT the template:
   - **Judge noise at small n** — the SAME captions scored 63% one run, 72% the next at n=11
     (+-10-18%). Need **~50 moves/situation** before a match number is stable enough to "lock."
   - **Gold quality** — the gold itself overclaims (piece_safety: 2/11 golds said "supports e4"
     when the move does NOT cover e4). A truthful caption gets PARTIAL for not repeating a false
     gold claim. **You MUST verify the gold (step 5b) before grading against it.**
   - **Principle-variation** — one fixed principle can't match the gold's situation-specific one
     (Qc3's gold teaches "scan for checks"). Needs a sub-case principle-bank (step 6b).
A 72%-style-match with one false claim is WORSE than 63% all-true. **Optimize verified-truth; treat
gold-match as a direction, not a finish line, until the gold is clean and the sample is ~50.**

## Steps

1. **Pull the gold for the situation.** `db.gold_captions` filtered by `cognitive_gap` (+ optionally
   `created_by` per user). If thin, generate more first with `build_gold_set.py --user <id> --tag <t>
   --per-gap N` (engine-verified Claude gold; ~40-60 examples per situation is the working number).
   Connect via the **stable direct DB** (`mongodb://...@72.60.204.176:27017`), NOT the flaky tunnel.

2. **Compute deterministic, STRICT engine slots per move** (python-chess on `fen_before` + stored
   `pv_after_played` / `pv_after_best`). The structured facts, e.g. for piece_safety:
   - `hung_piece` / `hung_square` = the USER's own piece captured by `pv_after_played[0]` (color == mover).
   - `check_phrase` = " with check" iff the reply gives check.
   - `best_purpose` — **STRICT attribution**: only claim "defends X" if the *moved piece itself* covers X
     after the move (`X in board_after.attacks(best.to_square)`), NOT if some other piece already did.
     Order: capture > (develops AND strict-defends) > strict-defends > attacks-a-valuable-piece > develops.
     If none fire, `best_purpose` stays EMPTY (the why abstains — don't pad).

3. **Distill ONE template** (Claude, offline, ONCE per situation). Prompt: "here are N (FACTS, GOLD)
   examples; write one str.format template using ONLY these slots {…}; max 2 sentences; end with one
   fixed universal principle." Claude returns `{"template": "..."}`. This is the only Claude call that
   ships into the pipeline path — and it happens once.

4. **Render deterministically + VERIFY every claim independently** (re-derive from the board, do NOT
   trust the slot's own computation — defense in depth). Verifier must cover EVERY claim type the
   template can emit: hang (reply captures piece on square), check, capture, defends (moved piece
   covers it), develops (minor from back rank), attacks (moved piece attacks the named enemy piece).
   Any failure -> abstain the offending clause (or the caption).

5. **Judge verified captions vs gold** (LLM judge, validate-the-judge first: gold-vs-self must MATCH,
   gold-vs-empty must MISS). Report verified-AND-match % + shortfall examples.

5b. **VERIFY THE GOLD too (mandatory).** Board-check the gold's own claims (e.g. "supports/defends
   {sq}" -> does the gold's recommended move actually cover {sq}?). Golds that overclaim are DEFECTIVE
   — exclude them from the denominator (or fix them). Grading against unverified gold is how a false
   "supports e4" becomes the standard. piece_safety: 2/11 golds were loose this way.

6. **Iterate SLOTS, not the cascade.** PARTIALs are almost always a *missing slot* (e.g. a quiet
   "fights-for-the-center" purpose, "lead-with-check" on a capture, "develops-eyeing-f7") or wrong slot
   ORDER — add the slot + ITS verifier checker, re-run. Each slot must be STRICT + verified.

6b. **Principle-bank keyed to sub-case.** A single fixed ending principle can't match varied gold
   principles. Key the principle to the failure sub-type (missed-check -> "scan for checks first";
   hung-piece -> "check every piece is defended"). Small bank, authored once.

7. **Stop at verified-truth = 100%, not at a noisy 85%-match.** If a situation's why is irreducibly
   positional (king_safety, pawn_structure), it **abstains by design** — never force it. The deliverable
   is: 0 false claims shipped + the highest match achievable on CLEAN gold at n>=50.

## What NOT to do
- Don't hand-edit `R12_blunder.json` why-clauses to chase a category — proven to regress + whack-a-mole.
- Don't grade on style-match alone — always gate on the verifier (the "h3 defends e5" false-positive
  shipped because the verifier had no "defends" checker; the template introduced a claim the verifier
  didn't cover).
- Don't add a verifier checker AFTER shipping the claim — every new claim type needs its checker FIRST.
- Don't run runtime Claude. Distillation is offline; rendering is template-fill + verify.

## Two SYSTEMIC prerequisites for a rollout (found 2026-06-16, the hard way)
1. **Clean taxonomy first.** Distillation works on CLEAN situations and stalls on vague buckets — the
   old `tactical_oversight` capped at 33% because it mixes hangs/missed-wins/mates. Re-classify gold into
   the clean 15-cat taxonomy (`classify_fundamentals.classify`) BEFORE distilling. The vague bucket split
   into missed_mate:17 / one_move_blunder:11 / walked_into_tactic:3 — each distills far better alone.
2. **Stored PV depth caps tactical specificity.** Our stored `pv_after_best` is often TRUNCATED, so
   missed_mate could only say "a forcing line that wins" not "Qg8# mate in 2" (capped ~33%). SHALLOW
   situations are fine (one_move_blunder / walked_into_tactic / missed_free_material name the hung/captured
   piece from the immediate position + short PV — piece_safety hit 72% with no deeper data). DEEP situations
   (missed_mate, multi-move combos) need deeper stored PVs (re-analyze) or Stockfish-at-distill-time.
   ROLLOUT ORDER: shallow clean situations now; deep ones after PV-deepening; positional abstain.

## Reuse
- `build_gold_set.py` (gold gen), `narrator_claim_verifier.py` (extend its checkers per new claim type),
  the judge pattern from `judge_vs_gold.py`, `build_move_teaching_decision` (serving layer).
- Scratch proof scripts from 2026-06-16: distill_proof.py / verify_match.py (the working harness).

## Measured result (2026-06-16, piece_safety, Shobhit held-out, 11 moves)
- hand-editing the cascade: 41% -> 36% (REGRESSED, collateral damage — DO NOT hand-edit)
- distilled template, loose slots, no verifier: 72% style-match BUT shipped 1 false claim ("h3 defends e5")
- distilled + STRICT slots + verifier: 11/11 verified-true, 63% match, 0 MISS
- + 3 slot passes (center / lead-with-check / develops-eyeing-f7) + double-check fix + gold-verify:
  **TRUTH BAR MET — 11/11 verified-true, 0 lies.** Match settled at ~63-72% (judge-noisy at n=11),
  with 2/11 golds themselves overclaiming and 1 positional residue (e3) abstaining the why.
- VERDICT: the shippable guarantee (never lie) is ACHIEVED for piece_safety. A *stable* 85%-match
  needs clean gold + ~50-move sample + sub-case principle-bank — measurement work, not template work.
- Per-situation cost (measured): ~35-60 gold (mostly already collected) + ~2 hrs slot work. No big
  Claude spend. Multiply by ~40-60 engine-decidable situations; positional ones abstain.
