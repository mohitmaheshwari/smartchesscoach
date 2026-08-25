# Coaching Components — What To Build

**Status:** DRAFT v1 — component architecture for the coached experience.
Companion to `coached_experience_design.md` (the what). This is the how.

---

## 1. What the user actually touches

Three surfaces. Not thirty.

| Surface | What it is | Status |
|---|---|---|
| **Today** | One screen. One line of context, then reps on a board. | **Missing** |
| **Play with Coach** | Real game; the Guardian intervenes at the moment of decision. | Built — not wired to the instruction |
| **Review** | Where the habit failed, shown on the board. | Built |

Everything else (Lab, Progress, Openings, Training pages) is either supporting or
should stop being a destination.

---

## 2. The pipeline

| # | Stage | Component | Status |
|---|---|---|---|
| 1 | Ingest games | `journey_service`, `analysis_worker` | **Built** |
| 2 | Observe per-move facts | `move_observation_deriver` (421k obs) | **Built** |
| 3 | Diagnose the thread | `focus_resolver`, `user_active_focus` | Built, needs repair |
| 4 | **Decide today's action** | Daily Decision Service | **MISSING** |
| 5 | **Serve reps** | Rep Engine | **MISSING** |
| 6 | Intervene live | `pre_move_guardian` | **Built** — not wired |
| 7 | Verify in real games | `piece_safety.d_live.v1` | In build |
| 8 | Advance | focus outcome path | Partial |

**Two components are missing, and they are the two that make it a coach.**
Everything else exists.

---

## 3. The Rep Engine

### The key property: reps are generated, not authored

This is the most important fact in this document.

LES stalled because it required human-reviewed Gold content and had **zero**.
That bottleneck exists because *"what is the best move here?"* needs human
judgment.

**"Is this square safe, and who takes it?" does not.** SEE answers it
deterministically. Which means reps can be generated from data already in the
database, verified at generation time, with no authoring queue:

| Source | Volume | Why it matters |
|---|---|---|
| `move_observations` v16 | **149,886** with `fen_before`, `move_uci`, `cp_loss` | The player's own decisions |
| `community_training_positions` | **37,266** with `fen`, both moves, `difficulty`, `source_user_rating` | Rating-matched fallback |

There is no content bottleneck for piece safety. There never was — we were
looking at the wrong question type.

### A rep

```
Rep = (fen, question_type, prompt, options, verified_answer, demonstration)
```

Five question types, all SEE-verifiable, zero authoring:

| Type | Prompt | Player does | Verified by |
|---|---|---|---|
| `is_safe` | "You want to play Bg5. Safe?" | taps Safe / Not safe | `SEE(dest) >= 150` |
| `who_takes` | "Who takes it?" | taps a square | least-valuable attacker |
| `pick_safe` | three candidate moves | taps one | SEE per candidate |
| `find_loose` | "One piece is loose. Which?" | taps a square | SEE over own pieces |
| `make_it_safe` | "Your knight is attacked. Fix it." | plays a move | `SEE after == 0` |

Escalation order is the curriculum: recognise → attribute → choose → repair.

### Difficulty is computed, not tagged

Piece value · number of attackers and defenders · direct attack vs discovered ·
whether a defender exists at all. All derivable from the position. No difficulty
authoring, no rating guesswork.

### Generation-time verification (non-negotiable)

Every candidate rep is verified before it can be served, and **rejected** when:

- SEE is borderline (100–200cp) — ambiguous reps teach nothing;
- `cp_loss` does not corroborate (a "hang" that is actually a sound sacrifice);
- a bigger idea competes — the player can hang a knight while delivering mate;
- the position or move is illegal, or the orientation is wrong.

### Same predicate for drilling and measuring

The rep generator uses **the exact `piece_safety.d_live.v1` predicate** that
measures real games: eligible piece ≥ knight, legal destination capture,
destination SEE ≥ 150, `cp_loss ≥ 150`.

That is deliberate. **What we drill and what we measure are the same thing**, so
improvement in reps is measurable in games *by construction* rather than by
hopeful correlation. One predicate, one source of truth, two uses.

### Source priority (this is the personalisation)

1. The player's **own** positions — moves they actually played
2. Rating-matched community positions
3. Corpus fallback

Same rep format, their board. Personalisation is in the *source*, not in a
separate personal feature.

---

## 4. The Daily Decision Service

One function. Input: player, now. Output: one action.

```
{ kind, reason_line, payload, estimated_seconds }
```

Priority cascade:

1. new game since last visit → review moment
2. checkpoint due → unannounced mixed set
3. delayed recall due → one folded-in item
4. active focus needs practice → reps
5. nothing pending → syllabus item from the skill tree

`reason_line` is the coach's one sentence. The frontend renders it; it never
composes it.

**Ship it stubbed.** Version one can return rule 4 every time. The cascade is
where the coach's judgment lives and it can grow later — but the interface must
exist from day one so no surface ever invents its own decision.

---

## 5. API surface

Five endpoints.

```
GET  /api/coach/today                     → one action + reason line
POST /api/coach/session/start             → session_id
GET  /api/coach/session/{id}/next         → the next rep
POST /api/coach/session/{id}/answer       → correct? + demonstration payload
POST /api/coach/session/{id}/finish       → short verdict
```

Reuse the LES resumable-session contract for state. Reuse `puzzle_attempts` for
per-rep records. No new mastery label — `concept_mastery_service` remains the
only publisher of learner-facing status.

---

## 6. One frontend component

**`RepRunner`.** Board dominant, one prompt line, 2–4 answer controls, a
feedback overlay that animates the demonstration.

Every rep type renders through it. Every concept reuses it. If a second rep
component appears, the abstraction failed.

It replaces, over time, the delivery flows in `SkillDrill`, `MotifDrill` and the
prescribed-training page — the three places that currently do this job three
different ways.

---

## 7. Build order

Each step is demonstrable on its own.

| # | Step | Proof it works |
|---|---|---|
| 1 | **Rep generator** (backend only) | Generate 500 reps from the corpus; verify 100% pass their own SEE + `cp_loss` gates; sample 50 by hand |
| 2 | **`RepRunner`** (frontend) | Eight reps, board-first, under three minutes, on a phone |
| 3 | **`/api/coach/today`** stubbed to rule 4 | One CTA on Home opens a real session |
| 4 | **Wire the Guardian** to the active instruction | Guardian's `HANGING_PIECE` fires the same words as the drill |
| 5 | **D_live emission** | Runtime reproduces 15.07% / 9.47% on the v16 corpus |
| 6 | Verdict + next focus | Honest verdict after a committed game |

Steps 1–3 are the product. Steps 4–6 make it honest.

Note the inversion from the PIC spec's sequence: **the fix ships before the
measurement.** Measurement should follow what is worth measuring.

---

## 8. What this does not build

No new dashboard. No second lesson dispatcher. No new mastery label. No content
authoring queue. No new taxonomy, rating table, or caption path. No social
features. Openings and endgames stay parked until the rep shell is proven on one
concept.

---

## 9. Open questions

1. **Does `RepRunner` extend `teaching_engine`'s lifecycle** (per LES/PIC
   authority rules) or is a rep too thin to be a "lesson"? Needs an
   architecture ruling before step 2.
2. **Where do rep records live** — `puzzle_attempts`, or the LES session event
   stream? They mean different things; pick one owner.
3. **How many reps per session**, and does it adapt to accuracy? Lock from
   post-launch data; ship at 8.
4. **Does the Guardian's intervention count as evidence?** It is assisted by
   definition — so it should train the habit but never prove it.
