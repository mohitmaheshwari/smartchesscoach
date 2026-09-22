# ChessGuru coaching UX polish — existing-surfaces audit

Date: 2026-09-22

Status: Section 0 complete; EXTEND existing is recommended. This is an audit and proposed treatment inventory, not an implementation-complete or release-ready claim. No application files changed.

Source baseline: fetched `origin/working-code`, commit `3df9ab99`. Isolated branch: `codex/coaching-ux-polish-v1`. Previous onboarding checkout `c7bf0587` is not the baseline: upstream contains newer invite, diagnostic, and lesson changes.

## 0. Existing surfaces audit

### Brief and evidence boundary

Mohit requests a polished experience across all ChessGuru pages, designed around a personal chess coach rather than copied from a competitor. Preserve cream, forest green and lime; put actual chess activity ahead of introductory prose; make guidance, feedback, completion and return visits coherent.

Evidence collected:

- Parsed the current `frontend/src/App.js`: **66 route declarations, 57 distinct directly routed page components**. Five declarations are direct redirects; repeated component owners account for the remaining difference. Additional behavior exists below those page components.
- Inspected route ownership, page render headings/actions/imports, shared navigation, curriculum presentation, opening cards, import handling, settings, training dispatch, and selected lesson/diagnostic/review state branches.
- Reviewed the user-provided Learn, Openings, onboarding, lesson, Progress and review screenshots. These are evidence of those captured states, not of every current live route.
- Inspected prior frontend scopes and the existing shared styles and motion configuration.
- Attempted browser inventory with the supported browser tool. It failed with `trusted Node process exited unexpectedly; kernel reset`. No live authenticated journey, timing, mobile rendering, computed contrast, or cross-browser pass is claimed.
- No production queries, enrollments, imports, attempts, emails, engine runs, model calls, migrations, payments or deployments were performed.

This is a complete **route inventory and source-level surface audit**, not a comprehensive behavioral test of all 57 components or every nested controller. Recommendations below must be checked in rendered states before shipping.

### Existing work to extend, not rebuild

| Existing owner | What already exists | Treatment |
|---|---|---|
| `docs/frontend_experience_ui_ux_scope.md` and `_spec.md` | Prior signed full-product design, route-family coverage, board-first design, motion, accessibility and rollout requirements | Inherit the coverage and safety commitments. Do not blindly reinstate its older amber palette or obsolete route ownership. |
| `docs/inner_product_experience_redesign_scope.md` | Coaching-room design for canonical pages; preserves APIs, chess logic, data and route contracts | Extend current presentation. This request is not authority for a replacement coaching controller. |
| `docs/first_coaching_session_onboarding_scope.md` and `_spec.md` | First-session design and explicit feedback work | Reconcile against current upstream. Previous implementation reports are not proof that the current diagnostic still behaves the same. |
| `Layout.jsx`, `index.css`, `lib/experience.js` | Desktop sidebar, mobile menu and bottom navigation, page families, shared colours, cards, type and actions | Improve the existing system; no second app shell or parallel design-token system. Current experience flag defaults on unless explicitly false. Do not assume it isolates a new rollout. |
| `App.js` `MotionConfig reducedMotion="user"` and existing CSS media rules | Reduced-motion support already exists | Preserve and verify it, including any CSS or board animations outside Framer Motion. |
| `HomePageNew` → `CurriculumHome` / `CurriculumPrimary`; `PersonalCurriculum` | Canonical recommendations, reasons, states, destinations and tracking hooks | Differentiate Home's immediate next action from Learn's current focus and exploration. Keep the recommendation authority. |
| `PrescribedTraining` → `PersonalizedLessonWorkspace`; `VerifiedEndgameLesson` | A shared personalised lesson workspace, move/reason handling, walkthrough, feedback and completion paths | Reuse this host. Design state transitions explicitly; do not introduce a new lesson engine. |
| `OpeningQuizPage` | Redirects to the personalised opening lesson | Keep compatibility redirect. Do not rebuild the retired answer-bearing quiz. |
| `AllGames` → `LabV2` → `GameDecryptionV5` | Coach selection, chapters, game archive, review and line controls | Improve discovery and reading order. Keep proof, admission and answer-hiding boundaries. |
| `OpeningsOverview` `InlineBoardPreview` | Existing opening-line stepping and board-preview behavior | Candidate reuse after data and rendering checks, not a claim that every lesson already supplies a suitable preview. |
| `UnifiedProgress` | Evidence-led progress, unavailable states and next actions | Show what is available without conflating activity, assisted success and real-game change. Do not bypass missing-baseline checks. |
| `CoachPlay` and its setup/board/panel children | Large existing game controller, legacy/unified branches, teaching and postgame interactions | Styling and interaction presentation only; controller repair or activation remains separately governed. |

