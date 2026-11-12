# Why queue: Opus writes, a second agent checks, agreed studies go live

Status: SIGNED 2026-11-12 (Mohit: "go ahead please", after the plan: Opus 5.5 writes every 10
minutes, Fable checks, auto-publish only when the board replay and the checker both agree, the
checker must first reject the known-bad e6 study).

## 0. Existing surfaces audit

| Surface | What it already does | Where |
|---|---|---|
| Scheduler | Task Scheduler "ChessGuru Why queue" on Mohit's PC, every 15 min, `--limit 3` | Windows task, `_why_worker` checkout |
| Writer | One Claude call writes the study; one rewrite if the gate found fault | `why_queue_worker.study` |
| Gate | Replays every claim on the board and checks the words | `why_study.run_gate` |
| Publish | A person presses Agree on the admin tab; `WHY_QUEUE_AUTO_PUBLISH=1` skips the person entirely | `admin_claude_reasons.py`, worker |
| Card | A published study becomes the card caption, "Studied by the coach" | `docs/why_study_on_card_scope.md` |

What the gate cannot see: whether the explanation is the REAL reason. Every claim in the false
Opus e6 study ("Kd8 was better") could replay and the lesson still be wrong. Today only Mohit
catches that.

Measured 2026-11-12 (`why_reasons.model`): the three studies Mohit agreed (Rf7, Ke7, e5) and the
b3 no-lesson were all written by Opus 5.5. Its one known failure is e6. Fable wrote e6's
no-lesson.

**Decision: EXTEND.** Same task, same worker, same admin tab. One new step between the gate and
the write.

## 1. What it is

Every ten minutes the worker studies new positions with Opus 5.5. When a study passes the board
replay, a second agent (Fable) reads the same engine facts and the study, and says whether the
study is true and names the real reason. Only when both say yes does the study go live on the
card without waiting for Mohit. Anything else waits on the admin tab with the checker's note.

## 2. What the user sees

No player-facing change: a published study looks as it does today ("Studied by the coach").
What changes is how fast a good study gets there, and that a doubtful one does not.

Admin tab, a held study (data only in V1; stored on the row as `check`):

```
Bc5 · held for review
  study:   ...
  checker: disagree. "The study says Bc5 leaves e5 unguarded, but the lines show
            the real cost is ..."
```

## 3. In scope (V1)

- Writer model: `claude-opus-5-5` (was Fable 5.1). `CLAUDE_MODEL` still overrides.
- Checker: one Claude call, model `claude-fable-5-1` (`WHY_CHECKER_MODEL` overrides), same packet
  plus the study and its replayed claims. Answer: `agree` / `disagree`, the problem, and its own
  one-line reading of the main difference. Unsure means disagree.
- Runs only on studies that passed the gate and have a lesson (no-lesson rows are unchanged).
- Publish rule: gate passed AND checker agrees AND `WHY_QUEUE_CHECKER_PUBLISH=1` -> `published`.
  Everything else -> `held_for_review`, with `check` stored on the row.
- Calibration before the flag is turned on: run the checker on the three agreed studies (must
  agree), the Opus e6 study (must disagree) and the two old card captions the study replaced on
  Ke7 and e5 (must disagree).
- Task interval 10 minutes.
- Admin tab: the checker's verdict shows as one line under the study (existing probe list, no
  new UI), and a study the checker published stays on the tab, first, marked LIVE, until a person
  rules (Agree keeps it, Disagree withdraws it and re-renders the cards). Without this nobody
  would see what the checker published, and the live measure in section 5 could not be taken.

## 4. Explicitly out of scope (V1)

- New admin UI beyond the one probe line.
- Checking no-lesson studies.
- A second rewrite driven by the checker's note.
- Re-checking the three already published studies on the card.

## 5. Success criteria

- Calibration: 3 of 3 agreed studies agree, 3 of 3 known-bad explanations disagree. If e6 is not
  rejected, the publish flag stays off.
- Live: of studies the checker publishes, zero that Mohit later rejects. Measured on the first
  ten published.

### Calibration result, 2026-11-12 (Fable 5.1 as checker, one run each, $3.84)

`scripts/why_checker_calibrate.py`, packets rebuilt locally at depth 20. 9 of 9:

| Position | Study | Expected | Checker |
|---|---|---|---|
| Rf7 | Opus study (published) | agree | agree |
| Rf7 | Fable study (published earlier) | agree | agree |
| Ke7 | Opus study (published) | agree | agree |
| Ke7 | Fable study (published earlier) | agree | agree |
| Ke7 | old card caption "They missed Bd6, it brings a new piece into the game" | disagree | disagree |
| e5 | Opus study (published) | agree | agree |
| e5 | Opus study rejected on the admin tab ("you can answer d5") | disagree | disagree |
| e5 | old card caption "Play Nge7, it brings a new piece into the game" | disagree | disagree |
| e6 | Opus "Kd8 was better" (held, false) | disagree | disagree |

On e6 its note was the right one: "Kd8 does not save the d7 rook: in its own line White still wins
it". 49-125 s and $0.28-0.59 a check. Nine cases, one run each: this shows it can reject a
known-bad study, not that it always will (section 5's live measure is the real test).

## 6. Open questions

- **Checker model.** Fable, so writer and checker are different models. *Unblocking:* the
  calibration result; if Fable fails it, try Opus as the checker and report.
- **Six calibration cases is small.** It proves the checker can reject a known-bad study, not
  that it always will. *Unblocking:* the live measure in section 5.

## 7. Pre-code requirements

- Open PRs and branches checked for the worker files (none, 2026-11-12).
- The scheduled task is paused while the worker checkout is edited (it runs from that checkout).
