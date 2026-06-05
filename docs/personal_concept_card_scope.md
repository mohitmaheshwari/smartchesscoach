# PersonalConceptCard V1 — Scope Document

**Status:** AWAITING MOHIT SIGNOFF (2026-06-05)
**Skill applied:** `/scope-driven-development`
**Next skills:** `/lock-via-data` (for ranking formula, once mongo's back) → `/audit-pre-code` (before first file)

---

## 1. What it is

A card that appears on the user's home page after they finish a game, telling them about a pattern they keep falling for. The card reads like a coach speaking — not a database report.

Each user sees up to 3 of these cards at any time. The cards are based on actual mistakes the user has made repeatedly across their own games. The first card on the shelf is whatever pattern they've been losing to most consistently in recent games.

If a user has no recurring pattern strong enough to surface, they see zero cards. The shelf is honest about what the data actually shows; nothing is padded.

This is the first feature where ChessGuru tells the user **"we remember what you keep getting wrong, and here's the proof from your own games."** That's the differentiation.

---

## 2. What the user sees

```
+---------------------------------------------------------------+
| You keep getting forked when your knight jumps to the rim.    |
| Seen 7 times across your recent games.                        |
|                                                               |
|   [ Review your most recent one -> ]                          |
|                                                               |
|   v Earlier examples (6)                                      |
|     - May 22 vs killerknight24 — fork cost the bishop         |
|     - Apr 30 vs bishop_lord_99  — fork cost the rook          |
|     - Apr 18 vs tactic_train_bot — fork cost the queen        |
|     ...                                                       |
+---------------------------------------------------------------+
```

**Hierarchy (this is the contract):**

1. **Headline** — the pattern in human language. Names the geometry/idea, never the SAN move. The user reads "I get forked when my knight goes to the rim" and recognizes themselves.
2. **Recurrence** — how many of the user's games show this pattern. Concrete number.
3. **Action button** — "Review your most recent one" links to the actual game where this most recently happened.
4. **Earlier examples (collapsed)** — opponent name, date, outcome in human terms. Never SAN move notation in the visible label.

A user with multiple cards sees them stacked, ranked by which one has been hurting them most recently. Each card from a different concept family (tactical / opening / middlegame / endgame / defense / strategy) — never two cards about the same thing.

---

## 3. In scope (V1)

- Up to 3 cards per user, **variable count** (0/1/2/3 — whichever the data supports, never padded with weak entries)
- One card per concept family (the cap prevents 3 tactical cards stacking on the same user)
- Cards are generated from the user's own recent games (not community data)
- Card recency-weighted so recent patterns surface first; old patterns fade
- Each card links into the user's actual game where it most recently happened
- Collapsed "earlier examples" list with up to 5 past occurrences (opponent name, date, what was lost)
- Per-card click tracking: impressions, expands, review-game clicks, dismissals
- Cards render on the home page (or Lab — see open questions)

---

## 4. Explicitly out of scope (V1)

These are deferred. Listing them here so they don't quietly creep into the build:

- **Trap-fall-in cards** — only 1 user in the entire user base has fallen for a named trap in their tracked history. There's no data to render. Re-enable when the data exists.
- **Position-pattern cards** ("you've lost this exact opening position 3 times") — only 7 users qualify and they're already users who get concept cards. The Position source runs in the background and stores candidates for later analysis, but does NOT render in V1.
- **Outcome tracking** — measuring whether the card actually changed user behavior is a separate later concern. Ship the card first, see if anyone clicks, THEN instrument outcomes.
- **LLM-generated coaching text** — any explanation under the headline must come from a deterministic rule, not an LLM. No "the AI says you should..." text. If we can't derive a clean explanation, the card has no explanation footer.
- **Theme labels** as a hard requirement — the card MAY have a small theme label at the bottom ("undefended-piece-capture"), but only when one of ~10-12 deterministic rules matches. If no rule matches, the card still renders without it.
- **Mastery Gate** — the system that suppresses coaching when a user already knows something. That's a separate feature (Phase 2). PersonalConceptCard does not gate or suppress anything.
- **Auto-discovery of new coaching patterns** — the background pipeline that finds new patterns to teach. Separate effort.
- **Aggregate (cross-source) CTR metrics** — only one source is active in V1, so aggregating across sources would just mirror the single source. Re-add when more sources are active.

---

## 5. Success criteria

**Primary:** Per-source review-game CTR. Within 2 weeks of launch, ≥25% of card impressions result in the user clicking through to the linked game.

**Why CTR and not "users see a card":** seeing a card is not value. Going to study the game IS value — that's behavior change. If users see cards and ignore them, the feature isn't working regardless of how many cards appear.

**Secondary metrics tracked (no targets in V1, just observed):**
- Card expand rate (users opening the "earlier examples" list)
- Card dismissal rate (users explicitly hiding a card)
- Card impressions per user per week (volume signal)

**Explicitly NOT a success metric:** activation rate. We don't care if 30% or 80% of users see at least one card. We care if the ones who do, find it valuable enough to click.

---

## 6. Open questions

### Q1. Which ranking formula picks the top-3?

4 candidates were proposed (A: total cp_loss × decay / B: recurrence × median cp_loss / C: recurrence × max(median, p75/2) / D: recurrence × log(1+median)). Each picks a different "top weakness" for a meaningful share of users.

- **Why unresolved:** the comparison workflow was blocked when mongo went down. The data-driven pick can't be made from gut.
- **Unblocking step:** mongo on port 27018 is reachable → resume the bake-off workflow → synthesis returns the winner → lock with `/lock-via-data`.

### Q2. Where does the card render — Home, Lab, or Insights tab?

- **Why unresolved:** discussion focused on backend correctness; surface choice was noted but not picked.
- **Unblocking step:** 30-minute decision after looking at the current Home page layout: "would this card displace something more valuable here?" If no → Home. If yes → Lab.

### Q3. Should the card have a theme label in V1?

Theme labels ("undefended-piece-capture") help users recognize the pattern type, but require 10-12 deterministic classifier rules to be authored.

- **Why unresolved:** the rules don't exist yet. Cards work without them, but they'd land softer.
- **Unblocking step:** decide whether to author the 10-12 rules pre-launch (~half day) or ship without theme labels and add them post-launch.

### Q4. Retention policy for shadow-collection (`user_position_pattern_candidates`)?

Position-pattern cards run in shadow mode — generated nightly, stored, but not rendered. Storage needs a TTL.

- **Why unresolved:** small decision, not made yet.
- **Unblocking step:** pick 90 days as default; revisit if the collection grows beyond expectation.

---

## 7. Pre-code requirements

Each item is a HARD gate. No code starts until all are true:

- [ ] **Mongo on port 27018 is reachable** — needed to complete the ranking-formula bake-off
- [ ] **Ranking formula is locked** via `/lock-via-data` — the bake-off has returned, a winner is named with data citation
- [ ] **Frontend route is chosen** (Home / Lab / Insights tab)
- [ ] **Theme label decision** — either the 10-12 rules are authored, OR the call is "ship without theme labels in V1"
- [ ] **Retention TTL for `user_position_pattern_candidates`** is decided (default suggested: 90 days)
- [ ] **Family mapping table** is enumerated (TAC_ → tactical, OP_ → opening, MID_ → middlegame, END_ → endgame, DEF_ → defense, STR_ → strategy, everything else → legacy)
- [ ] **Mohit explicitly signs off** on this scope document — explicit "lock this and code", not implicit "sounds good"

After all gates pass: `/audit-pre-code` runs as final check, then implementation begins.

---

## Appendix A — what gets built (for reference, not part of scope contract)

When all gates pass, the implementation produces:

**New collections:**
- `user_concept_pattern_cards` — materialized cards visible to users
- `user_position_pattern_candidates` — shadow-mode candidates (not rendered)
- `personal_concept_card_events` — per-source impressions/expands/clicks/dismissals (the `source` field exists from day 1 even though only `concept` fires in V1)

**New services:**
- `services/personal_concept_card_generator.py` — runs after game analysis, produces card candidates
- `services/personal_card_event_logger.py` — handles the 4 event types

**New frontend component:**
- `frontend/src/components/PersonalConceptCard.jsx` — renders one card with the hierarchy in §2
- Mounted at the chosen route (TBD)

**Reused:**
- `user_concept_understanding` (already populated by `concept_mastery_tracker`)
- `game_analyses.decryption_v5_data` (concept extraction priority: principle_id_used → plan.concept_id → caption_facts_principles_violated[0].principle_id)
- `games` (opponent, date, result for the human-readable encounter labels)
- `pattern_decay_service.DECAY_RATE = 0.85`

This appendix is **descriptive**, not contractual. The scope contract is sections 1–7. The implementation detail is downstream of signoff.
