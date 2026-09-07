# ChessGuru Acquisition Readiness Program — Scope

**Status:** LOCKED — MOHIT APPROVED 2026-09-06

**Scope path approved:** EXTEND, approved by Mohit on 2026-09-06

**Canonical starting point:** `origin/working-code` at `8b6e5ac34580e63d971e359eb18e911ff993f9a4`

**Implementation ownership:** Codex owns the program implementation; Claude owns the explicitly assigned emergency lane, independent review, push and production deployment; Mohit and invited coaches own final product and chess acceptance.

## 0. Existing surfaces audit

### What already serves this need

| Existing surface or authority | What it already provides | Program decision |
|---|---|---|
| `complete_coaching_system_scope.md` and spec | The locked end state: one persistent coach across Home, Review, Learn/Training, Play with Coach and Progress; one focus authority; verified chess claims; later-game transfer before improvement claims | **EXTEND.** This remains the product contract. The acquisition program may prioritize and finish it, but may not create a second coaching architecture. |
| Personal Improvement Cycle | The existing observe → diagnose → teach → practise → checkpoint → later-game transfer loop | **EXTEND.** Use it as the learning-loop authority; do not invent another mastery or progress loop. |
| Phase 8 Release Rescue | Reconciliation, focus creation, real non-admin reach, a target of ten completed full journeys after the eligible denominator is re-derived, and a mandatory deployment journey check | **CONTINUE.** Treat this as the distribution and last-wire workstream inside the program. Do not rebuild the already-live lesson-verdict fix. |
| Hidden Opportunities | Deterministic setup → constraint → payoff reasoning, gold and blinded evidence, Shadow incidence measurement and the planned try → hint → reveal → replay → recognition experience | **CONTINUE UNDER ITS OWN GATES.** It supplies memorable alternative lines in Game Review only after its proof family earns exposure. It is not replaced by generic best-move commentary. |
| `detector_quality` and concept execution registries | Fail-closed authority over which facts may support captions, plans or only research; historical promotion evidence and adversarial cases | **PRESERVE AND DISTRIBUTE.** Promotion remains evidence-based, but authorized detectors must be deliberately wired to player surfaces rather than left as unused inventory. |
| Product Claim Honesty Register | The current source for claims the product may and may not make, including the mismatch between recurring-subscription language and one-time billing behavior | **EXTEND.** Security, privacy, billing and acquisition claims must cite this authority. |
| `scripts/deploy.sh` and deployment verifier | Clean-server update, exact commit proof, build exit checks, bundle verification, health checks and a mandatory non-admin coaching-journey check | **EXTEND.** Add permanent security and release-integrity checks; do not replace the existing deploy path. Claude remains the production operator. |
| Launch Readiness Report and dated product audits | Historical launch scores, activation evidence, risk rankings and earlier recommendations | **PRESERVE AS HISTORICAL EVIDENCE.** A new dated acquisition baseline supersedes scores only when the measurement window and evidence differ explicitly. |
| Existing player routes and pages | More than fifty routed destinations, including duplicate or overlapping paths for Home, Review, games, openings, training and progress | **CONSOLIDATE THE EXPERIENCE.** The intended player-facing information architecture is Home, Review, Learn, Play and Progress. Existing deep links may remain as redirects or contextual destinations; they must not compete as separate products. |
| Existing production/repository operations | A strong `working-code` lineage and several good deployment safeguards, alongside a stale default branch, many worktrees, a dirty stale local checkout and work distributed across feature branches | **CANONICALIZE.** Every branch/worktree is explicitly merged, superseded, archived or abandoned with evidence. No whole-tree copying and no silent orphaning. |

### Verified risks already established

