# ChessGuru Landing Page Visual Redesign — Scope Document

**Status:** APPROVED FOR IMPLEMENTATION — Mohit: "go ahead" on 2026-09-02  
**Date:** 2026-09-02  
**Path:** Replace the current visual composition; preserve the working acquisition infrastructure.

## 0. Existing surfaces audit

### The user need

A first-time visitor should understand within one screen that ChessGuru studies their real games, identifies one mistake they repeat, and turns that evidence into personal practice. The page should feel authored by a distinctive chess product—not assembled from familiar AI-product gradients and card patterns—and it should prove the promise with convincing board-led visuals.

### What already exists

| Existing surface or asset | What it already provides | Decision |
|---|---|---|
| `frontend/src/pages/Landing.jsx` | A complete public page with navigation, Google sign-in, dev login, Pricing link, responsive behavior, motion, comparison, FAQ schema, policy links and repeated CTAs. Its central promise is accurate, but the page is roughly 1,000 lines and repeatedly presents text beside synthetic rounded UI cards. | **REPLACE the composition; preserve the wiring and strongest copy.** |
| Landing hero `CoachingDemo` | A working animated coach panel that demonstrates move feedback and pattern memory, but no board is visible and the presentation resembles a generic AI chat/SaaS demo. | **REPLACE** with a board-led, authentic product story. |
| Landing mock components | Hand-built illustrations for pattern memory, Lab, training, strength profile and escape squares. They communicate breadth, but their repeated dark-card geometry makes the product look mocked rather than real. | **RETIRE from the landing page.** Reuse only factual ideas that support the central cycle. |
| `chessguru-logo*.svg` and `og-image.png` | Existing logo variants and one social image; no meaningful library of landing-page product captures or editorial chess imagery. | **REUSE logo initially; CREATE a focused visual asset set.** Logo replacement is not required for this page V1. |
| `/login`, `/pricing` and activation routes | Working downstream acquisition and activation surfaces. | **PRESERVE routes and behavior.** This scope does not redesign those pages. |
| `docs/frontend_experience_ui_ux_scope.md` | Signed-off “Warm Intelligence” direction: a recognizable product, board as visual hero, editorial hierarchy, restrained amber/teal semantics and closed-loop landing story. | **INHERIT.** |
| `docs/personal_improvement_cycle_scope.md` | Makes the improvement cycle the product: evidence-backed diagnosis, one memorable instruction, practice, transfer and honest proof. It specifically asks Landing to reduce feature-led positioning. | **INHERIT.** |
| `docs/product_claim_honesty_register.md` | Prohibits unsupported improvement, mastery and resolution claims. | **HARD CONSTRAINT.** Marketing examples are labelled as demonstrations; claims use only implemented evidence levels. |

### Overlap

The current page already serves acquisition, explains the product, answers objections and routes visitors into authentication. A parallel public page would duplicate those responsibilities. The redesign therefore replaces the presentation inside the canonical `/` route rather than adding another route or marketing microsite.

### Genuine differentiation

- One board-led visual story instead of six similarly framed feature demonstrations.
- Authentic product captures or faithful product scenes rather than fabricated dashboard cards.
- An editorial layout with varied scale, whitespace and image treatment instead of repeated section templates.
- One memorable closed loop: **notice → explain → practise → carry into games → compare evidence**.
- A warmer human presence without generic stock-photo testimonials or invented customer claims.
- Mobile visuals designed as first-class compositions rather than desktop cards stacked vertically.

### Decision

**Path: REPLACE the current landing-page visual composition and EXTEND its working infrastructure.** Preserve route, authentication, Pricing navigation, SEO/FAQ schema, policy links, analytics hooks, reduced-motion behavior and honest product claims. Remove the repeated mock-card showcase and rebuild the page around authentic board/product imagery.

## 1. What it is

The redesigned ChessGuru landing page is a premium, board-led explanation of the personal improvement cycle. It opens with a real chess moment and a plain-English coaching insight, then shows how that same mistake becomes personal practice and later evidence. The page feels like a thoughtful coach's study: warm, precise, calm and unmistakably about chess. It does not sell “AI” as decoration or present ChessGuru as a collection of unrelated tools.

## 2. What the user sees

### Art direction

- Deep ink and warm ivory create the base; amber identifies the coach and teal identifies forward progress.
- Large boards and position crops carry the visual story. Chess notation and engine numbers remain supporting evidence.
- Product scenes use real ChessGuru components or faithful captures from implemented screens. If an illustrative composition is required, it is visibly editorial—not presented as a literal screenshot.
- Photography, if used, is limited to one quiet human moment and must feel documentary rather than like stock advertising. The V1 can succeed without photography.
- Rounded containers are used only where the product itself needs them. Sections are separated by composition, type, space and imagery—not a stack of glowing cards.
- Motion explains sequence: a mistake is noticed, a reason is revealed, and the position becomes practice. It does not animate every heading for spectacle.

