---
name: check-voice
description: Audit a caption or coaching-text snippet against the memory rules for voice (no chess jargon, target audience 600-1500, name the square not the concept, keep universal-principle ending). Also flag parallel coaching paths that bypass the central caption pipeline. Trigger before committing any caption template, coaching message, or game-mirror rewrite.
---

# Voice + memory-rule audit for caption snippets

When changing caption text, coaching templates, or any user-facing teaching string, run this BEFORE commit. The memory has accumulated rules; this skill enforces them so you don't ship the same regressions twice.

## When to invoke

- User pastes a proposed caption or coaching string
- User edits `services/caption_pipeline.py`, `services/game_mirror.py`, `services/coaching_voice.py`, `data/coaching/*.json`, or anything in `services/concept_detectors/*.py` (caption side, not detection)
- User says "does this read OK for 1200" / "is this jargon-y" / "is this teaching"
- Before any commit touching frontend text in `coach/`, `MasteryPanel.jsx`, `HomePage.jsx`, `SkillDrill.jsx`, `EvidenceModal`

## Input

Either:
- Path to a file (Read it)
- Pasted snippet (work from the paste directly)

## The rules to check (each links a memory)

### 1. Chess jargon — [memory/feedback_caption_voice_avoid_chess_jargon]

Target audience is 600-1500. The following words read as gibberish to that band — flag and propose a plain-English rewrite:

- **fianchetto** → "bishop on the long diagonal" / name the square (e.g. "your g2 bishop")
- **prophylaxis / prophylactic** → "stopping their threat before they make it"
- **zwischenzug** → "in-between move" / "tactic before the recapture"
- **zugzwang** → "every move loses something here"
- **luft** → "an escape square for your king"
- **tempo** (sometimes OK in endgame contexts) → "free move" / "extra turn"
- **opposition** → describe the geometry instead ("kings facing each other one square apart")
- **outpost** → name the square ("a knight on d5 that can't be kicked")
- **discovered attack / battery / pin / skewer** — usually OK at 1200+ but explain on first use
- **double attack / fork** — OK
- **back rank** — OK but always explain why it matters

When in doubt: **name the square**, not the concept.

### 2. cp_loss is NOT material — [memory/feedback_cp_loss_is_not_material]

The pre-commit hook catches one regression. Flag broader variants:

- "drops/loses/costs about N pawns" — the pawn count is centipawn evaluation, not actual pawn material. Rewrite as "the position got worse by about N pawns' worth" or "this is roughly N pawns behind."
- "loses material" — only correct if a piece was actually captured. For cp_loss without a capture, this is wrong.

When the line literally appears in an audit/test file as a quote of a forbidden phrase, ensure the suppress tag `# allow-cp-loss-phrase` is on the same line — see project root `.githooks/pre-commit`.

### 3. Keep the universal-principle ending — [memory/feedback_caption_keep_explicit_principle_ending]

A caption that ends without a universal principle is a missed teaching moment. The structure is:

> {what happened} + {why it mattered} + **{universal principle that applies beyond this position}**

If the snippet ends without that third sentence, flag it. Better verbose teaching than terse description.

### 4. Fix framing, not detection — [memory/feedback_fix_framing_not_detection]

If the snippet sits in a `detect_*` module under `services/concept_detectors/` and the rewrite is REMOVING a detection branch, push back: the right fix is rewriting the *caption template*, not deleting the *trigger*. See the v53 Légal regression.

### 5. One source of truth — [memory/feedback_one_source_of_truth] / [memory/project_pwc_runs_second_coaching_engine]

If the snippet adds a new caption-emitting code path that does NOT go through `services/caption_pipeline.build_move_teaching_decision`, flag it. The central layer exists; new helpers go there, not in parallel.

Particular trap: PWC's `move_critique` / `coaching_policy` / `coaching_voice` still run a SECOND coaching engine (per the memory). Any edit that adds to those without migrating to the central layer needs explicit sign-off, not a quick patch.

### 6. No hardcoded debug — [memory/feedback_no_hardcoded_debug_in_production]

Flag any production caption code with case-specific guards like `if move_san == 'Nf6': log(...)`. Use a scratch script in `/tmp` or an env-var gate.

### 7. Opening name only at critical lessons — [memory/feedback_opening_name_only_at_critical_lessons]

Naming the opening ("In the Scandinavian, ...") is only worth it when the lesson is opening-specific. For routine developmental moves (typical Nf3, e3, etc.), drop the opening name — it adds words without value.

## Output format

Keep tight. Per issue:

```
[rule violated] at <line N or position> — <quoted excerpt>
  Reason: <one sentence>
  Suggest: <rewrite, or pointer to memory>
```

End with a one-line summary:
- "✓ Clean — no rule violations" / "⚠️ N issues found, review before commit"

If you flag a parallel-coaching-path issue (rule 5), make this prominent — it's a much bigger debt than a wording fix.

## What NOT to do

- Don't grade tone subjectively ("this sounds cold"). Stick to the enumerated rules.
- Don't propose rewrites for snippets that pass all rules — silence on a clean snippet is the right output.
- Don't rewrite the user's prose into your voice. Match their register; just remove jargon and add the principle if missing.
- Don't run on snippets that aren't caption code (e.g. backend route logic, frontend JSX without text). Text-only.
