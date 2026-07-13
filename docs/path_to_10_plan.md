# Path to 10/10 — ChessGuru Master Plan

*Written 2026-07-13, from the two-pass full-product rescan (10 scan agents + live-data probes). Current honest rating: **6/10**. Every item below traces to a verified finding (file:line evidence in the rescan), not a wishlist.*

## What a 10 actually means

A 10/10 is NOT "all features built" — 40% of built capability is already dark. A 10 means:

1. **Every core promise is true in production** — personalized, verified, closed-loop coaching that users actually receive.
2. **Nothing dies at the last wire** — every feature is verified end-to-end before it counts as done.
3. **Quality compounds without hand-cranking** — the flywheel turns itself.
4. **The business loop works** — users pay, renew, return, and measurably improve.
5. **Outcome evidence exists** — "ChessGuru users stop making their mistake" is a measured fact, not a claim.

The codebase mostly doesn't need new inventions. It needs **wiring, flag flips, verification, and deletion**.

---

## Phase 0 — Stop the bleeding (Days 1–2) · Security & truth

*The product cannot be a 10 while it can be trivially compromised.*

| # | Item | Done when |
|---|------|-----------|
| 0.1 | **Rotate committed secrets** — OpenAI key, Mongo root password, Google OAuth secret live in `docker-compose.yml:49-54` + ~15 scripts. Rotate all three, move to untracked `.env`, scrub git history (BFG/filter-repo). | New creds live; `git grep` for old creds returns nothing; old creds revoked. |
| 0.2 | **Verify + fix DEV_MODE in prod** — base compose sets `DEV_MODE=true`; deploy recipe doesn't pass `-f docker-compose.prod.yml`. Check the server's actual env; make the prod deploy command explicit. | `curl` unauthenticated on prod returns 401, not dev-user data. |
| 0.3 | **Gate `admin_openings.py`** — currently any logged-in user can hit it. Add `require_admin`. | Non-admin gets 403. |
| 0.4 | **Firewall Mongo** — 72.60.204.176:27017 is publicly bound with plaintext root creds. Bind to localhost/VPN or firewall to known IPs. | External `mongosh` connect fails. |
| 0.5 | **Fix pricing mismatch** — ₹499 in `billing.py:52` vs ₹149 in `subscription_service.py:196`. One price, one source. | Same number everywhere (Mohit picks the price). |

## Phase 1 — Connect the last wires (Week 1) · 6 → 7.5

*Five features are 90-100% built and reach zero users. Highest ROI work in the codebase.*

| # | Item | Done when |
|---|------|-----------|
| 1.1 | **Fix training-aware coaching frontend bug** (flagship commit abf198ce, dead in browser): `fetchActiveTrainingFocus` reads `.length` on an object → use `.prescriptions`, and `cognitive_gap` → `issue_detected`. ~2 lines. | Playing PWC with an active prescription produces gap-matched coaching lines; verified in browser. |
| 1.2 | **Close the prescription loop**: (a) normalize auto-close metric per-game (lifetime-sum vs 7-day-sum is broken — guaranteed >50% "improvement"); (b) trigger `check_auto_close` from the analysis worker after each analysis; (c) surface completion: "You fixed Piece Safety — 71% fewer per game. Next focus: …". | A real prescription auto-closes on merit, user sees the celebration, next focus rotates in. |
| 1.3 | **Feed training back into the decay model everywhere**: worker currently computes pattern scores with empty recoveries and discards them (`analysis_worker.py:1339-1352`). Persist them; pass `get_puzzle_recoveries` at every consumer, not just lab-coach-pick. | Solving puzzles visibly changes home/progress prioritization, not just Coach's Pick. |
| 1.4 | **Resolve the dead premium pair**: `predict_coach_move.should_fire` returns False on line 1 while the frontend flag is `true`; `rate_your_move` is flag-off and write-only. Decide: re-enable Call-My-Move under the conductor with the clear-best gate, or remove its UI. Enable Rate-Your-Move and build ONE consumer (calibration insight: "You rate blunders as 'fine' N% of the time"). | Zero dead premium UI; at least one student-model signal visibly consumed. **Needs Mohit's call on Call-My-Move.** |
| 1.5 | **Flip the quality flags after sign-off review**: `VERIFIED_CAPTIONS` + `DISTILLED_CAPTIONS_ENABLED` are validated (53–91% coverage, 98–99% truth) and dark. Run a 20-game review batch for Mohit, then flip on server + bump `V5_COACHING_VERSION`. | Distilled/verified captions render for users on fresh game reviews. **Needs Mohit sign-off.** |
| 1.6 | **Make review captions rating-aware**: V5 path never passes `user_rating` (rating gate inert); 4 divergent rating-band tables exist. Pass rating into `MoveInputs`; collapse all bands into `rating_resolver`. | An 800 and a 1600 see different framing on the same mistake; one band table remains. |

