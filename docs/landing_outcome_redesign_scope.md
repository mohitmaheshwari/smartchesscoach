# ChessGuru Landing Outcome Redesign — Scope

## 0. Existing surfaces audit

ChessGuru already has one public landing page at `/`, a separate pricing page, a sign-in flow, a post-signup welcome page, a diagnostic, a personalized home page, training, and progress tracking.

The current landing page already provides a polished dark visual system, navigation, Google sign-in, pricing and legal links, SEO content, analytics hooks, a coaching demonstration, feature explanations, comparison copy, onboarding steps, and an FAQ. Its message is primarily: ChessGuru remembers recurring mistakes and offers many coaching features.

The diagnostic already estimates a playing-strength range, identifies a headline focus, and sends the player into training. The authenticated home page already presents one current focus and a personal improvement cycle. The training page already teaches the selected focus. The progress page already reports clean games and reduction in recurring patterns. These are the real product surfaces the landing page should explain.

The overlap is substantial: the existing landing page tries to explain game review, pattern memory, puzzles, openings, traps, endgames, coach play, strength scores, and progress independently. The genuine new value is not another feature. It is a single public story connecting the existing surfaces into an improvement promise: evaluate the player, choose a target, build a personal plan, teach it, and verify whether it transfers to real games.

Decision: **REPLACE existing**. The `/` route remains canonical, but its feature-catalogue presentation is replaced by an outcome-led sales experience. Pricing, authentication, diagnostic, home, training, progress, SEO, analytics, and legal routes are extended or reused rather than duplicated.

## 1. What it is

The redesigned landing page explains ChessGuru as a personal improvement system for 600–1500-rated players. A player connects their games, tells ChessGuru where they want to reach and how much time they have, receives an evidence-based coaching plan built from how they actually play, learns the missing chess knowledge through personal positions and carefully selected examples, and sees whether the targeted weakness stops recurring in future games. The page sells this outcome clearly and credibly without promising a guaranteed rating increase by a fixed date.

## 2. What the user sees

### Navigation

```text
ChessGuru                         How it works   The plan   Proof   Pricing   Sign in
                                                                  Build my plan
```

### Hero

```text
PERSONAL CHESS IMPROVEMENT FOR 600–1500 PLAYERS

Your next 100 rating points
need a plan built from your games.

ChessGuru discovers what is actually holding you back, teaches the
chess you need next, and tracks whether the weakness disappears from
your real games.

[ Build my improvement plan ]    [ See a real example ]

Works with Chess.com and Lichess · Free to start · No credit card
```

Beside the hero, the user sees a believable product preview:

```text
YOUR 1200 PLAN

Current playing range        1080–1140
Goal                         1200
Time available               20 minutes/day
First coaching cycle         21 days

WHAT IS HOLDING YOU BACK
Threat response after an attacked piece

Why ChessGuru chose it
• Appeared in 9 of your last 28 games
• Becomes worse when you move quickly
• Costs more games than your opening mistakes

This week
Learn → Practise → Blind test → Play → Verify
```

The example is explicitly labelled as an illustrative player plan unless every displayed fact comes from an approved, anonymized customer case.

### Core story

```text
ONE RATING DOES NOT EXPLAIN YOUR CHESS

An 1100 player can have 1250-level tactical recognition and 950-level
piece safety. Generic lessons treat both players the same. ChessGuru
does not.
```

The page then shows four concise stages:

```text
1. Evaluate
   Connect your games or complete the diagnostic. ChessGuru studies
   recurring decisions, not one isolated blunder.

2. Build your plan
   Choose a target and available time. ChessGuru selects the smallest
   set of skills currently separating your play from that target.

3. Learn and apply
   Learn the idea, practise with guidance, solve unseen positions, and
   play with one clear instruction.

4. Prove improvement
   ChessGuru checks future games. When the weakness stops recurring,
   the plan moves to the next bottleneck.
```

### Personalized teaching demonstration

```text
The same lesson should not sound the same for everyone.

Your game:
You moved the attacked knight, but it was defending e4.

Your coach:
Before moving an attacked piece, rebuild what it protects. In three of
your recent games, the first loss happened after a defender moved.

Today’s practice:
Five different positions where an attacked piece is also a defender.
The theme is hidden during the final test.
```

### Improvement proof

```text
WE DO NOT CALL A PUZZLE STREAK IMPROVEMENT

Before this coaching cycle       0.38 incidents per game
After 8 comparable games         0.17 incidents per game
Current status                   Improving — still being measured
```

This section uses an illustrative label until a fully verified, anonymized real outcome is approved for marketing.

### Curriculum breadth

The page shows openings, traps, endgames, tactics, positional understanding, calculation, and decision habits as resources inside the personal plan—not as unrelated product modules.

```text
ChessGuru can teach the whole game.
Your evidence decides what comes next.
```

### Final conversion

```text
Stop guessing what to study next.

Connect your games. Choose your goal. Let ChessGuru build the plan.

[ Build my improvement plan ]

Free to start · No credit card · Your plan changes as your chess changes
```

