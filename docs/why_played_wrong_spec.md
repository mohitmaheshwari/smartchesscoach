# "Why Played Wrong" — Two-Clause Caption Spec

**Status:** SIGNED OFF 2026-06-02 (Mohit "go"). v2 incorporates the contextual-verb table + the teaching-principle fallback decision.
**Version:** v2 (2026-06-02).
**Supersedes:** the 2026-06-01 reorder attempt (commit `72f21dfe`, reverted in `b0694980`) which proved this needs more than predicate ordering.

---

## 1. The problem

Lab page captions explain *why the alternative is better* but never *why the played move failed*. Mohit batch 2026-06-01 — feedback IDs `fb_3efccdbbf15e`, `fb_3d530eea5dd9`, `fb_1cd7562468d1`, `fb_79c33cd39b67`:

- m20 Bb2 (game_85bd0169aa4f): caption says "Bb2 is a mistake. h4 was better — it attacks the bishop on g3..." Mohit asks: "is this right reason for move to be a mistake, or there is something else?" The actual failure is Bb2 walks into Nb7 winning material; the caption never mentions it.
- m24 Qb8 (same game): **literally the same caption** as Bb2 (same h4-attacks-Bg3 alternative). Mohit asks "Qd8 was a mistake, because of the allowed fork now." Caption never mentions the fork.
- m16 Bf6 / Bg3: "Bf6 is a mistake. f5 was better." Mohit asks "why??" No reasoning at all.

The 2026-06-01 reorder attempt promoted failure-mode predicates above alternative-promotion predicates. Two issues surfaced:

1. **Wrapping mismatch.** When the why-clause changed to failure-mode, the surrounding template was still "{played} is a mistake. {best} was better — {why_clause}." This produces non-sequiturs like "Bb2 is a mistake. h4 was better — After Rb1, your bishop on b2 is under attack." The "h4 was better —" preamble only reads naturally when {why_clause} describes the alternative.
2. **Coverage gap.** Many played-move failures don't fit existing failure-mode facts. m24 Qb8 fails because Nb7 wins a *different* piece (rook on a8), not the played queen. None of `opp_reply_attacks_played_piece` / `pieces_now_undefended_present` / `captured_piece_type` / `opp_reply_san_is_check` matches. The predicate walker falls back to the alternative-promotion default.

The reorder was a band-aid. This spec replaces it.

---

## 2. The shape — four outcomes

Decisions made 2026-06-02:
- **Contextual verbs** per failure mode (not a single family).
- **Teaching principle** replaces the alternative clause when no concrete alternative-promotion fact fires. No naked "X was better" sentences. No silence on user mistakes when we have a failure-mode fact.

| State | Caption shape |
|---|---|
| failure ✓ + alternative-fact ✓ | `{played} {failure_clause}. {best} was better — {alternative_clause}.` |
| failure ✓ + alternative-fact ✗ | `{played} {failure_clause}. {teaching_principle_for_failure}.` |
| failure ✗ + alternative-fact ✓ | `{played} is a mistake. {best} was better — {alternative_clause}.` (existing behaviour) |
| failure ✗ + alternative-fact ✗ | silent (existing behaviour, unchanged) |

Examples (target after this ships):

- **m20 Bb2:** "Bb2 walks into Rb1 attacking the bishop. h4 was better — it attacks Bg3 with tempo."
- **m24 Qb8:** "Qb8 allows Nb7 forking your queen and rook. Two of your pieces a knight's jump apart are fork targets — keep them spaced or defended."
- **m16 Bf6:** "Bf6 hangs to Nxd5 winning the bishop. Count defenders before placing a piece on an undefended square."

### Contextual verb table (failure modes)

