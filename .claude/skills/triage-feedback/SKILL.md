---
name: triage-feedback
description: Process a batch of user feedback items from chessguru's admin feedback queue. Categorize each by failure class (silent move, wrong-reasoning caption, duplicate caption, etc.), cross-check engine truth per game, and propose which items belong in CAPTION_BACKLOG.md vs which are already-known issues. Trigger when the user pastes a JSON dump of feedback items, OR types /triage-feedback.
---

# Triage a batch of feedback items

The chessguru admin UI emits feedback items as JSON with a structured shape (feedback_id, page, issue, coaching_text_flagged, position, context, severity, status). Mohit periodically sends batches asking "what are these telling us, what's actionable." This skill does the categorization + engine-truth cross-check + file-or-skip decision in one pass instead of one-by-one discussion.

## When to invoke

- User pastes feedback items as JSON (recognizable by `feedback_id`, `coaching_text_flagged`, `context.component` keys)
- User types `/triage-feedback`
- User asks "what should we do with these flags?" with a feedback batch attached

Do NOT invoke for a single feedback item — that's faster as direct discussion.

## Required input

- A JSON list (or paste of items) following the chessguru feedback schema. At minimum each item should have: `feedback_id`, `issue`, `coaching_text_flagged`, `position.fen`, `position.move_san`, `position.move_number`, `position.cp_loss`, `context.game_id`, `context.component`, `context.concept_id`.

## The coverage rule (read first)

Every feedback_id in the input must appear in the final per-item accounting table. Mohit has caught me dropping items silently when running this skill in the past — the pattern was "I'd process the interesting ones and let the rest blur into a pattern summary." That's the failure this skill exists to prevent.

The rule, in one sentence: **N items in → N rows in the output table → 0 missed**. No exceptions. If a feedback_id ends up being uninteresting/off-topic/redundant, it still gets a row — the row just says "dismissed" with a reason. Silent drops are forbidden.

Per `[[feedback_complete_every_item_on_overnight_lists]]`.

## Steps

0. **Enumerate the roster (MANDATORY — do this first).** List every `feedback_id` in the input as a numbered roster. This is the fixed set of items to account for. Display it back to Mohit as the first thing in the response:

   ```
   ROSTER — N items received:
     1. fb_3efccdbbf15e
     2. fb_3d530eea5dd9
     ...
     N. fb_79c33cd39b67
   ```

   Do not skip this step even for batches of 2. The roster IS the coverage contract.

1. **Parse and group.** For each item, extract: game_id, move_number, played SAN, cp_loss, the flagged caption text, the user's `issue` question, the `concept_id` (`narrative`, `not_helpful_flag`, etc.), and the `severity`.

2. **First-pass categorize each item.** Use these classes:

   | Class | Pattern |
   |---|---|
   | A. Silent-on-routine | `concept_id=not_helpful_flag` + low cp_loss + issue says "silent" / "no comment" |
   | B. Wrong-reasoning | `concept_id=narrative` + issue questions the diagnosis ("why?" / "is this the right reason?") |
   | C. Duplicate caption | Same `coaching_text_flagged` across two or more positions in the batch |
   | D. Missing teaching value | `concept_id=narrative` + caption is terse ("X is mistake, Y better.") without a principle |
   | E. Confabulation | Caption mentions a piece or move that isn't on the board (rare; needs engine cross-check) |
   | F. Off-topic / process | Feedback about UI bugs, performance, etc. — not caption content. |

   Multiple classes can apply to one item. Note which fire for each.

3. **Engine-truth cross-check.** For each unique `game_id`, invoke `/probe-game {game_id}` once to get the top cp_loss moves + the engine view of each flagged position. Use that to confirm class B/E classifications. Specifically:

   - Class B: does the engine's `best_move` match what the caption recommended? Does the user's intuition about the "real" mistake hold up against `cp_loss`?
   - Class E: do the piece names / moves mentioned in the caption actually exist in the position?

4. **Cross-reference CAPTION_BACKLOG.md.** For each item, check if it matches an existing filed backlog item. Use [CAPTION_BACKLOG.md](../../CAPTION_BACKLOG.md) — items 1-4 cover sac-aware extensions, "why played wrong" (now shipped), marginal-cpl in losing, long-range central control. If an item matches an existing entry, note "already filed under item N" — don't propose re-filing.

5. **Recommendation per item.** One of:

   - **Already shipped** — solved by recent work (e.g. failure-mode promotion 03b84eb8 covers Class D items where the played move had concrete failure). Mark resolved with note.
   - **File against CAPTION_BACKLOG #N** — concrete pattern, has memory entry, ≥2 examples now exist.
   - **Need ≥1 more example** — promising pattern but only one instance; file with a "looking for second" note.
   - **Investigate** — needs deeper look (e.g. confabulation that the engine cross-check flagged).
   - **No action** — off-topic, dupe of already-resolved, or pebble-not-rock.

6. **Pattern table (the existing output)** of items with their class, engine-truth verdict, and recommendation. Cluster by class so patterns are visible. Then 2-3 line summary of "the actual signal" — what these flags collectively tell us.

