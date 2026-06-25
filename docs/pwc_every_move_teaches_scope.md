# PWC — "Every Move Teaches" — Product Scope

_Status: DRAFT for sign-off. No code until Mohit signs off._
_Parent north star: [coaching_presence_scope.md](coaching_presence_scope.md) — "a coach
that teaches you how to think." This doc is the concrete v1 of that, for the in-game
your-move surface._
_Origin: Mohit, 2026-06-25 — "you play a move it says good or bad, it only tells about
your move when the coach plays… not a premium coach experience." Direction chosen:
**every move teaches.**_

---

## The problem (verified in code, not assumed)

PWC coaches your move and the coach's move through **two asymmetric surfaces**:

| | Your move | Coach's move |
|---|---|---|
| Narrative source | central library (`build_move_teaching_decision` via `_central_narrative_for_move`) | central library (`coach_move_narration_for_live_move`) |
| Speaks when? | **only sometimes** — `coaching_policy.decide()` returns `narrative="", severity="silent"` on most routine/good moves (`shared_coaching_v5.py:1018`) | **always** — "no fallback path remains," narrates every move |
| What leads the card | a separate **good/bad badge** from cp_loss | the teaching line |

So on a normal move you see only a **"Good"** chip and no teaching, while the coach's
move always gets a full card. That asymmetry is the whole complaint: it feels like the
coach only talks when *it* moves, and like it only judges ("good/bad") your moves.

**Crucially:** the library already writes good lines for routine moves (verified
2026-06-25):
- `Nc6 — supports your central pawn on e5.`
- `d3 — controls c4, keeping enemy pieces off those squares.`
- `e5 — Open Game. Both sides fight for the center…`

The gate is **discarding captions that already exist**. This is the cheap, high-leverage
fix: stop suppressing them.

---

## What we build (v1)

**1. Un-gate the your-move caption (never-silence, matching review).**
When the central library produces a non-empty caption for the user's move, **render it**.
The policy-gate `should_speak=False` no longer blanks the card — it can still *down-rank*
tone/length, but it cannot produce silence when the library has something true to say.
This mirrors the review surface's standing rule: _coverage is first-class; mediocre beats
silence_ ([feedback_coverage_is_first_class]).

**2. Demote the good/bad judgment.**
The severity badge shrinks from the headline to a **small quiet dot** (green/amber/red).
The **teaching line becomes the headline**. We are a coach, not a grader.

**3. Add a forward "how to think" prompt where the library has one.**
When the move is fine, end with one thing to watch next ("Before you move: is e5 still
defended?"). Only when the door already carries a verified think-prompt — never invented.

### The card — before / after (this IS the spec; schema serves it)

```
NOW (most of your moves):                PROPOSED (every move):
┌────────────────────────────┐           ┌────────────────────────────┐
│ YOUR MOVE  Nf6     ● Good   │           │ ·  YOUR MOVE · Nf6          │
│ (no coaching text)          │           │ Develops the knight and     │
└────────────────────────────┘           │ fights for the e4 square.   │
                                          │ │ Before you move: is e5    │
   good/bad is the headline,              │ │ still defended?           │
   nothing is taught                      └────────────────────────────┘
                                            good/bad = the small dot ·
```

---

## What we are NOT doing in v1
- **Not** rewriting the caption library. The text comes from the same door as review;
  quality work on the text is the separate, ongoing caption track.
- **Not** authoring new good-move content — the library already has it.
- **Not** touching the coach's-move card (already always-teaches).
- **Not** adding LLM. Deterministic library + verifier only (standing law).
- **Not** trimming verbose lines yet (e.g. the Bc4 opening-DB line) — logged as polish.

---

## Quality bar (non-negotiable)
Every now-visible your-move line must pass the **per-FEN claim verifier already inside the
door** — same guarantee as review. Un-gating must not surface a single false claim. If the
library's only output for a move is unverifiable, it abstains (stays a dot) — that is the
*only* remaining silence.

## Where the code changes (for the estimate, not a green light)
- `services/shared_coaching_v5.py` — the `should_speak=False` early-return (~line 1018):
  prefer the non-empty `_central_caption` over blanking. Severity still computed for the dot.
- `routes/coach_play.py` `/v5/interactive-feedback` user-move section — pass the caption through.
- `components/coach/CoachPlaySidebar.jsx` — the "User's Move Feedback" block: badge → dot,
  teaching line → headline, optional think-prompt line.
- Flag: `PWC_EVERY_MOVE_TEACHES` (default off → on after a live check).

## Acceptance (how we'll know it worked)
1. In a live game, **every** user move shows a teaching line, not a bare badge.
2. 0 false claims across a 50-move bulk render (verifier + `pwc_coaching_lint.py`).
3. The good/bad chip is no longer the most prominent element on the card.
4. Side-by-side: a routine game now reads as "the coach talked me through it," not
   "the coach graded me."

---

## Open questions for sign-off
1. **Any move that should still be a silent dot?** (e.g. the literal first 1–2 book moves,
   to avoid stating the obvious — or truly never silent?)
2. **Think-prompt:** always end fine moves with a "watch X next" line, or only when the
   board gives a concrete one?
3. Frontend polish depth for v1 — minimal (badge→dot + headline swap), or also the
   left-rule think-prompt styling shown in the mockup?
