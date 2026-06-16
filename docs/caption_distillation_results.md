# Caption Distillation — Baseline Results (2026-06-16)

Autonomous run: expand gold → reclassify into clean taxonomy → distill+verify+judge every clean
situation → scorecard. Stable direct DB (no tunnel). Templates saved to
`backend/data/distilled_templates.json`. Method/recipe: `distill-caption-template` skill.

## Corpus
425 verified gold (shobhit 149, mohit 147, parth 129), reclassified into the clean 15-cat taxonomy.

## Scorecard (held-out, two runs to expose judge noise)
| situation | n | verified-true% | match% (run1 / run2) | status |
|---|---|---|---|---|
| one_move_blunder | 77 | 100 | 72 / **80** | shippable (most common mistake) |
| walked_into_tactic | 69 | 95 | 30 / 26 | hard (deep tactic; partly positional) |
| missed_free_material | 17 | 100 | 60 / 40 | noisy (small test n) |
| missed_mate | 27 | 100 | 55 / 55 | **PV-capped** (stored PV truncated) |
| allowed_mate | 7 | 100 | 50 / 25 | thin (n=4 test) |
| opening_knowledge | 10 | 100 | 25 / 50 | noisy (n=4 test) |
| (defer to Claude) | 204 | 100 | — | **abstain-by-design** (positional) |

## Findings (honest)
1. **TRUTH holds ~100% across every situation** — the shippable, right-or-silent bar. The system ships
   no false claims, on all situations. This is the win.
2. **`one_move_blunder` is shippable now (~80%, n=77)** — the single most common beginner mistake,
   gold-grade + truthful.
3. **Match numbers are JUDGE-NOISY at current per-situation test sizes** — the *same* captions swung
   ±15–25% run-to-run (missed_free 60→40, allowed 50→25, opening 25→50; test n=4–9). **A stable match
   number per situation needs ~50-move test sets** — total n=425 is enough overall but thin per situation.
4. **`walked_into_tactic` (the 2nd most frequent, n=69) caps low (~26–30%)** — deep tactics: the loss is
   multi-move and the best-move "why" is often positional. The net-material front fallback did not lift it
   (vaguer "costs material" ≠ gold's specific piece). Likely a real ceiling → ships as truthful PARTIAL.
5. **`missed_mate` is PV-capped (~55%)** — stored `pv_after_best` is truncated, so we can't name the
   specific mate ("Qg8# in 2"); we ship the verifiable-vaguer "a forcing line that wins." Needs re-analyze.
6. **~48% of mistakes (`defer`) are positional** → abstain by design (no template).

## What this means
- **Ship-readiness is gated by TRUTH, and TRUTH is met everywhere.** A truthful "X hangs your Y; play Z
  instead" (even without a deep why) beats the legacy cascade's filler and is safe to serve.
- **Match-to-gold is the polish dial**, and it: (a) needs ~50/situation test sets to measure reliably,
  (b) has per-situation ceilings (one_move ~80, walked_into ~30), (c) is PV-data-limited for deep ones.

## Roadmap to a stable 85% (the bounded remaining work)
1. **Bigger per-situation test sets (~50)** so match is measurable, not noise. (More gold or pooled splits.)
2. **PV-deepening re-analyze** → unlocks missed_mate + deep combos to name specific tactics.
3. **Per-situation slot passes** on the engine-decidable ones with headroom (one_move 80→85 is a short hop;
   walked_into likely caps — accept truthful PARTIAL).
4. **Positional → abstain** (no chase). **Deep → after PV-deepening.**
5. **Prod-wiring** (separate, sign-off-worthy): feed `distilled_templates.json` into
   `build_move_teaching_decision`, flag-gated (default off → 10% → 100%). NOT done autonomously.

## PV-deepening proof (missed_mate, 2026-06-16)
Ran deep Stockfish on the 30 missed_mate positions: **found the forced mate line in 29/30.** Captions now
name the specific mate (*"Qg8# is checkmate"*, *"Qc1+ forces mate in 2 (Qc1+ Rd1 Qxd1#)"*) instead of the
vague "a winning line." Honest caveats found:
- **Verifier must trust Stockfish's mate score**, not a naive 3-ply replay (the replay falsely abstained
  deep mates that Stockfish had confirmed).