| Fact | Failure clause template |
|---|---|
| `opp_reply_attacks_played_piece` | "walks into {opp_reply_san} attacking the {moving_piece_type} on {target_square}" |
| `opp_reply_creates_fork` (NEW) | "allows {opp_reply_san} forking your {fork_target_1} and {fork_target_2}" |
| `opp_reply` + `captured_piece_type` | "hangs to {opp_reply_san} winning your {captured_piece_type}" |
| `opp_reply_san_is_check` | "loses to {opp_reply_san}" |
| `is_exchange_losing` | "drops the exchange after {opp_reply_san}" |
| `pieces_now_undefended_present` | "leaves your {piece_type} on {square} undefended" |
| `opp_reply_removes_defender` (NEW) | "exposes your {exposed_piece} after {opp_reply_san} takes the defender" |

### Teaching principles (failure-mode-keyed)

Hand-authored; ~7 entries to start. Each is universal so it teaches the *next* position too.

| Failure mode | Teaching principle |
|---|---|
| `failure_played_piece_attacked` | "Before every move, ask what your opponent's strongest reply does to your pieces." |
| `failure_allows_fork` | "Two of your pieces a knight's jump apart are fork targets — keep them spaced or defended." |
| `failure_allows_capture` | "Count defenders before placing a piece on an undefended square." |
| `failure_walks_into_check` | "Check your king's escape squares before any move that opens lines toward it." |
| `failure_exchange_losing` | "An exchange that loses material isn't 'trading' — count piece values first." |
| `failure_hangs_piece` | "Every move, scan: is anything of mine left without a defender?" |
| `failure_removes_defender` | "Before moving a defender, check what it was defending." |

---

## 3. Schema changes to R12_blunder.json

### 3a. New parallel predicate list

Add `failure_mode_clauses_user` alongside the existing `why_clauses_user`. The current `why_clauses_user` becomes the alternative-promotion list (rename in-place to `alternative_clauses_user` for clarity, though existing variants stay the same).

```json
"failure_mode_clauses_user": [
  { "when": {"opp_reply_san_is_check": true},                     "variant": "failure_walks_into_check" },
  { "when": {"opp_reply_san": "present", "captured_piece_type": "present"}, "variant": "failure_allows_capture" },
  { "when": {"opp_reply_creates_fork": true},                      "variant": "failure_allows_fork" },
  { "when": {"pieces_now_undefended_present": true},               "variant": "failure_hangs_piece" },
  { "when": {"opp_reply_attacks_played_piece": true, "target_square": "present"}, "variant": "failure_played_piece_attacked" },
  { "when": {"is_exchange_losing": true},                          "variant": "failure_exchange_losing" },
  { "when": {"opp_reply_removes_defender": true},                  "variant": "failure_removes_defender" }
],

"alternative_clauses_user": [
  /* existing why_clauses_user content, unchanged */
]
```

### 3b. Two resolvers, fired together

`caption_templates.resolve_why_clause` is called twice — once on each list. Result: `failure_clause` and `alternative_clause`, either may be None.

```python
facts["failure_clause"]     = resolve_clause("failure_mode_clauses_user", facts)
facts["alternative_clause"] = resolve_clause("alternative_clauses_user",  facts)
```

### 3c. New variants in `select_variant`

Three new variants drive the wrapping format (the second uses the teaching principle, not a naked "was better"):

```json
"variants": {
  "user_with_failure_and_alternative":
    "{played_san} {failure_clause}. {best_move_san} was better — {alternative_clause}.",
  "user_with_failure_and_principle":
    "{played_san} {failure_clause}. {teaching_principle}.",
  "user_with_alternative_only":
    "{played_san} {severity_phrase}. {best_move_san} was better — {alternative_clause}.",
  /* existing variants kept for opp-side + backwards compat */
}
```

Selector order (first match wins, as today):

```json
"select_variant": [
  {"when": {"failure_clause": "present", "alternative_clause": "present"}, "variant": "user_with_failure_and_alternative"},
  {"when": {"failure_clause": "present", "teaching_principle": "present"}, "variant": "user_with_failure_and_principle"},
  {"when": {"alternative_clause": "present"},                                "variant": "user_with_alternative_only"},
  /* existing fallbacks (user_winning_position, user_losing_position, silent, etc.) */
]
```

### 3d. Teaching principle resolution

