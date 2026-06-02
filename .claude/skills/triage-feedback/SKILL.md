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

## Steps

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

6. **Output: a tight table** of items with their class, engine-truth verdict, and recommendation. Cluster by class so patterns are visible. Then 2-3 line summary of "the actual signal" — what these flags collectively tell us.

## What NOT to do

- Don't propose fixes inline. This is triage, not implementation. Each "file under item N" becomes a separate design discussion.
- Don't run `/probe-game` more than once per unique `game_id` — re-running on the same game is wasted docker exec.
- Don't categorize items as "duplicate" unless the `coaching_text_flagged` strings match VERBATIM. Similar-sounding captions on different positions aren't duplicates; they're patterns.
- Don't trust the user's `issue` description as ground truth. The user might say "this is wrong because of fork" when the actual engine truth is something else. Confirm against `/probe-game` before promoting a class B finding.

## Notes

- [feedback_caption_filed_for_future.md] — the memory item explaining the "≥2 examples before designing" rule. Triage produces those examples; don't pre-build.
- [feedback_fix_framing_not_detection.md] — if an item suggests removing a detector, push back: the right fix is rewriting the caption template, not deleting the trigger.
- Off-topic items (Class F): drop them, don't add to caption backlog. They belong in a different queue (frontend bug tracker / perf monitoring).
