// Funnel analytics (2026-07-14, path_to_10 Phase 5.2).
// PostHog is loaded via the index.html snippet (autocapture only until now —
// zero custom events meant the funnel was unmeasurable). This is the ONE
// place custom events go through: guarded so a blocked/missing PostHog can
// never break the app.
//
// Funnel vocabulary (keep names stable — dashboards key on them):
//   funnel_activation_cta      — welcome page primary action clicked
//   funnel_diagnostic_done     — diagnostic puzzles completed
//   funnel_import_done         — platform account linked / games synced
//   funnel_review_opened       — a game review (decryption) opened
//   funnel_training_solve      — a training puzzle attempted
//   funnel_pwc_started         — a Play-with-Coach session started
//   funnel_paywall_viewed      — pricing/paywall seen
//   funnel_payment_success     — Razorpay payment verified
//   funnel_home_viewed         — Home page load, any branch (onboarding /
//                                no-focus-yet / full conversation)
//   funnel_home_mirror_read    — "Since you last played" scrolled into view
//   funnel_home_conversation_scrolled — reached the end of the coach
//                                conversation (its main CTA button)
//   funnel_home_cta_clicked    — any primary Home CTA clicked; props:
//                                { cta: "play_with_coach"|"review_this_game",
//                                  has_conversation?: bool }
//   funnel_home_nav_tile_clicked — a faded nav tile clicked; props: { tile }
//   (Experiment 0, 2026-08-05 — Home had zero instrumentation before this.
//   "Return within 24h" is deliberately NOT its own event — compute it
//   downstream from repeat funnel_home_viewed timestamps.)
//
//   Diagnostic (Session 2 residency, 2026-08-05 — also had zero events
//   despite funnel_diagnostic_done being documented above and never
//   fired; superseded by this list, built around "where does commitment
//   break," not grading every answer):
//   diagnostic_started          — a genuinely new session (puzzle 1)
//   diagnostic_resumed          — returned to an already-in-progress
//                                 session; props: { puzzle_number }
//   diagnostic_first_answer     — first attempt submitted this session
//   diagnostic_puzzle_completed — any attempt submitted; props:
//                                 { puzzle_number } only — no verdict/
//                                 correctness, this is a funnel-position
//                                 signal, not a grading log
//   diagnostic_pause            — tab backgrounded mid-puzzle (unanswered
//                                 puzzle on screen); props: { puzzle_number }
//   diagnostic_exit_intent_shown — the exit-confirm modal opened; props:
//                                 { puzzle_number }
//   diagnostic_abandoned        — "Exit anyway" actually clicked; props:
//                                 { puzzle_number }
//   diagnostic_completed        — a diagnosis was produced, full run or
//                                 early exit; props: { exited_early, puzzle_count }
//   diagnostic_training_started — "Start training" clicked from the
//                                 results screen; props: { headline_gap }
//
//   insight_shown (2026-08-05, added per Mohit's activation-timeline
//   review — the timeline had no server-side event for "a personal
//   insight was delivered" at all; Signal A had been PostHog-only by
//   default). Deliberately minimal, source-agnostic: props:
//   { insight_id, source, version }. Wired ONLY into the diagnostic
//   results screen for now (source: "diagnostic") — Home and Game
//   Review are NOT wired yet. Not an oversight: which surface actually
//   delivers "the first undeniable proof ChessGuru understands me" is
//   an open question per the 5-user watch, and hardcoding "home"/
//   "review" as sources before that answer exists would smuggle an
//   unverified assumption into the instrumentation itself. Add those
//   once the qualitative study says where the real moment is.

export function track(event, props = {}) {
  try {
    if (typeof window !== "undefined" && window.posthog && typeof window.posthog.capture === "function") {
      window.posthog.capture(event, props);
    }
  } catch (_e) {
    /* analytics must never break the product */
  }
}
