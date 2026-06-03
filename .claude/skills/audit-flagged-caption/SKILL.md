---
name: audit-flagged-caption
description: Audit a SINGLE flagged caption against the actual chess position. Forces a structured walk of the origin square + destination square + opponent's response candidates so discovered attacks, x-rays, zwischenzug refutations, and unscreened pieces never get missed. Trigger when the user pastes one feedback_id with a complaint about caption correctness, OR types /audit-flagged-caption.
---

# Audit a flagged caption

Built 2026-06-03 after Claude hallucinated a verdict on `fb_3280cebef2e5` (FEN `1kr3r1/1p3p1p/p5b1/6Q1/8/2P5/PP4PP/2K1R2R b - - 2 25`, move 25...Be4). The bishop on g6 was screening Qg5 from Rg8. When the bishop left, the discovered attack opened — the caption said "Be4 loses to Qf4+" (correct, the zwischenzug saves the queen AND keeps Re1 attacking the bishop). Claude said the caption was wrong because the bishop "just hangs to Rxe4" — but Rxe4 loses to Rxg5 winning the queen, so it's white that's wrong without the in-between.

The miss was procedural: walked the destination square, never walked the **origin** square. This skill enforces both.

## When to invoke

- User pastes one feedback item (one `feedback_id`) with a complaint about caption correctness — usually a markdown block with `What was shown to the user` + `User's complaint`.
- User asks "is this caption right" / "did the engine actually see X here" / "walk this position"
- User types `/audit-flagged-caption`

Do NOT invoke for:
- Batches of feedback — use `/triage-feedback` instead.
- UI bugs about *where* the caption shows — that's frontend, not caption correctness.
- "Rewrite this caption" requests — use `/rewrite-for-1200` to draft, `/audit-flagged-caption` to verify it.

## Required input

- FEN string of the position BEFORE the flagged move was played.
- The played move (SAN like `Be4`, plus side-to-move from FEN).
- The caption text shown to the user.
- The user's complaint (what they think is wrong).

Optional but useful: engine `cp_loss`, `eval_before`, `eval_after`, `best_move`. Sanity-check against the analysis below.

## Steps

Work through ALL six. Skipping any one is how the Be4 miss happened. The single biggest failure mode is doing step 3 (destination square) and skipping step 2 (origin square).

### 1. Build the position from FEN

List every piece by color. Put them in a clean table:

```
White: Kc1, Qg5, Re1, Rh1, Pa2 Pb2 Pc3 Pg2 Ph2
Black: Kb8, Rc8, Rg8, Bg6, Pa6 Pb7 Pf7 Ph7
```

Material: total each side. If white has Q+2R and black has 2R+B, white is up Q-for-B ≈ +6. Match this against `eval_before` to sanity-check you read the FEN right.

### 2. Walk the ORIGIN square (the key step Claude skipped on the Be4 case)

The moved piece was sitting on its origin square. When it leaves, **whatever it was screening is now exposed**. List every ray that passes through the origin square:

- N / S (file)
- E / W (rank)
- NE / NW / SE / SW (four diagonals)

For each of the 8 rays, walk it from the origin outward in both directions. Note every piece on the ray, both colors. **The pattern you're looking for: a friendly piece (yours, of the moved color) on one side, an enemy piece on the other.** That's a discovered attack — the moved piece was the screen, and removing it opens the line.

On the Be4 case, walking g6 along the g-file gives: Rg8 (black, north) — Qg5 (white, south). Removing Bg6 ⇒ Rg8 attacks Qg5. **Discovered attack on the queen.** That's the whole story of why Be4 isn't a simple piece-hang.

Specific patterns to flag:
- **Discovered check** — same as discovered attack but enemy piece is the king.
- **X-ray / skewer** — enemy piece in front, more-valuable enemy piece behind on the same ray.
- **Pin removal** — moved piece was pinned; the move is illegal OR the move releases the pin.

### 3. Walk the DESTINATION square

Standard hanging-piece check:

- Who attacks the destination square (list pieces by color).
- Who defends it (list pieces of the moved color).
- If `attackers - defenders > 0` and attacker value ≤ moved piece value, the piece hangs.

This is the easy half. Don't skip it — but don't STOP at it either.