After `failure_clause` is computed, look up the principle for the failure variant that fired:

```python
if facts.get("failure_clause"):
    failure_variant = ... # the variant name that produced the failure_clause
    facts["teaching_principle"] = TEACHING_PRINCIPLES.get(failure_variant)
```

`TEACHING_PRINCIPLES` lives in R12_blunder.json as a dict keyed by failure variant name. Adding a new failure mode means adding both a `failure_X` variant AND a `TEACHING_PRINCIPLES["failure_X"]` entry — enforced by a unit test that loops the failure variants and checks every one has a principle.

---

## 4. New facts the extractor must produce

The failure-mode predicates cover 5 existing facts (already produced by `caption_facts.py`) plus 2 new ones:

| Fact | Status | Where it fires |
|------|--------|----------------|
| `opp_reply_san_is_check` | Existing | Opp's reply gives check |
| `opp_reply_san` + `captured_piece_type` | Existing | Opp's reply captures something |
| `opp_reply_attacks_played_piece` | Existing | Opp's reply attacks the destination square of the played piece |
| `pieces_now_undefended_present` | Existing | Played move left material undefended |
| `is_exchange_losing` | Existing | Played move enters a losing exchange |
| **`opp_reply_creates_fork`** | **NEW** | Opp's reply forks ≥2 of your pieces (king + piece, or two non-king pieces both ≥minor) |
| **`opp_reply_removes_defender`** | **NEW** | Opp's reply captures a piece that was defending a more-valuable own piece, exposing it |

### Two new extraction functions in `caption_facts.py`:

**`_opp_reply_creates_fork(board_after, opp_reply_move)`** — push opp's reply, find squares attacked by the moved piece on the resulting board, intersect with user pieces ≥minor. Return True iff ≥2 hits where at least one is a fork target (different piece types, or one is king).

**`_opp_reply_removes_defender(board_after, opp_reply_move, played_move)`** — was opp's reply a capture of a piece that defended a more-valuable own piece on `board_before`? Walk pre-move defender map; post-capture, that defender is gone and the higher-value piece is undefended.

Both functions return a structured dict (the target piece(s) + square(s)) so the variant templates can name them, e.g. "Nb7 forking your queen on c8 and rook on a8" or "Nxe4 removes the defender of your bishop on d3."

---

## 5. Gating — preventing the "generic could be better" trap

Memory `project_caption_filed_for_future.md` item #2 explicitly flagged: "careful gating so it doesn't degrade into a generic 'could be better' template noise."

Three gates:

**Gate 1: Concrete fact required.** Every failure-mode variant has explicit `when` predicates requiring specific named facts. No `cp_loss > N` shortcut. Missing fact → no clause. Same for alternative-promotion.

**Gate 2: Both clauses must be ≥1 sentence with a named target.** If a clause renders as `""` or contains an unfilled `{slot}`, the renderer drops it (existing `render_template` behavior). So a partially-extracted fact bag can't produce "Bb2 walks into . h4 was better — ." We get silence instead.

**Gate 3: cp_loss ≥ 50 floor for failure-mode clauses.** Adding noise-floor specifically for failure modes — at cp_loss < 50 the engine doesn't really care and saying "Nf6 hangs material" reads as scolding. The alternative-promotion list keeps its current threshold (per existing rule).

**Gate 4 (already in place): suppression block at the top of R12_blunder.json.** Existing `is_suppressed` checks (silent_near_best, user_winning_position) still run first; they can veto everything below.

---

## 6. Test strategy

### Phase 1 — stateless probe (pre-deploy)

`backend/scripts/probe_why_clause_v2.py`. Synthetic fact dicts covering:

1. Both clauses present (the m20 Bb2 case) → expect `user_with_failure_and_alternative`
2. Failure only → expect `user_with_failure_only`
3. Alternative only → expect `user_with_alternative_only`
4. Neither → expect silent (existing suppression)
5. Each new failure-mode predicate fires correctly on its dedicated fact set
6. Each existing alternative-promotion predicate STILL fires when only its facts are present (no regression)