### Findings that change the plan

**F1 — The hierarchy promotes the introduction over the chess.**

`PersonalCurriculum.jsx:91` places a large `cg-hero` before the actual focus; `CurriculumHome.jsx:17` repeats the structure. `index.css:1278` gives the hero substantial padding, and `:1310` defines headings up to 4rem. `OpeningRepertoire` uses `text-xs` for lesson descriptions and reasons. The supplied screenshots confirm the imbalance in those states.

Treatment: compact contextual page titles; strongest visual weight on the current position and start/resume action. A legal or account page does not need a coaching-sized hero. Do not shrink useful chess text to make an oversized slogan fit.

**F2 — Openings presents performance as knowledge.**

`OpeningRepertoire.jsx:19` declares “You don't know these yet” / “You know these” bands. `backend/services/opening_library_service.py:548` derives those bands from opening-phase cp-per-move. That does not directly establish knowledge. The backend also emits “drilling it will hold it together” and similar causal promises.

Treatment: keep the existing assessment and selection for now, but present its meaning honestly: “Worth revisiting”, “Handled well in recent games”, or “Not enough evidence yet”. Distinguish this copy correction from any future change to grading or ranking. Backend-authored copy changes need focused tests and the normal caption/voice review.

**F3 — The discovery cards do not distinguish their promises.**

`lib/personalCurriculum.js:7` sends “Tactics & traps” and “Thinking habits” to `/training`; “Plans” goes to `/coach`, which redirects to `/training?weakness=current`. Distinct-looking destinations do not establish distinct teaching experiences. The screenshot also shows two Philidor labels; source/data inspection has not established whether those specific recommendations duplicate content.

Treatment: audit the actual destination and content for each label. Use clear labels for existing experiences, or explicitly parameterised existing routes where supported. Do not invent new catalogs or hide a duplicate behind a new title. Confirm opening-family relationships before deduplicating.

**F4 — Current diagnostic feedback still has timed transitions.**

`DiagnosticPuzzles.jsx:311`, `:331`, and `:337` schedule `applyPending` after 1000/2400 ms. The earlier isolated onboarding work must not be assumed to have survived unchanged upstream. Current source has a different interaction implementation.

Treatment: explicitly audit intermediate move, reason question, final verdict, walkthrough and completion states together. Preserve feedback until deliberate continuation where that is the lesson contract; distinguish an automatic opponent move from automatically dismissing an explanation. Reconcile existing changes rather than cherry-picking an old branch blindly.

**F5 — Transport failures can masquerade as lack of chess evidence.**

`OpeningRepertoire.jsx:141` only logs fetch failures and clears loading. Its null repertoire then yields empty arrays, so a failed request can produce an empty-looking page. `ImportGames.jsx:31` has a similar initial games-list fetch pattern. This is source-path evidence, not a measured live outage.

Treatment: separate loading, no content, partially available data and request failure. Retain usable cached/current content where safe, expose Retry, and never tell a player to play more games merely because a request failed.

**F6 — Some action destinations have no router entry.**

`CoachPlay.jsx:3989` has `/upgrade` as a fallback; `:4282` links to `/plateau-breaker/training`. `PlateauBreakerDashboard.jsx:261`, `:268`, `:317` and `PlateauBreakerReview.jsx:479` link to `/plateau-breaker/training` or `/plateau-breaker/play`. None is declared in current `App.js`; there is also no wildcard route. The upgrade path depends on whether the backend supplies a different URL.

Treatment: verify the intended destination and required state for each action, then repair links with regression coverage. Do not assume `/training` is an equivalent replacement for a stateful enforcement flow. Unknown links need a useful recovery page, not an invented activity.

**F7 — Several roles are useful but visually indistinguishable.**

