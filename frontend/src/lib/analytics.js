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
//
//   pwc_insight_shown (Sprint 1, 2026-08-07 — PWC's own first-insight
//   funnel, distinct from the diagnostic's `insight_shown` above).
//   Fired from PostGameReflection.jsx when the postgame screen renders
//   a real `pattern_verdict` (Case A/B/C from pattern_memory_service's
//   decay model) — the signal a PWC player actually sees on the
//   in-session postgame card. Props: { session_id, type [failed/
//   partial/success], pattern, occurrences, move_number, is_first_pwc_
//   game, games_together, instruction_id, is_carried_forward }. The
//   last two (Sprint 2, docs/one_surviving_instruction_scope.md)
//   are non-null/true ONLY for rollout-gate-eligible users
//   (admin/super_admin, PWC_SURVIVING_INSTRUCTION_ENABLED) with a real
//   active user_active_focus — null/false for everyone else, which is
//   the right audit granularity (ineligible vs. no-active-focus both
//   mean "no canonical instruction this session"). Deliberately ONE
//   event covering what the
//   original Sprint 1 spec listed as 4 separate events (shown/seconds/
//   move_number/type) — they're all just props on one occurrence.
//   `pwc_completed_after_insight` and `pwc_returned_after_insight` from
//   that same spec are NOT separate emitted events: join this event's
//   (session_id, timestamp) against coach_sessions/postgame_analyses
//   downstream, same as the established "don't emit a return event,
//   compute it from repeat views" pattern used for Home's 24h-return
//   signal above. See docs/product_residency_notes.md Session 3 for
//   why `pattern_verdict`, not `coach_prescription`, is the real
//   signal here — the latter is written to postgame_analyses but only
//   ever read by Home's next-session narrative, never by this screen.
//
//   Personal Curriculum baseline (2026-08-28). These events observe the
//   unchanged legacy learning surfaces before the flag-protected /learn A/B.
//   They carry canonical content IDs and coarse funnel state only; no moves,
//   positions, player text, usernames, or database IDs.
//   curriculum_decision_shown / curriculum_primary_clicked /
//   curriculum_review_clicked — recommendation impression and choice
//   learn_viewed / progress_viewed / explore_opened — surface exposure
//   lesson_started / explanation_completed — lesson entry and transition
//   guided_attempt / independent_attempt / review_attempt — real attempts
//   back_to_plan — lesson return to the future coach-owned plan

// Canonical event IDs. Emitters import this object instead of repeating raw
// strings, so a rename cannot silently split one funnel into two event names.
export const ANALYTICS_EVENTS = Object.freeze({
  FUNNEL_ACTIVATION_CTA: "funnel_activation_cta",
  FUNNEL_DIAGNOSTIC_DONE: "funnel_diagnostic_done",
  FUNNEL_IMPORT_DONE: "funnel_import_done",
  FUNNEL_REVIEW_OPENED: "funnel_review_opened",
  FUNNEL_TRAINING_SOLVE: "funnel_training_solve",
  FUNNEL_PWC_STARTED: "funnel_pwc_started",
  FUNNEL_PAYWALL_VIEWED: "funnel_paywall_viewed",
  FUNNEL_PAYMENT_ATTEMPTED: "funnel_payment_attempted",
  FUNNEL_PAYMENT_SUCCESS: "funnel_payment_success",
  FUNNEL_HOME_VIEWED: "funnel_home_viewed",
  FUNNEL_HOME_MIRROR_READ: "funnel_home_mirror_read",
  FUNNEL_HOME_CONVERSATION_SCROLLED: "funnel_home_conversation_scrolled",
  FUNNEL_HOME_CTA_CLICKED: "funnel_home_cta_clicked",
  FUNNEL_HOME_NAV_TILE_CLICKED: "funnel_home_nav_tile_clicked",
  FUNNEL_FIRST_AHA: "funnel_first_aha",
  DIAGNOSTIC_STARTED: "diagnostic_started",
  DIAGNOSTIC_RESUMED: "diagnostic_resumed",
  DIAGNOSTIC_FIRST_ANSWER: "diagnostic_first_answer",
  DIAGNOSTIC_PUZZLE_COMPLETED: "diagnostic_puzzle_completed",
  DIAGNOSTIC_PAUSE: "diagnostic_pause",
  DIAGNOSTIC_EXIT_INTENT_SHOWN: "diagnostic_exit_intent_shown",
  DIAGNOSTIC_ABANDONED: "diagnostic_abandoned",
  DIAGNOSTIC_COMPLETED: "diagnostic_completed",
  DIAGNOSTIC_TRAINING_STARTED: "diagnostic_training_started",
  INSIGHT_SHOWN: "insight_shown",
  PWC_INSIGHT_SHOWN: "pwc_insight_shown",
  PIC_LESSON_STARTED: "pic_lesson_started",
  PIC_LESSON_MOVE_CHECKED: "pic_lesson_move_checked",
  PIC_FOCUS_GAME_UPDATED: "pic_focus_game_updated",
  PIC_NEXT_ACTION_CLICKED: "pic_next_action_clicked",
  CURRICULUM_DECISION_SHOWN: "curriculum_decision_shown",
  CURRICULUM_PRIMARY_CLICKED: "curriculum_primary_clicked",
  CURRICULUM_REVIEW_CLICKED: "curriculum_review_clicked",
  LEARN_VIEWED: "learn_viewed",
  PROGRESS_VIEWED: "progress_viewed",
  EXPLORE_OPENED: "explore_opened",
  LESSON_STARTED: "lesson_started",
  EXPLANATION_COMPLETED: "explanation_completed",
  GUIDED_ATTEMPT: "guided_attempt",
  INDEPENDENT_ATTEMPT: "independent_attempt",
  REVIEW_ATTEMPT: "review_attempt",
  BACK_TO_PLAN: "back_to_plan",
});

