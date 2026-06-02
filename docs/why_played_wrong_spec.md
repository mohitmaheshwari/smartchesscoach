# "Why Played Wrong" — Two-Clause Caption Spec

**Status:** DRAFT v1 — awaiting Mohit sign-off before implementation.
**Version:** v1 (2026-06-02).
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

## 2. The shape

Every caption for a user mistake renders **two clauses, both grounded in concrete facts**:

```
{played} {failure_mode_clause}. {best} was better — {alternative_promotion_clause}.
```

Examples (target after this ships):

- **m20 Bb2:** "Bb2 walks into Rb1 attacking the bishop. h4 was better — it attacks Bg3 with tempo."
- **m24 Qb8:** "Qb8 allows Nb7 forking your queen and rook. Be7 was better — keeps the back rank defended."
- **m16 Bf6:** "Bf6 hangs to Nxd5 capturing the bishop. f5 was better — locks the pawn structure."

When **only** a failure-mode clause exists (no concrete alternative-promotion fact):

```
{played} {failure_mode_clause}. {best} was better.
```

When **only** an alternative-promotion clause exists (no concrete failure-mode fact — the played move was just suboptimal):

```
{played} is a mistake. {best} was better — {alternative_promotion_clause}.
```

When **neither** exists (no concrete facts at all):

- Stay **silent** in V5. Existing behaviour. Don't fall back to engine-speak ("the move loses material in the resulting line") — that was already removed in v94 per the memory note in R12_blunder.json.

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

Three new variants drive the wrapping format:

```json
"variants": {
  "user_with_failure_and_alternative":
    "{played_san} {failure_clause}. {best_move_san} was better — {alternative_clause}.",
  "user_with_failure_only":
    "{played_san} {failure_clause}. {best_move_san} was better.",
  "user_with_alternative_only":
    "{played_san} {severity_phrase}. {best_move_san} was better — {alternative_clause}.",
  /* existing variants kept for opp-side + backwards compat */
}
```

Selector order (first match wins, as today):

```json
"select_variant": [
  {"when": {"failure_clause": "present", "alternative_clause": "present"}, "variant": "user_with_failure_and_alternative"},
  {"when": {"failure_clause": "present"},                                    "variant": "user_with_failure_only"},
  {"when": {"alternative_clause": "present"},                                "variant": "user_with_alternative_only"},
  /* existing fallbacks (user_winning_position, user_losing_position, silent, etc.) */
]
```

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

## 10. Open questions for Mohit

1. **Sentence flavour.** "walks into" vs "allows" vs "drops to" — current draft uses "walks into" for opponent-piece-attacks-played; "allows" for fork; "hangs to" for capture. Want a single verb family or contextual?
2. **Engine-best-vs-alternative-promotion-fact divergence.** When the engine's best move is sometimes NOT one of the alternative-promotion-fact-emitting moves, do we still say "{best} was better"? Today's behavior: yes. Should we silence the alternative clause when the engine's best move is just "less bad" rather than "concretely better via fact X"?
3. **Failure mode + alternative are inconsistent.** What if `failure_mode_clause` says "walks into Nb7 winning your rook" but the engine's best move is also a non-defending move (just a slightly-less-bad alternative)? The combined sentence reads as "X allows fork. Y was better." but the user might wonder why Y was better. Is silent on the alternative clause OK here?