- Codex's 2026-09-06 review scored technology potential **8.5/10**, current player product **5.5–6/10**, acquisition diligence readiness **3/10**, and overall product approximately **5.5/10**.
- Claude's independent review used different lenses and scored engineering craft **9/10**, evidence discipline **9/10**, architecture **8/10**, value reaching actual users **2/10**, release readiness **3/10**, and the current product overall **4/10**. These scores are not averaged together; the acquisition baseline will preserve each lens and its evidence.
- Five perimeter/repository findings were independently reproduced by both reviewers: permissive credentialed CORS, an unauthenticated feedback-download endpoint, tracked customer identifiers, missing browser security headers and a default branch thousands of commits behind the product branch.
- Claude additionally reported that 105 of 119 measured users did not return after day zero, 45% of Play-with-Coach sessions ended before move two, completed games produced a 2.6% user win rate, and six people used the product in the preceding 30 days. These are treated as a P0 commercial signal, but remain **independent-reproduction pending** until the cohort definition, exclusions, time window and source query are frozen in a versioned snapshot.
- Earlier Phase 8 measurement found that real-user reach was constrained by missing detector backfill and missing active focus bundles, not merely by UI flags. The denominator must be re-derived after reconciliation; success may not be silently graded against a convenient cohort.

### Overlap and genuine differentiation

The repository already contains the intended coaching product, release rescue, chess-proof work, honesty policy, deployment machinery and several audits. The missing thing is not another feature or report. It is a single execution program that orders the work, prevents the highest-risk gaps from being buried beneath detector research, proves that ordinary players can reach the value, and gives a buyer reproducible evidence instead of claims.

The program's genuine differentiation is therefore governance tied to delivery: every gap has an owner and proof requirement; every player-facing claim has an authorization source; every score change has independent evidence; and every release proves both safety and a complete ordinary-user journey.

### Overlap decision

**EXTEND — approved by Mohit.** No new player dashboard, coaching engine, progress model, detector authority, curriculum registry or deployment path will be created. The program extends and finishes the existing product, consolidates duplicate presentation, and records explicit disposition for unfinished branches and worktrees.

## 1. What it is

The Acquisition Readiness Program turns ChessGuru's large body of promising coaching technology into one secure, understandable and demonstrably useful product for 600–1500 players, while making the company inspectable by a serious buyer. A player should quickly feel that the coach understands their chess, shows memorable evidence, teaches something they can use and checks whether it appears in later games. A buyer should be able to verify how the system works, what is proprietary, what is licensed, what reaches users, how claims are proven, how releases are controlled and what real players actually do. The program finishes and connects the existing system; it does not replace it with another vision.

## 2. What the user sees

This program adds no acquisition-readiness page to the player product. It improves the existing five destinations until they read as one relationship with one coach.

### A new or returning player

```text
HOME

I've studied your recent games.

The first thing I want us to work on:
After you choose an active move, you sometimes stop checking what your
opponent can do immediately.

I found two recent positions where the same decision appeared.
One cost you a rook. In the other, you caught the danger yourself.

[ See both positions ]

Today we will practise the decision, not memorize the old moves.
[ Start with my position ]
```

If evidence is insufficient, the coach says so and gives one bounded way to create evidence. It does not manufacture a weakness from rating or generic curriculum.

### Game Review

```text
GAME REVIEW

What this game was really about
You handled the opening plan well and reached the position you wanted.
The game changed when your rook moved away from d3: Black's queen could
enter on c2, and your back rank stopped holding together.

WHAT YOU PLAYED
[ replay on the board ]

WHAT WAS POSSIBLE
There was a forcing idea for you here. Try to find it before I reveal the
line. This is not simply "the engine move"—the point is the pin on the
d-file and the defender that cannot move.

[ Try ]  [ One hint ]  [ Show the idea ]

WHAT TO REMEMBER
Before moving a defender, ask what it is holding together behind it.
```

Review may explain openings, traps, endgames, tactical geometry, plans, opponent intentions and exceptional alternative lines, but only from verified facts. It also identifies good decisions worth preserving.

### Learn and Play