### Desktop page contract

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ ChessGuru                  How it works   Why ChessGuru   FAQ   Sign in      │
│                                                               [Start free]  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ YOUR GAMES ALREADY SHOW                 ┌──────────────────────────────────┐ │
│ WHAT TO WORK ON NEXT.                   │          REAL BOARD              │ │
│                                         │                                  │ │
│ ChessGuru finds the mistake you repeat  │  “Your knight moved, but the     │ │
│ and turns your own positions into a     │   piece behind it was left       │ │
│ plan for breaking it.                   │   undefended.”                   │ │
│                                         │                                  │ │
│ [Connect my games]  [Watch the loop]    │  Seen in 3 recent games          │ │
│ Works with Chess.com and Lichess        └──────────────────────────────────┘ │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ A blunder is one move. A pattern is what keeps costing you games.            │
│                                                                              │
│ [three board crops from different games connected by one visual motif]       │
│ “Different positions. The same habit: moving before checking what becomes    │
│  loose.”                                                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│ ONE CONTINUOUS COACHING LOOP                                                  │
│                                                                              │
│  01 NOTICE           02 EXPLAIN          03 PRACTISE        04 CHECK AGAIN    │
│  board + evidence →  plain-language  →   own-game puzzle → later-game window │
│                                                                              │
│  The sequence reads horizontally as one story, not four feature cards.       │
├──────────────────────────────────────────────────────────────────────────────┤
│ FROM YOUR LOSS TO YOUR NEXT REP                                               │
│                                                                              │
│ ┌───────────────────────────┐       ┌─────────────────────────────────────┐ │
│ │ large training board      │       │ “Before moving a piece, check what  │ │
│ │ from the same position    │       │  it was protecting.”               │ │
│ │                           │       │                                     │ │
│ │       Find the safe move  │       │ One instruction. Repeated until it  │ │
│ └───────────────────────────┘       │ survives a real game.               │ │
│                                     └─────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────┤
│ WHY THIS IS NOT ANOTHER ENGINE REPORT                                         │
│                                                                              │
│ Ordinary analysis: “Move 23 was −2.4.”                                        │
│ ChessGuru: “Moving the knight uncovered your rook. Check what a piece is      │
│             protecting before it leaves.”                                    │
│                                                                              │
│ [honest comparison]                    [small implemented-capability proof]   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Built for players rated 600–1500 who are tired of repeating the same mistake.│
│ [Connect my games]                                                            │
│                                                                              │
│ FAQ                                                         Footer/legal     │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Mobile page contract

```text
┌──────────────────────────────┐
│ ChessGuru         [Start]    │
│                              │
│ YOUR GAMES ALREADY SHOW      │
│ WHAT TO WORK ON NEXT.        │
│                              │
│ [Connect my games]           │
│ Chess.com + Lichess          │
│                              │
│ ┌──────────────────────────┐ │
│ │      full-width board    │ │
│ │ coaching note overlaps   │ │
│ │ the lower edge           │ │
│ └──────────────────────────┘ │
│                              │
│ Different games.             │
│ The same habit.              │
│ [swipeable board evidence]   │
│                              │
│ NOTICE                       │
│   ↓                          │
│ EXPLAIN                      │
│   ↓                          │
│ PRACTISE                     │
│   ↓                          │
│ CHECK AGAIN                  │
│                              │
│ [final CTA]                  │
│ FAQ + legal                  │
└──────────────────────────────┘
```

### Literal core copy

- Eyebrow: **PERSONAL COACHING FROM YOUR OWN GAMES**
- Headline: **Your games already show what to work on next.**
- Supporting line: **ChessGuru finds the mistake you repeat and turns your own positions into a plan for breaking it.**
- Primary CTA: **Connect my games**
- Secondary CTA: **Watch the loop**
- Pattern transition: **A blunder is one move. A pattern is what keeps costing you games.**
- Training principle example: **Before moving a piece, check what it was protecting.**
- Final CTA heading: **Stop reviewing the same mistake. Start breaking it.**

All example recurrence counts are explicitly marked as demonstrations unless populated from an authenticated user's verified data. No testimonial, player count, outcome percentage or improvement claim is invented.

## 3. In scope (V1)