Generic heroes and cards are reused for coaching, library browsing, progress, utilities and failures. Login/Pricing and public opening guides still contain amber-led styling, while current learning pages use cream/green/lime. Legacy pages retain violet/rose treatments. This is source and screenshot evidence of mixed styling; actual computed colours must be checked before asserting accessibility failures.

Treatment: one brand, several purposeful layouts: an activity stage, a browsing library, an evidence comparison, a utility form and an operational table. Avoid making every page a giant recommendation card.

**F8 — Completion and longer-term change need separate presentation.**

The current curriculum language repeatedly promises to keep a focus until games change. It does not, by itself, communicate a finite completed session. Lesson and practice completions already exist elsewhere.

Treatment: surface the existing recorded session outcome and its next action. Do not equate “finished today's practice” with mastery, and do not introduce a separate progress database. If a durable resume/completion record is missing on a path, record that as a data dependency rather than fabricating it in the UI.

**F9 — Settings displays connection status without a nearby management action.**

`Settings.jsx` renders Chess.com/Lichess rows as connection text and a “linked” span. The existing `/import` flow owns connection work.

Treatment: place a clear action beside those statuses, using the existing import/connection journey. Keep save/error feedback at the control being edited.

**F10 — An empty result is sometimes framed as improvement.**

`PersonalMoments.jsx:97` describes no matching moments as good news and says it probably means the player has avoided the pattern. Empty matching content alone cannot distinguish good play from limited coverage, missing analysis, or filtering.

Treatment: name the result actually known, offer a valid next action, and preserve the email-to-page promise. Do not turn absence of evidence into a progress claim.

### Full route treatment inventory

Every route below is present in baseline `App.js`. “Current” describes source-visible responsibility, not proof of live availability. “Treatment” is proposed; no route is being deleted or redirected by this audit. Component paths are under `frontend/src/pages/` unless otherwise noted.