## Phase 2 — Verification culture (Week 2) · The disease cure

*Every major failure found is a last-wire failure. This phase makes the class extinct.*

| # | Item | Done when |
|---|------|-----------|
| 2.1 | **One Playwright e2e smoke**: login → home renders prescriptions → open a game review → captions present → start pattern training → solve → PWC start + move + coach reply. | Runs green locally + in CI; would have caught the abf198ce bug. |
| 2.2 | **CI gate on push** (GitHub Actions): the e2e + `pwc_coaching_lint` + `opening_sync_check` + caption probe suite + backend unit tests that don't need live data. | Red build blocks merge to working-code. |
| 2.3 | **Contract checks for frontend↔backend shapes** — the `.length`-on-object class. Lightweight: JSON-schema snapshots for the ~10 endpoints the frontend consumes hardest. | Shape change without frontend update = red build. |
| 2.4 | **Backups + deploy hygiene**: nightly `mongodump` cron + retention; prod deploy script that always uses the prod compose file. | A restore has been tested once; deploy is one command that can't pick the wrong compose. |

## Phase 3 — Teaching quality to "wow" (Weeks 2–4) · The product core

*Truth is solved (0 lies at 46k scale). Depth is not: 44% of clear mistakes still get verdict-only captions.*

| # | Item | Done when |
|---|------|-----------|
| 3.1 | **Mechanism-why on clear mistakes: ~56% → 85%+.** Configure the narrator gateway in prod (budgeted), drain the abstention queue nightly, extend distilled templates (walked_into_tactic PV-deepening, missed_mate). | Measured on a fresh 300-game sample: ≥85% of cp≥150 mistakes carry a position-specific why. |
| 3.2 | **Automate the flywheel** — it's architecturally complete but hand-cranked (no cron for gold/judge/backfill/abstention-drain). Schedule: nightly abstention drain, weekly gold expansion + judge run, report to an admin page. | Quality metrics move week-over-week with zero manual script runs. |
| 3.3 | **Openings consolidation**: delete orphaned `opening_curriculum_hierarchical.json` (253KB, zero refs); finish the theory_tree→curriculum migration (it's "retired" but still live in caption/mastery paths); collapse 3 recognizers to 1 (curriculum-backed; retire the hardcoded 25-opening `opening_book` table); fix mojibake (`â€"`) in curriculum strings; derive skill-tree opening counts live (kill the manual recompute script). | One data file, one recognizer, `opening_sync_check` deleted because there's nothing left to drift. |
| 3.4 | **Deepen the shallow openings**: 56/79 are name+4-rules shells. Author full trees for the 10 most-played (by live user data). | Top-10 openings by user play have move-by-move why + wrong_feedback. |
| 3.5 | **Delete the dead code** (it misleads every future scan/session): `caption_pipeline_verified.py` (broken), `smart_coaching.py`, `useCoachSession.js` + `/move-feedback` bridge, 7 dead frontend pages, `CoachingPrescriptions.jsx` (or mount it). | Grep-verified zero references; bundle shrinks. |

## Phase 4 — Personalization users can FEEL (Weeks 4–6) · The moat

| # | Item | Done when |
|---|------|-----------|
| 4.1 | **Causal improvement proof**: current "before/after" matches any clean same-phase move (coincidence). Join trained pattern → post-training games in the SAME pattern, per-game normalized; render as the "You Learned This" proof. | Card reads "Since training piece safety: 2.1 → 0.7 hangs/game" and the join is real. |
| 4.2 | **Student model consumers**: prediction-accuracy → coach difficulty adaptation; self-rating calibration → a recurring insight card. (Data already collected: 30k+ session traces, move_observations.) | At least two live surfaces change behavior based on student-model data. |
| 4.3 | **PWC component health**: split `CoachPlay.jsx` (3,443 lines, 71 useState, 3 overlapping polling loops → SSE + one fallback poll); split `coach_play.py` (10k lines) into modules. | No duplicate-fetch races; files under 1,500 lines; behavior unchanged (e2e green). |
| 4.4 | **Unify the remaining PWC legacy engines**: coach-own-move explanation (hand-rolled, 4 call sites) and opponent-move fallback route through the central pipeline; retire `move_critique`/`coaching_policy`/`coaching_voice` remnants. | One coaching-prose door, grep-verified; `check_caption_sources.py` passes strict. |

## Phase 5 — Business engine (Weeks 6–8) · From rail to revenue

| # | Item | Done when |
|---|------|-----------|
| 5.1 | **Real subscriptions**: Razorpay Subscriptions (auto-renew) + payment webhook (currently a dropped browser after payment = paid but not upgraded) + cancellation flow + dunning. | A renewal happens without user action; webhook reconciles; cancel works. |
| 5.2 | **Funnel instrumentation**: PostHog is installed but captures zero custom events. Instrument welcome → diagnostic → import → first-review → first-training → PWC → paywall → paid. | A funnel dashboard shows conversion per step; one improvement shipped based on it. |
| 5.3 | **Lifecycle email automation**: today = 5 hand-run scripts with hardcoded user IDs, 2 moments topics. Build a registry-driven weekly job over the whole cohort (respecting the email→page contract) + a weekly progress digest. | Emails send on schedule to cohorts, not names; CTR tracked. |
| 5.4 | **SEO completion**: sitemap lists 10 of ~80 openings. Generate it from the curriculum; expand public content. | All public opening pages indexed; impressions trending in Search Console. |

## Phase 6 — The last mile to 10 (Weeks 8–12) · Outcome evidence

*A 10/10 coaching product is proven by its users, not its code.*

| # | Item | Done when |
|---|------|-----------|
| 6.1 | **Perf + polish**: Stockfish engine pool (currently spawn-per-request), shared Mongo clients, mobile pass on the top-5 surfaces. | p95 analysis-feedback latency halved; mobile usable end-to-end. |
| 6.2 | **Engagement depth**: today 34 WAU but 2-3 power users dominate. Target: ≥10 users at ≥3 sessions/week via the Phase 4-5 loops. | Cohort chart shows it. |
| 6.3 | **The outcome metric** (the real 10/10 test): % of users whose top trained pattern shows ≥40% per-game reduction after 20 games. Publish it in-product ("ChessGuru users fix their #1 leak in N games"). | The number exists, is honest, and is the homepage claim. |
| 6.4 | **Retention + revenue proof**: M1 retention ≥40%, ≥15 paying subscribers, churn understood via funnel data. | Three consecutive weeks of data. |

---

## Rating math

| Milestone | Rating |
|---|---|
| Today | **6.0** |
| Phase 0+1 complete (secure + last wires connected) | **7.5** |
| + Phase 2+3 (verification culture + teaching depth 85%+) | **8.5** |
| + Phase 4+5 (felt personalization + real subscription business) | **9.0–9.5** |
| + Phase 6 outcome evidence (users measurably improve, retain, pay) | **10** |

## Decisions only Mohit can make

1. **Call-My-Move**: revive under conductor (with the clear-best gate) or delete the UI. (Phase 1.4)
2. **Flag sign-off**: review the 20-game distilled/verified caption batch, then flip. (Phase 1.5)
3. **Price**: ₹149 or ₹499. (Phase 0.5)
4. **Narrator LLM budget** for prod (Phase 3.1) — the 85% why-rate needs it.
5. **Deploy access** for the server-side steps (secrets rotation, compose fix, flags, cron).

## Standing rules while executing

- Every phase item lands only with its **"done when" verified end-to-end** (the last-wire rule — this plan's items 1.1–1.5 exist because that rule was broken).
- No new parallel sources — extend the existing one (`single-source-of-truth`).
- Scope docs before any *new* feature; this plan is wiring/flags/deletion, not new features, until Phase 4.2.
