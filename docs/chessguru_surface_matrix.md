# ChessGuru Surface Matrix

**What this is:** the residency dashboard — one row per major surface,
updated as each gets reviewed. Confidence varies by row on purpose: the
first three have been through a real Product Residency session; the
last three haven't yet, and are marked as such rather than guessed at.
Don't read a `?` as "unknown forever" — read it as "not reviewed yet."

| Surface | Promise | Analytics | Experiment Ready | Biggest Risk | Status |
|---|---|---|---|---|---|
| **Home** | "I remember who you are" — real, but complicated: the Mirror renders first, unconditionally, and is 100% episodic. The identity-framed content is genuinely strong, just not the first thing read each day. | **Live** (shipped Session 1: `home_viewed`, `mirror_read`, `conversation_scrolled`, `cta_clicked`, `nav_tile_clicked`) — no data has accumulated yet, engagement is still unmeasured in practice | No — infrastructure exists, no specific experiment queued | 8 of 11 backend fields computed, 3 read — real engineering cost with no product value yet, pending the ownership table's Keep/Retire calls | 🟡 |
| **Diagnostic** | "I'll understand how you think" | **Live** (shipped Session 2: 9 events built around "where does commitment break") | Infrastructure ready, no specific experiment queued — not a flat yes | Abandonment: 75% of all sessions ever started (18/24) sit in `in_progress` indefinitely, un-distinguished from "still trying" | 🟡 |
| **Game Review** | Provisional — "I'll teach you" was the working assumption in Session 3a, but the screen visibly contains 7+ distinct sub-products (move coaching, reflection/thoughts, plan mode, habits report, coach-line playback, future-moves preview, concept acknowledgments). Session 3b exists specifically to test whether one promise actually holds or whether this needs to be named per sub-feature. | **Partial** — wrapper fires `funnel_review_opened`; nothing inside the 2,447-line component itself is tracked (no move navigation, no thoughts saved, no plan mode used, no feedback submitted) | No | Real, fixed this session: an internal gold-caption tester tool had zero access control, confirmed live on one real user's game. Unfixed, still open: 7 sub-products with no confirmed hero | 🟡 |
| **Play with Coach** | Not yet reviewed as a screen. Real facts already known from earlier work this session (not a residency pass): live captions come from the same `caption_pipeline.build_move_teaching_decision` as Game Review; zero LLM calls anywhere in the hot path; the Coach Conductor's "STATE, never ASK" law currently overrides the rating-gated Socratic mechanism unconditionally, an unresolved tension the constitution's §3.1 already flags | 1 `track()` call confirmed in `CoachPlay.jsx` — which specific event, and whether it covers the actual coaching interactions (not just session start), not yet checked | **Yes, uniquely** — Experiment #1's Habit Coach reminder fires through this surface; Cohort B enrollment runs here once implemented | Not yet identified — no residency pass done | ⚪ not yet reviewed |
| **Training** | Not yet reviewed. Split across two components with inconsistent instrumentation, worth flagging now rather than waiting: `ThinkingTraining.jsx` (the actual `/training` route) has zero analytics; `PrescribedTraining.jsx` (`/training/prescribed`, `/training/pattern/:pattern`) has 1 `track()` call | Partial, inconsistent across the two components | No | Not yet identified | ⚪ not yet reviewed |
| **Progress** | Not yet reviewed | **None** — zero `track()` calls found | No | Not yet identified — though per the constitution's own §4.1.4, this is the designated home for several of Home's orphaned fields (`accuracy`, possibly `chess_dna`), which makes it higher-priority to review sooner rather than later | ⚪ not yet reviewed |

---

**One connection worth naming**: Game Review's "7 products on one screen" and Home's "8 of 11 backend fields unused" are the same disease at different scale — feature accretion without a forcing function to ask "does this still deserve to exist." Independent evidence for the pattern, not just the same observation twice.

**Next**: Session 3b — five product-only questions on Game Review (promise, the one thing to learn, the emotion to leave with, tomorrow's one action, what doesn't serve the mission). No implementation, no security, no backend.