| Route | Current owner and responsibility | Proposed UX treatment |
|---|---|---|
| `/` | Landing — public coaching narrative, demonstrations, entry CTA | Keep identity; show an honest interactive-looking coaching example, concise promise and current invite-aware entry. No unsupported outcome claims. |
| `/login` | Login — email/Google auth, invite-gated registration | Consistent brand, visible field errors, submitting state and preserved intended destination; retain auth/security semantics. |
| `/invite` | RequestInvite — request access and success state | Clear eligibility, submission and next-step message; no fake acceptance or turnaround promise. |
| `/pricing` | Pricing — plans, subscription and checkout | Readable plan comparison and entitlement/checkout feedback; no price or billing-policy changes. |
| `/terms` | TermsOfService — legal text | Readable document layout and navigation; preserve legal content. |
| `/privacy` | PrivacyPolicy — legal text | Same document layout, accessible links and reading width; preserve policy. |
| `/refund` | RefundPolicy — cancellation/refund text | Same treatment; keep conditions unambiguous and unchanged. |
| `/contact` | ContactUs — contact channels and common topics | Easy-to-find support actions, consistent public frame. |
| `/prototype/interactive-moment` | PrototypeInteractiveMoment — design/demo scenario | Keep clearly marked prototype; do not expose it as a real personalised lesson. |
| `/learn/openings` | OpeningsIndex — public opening directory | Visual lesson previews and scan-friendly navigation; preserve SEO and public access. |
| `/learn/openings/:slug` | OpeningGuide — public guide, setup, rules, traps, plans | Clear article/board hierarchy and local navigation; preserve authored content and public metadata. |
| `/welcome` | ActivationHub — self-level, diagnostic, coached-game and connection choices | Keep current diagnostic-first policy pending reconciliation; make game connection visible without another wall. Short optional intake, meaningful first action. |
| `/onboarding` | Onboarding — connect account, goals, analysis and starting point | Clear steps and field states; imports must not leave the player stranded. Retain current supported alternatives while analysis runs. |
| `/diagnostic` | DiagnosticPuzzles — move/reason assessment, feedback and summary | Position-led prompts; understandable progress; retained verdicts and deliberate continuation; no diagnostic result treated as mastery. |
| `/coach` | Direct redirect to current training | Preserve compatibility; fix misleading incoming labels rather than add another coach page. |
| `/focus` | Direct redirect to current training | Preserve compatibility and exact target. |
| `/progress` | UnifiedProgress — evidence, comparison states and next action | Separate activity, practice and real-game change; show available evidence even when a particular comparison is unavailable, if API supports it. |
| `/journey` | Direct redirect to Progress | Keep alias, test navigation. |
| `/dashboard` | Direct redirect to Home | Keep alias, avoid resurrecting a dashboard. |
| `/home` | HomePageNew; canonical CurriculumHome or fallback | Short greeting, specific current activity, real start/resume state; compact import status; no duplicate Learn catalog. |
| `/learn` | PersonalCurriculum → CurriculumPrimary | Current lesson as a board-led activity; session finish separate from ongoing focus; visual exploration beneath. |
| `/today` | Direct redirect to Home | Keep alias, test navigation. |
| `/lab` | Dashboard — fallback learning/review mix | Preserve existing eligibility fallback; clarify its job and navigation. Do not remove before incoming-route and rollout checks. |
| `/coach/moments/:topic` | PersonalMoments — topic evidence from email links | Deliver the promised topic first, with relevant boards and practice; truthful empty/error states. |
| `/games` | AllGames — coach selection and own/coach game archives | One specific study recommendation with a valid position preview; compact browsable history; explicit unavailable reason. |
| `/review` | ReviewQueue — internal review list and filters | Operational table polish; visually separate from player Game Review; preserve access checks. |
| `/import` | ImportGames — Chess.com/Lichess import and game list | Connection versus import versus analysis status distinct; useful persistent outcome and next step, not toast-only completion. |
| `/replay/:gameId` | CoachReplay — guided game replay | Consistent board controls and return destination; clarify relation to full review without removing compatibility. |
| `/game/:gameId` | LabV2 → GameDecryptionV5 and review components | Board-first study, concise verified explanations, distinct actual/counterfactual lines, deliberate replay and next chapter. |
| `/lab/game/:gameId` | LabV2 — same owner as canonical review | Inherit canonical treatment; retain deep-link contract. |
| `/game-old/:gameId` | Lab — older decryption/classic presentation | Compatibility audit and minimum functional/accessibility coverage, not a second redesigned product. |
| `/weaknesses` | WeaknessTracker — separate weakness summaries | Label observations honestly; connect to canonical learning/progress. Keep until source/usage audit supports consolidation. |
| `/training` | PrescribedTraining — generic or personalised query-driven activity | One coherent activity presentation across supported modes; explicitly verify each query branch. |
| `/daily-fix/drill` | DailyFixDrill — timed habit drill | Clear timer purpose, retry/skip, unhurried feedback and honest finish; preserve timing/scoring semantics. |
| `/training/prescribed` | PrescribedTraining — same owner | Inherit shared training treatment; preserve entry parameters. |
| `/training/pattern/:pattern` | PrescribedTraining — pattern-specific entry | Keep promised pattern and origin; no generic replacement on missing content. |
| `/training/skill/:skillId` | SkillDrill — detector-graded attempts | Shared board/feedback appearance, neutral grading failure, clear retry and explicit next. |
| `/training/motif/:motif` | MotifDrill — motif demonstrations and sequence controls | Make read/demo versus attempt mode unmistakable; do not imply passive replay proves a solve. |
| `/training/geometry` | BoardGeometryLesson — module selection | Visual geometry previews, clear availability and honest learner state. |
| `/training/geometry/:moduleId` | BoardGeometryLesson — board-shape practice and checks | Consistent touch/keyboard targets, hint/reveal distinction, completion and return. |
| `/training/quiz/:openingKey` | OpeningQuizPage — compatibility redirect | Retain redirect to personalised opening lesson; test encoded key and back navigation. |
| `/openings` | OpeningRepertoire — personal recommendations and library | Specific primary recommendation, shorter titles, relevant boards, truthful labels and separate load errors. |
| `/openings/:openingKey` | OpeningLesson → guided/practice/trap components | Board-first teaching, compact controls, consistent feedback and clear lesson progression; retain existing branches. |
| `/opening-walkthrough` | OpeningWalkthrough — personal-game lesson | Consistent step/replay controls, position context and meaningful finish; verify entry and return paths. |
| `/admin/openings` | AdminOpenings — editor/validate/save/preview | Readability, explicit save/validation states; preserve authoring authority and destructive safeguards. |
| `/review/authoring` | AdminAuthoring — authoring queue | Compact queue, filters and status clarity; no player navigation promotion. |
| `/admin/captions` | AdminCaptionAuthoring — coverage and template review | Board/text comparison readability, preview/save states; no silent publishing. |
| `/admin/positional-reasons` | AdminPositionalReasons — disposition workflow | Clear evidence, keyboard/focus states and submission confirmation. |
| `/admin/reason-judge` | AdminReasonJudge — comparative judgement | Equal visual weight of blinded choices; no visual answer leakage. |
| `/admin/waitlist` | AdminWaitlist — invitation operations | Clear status and action confirmation; polish must not send invitations. |
| `/admin/geometry-gaps` | AdminGeometryGaps — geometry review | Consistent board and ruling controls, preserved evidence context. |
| `/admin/detector-review` | AdminDetectorReview — detector cases and rulings | Accessible evidence inspection, retained keyboard shortcuts and clear pending/saved state. |
| `/admin/captions/drafts` | AdminCaptionDrafts — approve/reject draft queue | Distinguish preview from approval; keep mutation consequences explicit. |
| `/admin` | AdminDashboard — users, feedback and operational tabs | Usable dense tables/forms, search, filters and view-as banner continuity; not a consumer hero layout. |
| `/admin/authoring-review` | AdminAuthoringReview — per-item edits/rulings | Board/editor balance, visible unsaved changes and clear approve/reject/skip semantics. |
| `/openings-overview` | OpeningsOverview — opening and endgame libraries | Retain endgame entry from Learn; reuse valid previews; clarify overlap with `/openings` before any consolidation. |
| `/endgames/:categoryKey/:lessonKey` | VerifiedEndgameLesson → PersonalizedLessonWorkspace | Same activity experience as other personalised lessons, not a new endgame runner. |
| `/challenge` | Challenge — weakness/random puzzle selector | Clear optional exploration mode and reliable next/retry/skip; not an extra compulsory onboarding path. |
| `/settings` | Settings — profile, connections, email and theme | Compact utility layout, connection-management links and local save/error feedback. |
| `/reflect` | Reflect — thoughts/confidence, board and feedback | Ask one relevant question at a time; keep user self-report distinct from engine facts; reduce competing panels. |
| `/mission/:missionId` | MissionRunner — briefing, protocol, positions, completion | Short briefing, obvious start, board-first exercise and honest completion; preserve existing protocol and scoring. |
| `/play-with-coach` | CoachPlay → setup, board and coaching panels | Resume/setup clarity, one active coaching message, readable timeline, reconnect/error and postgame states. No controller switch or grading change. |
| `/recover/:gameId` | PostLossRecovery — single-loss help and full-review link | Calm, non-shaming invitation with an actual position; keep optional full analysis and exit. |
| `/plateau-breaker` | PlateauBreakerDashboard — enforced-learning summary | Repair unregistered destinations after state-contract check; clearly communicate enforcement, preserve existing policy. |
| `/plateau-breaker/review/:gameId` | PlateauBreakerReview — review, lines, practice handoff | Consistent line labels/controls, verify handoff state and destination; do not confuse actual and alternative moves. |
| `/plateau-breaker/apply` | ApplyMode — constrained game and checklist | Explain current mode, input/feedback state and finish; do not change move enforcement in a UX patch. |

