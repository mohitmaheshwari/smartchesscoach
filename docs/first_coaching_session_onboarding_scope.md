# First Coaching Session — Onboarding Extension

Status: DRAFT — product direction approved; this detailed scope awaits Mohit's sign-off.
Date: 2026-09-18.
Decision: EXTEND the existing onboarding and diagnostic surfaces.
Evidence base: local origin/working-code at 8c6685c1, inspected read-only. This is not a verification of the deployed image, live pool, or the reported player's session.
No implementation, deployment, account enrollment, or production data changes accompany this document.

## 0. Existing surfaces audit

| Existing surface | What it already does | Extend, preserve, or repair |
| --- | --- | --- |
| `frontend/src/pages/ActivationHub.jsx` and `/welcome` | Offers positions, PWC and account connection; optional experience and motivation; starts value actions without awaiting a profile-save round trip. | Preserve immediate entry. Make the recommended action a first lesson. Keep importing prominent and optional. |
| `frontend/src/pages/Onboarding.jsx` | Verifies accounts, requests imports, then requests a priority first-game review. Can navigate to a game before analysis is ready. Includes synthetic progress stages. | Decouple useful coaching from provider/import/analysis completion. Render actual import states, not invented completion percentages. |
| `frontend/src/pages/DiagnosticPuzzles.jsx` and `/diagnostic` | Starts/resumes puzzles, submits moves, shows feedback and a diagnostic result, offers training. Advances after two seconds. | Host the first-session interaction here; preserve deliberate feedback, teach, replay and try a changed position. No second onboarding destination. |
| `backend/routes/diagnostic.py` | Chooses V2 when enough current graded pool rows exist; otherwise legacy. Supports adaptive selection, partial exits and multi-step calculation. | Preserve compatibility and resumability. Separate assessment from assisted teaching. A correct intermediate step has `step_verdict` with `verdict: null`; repair its UI treatment. |
| `backend/services/diagnostic_service.py` | V2 grades against content-bound frozen move evaluations, accepts graded alternatives and adapts difficulty. Writes provisional diagnostic focus through existing profile/memory paths. | Keep deterministic grading. Replace unsupported concept-template explanations with evidence-bound teaching. A capture is not necessarily a net material win. A move grade is not proof of understanding. |
| `backend/routes/coach.py` and `test_diagnostic_focus_reaches_the_home_page.py` | Existing read-side fallback exposes diagnostic focus as provisional when no game-backed focus exists. | Reuse this distinction; do not create a competing writer into the game-evidence focus store. Verify the full destination, not just the fallback helper. |
| `PersonalizedLessonWorkspace.jsx`, `personalized_lesson_adapter.py`, central caption/fact services and `learning_evidence_ledger.py` | Existing training presentation, proof/authorization boundaries and learning-evidence infrastructure. | Inspect and reuse suitable contracts. They are not automatically wired into onboarding. The local `07b4632e` lesson repair is separate work, not evidence that diagnostic feedback is fixed. |
| `backend/routes/journey.py` and `backend/analysis_worker.py` | Existing first-game priority and queued analysis. | Preserve prioritization; investigate actual delay before changing throughput. Never rerun stored game analysis just to power onboarding. |

Prior decisions: `docs/activation_hub_scope.md` records the removal of an account-link wall and a historical 32% inactive-signup finding. That is historical evidence, not a new measurement or proof of causality. `docs/diagnostic_v2_scope.md` describes a longer assessment; current code uses offline grading rather than that document's original runtime-engine design. `memory/project_diagnostic_onboarding_20_puzzles.md` already requires useful activity while analysis runs.

Overlap: account connection, adaptive puzzles, feedback, partial persistence and provisional coaching already exist. The missing value is a short, coherent teaching encounter that works before game analysis and continues meaningfully on the next visit.

Decision: EXTEND. No new onboarding page, diagnostic engine, lesson taxonomy, rating model or parallel coach. This revises the prior conversation's connect-first CTA recommendation: the first lesson remains primary; import becomes visibly available near it, never a wall. Final approval includes this correction.

## 1. What it is

ChessGuru welcomes a player by coaching them through a real chess decision, explaining a verified consequence, and helping them recognize the idea in another position. Their games can arrive in the background. The session ends with an honest account of what they did and a clear next lesson, not a compulsory long exam, an empty dashboard or a claim that the coach already understands their entire chess ability.

## 2. What the user sees

### Welcome

> Let's find something useful for your next game.
>
> Make a move, and I'll help you understand what happens next.
>
> **Start my first lesson**
>
> **Bring my Chess.com or Lichess games**
> We can start learning while your games are being analysed.

The import card is visible beside/below the primary action without scrolling past a questionnaire on the supported mobile layout. PWC remains an available secondary choice. An optional experience question helps choose a starting position; it is not presented as a measured rating.

### First decision

> It's your turn. What would you play?
>
> [Interactive board, with side to move clear]
>
> [Give me a hint] [Continue later]