```text
YOUR CURRENT LESSON

You recognized the danger with a hint. Now solve the same idea from a new
position without help.

[ Play the move on the board ]

VERDICT
Correct — and here is why it works.

Practice is complete for today. I will not call this learned yet. I will
watch for the same decision in your next unassisted games.
```

### Progress

```text
PIECE SAFETY

You can now solve this idea without a hint.
In later games: not enough comparable decisions yet.

COACH VERDICT
Promising in practice. Not proven in your games yet.

[ See the evidence ]
```

### What a technical buyer can verify

```text
Fresh canonical checkout
  → documented setup
  → reproducible tests and evidence packets
  → security and licensing inventory
  → one traceable coaching decision from stored fact to player wording
  → one non-admin complete journey
  → one reversible, commit-bound deployment
```

## 3. In scope (V1)

- A versioned acquisition baseline with stable finding IDs, dated evidence, severity, owner, status and the exact proof required to close each finding.
- Separate scorecards for player product, value reach, chess intelligence, engineering/reliability, security/privacy, commercial readiness and acquisition diligence; scores are never averaged into a flattering number that hides a failed dimension.
- An emergency Claude-owned lane for the five independently verified issues: CORS, admin-download authorization, tracked PII disposition, security headers/server disclosure and repository default-branch correction. Codex independently reviews that lane; Claude supplies the patch, test and live-production evidence.
- Codex-owned remediation for all remaining verified or reproduced findings, including authentication exposure, privacy disclosures and controls, billing/marketing consistency, dependency risk, CI reproducibility, operational evidence and buyer documentation.
- Independent reproduction of Claude's retention and Play-with-Coach funnel findings, with test/bot/admin exclusions, cohort windows and query definitions frozen before targets are chosen.
- A commercial rescue path based on the verified funnel: shorten time to first personal value, make the first coaching loop finishable, make Play with Coach humane at the player's level, and measure return behavior rather than feature impressions.
- A clean implementation worktree based on the latest canonical `origin/working-code`; the stale dirty root checkout remains untouched.
- Explicit disposition of local and remote branches/worktrees containing real work: merged, already superseded upstream, retained as evidence, archived or intentionally abandoned. No scope completes with unknown unmerged product work.
- A reproducible fresh-checkout backend and frontend test path, with unit, integration and end-to-end boundaries; tests requiring Mongo, a running server, Stockfish, browsers or network state are provisioned or explicitly selected, never accidentally collected as ordinary unit tests.
- Dependency and supply-chain remediation with a reproducible manifest, vulnerability disposition and license/provenance record for Python, JavaScript, Stockfish, Maia2, Otter, Fathom, Syzygy/tablebase data, opening/endgame/trap content, community games and generated code/assets.
- A truthful billing state: the product either implements the promised recurring lifecycle or clearly offers the actual one-time/preview behavior everywhere. Payment, cancellation, renewal, refund and access state must agree.
- Privacy and security behavior that matches public policy, including PostHog/session-recording disclosure and controls, data export/deletion handling, safe token/session storage, least-privilege admin routes, restrictive production CORS and required browser headers.
- One coherent player information architecture: Home, Review, Learn, Play and Progress. Duplicate routes are redirected, contextualized or retired after compatibility evidence.
- Completion of the Phase 8 distribution path: stored-observation backfill, eligible focus creation, honest reconciliation, feature-access decision, ordinary-user complete-journey verification and real cohort observation.
- Completion of the existing complete-coaching loop across surfaces: one focus and instruction, personal evidence, suitable teaching act, explicit right/wrong verdict, assistance-aware attempt, unassisted checkpoint, later-game observation and honest adaptation.
- Game Review that explains both what happened and the most valuable verified possibilities that were not played, including opening ideas, traps, tactical geometry, positional plans, endgame knowledge, opponent resources and good decisions.
- Hidden Opportunities continues through its existing proof gates and interaction phases. Critical false-claim classes such as truncated recaptures, forks beyond the stored horizon and quiet checking resources remain adversarial regressions.
- Authorized detector and curriculum value is wired to real player surfaces. Shadow evidence is measured and promoted or retired deliberately; detector count alone is not progress.
- Existing game analysis remains the Stockfish source of objective stored truth. Stored positions are not re-evaluated merely to decorate a new feature; new engine work requires a separate evidence need and approval.
- Human-move models such as Maia/Otter are used only for validated jobs such as human-likeness, findability, difficulty or time-conditioned behavior. They never replace objective legality, tactics, tablebase truth or detector authorization.
- Product analytics that distinguish reach, start, completion, practice assistance, later unassisted opportunity, transfer, return and payment. Instrumentation must be present before a rollout is graded.
- Five observed real-player sessions and the Phase 8 full-journey cohort, with Mohit/coaches recording confusion, trust, chess usefulness and where players stop.
- A buyer-ready evidence room containing architecture, data flow, security posture, privacy, billing, deployment, recovery, test evidence, licenses/provenance, model boundaries, product metrics, known risks and rollback procedures.
- A reciprocal independent-review protocol: Claude reviews Codex changes; Codex reviews Claude's emergency lane; Mohit/coaches review player and chess quality. The author of a change cannot be its only release authority.
- Claude continues to own push and production deployment. Codex provides a commit-ready handoff with exact ordering, migrations, dry runs, rollbacks and post-deploy checks.