const KNOWN_EVENT_IDS = new Set(Object.values(ANALYTICS_EVENTS));

export const CURRICULUM_ANALYTICS_VERSION = "personal_curriculum.baseline.v1";

const CURRICULUM_EVENT_IDS = new Set([
  ANALYTICS_EVENTS.CURRICULUM_DECISION_SHOWN,
  ANALYTICS_EVENTS.CURRICULUM_PRIMARY_CLICKED,
  ANALYTICS_EVENTS.CURRICULUM_REVIEW_CLICKED,
  ANALYTICS_EVENTS.LEARN_VIEWED,
  ANALYTICS_EVENTS.PROGRESS_VIEWED,
  ANALYTICS_EVENTS.EXPLORE_OPENED,
  ANALYTICS_EVENTS.LESSON_STARTED,
  ANALYTICS_EVENTS.EXPLANATION_COMPLETED,
  ANALYTICS_EVENTS.GUIDED_ATTEMPT,
  ANALYTICS_EVENTS.INDEPENDENT_ATTEMPT,
  ANALYTICS_EVENTS.REVIEW_ATTEMPT,
  ANALYTICS_EVENTS.BACK_TO_PLAN,
]);

// Privacy and schema boundary for the Personal Curriculum run-in. Emitters
// may supply only these coarse, stable dimensions. Everything else is dropped
// before it can reach PostHog.
const CURRICULUM_ALLOWED_PROP_KEYS = new Set([
  "surface",
  "decision_id",
  "decision_source",
  "recommendation_kind",
  "content_type",
  "content_id",
  "origin",
  "rating_band",
  "flag_state",
  "support_level",
  "outcome",
  "position_index",
  "attempt_number",
  "explore_level",
  "tab",
  "is_recommended",
]);

const safeCurriculumValue = (value) => {
  if (typeof value === "string") return value.slice(0, 120);
  if (typeof value === "boolean") return value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  return undefined;
};

export function track(event, props = {}) {
  try {
    if (!KNOWN_EVENT_IDS.has(event)) {
      if (process.env.NODE_ENV !== "production") {
        console.warn(`[analytics] ignored unknown event: ${event}`);
      }
      return;
    }
    if (typeof window !== "undefined" && window.posthog && typeof window.posthog.capture === "function") {
      window.posthog.capture(event, props);
    }
  } catch (_e) {
    /* analytics must never break the product */
  }
}

export function trackCurriculum(event, props = {}) {
  if (!CURRICULUM_EVENT_IDS.has(event)) {
    if (process.env.NODE_ENV !== "production") {
      console.warn(`[analytics] ignored non-curriculum event: ${event}`);
    }
    return;
  }

  const safeProps = {
    instrumentation_version: CURRICULUM_ANALYTICS_VERSION,
    flag_state: "legacy_control",
  };
  for (const [key, value] of Object.entries(props || {})) {
    if (!CURRICULUM_ALLOWED_PROP_KEYS.has(key)) continue;
    const safeValue = safeCurriculumValue(value);
    if (safeValue !== undefined) safeProps[key] = safeValue;
  }
  track(event, safeProps);
}