The first unaided prompt does not reveal the target tactic. Requests for help are recorded as assistance, not treated as failure. No compulsory generic reason question appears before or after every move.

### Coaching response

Illustrative copy below is conditional on the exact position proving the statement; it is not an already-authored chess example:

> Your rook was protected before that move. Moving the bishop took away its defender.
>
> [Show me what happens] [Let me try again]

The demonstration starts from the relevant board, shows the verified consequence and can be paused/replayed. A safe alternative gets its own supported feedback, not rejection merely for differing from the stored best move. If a move is acceptable but its idea is not explained by available evidence, say only what is supported and offer the verified demonstration separately.

After an appropriate retry:

> Yes — you kept the rook protected.
>
> [Replay] [Try a different position]

Feedback stays until the player chooses to continue. Recognition combines a visible mark with text; it does not rely on green alone. No automatic two-second advance.

### Recognizing the idea elsewhere

> Let's try another position. What would you play here?

Use a genuinely different verified position testing the same relationship, not a cosmetic clone or an identical answer in disguise. Where useful, a position-specific question asks the player to identify a threat, piece, defender or consequence. Choices are board-verified, plausible and answer-position balanced; no static "it uses the rule" filler. Not every position requires a multiple-choice explanation.

### Session end and return

When supported by the attempts:

> You found the safe move in the second position without a hint.
> Next, we'll practise spotting the threat before choosing where to move.
>
> [Continue with my coach] [Finish for today]

If help was needed, acknowledge the learning without claiming independent success. If they already handled the idea well, offer an appropriate next challenge rather than inventing a weakness. The next visit resumes the unfinished teaching or offers the promised continuation.

An analysed personal game is offered at a natural stopping point, not by replacing a live board. Say "Here is the same idea in your game" only when evidence establishes that match. Otherwise offer it as a different useful decision. Imported-game availability is not required to finish this session.

## 3. In scope (V1)

- Extend `/welcome`, `/onboarding`, `/diagnostic` and the existing Home continuation. Preserve the optional longer diagnostic instead of making full completion the first-value gate.
- Keep account connection prominent, dismissible and recoverable. An import failure, empty account or slow provider cannot prevent a supported starter lesson. Background jobs must survive leaving the link screen; starting a browser request and navigating away is not sufficient implementation.
- Deliver a complete encounter: unaided decision, supported feedback, optional explanation/demonstration, retry where appropriate, changed-position practice and honest continuation. Let the player finish early and resume.
- Audit and curate existing verified content into complete teaching encounters. A frozen grade map alone does not prove an explanation or a transfer pairing. Enroll only where current, independently reviewed teaching content is available.
- Keep deployed authorization and content-version checks. No weakening admission or replacing missing causal proof with an eloquent template. Do not assume every diagnostic concept has teachable content today.
- Accept already-verified sound alternatives under the existing acceptance contract. Distinguish move quality from target-idea demonstration and from independent understanding. Unknown grades are unverified, not wrong; offer a supported path without inventing analysis.
- Normal starter grading and demonstrations use precomputed evidence; no runtime LLM or Stockfish dependency. Refreshing content evidence is an explicit offline operation, not an invisible request-time fallback.
- Correct the intermediate-step verdict mismatch and preserve readable feedback until explicit continuation. Playback, hint, retry and changed-position interactions are new integration work in this host, not assumed free reuse.
- Record unaided, hinted, demonstrated and retried attempts separately. Learning after a demonstration cannot strengthen the original diagnostic as if it were an independent first attempt. Repeated submission/reload must not double-count evidence.
- Persist feedback/next-step state sufficiently to resume correctly after refresh, reconnect and sign-in. A client-held card with server-side advancement alone does not meet this requirement.
- Reuse provisional coaching memory and existing learning evidence; keep organic-game progress and lesson-transfer claims unchanged. A starter lesson never fabricates a historical baseline or Plan-grade diagnosis.
- Show genuine import states and recoverable actions. Preserve existing queue priority. Capture timing from entry to playable position and to a visible useful explanation, not just a returned game ID.
- Provide mobile, keyboard, contrast, reduced-motion and loading/error behavior. Board controls, playback and overlays cannot block the next legal action.
- Default-off rollout with account-level eligibility checked at all relevant endpoints. Role-only access is not sufficient for isolating a named pilot. Preserve in-progress legacy sessions and have a documented mid-session rollback path.

## 4. Explicitly out of scope (V1)

- A new onboarding engine/page alongside the existing journey; a redesign of the whole app.
- New chess detectors, universal idea coverage, new rating inference, Maia integration or new production LLM use.
- Running Stockfish again on imported games that already have analysis; production backfills or broad database exports without separate authorization.
- Claiming a true rating, complete weakness profile, permanent mastery or rating improvement from this short session.
- Rebuilding PWC or making a full coached game compulsory. Its existing behavior and separate repair work remain separate.
- Automatic matching to the player's own game without verified shared evidence, or labelling generic/community content as their own.
- New paywall/pricing, mandatory streaks or notification enrollment. Payment and return experiments require a separate approved measurement plan.
- Broad promotion or retirement of legacy flows before content, compatibility and real-user gates pass.