6.5. **Fix Quality Gate (MANDATORY for any item recommending a fix).** Added 2026-06-06 after Mohit pointed out that the skill produces "Actioned" stamps without judging whether the proposed fix is actually good. Three dimensions; an item must PASS all three to keep "Actioned" status. Any FAIL demotes to "Investigating" with the failure reason recorded.

   **Dimension 1 — Generalization confidence.** Does the proposed fix work for ALL positions/geometries where this caption fires, or only the specific board Parth flagged? Rate as:
   - **HIGH** — fix targets the template / detector branch directly; I've confirmed (grep, predicate read) that no other positions break
   - **MEDIUM** — fix is plausibly general but I haven't verified against all firing positions; would need a snapshot probe before shipping
   - **LOW** — fix only solves the flagged board; fixing it here would create regressions elsewhere. This is a position-specific patch, not a real fix.

   For each HIGH/MEDIUM rating, state in one line WHY confidence is at that level ("HIGH — change is in the template constructor, applies to all R12 fires" / "MEDIUM — need to grep for other call sites").

   **Dimension 2 — Language accessibility (1200 audience).** Apply [[caption_voice_avoid_chess_jargon]] Reading B (updated 2026-06-06):
   - PASS if standard chess concept words name something precisely (`zwischenzug`, `fianchetto`, `prophylaxis`, `pin`, `fork`, `outpost`, `opposition`, etc. all fine)
   - FAIL if jargon is decoration when a concrete square/piece would teach more
   - FAIL if made-up coach compound when a standard chess word exists (`aligned pieces` → use `battery`)
   - FAIL if sub-cultural shorthand (`ply`, `book`, `en prise`)

   **Dimension 3 — Teaching value (not principle-bank filler).** Per [[principle_bank_is_filler]]:
   - **REAL** — the fix teaches something position-specific the user can apply ("Qe2 abandons defense of d4 pawn" — concrete cause and effect)
   - **FILLER** — the fix appends a generic principle that reads like teaching but isn't ("fix your worst piece first" / "develop with a follow-up") — no position-specific insight, no failure mode named, no alternative promoted with rationale

   FILLER demotes to "Investigating" with note: needs predicate work to surface the real failure mode + concrete alternative.

   **Format the assessment as a short block per fixed item, BEFORE Step 7's table:**

   ```
   FIX QUALITY — item N (fb_xxx):
     Generalization: HIGH / MEDIUM / LOW — <one line why>
     Language:       PASS / FAIL (which dimension violated)
     Teaching:       REAL / FILLER — <one line why>
     Verdict:        Actioned (3/3 pass) OR Investigating (gate N failed)
   ```

   Dismissed and Already-shipped items SKIP this step (no fix is being proposed).

7. **Per-item accounting table (MANDATORY — coverage gate).** After the pattern table, render a flat list with one row per `feedback_id` from the Step 0 roster. Every row has these columns:

   | # | feedback_id | game m# played | class | recommendation | gen | lang | teach | status |
   |---|---|---|---|---|---|---|---|---|

   The three middle-right columns (`gen` / `lang` / `teach`) come from Step 6.5. For Dismissed/Already-shipped items they're "n/a".

   `status` is one of:
   - **Actioned** — filed against a CAPTION_BACKLOG item / shipped a fix / opened a new backlog entry. Include the link.
   - **Filed-for-second** — promising pattern; one of two needed; noted in the relevant backlog item.
   - **Already-shipped** — solved by prior work; cite the commit / shipped scope.
   - **Investigating** — needs deeper engine cross-check or codebase dive that doesn't fit this triage pass. Open a new line in PROGRESS_BACKLOG.md / CAPTION_BACKLOG.md.
   - **Dismissed (reason)** — off-topic / pebble-not-rock / dupe-of-already-resolved. Reason must be one of those three, NOT "didn't seem important."

   **Coverage gate: row count must equal the roster count.** Before submitting the response, count rows. If it doesn't match the roster size, GO BACK and find the missing item(s). The triage isn't done until every feedback_id has a row.

   Below the table, state explicitly: `Coverage: N/N items accounted for.` This sentence is the contract.

## What NOT to do

- **Never** submit the response with `Coverage: M/N` where M < N. That's the failure mode this skill exists to prevent.
- **Never** collapse multiple items into a single row of the per-item table. Two items that fall under the same pattern still get two rows in the per-item table — they can both point to the same CAPTION_BACKLOG entry, but each row exists.
- Don't propose fixes inline. This is triage, not implementation. Each "file under item N" becomes a separate design discussion.
- Don't run `/probe-game` more than once per unique `game_id` — re-running on the same game is wasted docker exec.
- Don't categorize items as "duplicate" unless the `coaching_text_flagged` strings match VERBATIM. Similar-sounding captions on different positions aren't duplicates; they're patterns.
- Don't trust the user's `issue` description as ground truth. The user might say "this is wrong because of fork" when the actual engine truth is something else. Confirm against `/probe-game` before promoting a class B finding.

## Notes

- [feedback_caption_filed_for_future.md] — the memory item explaining the "≥2 examples before designing" rule. Triage produces those examples; don't pre-build.
- [feedback_fix_framing_not_detection.md] — if an item suggests removing a detector, push back: the right fix is rewriting the caption template, not deleting the trigger.
- Off-topic items (Class F): drop them, don't add to caption backlog. They belong in a different queue (frontend bug tracker / perf monitoring).