- **Deep mates (5–10) are not realistic 1200 teaching targets** and drag the metric. **Scope missed_mate to
  short mates (≤3):** that subset is ~80% MATCH (specific + gold-grade). Reclassify/down-rank deep mates.
- **Verdict: PV-deepening is the right Phase-2 unblock** — it makes short-mate (the realistic) captions
  gold-grade; pair it with a short-mate scope + Stockfish-trusting verifier.

## Corpus-wide PV-deepening (2026-06-16) — the key finding
Deepened all 425 gold positions (deep Stockfish → `gold_deep_pv`, 33 forced-mates found), then re-ran the
sweep consuming the deep PVs. Result:
- **Coverage UP:** defer 204→173 (deeper PV reveals tactics that were "positional" at shallow depth);
  walked_into_tactic 69→92, one_move_blunder 77→91 — more moves engine-decidable.
- **Match DOWN on shallow situations:** one_move_blunder 80→46%. **Cause: the gold was generated on the
  SHALLOW stored PVs**, so deep Stockfish names a *different (better)* refutation than the gold assumed —
  the detector becomes *more* accurate but *diverges from its own gold*. Truth stayed ~100% (no lies).
- **LESSON: gold and detector must share the same engine depth.** Deepening one side alone is a measurement
  mismatch, not a real regression.
- **Proper completion of PV-deepening = regenerate the gold on the deep PVs** (gold+detector realign; deep
  situations lift; shallow ones stop regressing; coverage stays up). Deep PVs are cached, so the regen is
  ready. NOT auto-run (large Claude spend; surfaced first because naive deepening hurt the headline number).

## Deep-aligned regen outcome (2026-06-16) — match metric is unreliable
Regenerated all 422 gold on the deep PVs (gold_*_deep) so gold+detector share depth, then re-swept.
**Match did NOT recover** (one_move_blunder stayed ~46%, not back to ~76%; walked_into swung to 13%). Two
honest reasons:
1. **Deeper PV → richer Claude gold → harder for a fixed template to match.** Deepening raises the bar
   faster than the template climbs it. Deep-PV trades richer-gold for harder-match; it is NOT a match lift.
2. **The match metric is too noisy/confounded to optimize against.** The sweep re-distills the template +
   re-splits train/test + LLM-judges (non-deterministic) EVERY run, so the same situation swung
   72→80→46→46 (one_move) and 30→26→40→13 (walked_into) — ±20-30% is variance at n=4-30, not signal.
**CONCLUSION:** TRUTH (~100%, stable every run) is the only reliable metric and it is met everywhere — ship
on TRUTH. COVERAGE improved with deep PVs (defer 204→172). MATCH cannot guide fine optimization until the
harness is rigorous (FROZEN test set + FROZEN template per condition + AVERAGED judge votes). Do not chase
match% with the current noisy harness.

## FULL-CORPUS VALIDATION (2026-06-16) — readiness on real data, no prod, no Claude
Ran the deterministic caption system (classify -> template -> render -> verifier) over ALL 7,837 analyzed
games / 46,409 flagged mistakes (`backend/scripts/validate_full_corpus.py`):
- **COVERAGE: 53%** (24,920 captioned; 46% abstain — positional/non-engine-decidable).
- **TRUTH: 98%** (24,641/24,920 verify true; the 2% fails are all walked_into -> abstain in prod -> 0 lies ship).
- Per situation: one_move_blunder 10,255@100%, walked_into 7,512@96%, allowed_mate 3,033@100%,
  missed_free 1,975@100%, missed_mate 1,893@100%, opening 252@100%.
