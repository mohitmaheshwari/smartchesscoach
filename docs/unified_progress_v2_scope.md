# UnifiedProgress v2 — Scope Document

**Status:** AWAITING MOHIT SIGNOFF (2026-06-05)
**Skill applied:** `/scope-driven-development` (with new Section 0 existing-surfaces audit)
**Predecessor:** [personal_concept_card_scope.md](personal_concept_card_scope.md) (SUPERSEDED — discovered to overlap UnifiedProgress)
**Next skills:** `/lock-via-data` (for any new numeric thresholds) → `/audit-pre-code` (before first file)

---

## 0. Existing surfaces audit

### What exists today

[`frontend/src/pages/UnifiedProgress.jsx`](../frontend/src/pages/UnifiedProgress.jsx) (700 lines, mounted at `/progress`) renders three sections fed by three backend endpoints:

| Section | What it shows now | Data source |
|---|---|---|
| "Currently working on" (violet card) | The user's primary weakness category (e.g. `calculation_depth`), reduction % over 90 days, current clean-streak count, Drill CTA → `/training/prescribed?weakness=...` | `narrative.weaknesses[0]` + `proof.primary_pattern.reduction_pct` |
| "Also tracking" (list) | Remaining weakness categories with per-bucket reduction % | `narrative.weaknesses[1:]` mapped to `proof.all_patterns[].reduction_pct` |
| "Archived · you've been consistent at" | Patterns the user has beaten (5+ clean games OR graduated weaknesses) | `narrative.archived_weaknesses` + `narrative.strengths` |

Backend endpoints involved: `/progress/real`, `/progress/narrative`, `/progress/proof`.

### What it already provides that PersonalConceptCard would have