## 3. In scope (V1)

- Replace the current `/` landing-page presentation while retaining the canonical route.
- Create a responsive, premium visual design for desktop, tablet, and mobile.
- Lead with the personal improvement-plan outcome rather than the AI-coach feature category.
- Present one coherent journey: evaluate, plan, learn, play, verify, adapt.
- Show a clear illustrative “Your target plan” product preview above the fold.
- Make “Build my improvement plan” the primary CTA throughout the page.
- Route the primary CTA through the existing authentication and post-auth activation flow.
- Preserve sign-in, pricing, legal, SEO, accessibility, and analytics behavior.
- Reframe openings, traps, endgames, puzzles, positional concepts, and coach play as tools selected by the personal plan.
- Reuse truthful product capabilities already present in diagnostic, home, training, and progress surfaces.
- Clearly label illustrative plans and progress evidence so mock data cannot be mistaken for a customer result.
- Include focused sections for the problem, personal evaluation, example plan, teaching method, real-game proof, curriculum breadth, FAQ, and final CTA.
- Add frontend tests for primary navigation, CTA routing, disclosure labels, responsive-critical content, and preservation of public links.
- Keep animation purposeful and lightweight, supporting hierarchy without delaying comprehension or interaction.

## 4. Explicitly out of scope (V1)

- No guaranteed claim that a player will gain 100 Elo or reach a target rating in 21 days.
- No unverified testimonials, customer counts, improvement percentages, investor logos, or authority badges.
- No Maia, Otter, or new learner-model implementation as part of the landing-page redesign.
- No change to detector authorization, puzzle admission, curriculum selection, or improvement calculations.
- No new pricing model or payment implementation.
- No duplicate public landing route or campaign microsite.
- No redesign of authenticated home, training, diagnostic, progress, or pricing pages in this scope.
- No live interactive chessboard requiring backend inference on the public landing page.
- No claim that ChessGuru has determined a precise “true Elo” for every chess skill before that measurement is calibrated.
- No large catalogue of every feature ChessGuru contains; secondary capabilities remain supporting evidence rather than the page structure.

## 5. Success criteria

- In a controlled comparison, the redesigned page produces a higher visitor-to-authentication-start rate than the existing page without increasing authentication failures.
- A new visitor can state, after viewing the hero and plan preview, that ChessGuru evaluates their games, builds a personal goal-based plan, and checks future-game improvement.
- The primary CTA takes a signed-out visitor into the existing authentication flow and preserves the intended post-auth destination.
- The page communicates the core value on a mobile viewport without requiring the user to pass a feature catalogue first.
- Every quantitative result shown on the page is either sourced from approved evidence or visibly labelled illustrative.
- Existing pricing, sign-in, legal, SEO, and analytics contracts continue to work.
- Automated accessibility checks find no critical violations, keyboard navigation reaches every interactive element, and reduced-motion users receive a complete experience.
- The production build succeeds and the landing-focused frontend test suite passes before handoff.

Numeric conversion thresholds will not be invented from contaminated pre-launch history. The release comparison and minimum sample will be locked against an approved measurement protocol before rollout.

## 6. Open questions

- **Question:** Should the example target be 1100 to 1200, or should the plan preview adapt to a rating selected by the visitor?
  **Why unresolved:** An interactive selector may increase relevance but also adds friction and complexity above the fold.
  **Unblocking step:** Compare the static and selector mockups during the landing review and choose one before implementation.

- **Question:** Does “Build my improvement plan” lead first to Google authentication or to a short goal/time capture?
  **Why unresolved:** Capturing intent first may strengthen commitment, while authentication first preserves the current funnel and avoids anonymous state.
  **Unblocking step:** Inspect the existing post-auth redirect and activation instrumentation, then lock the lowest-friction route before coding.

- **Question:** Which approved real evidence, if any, can replace the illustrative improvement card at launch?
  **Why unresolved:** Current structural corpus measurements are not customer outcome claims, and live coaching-transfer sessions are still an external input.
  **Unblocking step:** Marketing evidence review must approve an anonymized case; otherwise V1 keeps the illustrative disclosure.

- **Question:** Should pricing appear as a compact section on the landing page or remain a navigation destination only?
  **Why unresolved:** The present pricing contract is separate, but investors may expect the business model to be legible without another click.
  **Unblocking step:** Review the current pricing tiers and choose compact summary versus link-only during visual sign-off.

## 7. Pre-code requirements

- Mohit explicitly signs off on this complete scope document.
- The static-versus-interactive target-plan preview is selected.
- The primary CTA destination is verified against the current authentication and activation flow.
- Existing landing analytics events and pre-change funnel evidence are inventoried so the redesign remains measurable.
- Every player-facing quantitative claim is classified as verified evidence or illustrative content.
- The existing landing-page tests, public-route tests, SEO behavior, and pricing/legal navigation contracts are identified.
- Numeric rollout and conversion thresholds, if required, are locked through the repository’s data-driven decision process rather than chosen from intuition.
- The pre-code feature audit is completed before the first frontend source edit.