## 4. Explicitly out of scope (V1)

- A new top-level acquisition dashboard, AI Coach page, player portal or duplicate planning system.
- Replacing the locked Complete Coaching System, Personal Improvement Cycle, detector-quality authority, Hidden Opportunities scope or Phase 8 journey with new parallel abstractions.
- Net-new detector families during the perimeter/reach rescue. Fixing, validating, promoting, wiring or retiring existing detectors remains in scope.
- Showing Shadow or failed chess proofs to players merely to increase content volume.
- Treating an LLM, Maia, Otter or a human-written explanation as objective chess truth without the appropriate deterministic or engine/tablebase evidence.
- Re-running Stockfish over already-analyzed games when the required fact is already stored and sufficient.
- Claiming improvement because a lesson or puzzle was completed; only later unassisted evidence can support transfer.
- Faking retention, activity, payment, training or transfer records to satisfy a gate.
- Quietly changing the eligible denominator, review window, success threshold or score after results are visible.
- Rewriting Git history containing PII without a separately approved impact plan covering clones, deployments, tags, backups and credential/identifier exposure. Forward removal can proceed in Claude's emergency lane; history treatment remains an explicit decision.
- Production mutations without a bounded dry run, backup/restore proof where material data is affected, deterministic reconciliation report and rollback procedure.
- Production push or deployment by Codex; Claude owns those actions under Mohit's operating decision.
- Legal opinions, acquisition negotiation, tax advice or a claim that a code audit substitutes for privacy, licensing or acquisition counsel.
- A guaranteed Microsoft transaction, valuation, Elo increase, retention outcome or 9/10 score.
- Broad paid acquisition before activation, return behavior, billing truth and the complete coaching journey pass their gates.
- Cosmetic redesign detached from the canonical journey, or new navigation destinations that increase product sprawl.
- Deleting historical evidence because it is embarrassing, stale or lowers a score. Superseded evidence is dated and retained.

## 5. Success criteria

### Immediate safety and repository truth

- A request from an unapproved origin cannot receive credentialed readable API responses; an approved ChessGuru origin still works. The live retest is archived.
- Every feedback export/download requires authenticated administrative authorization, rejects traversal attempts and records access appropriately; an unauthenticated live request returns `401` or `403` rather than file-state information.
- Canonical HEAD contains no raw customer email addresses or other unapproved direct identifiers in the identified evidence files, and the history-disposition decision is documented separately.
- Production HTML and API responses carry the approved HSTS, CSP, content-type, frame, referrer and permissions policies; unnecessary server-version disclosure is removed at the serving layer.
- The hosting provider's default branch points to the canonical release lineage, and a fresh clone lands on a current documented product rather than the February snapshot.
- Claude supplies commit and live evidence for this lane; Codex independently audits the diff and runtime results before the findings close.