### Cross-route surfaces not counted as separate route declarations

- `AuthCallback` is invoked via the legacy session fragment branch; preserve authentication completion and safe return behavior. Do not redesign by weakening auth checks.
- `ProtectedRoute` loading, unauthenticated, onboarding redirect and resumed deep-link states affect every protected page.
- `ViewAsBanner` is globally rendered. It must remain unmistakable in any admin viewing-as-user session.
- Shared notifications, menus, toasts, dialogs, entitlement dialogs and payment handoffs need focus, keyboard, error and small-screen checks.
- The two board renderers have different interaction contracts. Share appearance where safe, not controllers. Preserve orientation, FEN, move legality and promotion handling.
- The current `experience-v1` CSS includes broad overrides. Inspect computed styles and precedence before adding another layer of overrides.
- Page files not reachable from current routes are not automatically deleted or redesigned. Incoming dynamic links and legacy compatibility need separate evidence.

### Proposed original design direction

The organising idea is a coach who has prepared the board, not a dashboard that asks the student to prepare their own curriculum.

- **Home:** what should I do now, and where did we stop?
- **Learn:** the current learning activity and optional exploration.
- **Game Review:** why this game/position is worth studying, followed by the actual study.
- **Play:** a playable board and well-timed, understandable help.
- **Progress:** what is recorded, what changed in games, and what cannot yet be concluded.
- **Import/account:** concise, dependable tools, not another coaching speech.
- **Internal tools:** efficient evidence work, not consumer storytelling.