## 5. Success criteria

Product acceptance is a completed coaching encounter, not successful signup or HTTP 200:

- A fresh eligible non-admin user can make a move, see a position-specific verified explanation, control replay/continuation, attempt a changed position and reach the promised next activity without any imported game finishing analysis.
- The same journey remains usable when account linking is skipped, import is slow/empty/failed, the player asks for help, chooses a sound alternative, gets everything right, refreshes mid-feedback or returns later.
- Invalid/stale content cannot produce a chess claim or fake successful grading. Missing eligible content produces an honest safe alternative; it is recorded as a failed first-lesson delivery, not counted as activation.
- Independent review grades factual correctness, causal explanation, transfer-pair suitability and teachability separately. Any verified critical false claim blocks that content from exposure. Numerical promotion gates remain the existing authorized ones; this scope does not lower them.
- A tester can follow the full cold-user journey on the deployed candidate, including its Home continuation, without admin privileges, manual database repair or the founder explaining where to click.
- During a pilot, compare meaningful encounter completion, unassisted changed-position performance, next-session continuation and return behavior with an explicitly defined eligible cohort/control. Report denominators, assistance, content availability and drop-off stages. Assisted success is not evidence of independent transfer; immediate transfer is not proof of durable game improvement.
- Response-time budgets, pilot size, observation window and improvement thresholds must be locked from baseline measurements before the experiment. No unmeasured "instant" claim or invented conversion target. Until those decisions and pilot results exist, report functional readiness separately from proven retention benefit.

## 6. Open questions

- **Which starter ideas and changed-position pairs are ready?** Existing grades do not prove teaching quality. Inventory current pool evidence, legal candidate coverage, explanations and pairings; independently review complete encounters before choosing the starter set. If none qualify, content preparation is a blocker, not a reason to ship generic copy.
- **Where did the reported player's delay occur?** The affected account/session has not been traced in this audit. Inspect an authorized read-only timeline covering connection, import, queue, analysis, provisional focus and first visible teaching; distinguish wait time from user inactivity. Do not attribute an hour to Stockfish without that evidence.
- **How short should the first session be?** The product boundary is one useful encounter with a voluntary exit, not a guessed universal puzzle count. Observe existing completion/drop-off and representative usability sessions before locking time or branching limits.
- **Which shared interaction/evidence contracts can be reused safely?** Map exact supplier for hint, playback, retry, feedback persistence and transfer recording; reconcile `07b4632e` against the integration base. Do not copy whole stale files or assume a lesson fix repaired onboarding.
- **What happens when historical analysis supersedes diagnostic mid-session?** Preserve the active teaching encounter and transition at a user-chosen boundary; specify compatibility with current `/diagnostic/start` supersession before implementation.
- **Who is the first cohort and how is success judged?** Name test accounts and a representative non-admin cohort, obtain the baseline, then lock latency/behavior criteria and a dated review. Founder access alone cannot establish rollout readiness. Proposed rollout sequence is internal A/B for one week, an approved 10% eligible cohort for one week, then broader release only on evidence; legacy removal requires two clean weeks at full rollout. These are process stages, not evidence that a small sample establishes retention.

## 7. Pre-code requirements

- Mohit explicitly signs off this scope, including lesson-first entry with prominent optional import and preservation of the longer diagnostic as optional.
- Complete the existing-surface/state contract audit against the then-current integration base. Record the previous lesson repair's actual integration/deployment status and preserve other agents' changes.
- Produce a separate implementation specification using `draft-feature-spec`, naming affected files, endpoint/session compatibility, evidence writes, component ownership, account-scoped default-off flag and rollback behavior. The architecture follows the approved experience; it is not silently bundled into this scope.
- Read `single-source-of-truth` before designing domain data/services. Reuse existing graders, proof contracts and learning stores; document any necessary new content package without introducing a competing source of chess truth.
- Perform a content feasibility/coverage audit and build at least one legally verified, fully teachable example encounter for product review, including wrong move, accepted alternative, help and a changed-position check. Do not promise unsupported branches from cp-loss alone.
- Use `lock-via-data` for numeric thresholds and candidate-ranking choices. Confirm baseline instrumentation and latency evidence; distinguish unavailable production access from zero activity. No fabricated measurement.
- Run `audit-pre-code` after scope and required decisions are approved. Plan unit, API-integration and browser journey tests, plus failure injection for slow imports, stale evidence, retries, account isolation and resume.
- Deployment handoff must include real browser evidence from a non-admin cold-start account, not only test counts. Hard rollback triggers include false chess claims, rejected verified alternatives, assistance contaminating unaided evidence, cross-account exposure or blocked resume. On rollback preserve attempts and explain the change to a mid-session player; never silently erase their lesson.
- No push, deployment, enrollment, engine runs, model calls or production writes are authorized by creation of this document. Claude retains the previously agreed push/production deployment role.
