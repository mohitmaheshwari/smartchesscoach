# The ChessGuru Evidence Board

**What this is:** governance, not inventory. Every row forces a decision.
No architecture, no implementation notes — those live elsewhere. If a
row can't produce a Decision, it isn't ready to be on this board yet;
go find out more first.

**The rule that comes with this document**: before discussing a new
feature, ask *"which row does this strengthen?"* If the answer is
"none," it doesn't get built. If it would need a new row, the new row
gets written and evidenced *before* the feature does.

**Owner:** product governance stream. **Reviewed:** every Friday
research meeting — did any row's Decision change this week?

---

| System | User Problem Solved | Live? | User Value | Evidence | Decision |
|---|---|---|---|---|---|
| **Universal Habit Coach** | Reduce a repeated mistake via an in-game reminder at the moment it matters | Yes — 8 of 62 eligible users | Medium (real, unproven at scale) | Low-Medium — real 4v4 randomized holdout, 68% vs. 48% clean-rate, promising but underpowered | **Expand experiment** to full eligible population (Experiment #1, this week) |
| **Root-cause captions** (turning-point callback) | Explain the real earlier cause of a mistake, not just the symptom move | Yes | High — real examples read as a genuine differentiator ("this spot got hard around move 48... the real fix is earlier") | Low-Medium — mechanism is real and firing; zero outcome data on whether it teaches more durably than move-specific coaching | **Queue as Experiment #2**, after #1 |
| **Meta Patterns** (25 psychology/causal composition rules) | Higher-order coaching — tilt, overconfidence, confidence illusion, not just "you blundered" | **No** — well-built, confirmed unreachable from any live route | Unknown — never reached a real user | None — never fired in production | **Integrate safely**: trace the single lowest-risk live surface, wire behind a flag, verify output before wider rollout |
| **Coach Notes** (`player_identities.coach_notes`) | Long-term memory — the literal "coach's notebook" concept | Partial — real for 1 of 5 sampled users, empty for the rest | Unknown | None | **Investigate** trigger coverage before deciding whether to fix generation or retire the field |
| **Player Identity** (`player_identities` — style_profile, behavioral_profile, learning_velocity) | Personalization — "does the coach know me" | Yes — 63/114 users, read unconditionally into game review and Home | Medium — real differentiated style data, but narrow effect (threshold-gating only, not sentence content) | **Resolved 2026-08-07**: `style_profile` genuinely computed and live. The 4 named fields are worse than "stuck at a default" — they're double-orphaned. Two independent writers exist: `player_identity.py`'s dataclass declares `post_blunder_accuracy`/`recovery_capability`/`plays_worse_after_loss`/`overall_improvement_rate` as constructor defaults that are never assigned anywhere; `analysis_worker.py`'s dominant dict-based writer (the path most users actually go through) doesn't even include those keys in its writes. Only `post_blunder_accuracy` has any reader at all (`behavioral_coaching_layer.py:diagnose_player_behavior`), and every one of its 3 call chains is independently broken: `GET /api/coach/behavioral-profile` calls a nonexistent `get_player_identity()` method (only `get_or_create()` exists) and isn't wrapped in try/except — 500s every call, frontend never calls this route; `POST /api/coach/teaching/feedback` hits the same nonexistent method but is silently swallowed by try/except; `routes/openings.py` imports a nonexistent `get_behavioral_coaching_feedback` function, `ImportError` caught silently, and even if it worked the frontend never reads the resulting field | **Retire**: delete the 4 fields from the dataclass/model and the dead `diagnose_player_behavior` reader — there is no working path from write to a real user for any of them, confirmed end-to-end, not a wiring gap to "finish" |
| **Pattern Decay** (`user_pattern_decay`) | Recency-weighted weakness tracking instead of a lifetime count | Yes — every Home load, unconditionally | Medium-High — the product's own stated key differentiator, and the evidence backs it | Medium — internally consistent, live-verified, was the correction mechanism for a real classifier bug found and fixed this year | **Keep as-is**, monitor via weekly review |
| **Thinking Scores** (per-game habit composite) | "How well did you think this game" — the closest existing thing to an Improvement Score | Yes — 12,676 docs, feeds the focus system | Medium — real per-game signal, one hop removed from anything a user reads directly | Low — feeds real decisions but has never been outcome-validated itself | **Investigate** as the seed of a real composite Improvement Score (a confirmed open gap — no single longitudinal score exists today) |
| **Daily Fix** (rush-drill + practice streak) | A solo daily-return habit loop | Backend yes, entry point orphaned | Unknown — currently unreachable from Home | None | **Genuine open decision, not a bug**: reconcile with Home's "one action" system, which now solves the same problem differently — decide merge, retire, or separate surface |
| **Coaching Prescriptions** | Structured training-plan tracking and acceptance | Partial — data alive (2 real active users, still auto-creating), standalone UI orphaned | Low-Medium — real but thin, quietly enriching 3 other live surfaces | None — no causal outcome measurement | **Open decision**: revive the accept/browse UI, or formalize silent auto-promotion — not urgent, not dead |
| **PWC Coach Conductor** (STATE, never ASK + narrative threads) | Real-time in-game teaching | Yes — governs the primary live-play caption surface | Presumed High (it's what most PWC users actually read) — unmeasured directly | None | **Resolve the ask/state conflict** per the manifesto (§3.1) — the blanket override should defer to the existing rating/repetition gate |
| **PWC quiz surfaces** (escape-squares, predict-move, rate-move, habit-prompt) | Unclear — possibly superseded by the Conductor's narrative engine, possibly complementary | Yes — still wired | Unknown — never measured | None | **Investigate before deciding** — same forensic-first discipline as everything else this session; do not purge on assumption |
| **Teaching Recall** (`user_teaching_memory`) | "Have I explained this to you before" cross-session recall | Partial — read path code-live but never exercised, write path orphaned since 2026-05-18 | **Correction, 2026-08-07**: previously described as "confidently serves 2.5+ months of stale memory" — that was wrong. Direct DB proof: `coach_messages` has 0/755 docs of `type: "v5_teaching"`, ever, for any user. Never once served anything | Strong — 29,974 docs, writer last wrote 2026-05-18 (single backfill-script run, never had an incremental hook), 4 fresh 2026-08-07 games with 96 gold-eligible fires produced 0 new index entries; reader is gated behind `pwc_v5_teaching`, on for only 2 internal accounts since day one; recency decay (14-day half-life, ~40-day cutoff) means every existing entry is now too old to surface even if the flag were flipped for everyone today | **Retire, don't restore** (with caveat): this shipped to a 2-person internal cohort and was abandoned on both ends simultaneously — not a load-bearing feature silently regressing under real users. If Mohit wants it shipped: (1) wire the writer into the postgame-analysis-complete path, (2) backfill the 2026-05-18→today gap, (3) expand `pwc_v5_teaching` past the internal cohort. Otherwise remove the dead `depth_explanations.py` Level-3 reader (zero callers anywhere) and leave the rest as documented-dead rather than re-investigated again |
| **Diagnostic onboarding** | Fast initial skill read for a brand-new user | Yes | Low — 8% real completion, 42% abandon before puzzle 1 | Strong evidence it's underperforming its own design intent | **Redesign scope or length**, or fold into "play a game" as the sole onboarding path |
| **Daily digest emails** | Bring a user back the next day | Computed live for every eligible user, **sent only to one pilot address** | Zero for real users — the mechanism reaches nobody but the product owner | N/A — never tested on a real user | **Expand pilot** to a real cohort — near-zero engineering cost, currently the single cheapest unrealized lever on this board |
| **Payment / subscription flow** | Monetize the PWC daily limit | **Yes** — real, live Razorpay integration (order creation, HMAC-verified confirmation, correctly wired), corrected 2026-08-04: the CTA pointed to `/upgrade`, a route that never existed, instead of `/pricing`, the real working page — a stale redirect string, not a missing payment system | Unknown — never successfully completed by a real paying user | None — 3 real `payment_intents` exist, all `status: created`, none ever reached `paid`; the only 2 `plan: pro` accounts are both `super_admin` manual grants | **Measure**: now that the dead-end CTA is fixed, watch whether any real order reaches `paid` status |
| **Rating-band teaching-depth tiers** (`teaching_depth_pilot.py`) | Explain the same concept differently by rating band, not just different concepts at different levels | No — validated prototype only | Unknown — never shown to a real user | None (design-verified, not outcome-tested) | **Pilot behind a flag** on `piece_safety` only, per the already-approved scope — do not generalize until this one pilot is measured |
| **Deterministic caption pipeline** (`build_move_teaching_decision`) | Explain every real mistake accurately, the primary coaching surface for essentially all real users | Yes — this is what's actually shown, for all 5 highest-volume users, 100% of the time | High — confirmed by a real 217-game/56-user audit: mostly strong, causal, specific | Medium — real audit exists, but surfaced named, systemic defects at real scale | **Fix the known template bugs now** (defect batch); institute the recurring 100-message audit (item 6) as standing process, not a one-off |

---

## Home page — `dashboard-v2` orphaned fields (Session 1 residency, 2026-08-05)

The frontend reads exactly 3 fields (`games_analyzed`, `games_imported`,
`last_session`) from a backend payload that computes 8 more, every page
load. Per the "ownership before deletion" rule agreed this session:
each field needs a named target surface within 90 days or a Retire
decision — no field stays in limbo. Recommendations below, not final
calls — flagging for confirmation, not deciding unilaterally.

| Field | Intended surface | Recommendation |
|---|---|---|
| `chess_dna` (archetype, before/after lines) | None yet — but this is the one field that could directly answer this session's open "episodic vs. identity" question | **Keep, earmark** — the most likely real candidate for a future Identity/Progress surface, not dead weight |
| `patterns` (top-3 with trend) | Possibly Lab's existing pattern cards (coordination/prophylaxis/motifs) | **Check for redundancy first** — may already be superseded by a live surface, not a field needing a new home |
| `streak` (win/loss/draw count) | None | **Retire as a displayed field** — the constitution's own §3 explicitly bans exposing raw streak counts in the coach's voice; nothing currently reads this as a backend-only signal either |
| `training_ready` (live puzzle count for top pattern) | Training page | **Keep** — cleanest fit of the eight, real live query already computes exactly what a "puzzles ready" prompt needs |
| `one_thing_to_fix` | None — likely superseded | **Strong retire candidate** — functionally the same job the Coach Conversation's `one_action` now does; confirm before deleting that this isn't two systems solving one problem in parallel (same disease shape as the earlier `meta_patterns`/`realtime_coaching_feedback` split) |
| `last_battle` (critical position + moves) | Game Review already covers this in more depth | **Likely redundant** — retire pending confirmation |
| `accuracy` (raw %) | Progress page | **Keep for Progress** — matches the constitution's own §4.1.4 distinction (raw Skill-layer numbers belong on a quieter surface, not Home) |
| `context_action` (review-loss vs. play-again) | Could feed which CTA text the Coach Conversation shows (currently static "Play with Coach" regardless of last result) | **Real open question, not obviously redundant** — flagging as a genuine gap worth a real look, not a retire candidate |

## What's deliberately not on this board yet

Systems investigated today but not yet evidenced enough to force a real
decision: `identity_snapshots` (5/114 users, isolated to its own unused
page), `player_strength_profiles` (real data, never reaches coaching
output), `community_learning` puzzle personalization (alive as a
catalog, no personalization evidence). None of these are urgent enough
to earn a row before something else surfaces a reason to look again —
added here so they aren't silently forgotten either.
