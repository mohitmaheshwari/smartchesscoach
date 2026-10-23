# One face: the framework decides everything

Mohit, 2026-10-23:

> "I want everything inside framework and framework takes care of
> everything, right now we have different faces, and detectors and
> framework and facts, everything is inside framework, games or moves talk
> to framework and framework decide and generate and send to LLM and LLM
> gives the sentences and build arrows when needed... I am not asking you
> to change detectors to something else, I am asking you to consolidate
> everything inside one face, so game talks to one face and then that face
> decides what to do."

Not a detector change. A change to how many doors there are.

## Why the page has six voices

Measured on five re-analysed games, 372 captions:

| writer | share |
|---|---|
| the framework (purposes to facts to LLM) | 22.0% |
| distilled template | 17.2% |
| held (an earlier stage's text kept) | 15.0% |
| ~15 deterministic rules | ~34% |
| authored by hand, June 2026 | 1.6% |

The cause is in the call graph, not the writers. There are **three
independent decision-makers** and the renderer arbitrates:

| face | lives in | what it knows |
|---|---|---|
| 1 | `analysis_worker` | runs `purposes_for` / `plan_purposes_for`, builds facts, calls the LLM, writes `llm_caption` onto the move |
| 2 | `caption_pipeline.build_move_teaching_decision` | the R-rule cascade and the distilled layer. **0 references to purposes. 0 to the LLM.** |
| 3 | `game_decryption_v5_service:4050` | splices face 1's text over face 2's decision |

`build_move_teaching_decision` is already described in this repo as THE
central caption layer, and it does not know that either the purposes layer
or the LLM exists. Both were bolted on outside it. So the renderer decides
precedence, which is why the same page speaks in six registers and why the
two cards Mohit flagged today -- the `a4` filler and the bare `Bg4` line --
came from writers nobody had been improving.

## The one face

Two functions. Everything else calls only these.

```
framework.facts_for(move)              -> FactBundle | None
framework.decide(move, llm_text=None)  -> MoveTeachingDecision
```

**`facts_for`** picks the detector set by move type, which is the choice
currently scattered across three call sites:

| move | detectors | measured |
|------|-----------|----------|
| a fault (cp_loss >= 40) | `purposes_for`, facts about the BETTER move | facts on 75% of faults |
| not a fault | the same detectors aimed at the PLAYED move, `played_*` purposes dropped | facts on **62.4%** of 5,879 non-faulted moves |
| a plan | `plan_purposes_for`, the named-shape table | 1.5% of games |

That middle row is the big one and it is new: pointing the existing
detectors at the played move instead of the alternative. No new detector,
no new engine call. Together with faults it takes the framework's reach
from the 22% it writes today to about 68% of the page.

**`decide`** owns precedence, which is the thing being moved out of the
renderer:

1. a proven purpose with LLM text -> use it
2. a proven purpose without LLM text -> the deterministic sentence built
   from the same facts
3. no proven purpose -> the existing distilled / R-rule / floor cascade,
   untouched
4. an authored override -> wins over everything, as it does today

## What does NOT change

- **The detectors.** Not one line. Mohit was explicit.
- **The arrows.** `decide` already returns them and will keep returning the
  same ones. The fingerprint records `arrows` and `best_arrows` per card so
  this is provable rather than asserted.
- **The authored overrides.** 190 hand-written captions keep winning.
- **Where the LLM runs.** Still at analysis time, not on page load. The LLM
  call is async and needs the engine data; `facts_for` is what the worker
  asks, and the text is passed into `decide` later.

## The safety net, before any code

`feedback_snapshot_the_corpus_before_refactoring`: fingerprint the output
and diff per row, because this moves the precedence decision for every card
in 19,000 games and totals hide a card that turned into another card.

Baseline taken 2026-10-23: **23,618 cards across 400 games**, one row each
with the rule chain, a caption hash, a readable prefix, the word count and
both arrow counts.

The gate to ship: re-fingerprint and diff per row. Every changed row must
be explainable as "the framework now writes this card, and here is the
fact it used". An unexplained change, or any change at all in the two
arrow columns, blocks it.

## Order of work

1. ~~Fingerprint the corpus.~~ Done: 23,618 cards.
2. `framework.py` with the two functions, delegating to today's code paths
   unchanged, so the first commit is a pure move with no behaviour change.
   Re-fingerprint: expect a ZERO-row diff. Anything else means the move was
   not pure.
3. Point `facts_for` at the played move for non-faults. Re-fingerprint:
   expect changes only on non-faulted cards that had no framework facts
   before, and no arrow changes.
4. Move the precedence decision out of the renderer into `decide`.
   Re-fingerprint and explain every changed row.
5. Repoint the other callers (`routes/games.py`, `routes/coach_play.py`,
   `active_recall_integration.py`, the admin routes) at the one face.

Step 2 is the one that proves the design: if a pure move does not produce
an identical corpus, the faces were doing more than arbitrating and the
plan needs revising before going further.