- Replace the canonical `/` landing composition inside `Landing.jsx` or a small set of landing-specific components.
- Preserve Google authentication, dev login, Sign in, Pricing navigation and post-auth redirect behavior.
- Preserve or improve public metadata, FAQ structured data, policy links and crawlable product copy.
- Build the desktop and mobile compositions specified above.
- Create a cohesive asset set: hero board/product scene, recurring-pattern evidence strip, training transformation scene and responsive crops.
- Prefer authentic rendered product scenes; use custom editorial imagery only when it clarifies the story.
- Make the board the dominant visual above the fold on supported desktop widths and a full-width early visual on mobile.
- Reduce the page to one product story and remove the six repeated feature showcases from the public narrative.
- Use the established Warm Intelligence palette and typography roles; eliminate competing decorative gradients and excessive glow.
- Keep motion purposeful, lightweight and compatible with `prefers-reduced-motion`.
- Add semantic HTML, useful alt text, keyboard-visible controls and accessible color contrast.
- Optimize generated/raster assets for responsive loading and prevent layout shift.
- Preserve analytics hooks and add only the events required to compare the new page against the current acquisition baseline.
- Verify lint/build, relevant frontend tests, desktop/mobile layout, keyboard navigation, reduced motion and primary CTA flows.

## 4. Explicitly out of scope (V1)

- Redesigning Login, Pricing, activation, Home or other authenticated pages.
- Replacing the product logo or finalizing a company-wide identity system.
- Changing authentication, billing, entitlements or backend coaching logic.
- Building personalized anonymous landing content from live user data.
- Inventing testimonials, ratings, user counts, improvement percentages or partner endorsements.
- Producing a large stock-photo or lifestyle-photo library.
- Adding autoplay video, WebGL, 3D pieces or effects that materially hurt loading or accessibility.
- Creating a second landing route, experiment microsite or parallel design system.
- Claiming durable improvement from puzzle completion, one game, a win streak or unverified marketing examples.
- Rewriting the full FAQ purely for SEO expansion; only clarity and claim-honesty edits are included.

## 5. Success criteria

- In a five-second unmoderated comprehension check, a visitor can state all three ideas: ChessGuru uses their games, finds repeated mistakes, and creates personal practice.
- In blind visual review, the page is identified as a chess coaching product without relying on the ChessGuru name, and reviewers do not describe it as a generic AI/SaaS template.
- The primary behavior metric—completed authentication starts per eligible landing visitor—improves against the current landing baseline in a controlled comparison. The minimum winning threshold is locked only after baseline volume and test power are measured.
- Engagement with **Watch the loop** demonstrates that visitors deliberately explore the product explanation; its target is locked after the current equivalent interaction baseline is measured.
- Primary CTA, Sign in, Pricing, FAQ, SEO schema and policy routes retain their current functional behavior.
- Mobile at 360px has no horizontal overflow, clipped board, unreadable overlay or CTA below an accidental full-screen spacer.
- Above-the-fold visual assets do not cause visible layout shift; optimized asset budgets are locked after the chosen visual format and current performance baseline are measured.
- Keyboard and reduced-motion checks pass, and all meaningful images have useful alternative text or an accessible text equivalent.

## 6. Open questions

- **Question:** Should V1 use only authentic product/board scenes, or include one documentary human image?  
  **Why unresolved:** A human image may add warmth, but a weak or synthetic-looking image would reduce trust.  
  **Unblocking step:** Compare two hero-support artboards during visual review; default to product-only unless the human image clearly improves the page.

- **Question:** Which exact real game position anchors the hero and recurring-pattern sequence?  
  **Why unresolved:** It must be visually understandable, engine-grounded and representative of the implemented piece-safety teaching quality.  
  **Unblocking step:** Select three candidate positions from existing verified game-review fixtures and choose the clearest narrative after board review.

- **Question:** What numeric conversion lift constitutes a winning redesign?  
  **Why unresolved:** A defensible threshold depends on current traffic, auth-start baseline and experiment power.  
  **Unblocking step:** Read the current analytics baseline and run the threshold decision through the data-lock workflow before implementation instrumentation is finalized.

- **Question:** Which raster/vector formats and byte budgets apply to each visual?  
  **Why unresolved:** The right budget depends on whether the final scenes are DOM, SVG, WebP or AVIF and on current LCP.  
  **Unblocking step:** Prototype the selected art direction, measure the current page, and lock budgets from observed quality/performance tradeoffs.

## 7. Pre-code requirements

- Mohit explicitly signs off on this complete scope document.
- The hero, recurring-pattern strip and training scene have approved low-fidelity artboards using the literal copy above.
- The hero position and any supporting game positions are verified against the actual board state and coaching claim.
- Current landing analytics events and available acquisition baseline are documented; any numeric experiment threshold is derived from that data.
- Current desktop/mobile performance is recorded so asset budgets are evidence-based.
- Required assets are classified as real product capture, DOM/SVG composition or generated editorial image; none can be mistaken for a live feature that does not exist.
- The pre-code audit passes: literal mockup exists, narrative is pattern-led, numbers are data-derived, success measures behavior, deferred work stays deferred and explicit signoff is recorded.