- Recurrence signal (mistake counts per bucket)
- Recency signal (reduction % over 90 days, clean-streak count)
- Personalization (per-user, derived from the user's own analyzed games)
- Graduation mechanic (archived once a pattern stays quiet)
- Per-pattern Drill CTA

### Where the genuine value of PersonalConceptCard goes BEYOND existing

| Dimension | UnifiedProgress today | Real gap |
|---|---|---|
| Granularity | Bucket-level (`tactical`, `calculation_depth`, `king_safety`) | Concept-level (`TAC_HANGING_PIECE`, `TAC_CHANGED_AFTER_MOVE`, `OP_SAME_PIECE_TWICE`) — much more actionable |
| Narrative anchor | Statistical ("mistakes down 14% from 90 days ago") | Memory recall ("May 22 vs killerknight24 — you lost this same pattern") |
| Card body | Trends + numbers | The actual recent game where it happened |
| Action | Drill (puzzles) | Review (study your own game) |

### Decision

**EXTEND** existing UnifiedProgress. Don't build a parallel surface. The "Currently working on" card becomes the home for concept-level granularity + narrative recall, INSIDE the existing structure.

PARALLEL was rejected because the overlap with the existing surface is large enough that two cards on different routes describing the same underlying signal would feel like duplication. REPLACE was rejected because the bucket-level view (good for high-level "are you improving?") and concept-level view (good for "what specifically?") complement each other — the bucket should remain.

---

## 1. What it is

We're upgrading the existing UnifiedProgress page. Today's "Currently working on" card shows a category like *"calculation depth, down 14% over 90 days, 3-game clean streak."* That's a trend report.

After v2, the same card ALSO shows:
- The specific concepts inside that category that the user actually mishandles (e.g. *"you keep getting forked when knights jump to the rim"*)
- A recent example from one of their own games (opponent name, date, what was lost)
- A new "Review the game" action button next to the existing "Drill" action

The page structure stays the same. Three sections, same routes, same data fetches. v2 enriches the "Currently working on" and "Also tracking" cards with concept-level body content, but keeps the bucket-level headers and reduction% as the spine.

In plain English: the user's Progress page goes from *"you're improving on tactics"* to *"you're improving on tactics — specifically, you keep getting forked when your knight jumps to the rim; here's your most recent example against killerknight24."*

---

## 2. What the user sees

The existing layout, with new body content inside each pattern card:

```
+-------------------------------------------------------------------+
| CURRENTLY WORKING ON                                              |
|                                                                   |
|   Tactical patterns — down 14% over 90 days                      |
|   3-game clean streak. We'll archive this after 5.               |
|                                                                   |
|   ─── What you keep doing ───                                     |
|   You get forked when your knight jumps to the rim.              |
|   Seen 7 times across your recent games.                          |
|                                                                   |
|   Most recent — May 22 vs killerknight24:                        |
|   the fork cost the bishop.                                       |
|                                                                   |
|   [ Review the game -> ]   [ Drill this pattern -> ]              |
|                                                                   |
|   v Earlier examples (6)                                          |
|     - May 12 vs bishop_lord_99 — fork cost the rook              |
|     - Apr 30 vs tactic_train_bot — fork cost the queen           |
|     ...                                                           |
+-------------------------------------------------------------------+

+-------------------------------------------------------------------+
| ALSO TRACKING                                                     |
|                                                                   |
|   • Opening discipline · down 8% · 2-game clean streak           |
|     "You move the same piece twice early." (4 recent)            |
|     [ Drill -> ]                                                  |
|                                                                   |
|   • Endgame · no change yet                                       |
|     "King stays passive in pawn endings." (3 recent)             |
|     [ Drill -> ]                                                  |
+-------------------------------------------------------------------+

+-------------------------------------------------------------------+
| ARCHIVED · YOU'VE BEEN CONSISTENT AT                              |
|                                                                   |
|   • Back-rank weakness — beaten 12 games ago                      |
|   • King safety — beaten 18 games ago                             |
+-------------------------------------------------------------------+
```

**What's new (v2 enrichment):**
- "What you keep doing" subsection inside Currently-working-on, surfaces the concept-level pattern in plain language
- "Most recent" memory recall with opponent name + outcome (the game link, no SAN move notation in the visible label)
- "Earlier examples" collapsed list
- "Review the game" action button alongside the existing "Drill"
- "Also tracking" each gets a one-line concept summary + count + Drill (no game link required for non-primary entries, keeps the section compact)

**What stays the same:**
- Three-section layout
- Bucket-level reduction % and clean-streak headers
- Archive mechanic
- All existing routes and data fetches
- Drill CTA on every pattern

---

## 3. In scope (V2)

- "Currently working on" card gets a "What you keep doing" subsection with concept-level pattern in plain language
- "Currently working on" card gets a "Most recent" line with opponent + date + outcome (NO SAN move notation in the label)
- "Currently working on" card gets a "Review the game" action button alongside the existing Drill
- "Currently working on" card gets a collapsed "Earlier examples (N)" list (up to 5)
- "Also tracking" entries get a single-line concept summary + recent count
- One-concept-per-family cap enforced when picking which concept to surface (prevents the same family populating both Currently-working-on body AND Also-tracking entries)
- Variable surfacing — if no qualifying concept exists inside the bucket, the new subsection doesn't render (card falls back to today's behavior)
- New click tracking: "Review game" clicks, "Earlier examples" expands
- All under `/progress` route — no new pages, no new mounts

---

## 4. Explicitly out of scope (V2)