### 4. Walk what the moved piece NOW attacks

From its new square: 8 rays, plus knight jumps if it's a knight, plus pawn diagonals if it's a pawn.

- Does it now attack a higher-value enemy piece? (Threat.)
- Does it deliver check or threaten to? (Forcing.)
- Does it create a double attack / fork together with another friendly piece?

### 5. Enumerate the opponent's response candidates IN PRIORITY ORDER

This is where zwischenzug refutations get found. The order matters:

1. **Checks** — most forcing. List every check the opponent has, even if it looks dumb. Especially check moves that **also solve another problem** (save a hanging piece, escape a discovered attack, win material elsewhere).
2. **Captures** — list every capture, ordered by victim value.
3. **Threats / quiet moves** — moves that threaten mate or material on the next ply.

For each candidate, ask: "does this move solve the problem the played move just created?" The Be4 case: white's queen is attacked (problem). Qf4+ is a check (highest priority candidate) that moves the queen AWAY from the attack AND gives check, forcing black to deal with the king before recapturing. **Two birds, one stone — the zwischenzug.**

If you find ANY check the opponent has, especially one that escapes a discovery, consider it before saying "the move just hangs the piece."

### 6. Reconcile with engine truth

You have `cp_loss`. Compute the rough material balance change you expect from your analysis:

- If you concluded the move hangs a bishop (≈300cp) but `cp_loss` is 145, **you missed something**. Either the recapture costs the winner material (zwischenzug needed), the position was already so winning that material doesn't shift much, or there's a defense you didn't see.
- If you concluded the move is fine but `cp_loss` is 200+, **you missed something on the opponent's side** — walk step 5 again.

The engine doesn't lie. When your analysis doesn't match `cp_loss`, the engine is right and you're wrong. Go find what you missed before writing the verdict.

## Output format

End with one of four verdicts:

- **Caption correct** — the engine's refutation matches the caption's claim. User's complaint is based on miscalculation. Recommend: mark feedback `dismissed`, no override.
- **Caption framing wrong** — the engine eval is right, the caption diagnosis is wrong (e.g. claims "Qf4+" when the cleaner refutation is Rxe4). Recommend: propose an override caption and (separately) consider whether a detector path needs adjusting. See [feedback_fix_framing_not_detection.md] — fix the template, not the trigger.
- **Caption hallucinated** — caption mentions a piece, square, or move that doesn't exist in the position. Recommend: file under `/triage-feedback` Class E, investigate the caption generator.
- **Unclear — need probe** — engine eval and your walk disagree by a wide margin. Run `/probe-game {game_id} --move N` for the full engine PV before verdict.

Show your work: a short paragraph for each of steps 2, 3, 4, 5 (especially 2). One sentence per step is enough — the goal is to PROVE you walked it, not to write an essay.

## What NOT to do

- **Don't skip step 2.** This was the Be4 miss. Walking the destination square ≠ walking the position. Every flagged caption MUST get an origin-square ray-walk.
- **Don't trust the user's complaint as ground truth.** Users miscalculate. The user on the Be4 case said "Be4 already hangs, right?" — they were wrong; the caption was right. Confirm against the engine before writing a verdict.
- **Don't propose an override caption when the caption is correct.** That's how good captions get rewritten into worse ones. The verdict should be `dismissed` when the caption holds.
- **Don't run engine probes on every audit.** If the FEN walk gives a confident verdict and matches `cp_loss`, ship it. Use `/probe-game` only when your walk and the engine disagree (Step 6 mismatch).
- **Don't audit batches.** This skill is ONE feedback item, ONE position. For batches use `/triage-feedback`.

## Notes

- The cognitive pattern this skill exists to fix: **piece-on-square thinking instead of line thinking**. Pieces don't just attack squares — they screen lines. Removing a screen is half of all tactics.
- Three pieces on the same rank/file/diagonal of two different colors = always check for discovered attack. Always.
- Pair with [/rewrite-for-1200] when the verdict is "caption framing wrong" — that skill drafts the override, this skill verifies the position truth.
- Pair with [/author-r12-predicate] when the verdict suggests a missing failure-mode predicate that should fire on this pattern more broadly.