Carry cream/forest/lime consistently; use restrained semantic colours with text/icons. Make board previews real and relevant. Give success time to be understood. Use animation to explain state and chess sequences, not to obscure latency. Do not invent a coach character, imitate another product's skin, or add gamification as a substitute for useful teaching.

Session completion must have an ending even while a long-term focus remains active. Recommendation is a default, not a prison: exploration and stopping remain possible.

### Proposed implementation order after the scope amendment is approved

1. **Shared foundation and complete first slice:** existing tokens, compact headers, activity/utility states, navigation contracts; Learn → real lesson → verdict → completion → return. Validate the whole slice rather than calling new CSS a finished experience.
2. **Arrival and ongoing guidance:** Landing/Login/Invite, Welcome, Onboarding/Diagnostic, Import and Home. Preserve current invite and onboarding policy; reconcile prior onboarding work before changing it.
3. **Teaching and review:** opening/endgame/geometry libraries and workspaces, game selection, review/replay, specialist drills, reflection and recovery. Do not expose gated proof families merely to fill an attractive card.
4. **Playing and seeing change:** PWC presentation and postgame handoff, Progress and Settings. Preserve evidence lineage and controller choice.
5. **Completeness pass:** public guides, legal/contact/pricing, internal tools, compatibility routes, empty/error states, keyboard/mobile/dark/reduced-motion coverage.

All route families remain in the audit; sequence is not silent removal from the requested work. Each slice requires its own evidence before handoff.

### Verification requirements to carry into the scope amendment

- Every changed page: ready, loading, empty, partial/error, success and resumed state where applicable; no catch block presents failed transport as a student deficit.
- Desktop/mobile, both themes, keyboard navigation, visible focus, text scaling, reduced motion and measured contrast. Screenshot impressions are not accessibility measurements.
- Role/eligibility differences: new player, existing player, personalised enabled/disabled, and admin/reviewer. Do not use the founder's admin-only journey as the sole acceptance case.
- All 66 routes accounted for; shared wrappers and query modes explicitly exercised. Check incoming email links and return URLs, not only top-level navigation.
- No board preview or pre-answer prompt leaks a solution in assessment mode. Demo, hint-assisted success and unassisted attempt remain distinct.
- Feedback remains legible; transport error is not a wrong move; duplicate submission and reconnect do not create duplicate attempts.
- Measure click-to-feedback and first-useful-content latency before blaming Stockfish or adding new engine work. Do not declare a latency improvement from frontend tests alone.
- Existing frontend tests and production build, targeted backend tests if any backend-authored copy or response is changed, and mandatory core flow suite when applicable. Compare failures against the same baseline.
- Actual rendered and authenticated journey QA is required before release; the current browser-tool failure does not waive it.
- Completion/resume must be verified against durable existing records. An attractive mock completion is not acceptance.
- Preserve canonical ranking, thresholds, authorisation, flags, payment behavior, saved evidence and teaching engines. Missing data contracts become explicit work items, not synthetic client-side facts.
- Behavioral evaluation should compare task initiation, successful completion, unnecessary backtracking and correct resumption against baseline. Do not invent retention or conversion targets without measurements; do not conflate visual preference with learning.
- Deployment remains with Claude. Handoff must identify commits, actual checks, unrun checks, rollout exposure and rollback. No whole-site enablement hidden in a styling change.

### Scope decision and pause

**Recommended path: EXTEND existing.** Reuse the current route owners, shared visual primitives and canonical recommendation/lesson/review/progress services. Refresh the prior frontend scope through an explicit amendment based on this audit. Do not build another frontend, another lesson framework, or another progress model.

Per `scope-driven-development`, significant overlap has been surfaced before a new full scope is written. The next approval is agreement to this EXTEND path and the boundaries above; then the amendment will contain literal screen/state mockups and pre-code acceptance checks. No implementation signoff or completed redesign is claimed by this audit.
