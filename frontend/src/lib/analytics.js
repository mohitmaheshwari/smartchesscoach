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

export function track(event, props = {}) {
  try {
    if (typeof window !== "undefined" && window.posthog && typeof window.posthog.capture === "function") {
      window.posthog.capture(event, props);
    }
  } catch (_e) {
    /* analytics must never break the product */
  }
}