Pass criteria: all 6 + at least one variant of each existing alternative-promotion fact passing unchanged.

### Phase 2 — boundary suite

Run [backend/tests/test_r12_blunder*.py] (whatever test files cover R12). Compare before/after counts of:
- Total clauses produced per outcome
- Per-variant counts
- Silent rate (sanity check it didn't drop drastically — that'd mean we now talk more confidently when we shouldn't)

### Phase 3 — fresh re-render snapshot

Server-side: `snapshot_surface1.py --tag pre_two_clause` then deploy, then `snapshot_surface1.py --tag post_two_clause`, then `--diff`. Eyeball the 4 originally-flagged positions (m20 Bb2, m24 Qb8, m16 Bf6, m16 Bg3 from `game_85bd0169aa4f`) plus 10-15 randomly-sampled mistakes from the corpus. Pass criteria: no caption looks WORSE; the targeted four look strictly better.

### Phase 4 — Mohit eyeball + Parth review

Before declaring done: side-by-side comparison of the 4 flagged positions + 10 sampled mistakes posted as a single review doc. Sign-off before retiring the existing R12 behavior.

---

## 7. Risk + rollback

**High-risk surfaces:** any caption that today fires R12_blunder. That's V5 review + GameDecryptionV5 walkthrough + possibly home page recap (per `caption_pipeline_central_layer`).

**Blast radius:** ~30-50% of mistake-tier user moves get a different caption shape. Most should be improvements; a minority will look weird if facts misalign.

**Rollback:** the existing `why_clauses_user` predicate list is preserved as `alternative_clauses_user` unchanged. Reverting is a single PR (delete `failure_mode_clauses_user`, restore `select_variant` to today's order, restore renamed key). No data migration needed.

**Cache/storage:** captions render at request time (per `is_stored_data_cached: false` in central layer); reverting takes effect immediately. No backfill.

---

## 8. What this spec does NOT cover

- **Bug A (silence on routine moves)** — that's `fb_457d742bcc4b` / `fb_f4daba662227`. The "silent??" feedback on `m5 Nf3 cp=9` and `m4 c3 cp=24` is a different design question (positive fallback for sub-50cp opening moves). Separate spec.
- **Voice/persona variants** — the captions stay in the existing neutral voice. The Indian-coach persona pass from the 3-game audit is a layered concern, separate doc.
- **Opp-side captions** — `why_clauses_opp` is untouched. The pattern (alternative-promotion only) is correct for opp moves because the user wants to know "what should I have done about it" — that's the alternative.
- **Sac-aware extension** — item #1 in CAPTION_BACKLOG.md, deferred separately.

---

## 9. Implementation order

1. Write probe v2 (Phase 1 test fixtures).
2. Extract two new failure-mode facts (`opp_reply_creates_fork`, `opp_reply_removes_defender`) in `caption_facts.py`. Unit tests on synthetic positions.
3. Rename `why_clauses_user` → `alternative_clauses_user`. No-op verification (existing tests pass).
4. Add `failure_mode_clauses_user` list with the 7 entries.
5. Add 3 new variants + 3 new `select_variant` entries.
6. Wire `resolve_why_clause` to compute both clauses into `facts["failure_clause"]` and `facts["alternative_clause"]`.
7. Run Phase 1 + Phase 2 locally.
8. Deploy, run Phase 3 + Phase 4 server-side.

Estimated effort: half-day for steps 1-7, half-day for snapshot review + iteration.

---

## 10. Decisions (was: open questions)

Decisions made by Mohit 2026-06-02, resolving all three of the original open questions:

1. **Sentence flavour: contextual.** Different verb per failure fact. Table in §2.
2. **No naked "{best} was better" sentences.** No silence on user mistakes when we have a failure-mode fact.
3. **Contradiction case → teaching principle.** When the engine's best move doesn't match a concrete alternative-promotion fact, replace the alternative clause with a universal teaching principle keyed to the failure mode. Mohit's recommendation request answered with this design: always-something, always-grounded, always-teaches.
