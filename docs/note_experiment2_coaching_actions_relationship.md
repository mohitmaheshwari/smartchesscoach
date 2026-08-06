# Note: Relationship Between Experiment #2 and Coaching Actions

**Purpose:** resolve exactly one architectural question before the
Coaching Actions RFC gets drafted — everything else about that RFC is
downstream of this answer. One page, on purpose.

**Same question?** No. Experiment #2 varies the **explanation axis**
(what caused the mistake — move-specific vs. root-cause). Coaching
Actions varies the **instruction axis** (what to do about it next —
Rule, Habit, Trigger, Drill). Checked, not assumed: every
explanation × instruction combination is pedagogically coherent
(root-cause + trigger, move-specific + drill, root-cause + habit, etc.)
— that's the actual test for orthogonality, not just "these sound like
different things."

**Different question?** Yes, per above.

**Dependency?** Not a logical one. Coaching Actions' instruction
taxonomy doesn't need Experiment #2's outcome to be *definable* — the
four candidate instruction types can be designed today, blind to which
explanation style wins. Two real reasons to sequence anyway, and they're
different in kind, worth keeping separate rather than collapsing into
one "dependency":

1. **Resource/policy** — one-experiment-at-a-time blocks running both
   *live* at once, since both change coaching content for the same
   small population. A scheduling fact, not a scientific one.
2. **Design-quality** — whichever explanation style wins plausibly
   changes which instruction types pair best with it. A root-cause
   finding ("you stopped checking for threats around move 20") pairs
   naturally with a Trigger or a Habit; a move-specific finding pairs
   more naturally with a Drill. Designing the instruction taxonomy blind
   to Experiment #2's result risks optimizing for the losing
   explanation style.

Both point to the same sequencing conclusion, but only the second is a
real design dependency. Worth keeping distinct so nobody later assumes
Coaching Actions can't be *conceived* until Experiment #2 finishes — it
can be designed in parallel, just not tested or shipped in parallel.

**Queue order:** Experiment #1 (running) → Experiment #2 (queued) →
Coaching Actions (newly queued, third). Coaching Actions does not
replace Experiment #2's slot.

**Shared infrastructure:** Both are caption-content changes, delivered
through the same pipeline (`caption_pipeline.py`'s
`build_move_teaching_decision`). The caption data model should reserve
two independent fields (`explanation_type`, `instruction_type`) when
Experiment #2 is implemented, rather than building its variant as a
one-off — so Coaching Actions composes onto it later instead of forcing
a pipeline rewrite when its turn comes.

**Shared metrics:** Likely yes. Experiment #2's primary outcome (per the
Research Ledger) is whether the *same mistake recurs* in the next 10
games. Coaching Actions' natural outcome is the same shape — recurrence
rate of the targeted mistake — and eventually the recall metric, once
real actions exist to recall. If Experiment #2 builds recurrence-
tracking infrastructure, Coaching Actions likely doesn't need to build
its own. A second efficiency from sequencing, not just a shared
research question.

---

**Conclusion:** Orthogonal, but sequenced — by policy, and secondarily
by design quality. Coaching Actions does not replace Experiment #2. It
can be designed now; it should not be tested until Experiment #2
resolves.