### Real player value

- After the existing Phase 8 detector backfill and focus creation, the eligible denominator is re-derived and reported. At least **10 eligible analyzed-game users** complete the full coaching journey defined in the Phase 8 addendum; no denominator is silently substituted.
- One ordinary non-admin user can complete connect/import → verified focus → personal evidence → interactive lesson → explicit verdict → recorded attempt → progress state through production routes without database repair or administrator intervention.
- Home, Game Review, Learn, Play with Coach and Progress return the same focus identity and immutable instruction for the same user; a mismatch is release-blocking.
- At least five observed sessions are recorded using the existing launch-readiness protocol, with concrete confusion and stop points rather than general satisfaction notes.
- Practice completion never becomes a transfer claim. For every pilot user who later encounters a comparable unassisted decision, the system records `improving`, `still recurring` or `insufficient evidence` according to the canonical evidence contract.
- The reported retention/PWC baseline is independently reproduced before its target is locked. A fresh-cohort return and early-session-completion target is then selected through the repository's data-lock process and must be met before player-product readiness may score 8 or higher.

### Chess and coaching quality

- Every personalized diagnosis, caption, plan and progress claim resolves to the authorization grade required by its player-facing use; fail-closed behavior is covered at the API and rendered-surface boundaries.
- No critical false chess claim is accepted in the blinded gold/adversarial release packet. Precision, recall and true-negative requirements continue to come from the existing detector-quality gate rather than a new score invented here.
- Game Review presents verified alternative opportunities only when the setup, constraint and payoff survive legal replay and the applicable horizon/settlement proof. A plain engine best move without a teachable verified reason is not promoted as “magic.”
- A player can try an opportunity, receive bounded help, see why the line works, replay the idea from a changed position and have assisted versus unassisted performance recorded distinctly.
- Coaching language passes the existing 600–1500 voice rules and explains the board relationship in plain language rather than reporting centipawn arithmetic or generic labels.

### Engineering, operations and diligence

- A fresh canonical checkout can execute the documented backend and frontend quality gates with no unexplained failures. Environment-dependent suites are provisioned or explicitly selected; they do not fail or pass accidentally.
- No unresolved exploitable critical/high dependency or application-security finding remains without a written owner, compensating control, deadline and reviewer acceptance.
- The production deploy path mechanically blocks stale commits, failed builds, unchanged unexpected bundles, health failures, authorization failures, contract failures and a failed non-admin complete journey.
- Backup, restore and rollback procedures are tested against the assets they claim to protect; a successful dump without a successful restore is not accepted as recovery evidence.
- Billing behavior, Pricing, Terms, Refund and product access state tell the same story in source and production.
- Every material external engine, model, dataset and content source has a version, license/provenance record, permitted-use assessment and distribution decision. Legal conclusions remain counsel-owned.
- A buyer can trace at least one complete coaching decision from stored position/evidence through detector authorization, focus selection, wording, interaction, attempt history and later-game verdict.
- Each scorecard dimension is re-evaluated by an independent reviewer using the frozen rubric and attached evidence. A score may remain unchanged or decrease; implementation effort is never evidence of improvement.
- The program may claim 8–8.5 acquisition readiness only after the safety, reproducibility, ordinary-user journey, commercial measurement and evidence-room gates pass. A 9/10 claim remains unavailable until sufficient real-user retention/transfer evidence and external legal/licensing review exist.

## 6. Open questions

- **Question:** What exact cohort produced the reported `105/119` day-zero loss, 45% pre-move-two abandonment, 2.6% win rate and six recent users?

  **Why unresolved:** The figures were independently reported but the source query, bot/admin/test exclusions, time window and game-completion definition are not yet versioned.
  **Unblocking step:** Reproduce read-only, freeze the query and anonymized aggregate snapshot, then run the data-lock process before choosing retention targets.

