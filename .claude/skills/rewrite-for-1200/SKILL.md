---
name: rewrite-for-1200
description: Rewrite a caption / coaching snippet / template string for chessguru's 600-1500 audience. Different from /check-voice which audits — this DOES the rewrite applying the seven voice rules. Trigger when the user pastes a snippet and asks for a rewrite, or types /rewrite-for-1200, or says "make this less jargony" / "rewrite for 1200" / "drop the jargon here".
---

# Rewrite a snippet for the 1200 audience

[/check-voice](../check-voice/SKILL.md) audits and proposes — it tells you "rule N is violated, suggest X." This skill is the action verb: take the snippet and produce the rewritten version applying the seven voice rules, ready to drop into the code.

## When to invoke

- User pastes a caption / coaching template / game_mirror entry and says "rewrite this" / "make this 1200-friendly"
- User flags a specific phrase as too jargony ("this 'fianchetto' bit needs fixing")
- User types `/rewrite-for-1200`
- User asks "what would this sound like for a 1200?"

Do NOT invoke when the user wants an audit only — use `/check-voice` for that. Do NOT invoke for code logic changes — text-only.

## Required input

- The snippet to rewrite. Either pasted text OR a file path + the specific lines/template names to rewrite.
- Implicit context: the chessguru voice rules in [memory](../../../.claude/projects/c--Users-MIISCO-smartchesscoach/memory/). Listed below for reference.

## The seven voice rules (apply in order)

1. **No chess jargon for 600-1500.** Targets: `fianchetto`, `prophylaxis`, `zwischenzug`, `zugzwang`, `luft`, `opposition` (as concept), `outpost`, `ply` / `plies`, `book` (as theory), `deflection`. **Replace with**: name the square ("your g2 bishop"), describe the geometry ("kings facing each other"), use plain English ("one move further", "main opening line").
2. **cp_loss is NOT material.** Targets: "drops N pawns", "loses N pawns", "costs N pawns". **Replace with**: "the position got worse by N pawns' worth", "this is roughly N pawns behind."
3. **Keep the universal-principle ending.** Captions should end with a universal rule the user can carry to the next position. If missing, ADD one.
4. **Don't fix detection, fix framing.** If the snippet is in a detector module, don't propose deleting the trigger — only rewrite the caption template.
5. **One source of truth.** If the snippet adds a new caption emission path bypassing `services/caption_pipeline.build_move_teaching_decision`, push back BEFORE rewriting — surface the architecture concern.
6. **No hardcoded debug.** No case-specific `if move_san == 'X'` guards in the rewrite.
7. **Opening name only at critical lessons.** Routine developmental moves don't need "In the X opening, …" framing. Critical opening-specific lessons (a known theoretical mistake, a named trap) do.

## Steps

1. **Read the snippet.** If a file path was given, read the relevant lines. Get the surrounding context — the principle being taught, the audience for THIS specific surface (review caption / coaching prompt / drill hint), the placement (per-move vs per-game).

2. **Identify the surface.** Different surfaces have different voice conventions:
   - **R12_blunder caption** — short, structured, contextual verb + alternative or principle. See [backend/data/captions/R12_blunder.json](../../backend/data/captions/R12_blunder.json).
   - **Coach Review principle template** — title + diagnosis + principle. See `_PRINCIPLE_TABLE` in [backend/services/game_coach_review.py](../../backend/services/game_coach_review.py).
   - **Skill drill hint** — short conversational. See `SKILL_COPY` in [frontend/src/pages/SkillDrill.jsx](../../frontend/src/pages/SkillDrill.jsx).
   - **Home recap blurb** — phase-bucketed sentence. See [backend/routes/home.py](../../backend/routes/home.py).

   Match the existing voice of the surface — neutral, plain, ~25-50 words for a caption, ~12-20 words for a principle.

3. **Apply the seven rules in order.** For each violation found, draft the replacement. When jargon is replaced, name the square or describe the geometry (rule 1's positive form). Don't drop the universal principle if the original had one — rewrite it in plain English.

4. **Preserve the structure.** If the snippet has `{slot}` template variables, keep them in the same positions. If it's a JSON entry, preserve the keys + nested structure. If it's a Python dict, preserve indentation and ordering conventions of the surrounding file.

5. **Show the rewrite + a one-line note per change.** Format:

   ```
   BEFORE:
   {original snippet}

   AFTER:
   {rewritten snippet}

   Changes:
   - rule 1: replaced "fianchetto" → "your g2 bishop on the long diagonal" (named the square)
   - rule 3: added principle ending — "When your bishop sits on a long diagonal, defend the diagonal first"
   ```

6. **Verify by running through `/check-voice` mentally.** If any rule still fires on the rewrite, iterate before presenting.

7. **If the file is on the central caption pipeline path, run a probe.** For R12_blunder.json changes or caption_facts.py changes, render the affected variant via `probe_why_played_wrong.py` or a one-off snippet to confirm it actually renders cleanly. See [memory/feedback_fast_testing_strategy].

## Output format

- The rewritten snippet ready to paste into the file
- A short list of changes by rule number
- If the change is to a JSON file with template variables, note whether all template slot variables in the rewrite are guaranteed to be populated by the existing fact extractor (or whether a new fact is needed)

## What NOT to do

- **Don't change meaning.** The rewrite should teach the SAME concept; just in different words. If you can't preserve meaning without jargon, say so — sometimes the right answer is to write the rule differently in the JSON instead of rewriting the snippet.
- **Don't add new template variables silently.** If the rewrite needs `{new_fact}`, that's an architectural change — flag it instead of slipping it in.
- **Don't rewrite into a totally different register.** Match the surface's existing voice. Don't make a "Insights tab principle" sound like a "PWC turn coaching nudge" — they're different surfaces.
- **Don't fix-and-ship.** This skill outputs the rewrite. Editing the file + committing is a separate action the user decides on.
- **Don't drop the universal principle.** Per [memory/feedback_caption_keep_explicit_principle_ending] — teaching value > terseness. Even when the snippet feels long, the principle ending stays.

## Notes

- For batch rewrites (multiple snippets in one file), do them one snippet at a time so each rewrite gets the same care.
- If the surface is a HOME / RECAP / GAME_MIRROR template (phase-bucketed prose), favour very short sentences (≤12 words each) — the user reads these on a card with limited screen space.
- For LLM prompts (caption_llm_polish), this skill doesn't apply — those are model-facing instructions, not user-facing text.
- Pair with [/check-voice](../check-voice/SKILL.md) for the audit pass: audit → identify violations → rewrite.
