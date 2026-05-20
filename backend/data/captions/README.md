# Caption Templates — Content/Code Split

This directory owns every user-facing caption phrase the V5 coaching
pipeline emits. **No user-facing strings live in Python**, by design.
Mohit + Parth author the content here; Python only loads, dispatches,
and substitutes facts into the chosen template.

## Architecture laws

> These laws are enforced by code review and (eventually) a grep-based
> pre-commit hook that fails any PR adding string literals containing
> letters + punctuation inside the caption code files. The hook
> already enforces the narrower "drops about N pawns" rule today; the
> broader "no user-facing strings in Python" check is the next step
> after this migration lands.

- **LAW R1 — No `import chess`. No board parsing.** No `parse_san`,
  no SEE recomputation. Rules read the facts dict produced by
  `caption_facts.extract_facts()` and nothing else.

- **LAW R2 — No "smart" inference.** If a rule needs a derived value,
  the extractor produces it. Templates only do format-string
  substitution from existing facts.

- **LAW R3 — No user-facing strings in Python (Mohit 2026-05-20).**
  Caption text, severity words ("mistake" / "serious mistake" /
  "major blunder"), opening / trap / principle / shape blurbs all
  live in `backend/data/captions/*.json`. Python decides WHICH
  variant to use; JSON decides WHAT it says. Content is authored by
  Mohit + Parth, not Claude. The only legitimate strings remaining in
  caption code are developer-facing logs, identifier constants
  (category names, variant keys), and short comments — never prose.

- **LAW R4 — Rules are pure data.** A `Rule` is
  `(category, name, priority, trigger_fn, render_fn)`. The trigger
  function takes a facts dict and returns bool. The render function
  takes a facts dict and returns a `CaptionOutput`.

- **LAW R5 — Rules ordered by category match, then priority.** First
  match wins. No nested branching, no method dispatch.

## File layout

```
backend/data/captions/
├── README.md                            ← you are here
├── R01_mate.json                        ← R-rule content
├── R02_multi_target_attack.json
├── R03_aligned_pieces.json
├── R04_discovered_attack.json
├── R05_check_extra.json
├── R06_check_plain.json
├── R07_forced_recapture.json
├── R08_material.json
├── R09_king_safety.json
├── R10_threat.json
├── R12_blunder.json                     ← severity tiers + 13 why-clause variants
├── R13_opening_central_pawn.json
├── R14_forced_best.json
├── R15_good_move.json
├── R_PROMOTED_trap_setup.json           ← promotion-ladder content
├── R_PROMOTED_trap_defense.json
├── R_PROMOTED_opening.json
├── R_PROMOTED_shape.json
├── R_PROMOTED_principle.json
└── R_PROMOTED_basic_mistake.json
```

R11_development has no JSON file by design — the rule renders silence
unconditionally (a routine developing move teaches nothing the user
can't already see). When R11 fires, the renderer falls through to the
promotion ladder which surfaces opening / trap / principle / shape
content if the detectors hit. See `caption_rules.py:_r11_render` for
the locked rationale.

## Schema

Every file follows the same shape:

```json
{
  "rule_name": "R10_threat",
  "description": "When this rule fires, in plain English.",
  "fact_glossary": {
    "played_san": "human-readable description of what this placeholder means",
    "target_piece_type": "..."
  },
  "requires": ["played_san", "target_piece_type", "target_square"],
  "variants": {
    "default": "{played_san} threatens the {target_piece_type} on {target_square}."
  }
}
```

Optional sections:

- **`severity_phrases`** — used by R12_blunder + R_PROMOTED_basic_mistake.
  A dict of severity-tier → adjective phrase. Picked by cp_loss bucket.

## Runtime contract

1. **Missing required fact → silence.** If any key listed in `requires`
   is missing or empty in the facts dict at render time,
   `render_template` returns `None` and the renderer falls through to
   the next-priority rule. **Never crashes. Never renders a literal
   `{placeholder}` to the user.**

2. **Missing variant → silence.** Same fallthrough behavior.

3. **First-load is in-process cached.** To pick up edits without a
   container restart, call `caption_templates.reload_templates()`.

4. **Word cap.** The renderer enforces a 25-word cap as a final safety
   net (`MAX_CAPTION_WORDS` in `caption_config.py`). Templates should
   self-limit; this is the last guard.

## How to add an opening

1. Add an entry to `backend/data/opening_curriculum.json` with the
   opening's `name`, `summary`, `setup_order`, and `golden_rules`.
2. That's it. The next regen of any game that plays into that opening
   will surface its summary as the caption via
   `R_PROMOTED_opening.json` → `variants.default`.

No Python edits. No new R-rule registration. No Claude session.

## How to add a trap

1. Add an entry to `backend/data/traps.json` with the trap's `name`,
   `description`, `setup_steps`, and `trap_line_steps`.
2. That's it. The detector picks it up on the next regen.

The trap-setup caption uses `R_PROMOTED_trap_setup.json`; the
trap-defense caption (when the user holds the line) uses
`R_PROMOTED_trap_defense.json`. Both pull the trap name and
description from `traps.json`.

## How to change a caption's voice

1. Open the relevant `R*.json` file under this directory.
2. Edit the template string inside `variants`. Keep the `{placeholder}`
   names — those are the facts the renderer will substitute. Edit the
   prose around them freely.
3. Regen the game. New text appears. No Python.

Example — silencing R10_threat entirely:

```json
{
  ...
  "variants": {
    "default": ""
  }
}
```

The empty string returns silence and the renderer falls through.

## How to add a new variant

1. Open the relevant `R*.json` file.
2. Add a new entry to `variants` with a descriptive key.
3. **If the new variant is picked by Python logic** (e.g. a new
   severity tier), tell the Python render function to pick that
   variant key. (This is the one case where a Python edit is needed —
   when a new variant requires new dispatch logic. Phrasing changes
   don't require Python.)

## Where the renderer lives

- `backend/services/caption_templates.py` — JSON loader + `render_template()`.
- `backend/services/caption_rules.py` — R-rules. Trigger functions
  decide IF a rule fires; render functions decide WHICH variant to use
  and call `render_template`.
- `backend/services/game_decryption_v5_service.py` — the promotion
  ladder (Tier 1a/1b/2). Also dispatches into JSON via `render_template`.
- `backend/services/caption_renderer.py` — the dispatcher that picks
  the first matching rule and enforces the word cap.