- **Question:** Will tracked PII receive forward removal only or a coordinated Git-history rewrite?

  **Why unresolved:** A history rewrite affects every clone, worktree, deployment reference and collaborator; forward removal does not erase past objects.
  **Unblocking step:** Claude inventories affected paths/history and proposes both impact plans; Mohit selects the treatment with privacy/legal input where needed.

- **Question:** Which security headers belong at FastAPI and which at nginx/CDN?

  **Why unresolved:** The correct layer depends on the deployed topology and which component serves HTML versus API responses.
  **Unblocking step:** Claude documents the live serving path with header tests and implements the policy at the authoritative layer; Codex reviews the result.

- **Question:** Should current payment be disabled, honestly relabeled or replaced immediately with recurring subscriptions?

  **Why unresolved:** The code supports a one-time order while customer-facing documents have described a recurring product. This is a commercial decision as well as an implementation choice.
  **Unblocking step:** Freeze the current live flow and claims, quantify existing paid users/intents, then Mohit chooses disable, relabel or implement recurring before billing code changes.

- **Question:** What is the current production feature-access manifest for ordinary users after recent Phase 8 work?

  **Why unresolved:** Repository defaults and historical deployment messages do not prove current secret runtime flags.
  **Unblocking step:** Claude exports a credential-free runtime manifest and a real non-admin journey result after the emergency lane stabilizes.

- **Question:** Which dependency vulnerability counts still reproduce on the canonical branch?

  **Why unresolved:** Earlier scans reported 60 npm and 113 Python findings, but current registry-backed re-scans were not authorized/completed in the last audit and counts may have changed.
  **Unblocking step:** Run pinned reproducible scans in an approved networked CI/deployment environment and archive machine-readable reports.

- **Question:** Which of the many worktrees and branches contain unique, still-required product work?

  **Why unresolved:** Several have known upstream counterparts, but the repository still contains dozens of worktrees and feature branches.
  **Unblocking step:** Produce a commit/file-level disposition ledger; do not delete or prune until each unique change is classified.

- **Question:** What external legal/licensing review is available before acquisition diligence?

  **Why unresolved:** Engineering can inventory licenses and provenance but cannot issue the final opinion on model weights, datasets, game rights, GPL obligations, privacy or acquisition representations.
  **Unblocking step:** Produce the engineering inventory first, then route the bounded questions to counsel and record the resulting decision.

## 7. Pre-code requirements

- Mohit explicitly approves this full scope document after reviewing Sections 0–7. EXTEND approval alone does not approve implementation details.
- `docs/acquisition_readiness_baseline_2026_09_06.md` is written with stable finding IDs, the two unblended historical score sets, evidence links, owner, severity, state and closure proof.
- The implementation branch/worktree remains based on the latest canonical `origin/working-code`, and the stale dirty root checkout remains untouched.
- Claude provides the emergency-lane branch/commit ownership boundary before Codex edits any overlapping security, server, deployment or repository-governance file.
- Claude-reported retention and Play-with-Coach funnel numbers are independently reproduced or explicitly retained as pending; no target is derived from unversioned figures.
- Every new numeric product threshold or competing ranking/selection formula passes `lock-via-data`; existing locked Phase 8 and detector-quality thresholds are referenced rather than reinvented.
- The billing direction—disable, relabel or implement recurring—is chosen before billing implementation begins.
- The first implementation slice has named unit, integration, end-to-end, security, reach and rollback evidence before code changes begin.
- The reciprocal review packet format is frozen: scope/findings, diff, raw test output, runtime evidence and known limitations; the implementer's desired score is excluded from the review prompt.
- The repository `audit-pre-code` checklist passes after the baseline and numeric locks exist. Only then may the first implementation file change.