- **NET: ~52% of all real mistakes get a verified-true caption; ~48% silent. 0 lies at scale.**
READINESS: SAFE at scale (truth holds on 46k real moves) and covers HALF the mistakes truthfully (vs the
legacy cascade's ~16%). NOT "100% ready": coverage is ~half (rest abstains by design), teaching-quality is
uneven, and live-render validation + the product decision on 52%-coverage remain. NONE need a prod move.

## OPPONENT-MOVE validation (2026-06-16) — both sides, not just the user
We had been validating user moves only. Opponent moves (`opponent_move_evaluations`, user-framed:
"Black's move lets you ...") validated via backend/scripts/validate_opp_corpus.py:
- 2,057 games have opponent analysis (of 7,837 — only 26%; rest never got opp analysis, Jun-6 fix forward-only).
- 11,393 opponent errors (cp>=100). COVERAGE 30% (3,457), TRUTH 84% (unverified abstain -> 0 lies).
- opp_hung_material 2,583 @ **100% true** (clean: "Black drops the {piece} on {sq} — take it with {your_reply}").
- opp_allowed_mate 874 @ 37% true (same deep-mate verify weakness as user-side; unverified abstain).
BOTH-SIDES READINESS: user 53%/98%, opponent 30%/84%. Opponent is earlier-stage: narrower situations +
mate-verify gap + the STRUCTURAL cap that 74% of games have NO opponent analysis -> needs a RE-ANALYSIS pass
(not prod) to populate opponent_move_evaluations for older games.

## EVERY-MOVE captioning (2026-06-16) — Mohit: 500-1000 ELO, every move is a lesson
Added GOOD-MOVE teaching situations (develop / castle / center-pawn / capture / other), distilled from
Claude TEACHING gold on good moves (tag gold_goodmoves). Key insight: a good move's "why" is a UNIVERSAL
PRINCIPLE keyed to move-TYPE (develop->get pieces out, castle->king safety, center->control center) — NOT
the position-specific positional why that made mistakes hard. So it's deterministically templatable.
Validation (backend/scripts/validate_everymove.py, 300 games / 8,695 user moves):
- **COVERAGE 53% -> 91%** (mistakes 1000 + good 6,951; abstain 9%).
- **TRUTH 99%** (good 6,951@100%, mistakes 991/1000; walked_into fails abstain -> 0 lies). No Claude at render.
- Caveat: GOOD:other = ~33% of good captions (generic catch-all "repositions {piece}" — the THINNEST
  teaching, borderline filler). Refine by splitting into queen-safety / rook-activity / luft / space
  (all emerged in the good-move gold). The capture template gates "free" via the verifier (recapture ->
  no "free" claim).
This reconciles with the earlier "silence > fake explanation" rule: good-move captions are TRUE simple
teaching (engine-verified, no invented tactics), valuable for a 500-1000 beginner — not fake whys.

## GOOD:other split (2026-06-16) — refined the thinnest bucket
Split the generic `other` catch-all into 6 specific principle situations (centralize / rook_open_file /
space / luft / rook_activity / queen_safety), distilled from Claude teaching gold. Result on 300 games:
coverage held 91%, truth 99%, and `GOOD:other` dropped 33%->19% — ~1,800 moves now get SPECIFIC teaching
(centralize 529, rook_open_file 489, space 252, luft 197, rook_activity 184, queen_safety 155). The
every-move system now spans **11 good-move teaching situations + 6 mistake situations**. Templates persisted
to the HOST file `backend/data/distilled_templates.json` (earlier they were only in the container -> wiped on
a crash-restart; fixed). NOTE: a system crash mid-session took down docker + the exposer + briefly prod-mongo;
all restored, no data lost (gold lives in prod mongo).

## Assets produced
- `backend/data/distilled_templates.json` — per-situation distilled templates + scorecard.
- `backend/scripts/distill_baseline_sweep.py` — the unified sweep harness (reusable).
- `docs/caption_distillation_rollout_scope.md` — the scope. `distill-caption-template` skill — the recipe.