- **New page or route** — `/progress` stays the home. No `/insights`, no Home-page card, no Lab integration. The page UPGRADES, it doesn't expand surface area.
- **Trap-fall-in cards** — only 1 user in the corpus has any fallen-for trap. No data, no card.
- **Position-pattern cards** ("you've lost this exact opening position 3 times") — 7 users qualify, all of whom already get concept cards via the bucket. Position runs in background shadow mode for later analysis only.
- **Outcome tracking** — measuring whether the new body content changes behavior is a separate later concern. Ship first, see if Review-game CTR climbs, THEN instrument outcomes.
- **LLM-generated coaching text** — any "What you keep doing" line comes from a deterministic rule, not an LLM. No "the AI says you should..." text. If no rule matches, the body falls back to the bucket-level text (today's behavior).
- **Theme classifier as hard requirement** — the deterministic rules to turn a concept_id into plain-language ("you keep getting forked when knights jump to the rim") are nice-to-have. If they're not authored, the body shows the concept name in a softer form (e.g. "knight-on-rim tactical pattern").
- **Mastery Gate / PWC live coaching** — separate scope doc, separate feature. Path C from the Section-0 discussion. Not in v2.
- **Auto-discovery of new patterns** — content-infra pipeline, not user-facing.

---

## 5. Success criteria

**Primary:** Per-card "Review the game" CTR. Within 2 weeks of v2 ship, ≥25% of Currently-working-on card impressions result in the user clicking through to the linked recent game.

**Why this metric specifically:** existing Drill CTR is the only "did the page change behavior" signal today. Adding "Review the game" gives a SECOND behavior path (reflection vs practice) and the click rate tells us whether the narrative recall is actually compelling. If Review CTR is high → memory recall is working. If it's low → the recall didn't earn its slot.

**Secondary metrics tracked (no targets in V2, just observed):**
- "Earlier examples" expand rate
- Drill CTR (existing — watch for cannibalization; ideally Drill stays flat while Review adds new clicks)
- "Also tracking" entry click rate (today vs after v2)

**Explicitly NOT a success metric:** time on page. Users could dwell longer simply because there's more text; that's not improvement.

---

## 6. Open questions

### Q1. Which concept inside a bucket gets surfaced in the body?

A user's `calculation_depth` bucket might cover several concepts. Which one shows in the "What you keep doing" body?

- **Why unresolved:** depends on the ranking formula bake-off we couldn't finish (mongo blocked). The same A/B/C/D candidates apply here.
- **Unblocking step:** mongo on port 27018 reachable → resume the bake-off workflow → lock with `/lock-via-data`.

### Q2. Plain-language conversion — author 10-12 rules or ship with concept names?

Turning `TAC_FORK_PATTERN` into "you keep getting forked when knights jump to the rim" requires deterministic rules.

- **Why unresolved:** the rules don't exist yet.
- **Unblocking step:** decide whether to author the 10-12 rules pre-launch (~half day) or ship v2 with softer concept-name strings ("knight-on-rim tactical pattern") and add the polished labels post-launch.

### Q3. Single concept across bucket vs allow drill-down to multiple?

The body could show ONE concept (cleanest, matches the bucket-level header tone) or TOP 3 concepts (more granular but visually busier).

- **Why unresolved:** UX decision, no data drives it.
- **Unblocking step:** Mohit picks. Default: one concept, keeps the card tight.

### Q4. Shadow-collection retention for Position patterns?

Position-pattern detection still runs nightly into `user_position_pattern_candidates`. Storage needs a TTL.

- **Why unresolved:** small decision not made yet.
- **Unblocking step:** pick 90 days as default; revisit if collection grows.

---

## 7. Pre-code requirements

Each item is a HARD gate:

- [ ] **Mongo on port 27018 is reachable** — needed to resume the bake-off
- [ ] **Ranking formula is locked** via `/lock-via-data` (the per-bucket concept picker)
- [ ] **Plain-language decision** (Q2) — author 10-12 rules OR confirm fallback string format
- [ ] **One-vs-many decision** (Q3) — one concept in the body or up to 3
- [ ] **Retention TTL for `user_position_pattern_candidates`** decided (suggest 90 days)
- [ ] **Family mapping table** enumerated (TAC_ / OP_ / MID_ / END_ / DEF_ / STR_ / legacy → bucket category)
- [ ] **Mohit explicit signoff** on this scope document — explicit "lock this and code", not implicit "sounds good"

After all gates pass: `/audit-pre-code` runs as final check, then implementation begins.

---

## Appendix A — what gets built (for reference, not part of scope contract)

**Backend additions:**
- New endpoint OR extension to `/progress/narrative` — returns top concept inside each weakness bucket with recurrence + most-recent-game metadata
- Uses existing `user_concept_understanding` (no new collection)
- Uses existing `games` (opponent, date, outcome)
- The ranking formula chosen via `/lock-via-data` is implemented as a single swappable function

**Frontend additions:**
- New subsections inside `UnifiedProgress.jsx` "Currently working on" card
- New "Review the game" button → navigates to existing game-review route
- New click event types: `review_game_click`, `earlier_examples_expand` (added to existing `personal_card_event_logger` or equivalent)

**Reused:**
- Entire existing UnifiedProgress structure
- All three existing data endpoints
- `pattern_decay_service.DECAY_RATE = 0.85`

The appendix is **descriptive**, not contractual. The scope contract is sections 0–7.
