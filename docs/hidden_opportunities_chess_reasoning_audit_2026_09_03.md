# Hidden Opportunities — blinded chess-reasoning audit

Date: 2026-09-03

Status: research complete; no product code changed; no production writes; no fresh engine runs.

## Executive verdict

The product idea is real, but the current deterministic explanation layer is not safe enough to power it.

The strongest conclusion is not that ChessGuru needs more Stockfish. It needs a **differential chess-reasoning layer** that proves why an unplayed branch is educationally different from the played branch.

The current PV tactical analyzer has strong raw recall on obvious tactics, but weak causal precision. It often finds a true fact somewhere in the best line without proving that the fact is why the best move was better. That creates fluent but wrong coaching such as:

- describing a pawn win that occurs in both branches;
- naming an incidental relative pin instead of the move's real point;
- reducing a promotion race to “wins a pawn”;
- saying “the king falls next”;
- crashing on one valid position because `forker_value` is unbound.

This is fixable deterministically. The architecture must compare both branches before it is allowed to speak.

## Evidence design

The packet contains exactly 100 unique positions selected deterministically from stored production analysis:

- 25 from each rating band: 600–899, 900–1199, 1200–1499, 1500–1999;
- within every band: 5 opening, 15 middlegame, 5 endgame positions;
- within every phase: coverage of five stored `cp_loss` ranges from 75 to 1000+;
- FEN, played move, best move, and four stored plies after each move;
- no user IDs, game IDs, names, usernames, emails, dates, credentials, or source-game linkage.

All 100 FENs and all 200 branches replay legally when the named candidate move is pushed before its stored continuation.

This is a **stratified architecture-audit sample**, not a production incidence estimate. Equal severity buckets deliberately over-represent rare large swings.

## Blind chess gold

The positions were classified before current detector output was inspected.

| Gold disposition | Count | Meaning |
| --- | ---: | --- |
| Hidden opportunity | 24 | A memorable alternative with a concrete mechanism and payoff visible in the stored line |
| Caption only | 35 | A valid correction or principle, but not a cinematic “you missed something beautiful” moment |
| Insufficient evidence | 41 | Four stored plies do not support a truthful causal explanation |

The 24 real opportunities are diverse. They include forks, absolute pins, loose rooks and queens, a back-rank raid, a decoy rook sacrifice, two zwischenzugs, a clearance attack, removal of a defender, correct-rook geometry, a promotion race, key-square play, and move-order combinations.

That diversity is important: one detector per named motif will become another brittle library. The correct design is a small set of composable board-event primitives that can prove many named ideas.

## Current runtime comparison

### PV tactical analyzer

| Measurement | Result |
| --- | ---: |
| Gold hidden opportunities found | 22 / 24 (91.7% raw recall) |
| Total non-null explanations | 47 / 100 |
| Precision if every explanation became an opportunity card | 22 / 47 (46.8%) |
| Runtime crashes | 1 / 100 |
| Manually usable exactly as written | 9 / 47 (19.1%) |
| Partial but not ship-ready | 19 / 47 |
| Rejected as false, irrelevant, impossible, or crashing | 20 / 48 assessed events |

The analyzer is therefore useful as a **candidate fact generator**, not as a user-facing narrator or opportunity selector.

### Concept registry

With only the evidence available in the packet, the current concept registry fired on 0 of 100 positions, even with shadow detectors enabled. Some opening and trap detectors require full move history or an opening name, so this is not a claim that every registered detector is broken. It does show that the registry does not currently cover the tactical counterfactual job Hidden Opportunities requires.

### Static geometry

Static geometry was present in:

- 21 of 24 hidden opportunities;
- 24 of 35 caption-only positions;
- 34 of 41 insufficient-evidence positions.

Geometry is abundant and valuable for drawing the board, but presence alone is not evidence that a position deserves an opportunity card. It must be connected to a branch-specific payoff.

## Five examples that define the feature

### 1. A real opening fork

Position `00d2ea0ceda1a2e6ef83`:

> You had a fork hidden on c7. **Nxc7+** checks the king, so Black cannot save the rook on a8. After the king moves, **Nxa8** wins it. The clue to remember: a knight on b5 can jump to c7 with check.

This is not “the engine preferred Nxc7+.” It explains the forcing move, the unavailable defensive tempo, the payoff, and the reusable pattern.

### 2. A rook used as bait

Position `017a76d6a153237ced25`:

> Your rook could be bait: **Rh8+!** forces the king to take it. Then **Qh2+** makes Black block with the queen on h4, where **Qxh4+** wins it. You give a rook to pull the king onto the square your queen needs.

The memorable point is the decoy geometry, not the material total.

### 3. The in-between check

Position `05622e8ee664fa64e0f6`:

> Before taking back on d8, play **f5+!** Moving the pawn clears your rook's line to the king, so White must answer the check. Only then do you play **Rxd8**, winning the bishop with the extra tempo.

This teaches zwischenzug through visible squares and move order.

### 4. Which rook matters

Position `055d9f8521e114e4d995`:

> Both rooks can take the bishop on e3, but only one keeps the promotion covered. **Rdxe3!** leaves the rook on e1 on the first rank. When the g-pawn promotes, **Rxg1** catches the new queen. If the e1-rook moves instead, promotion comes with check.

This is exactly the kind of deterministic chess intelligence generic captions miss: same destination, different origin, different future geometry.

### 5. Clear the file, then collect

Position `0092ee3966f8cb299628`:

> Start with **Bxf5!** If the g-pawn recaptures, the f-file opens for your rook: **Rxf5+**, and after the rook is challenged, **Rxe5** collects the knight. The bishop is not just taking a pawn—it clears the rook's road.

The current analyzer reports only a net material summary and loses the teachable clearance idea.

## Why the current analyzer fails

1. **It analyzes only the best branch.** A fact in the best line is not automatically the reason that line is better. If both branches win the same pawn, “wins a pawn” explains nothing.
2. **It selects incidental geometry.** The first pin, fork, or exposed piece found can outrank the causal mechanism.
3. **It does not require a payoff edge.** A geometrically true pin can be surfaced even when no advantage follows from it.
4. **It treats the king as a deflectable target.** The exposed-defender scan includes kings, producing “the king falls next.”
5. **It compresses transactions, not ideas.** “Wins two pawns net” can hide a clearance, decoy, or removal-of-defender combination.
6. **It has a live scope bug.** `forker_value` is assigned only in the fallback safety branch but read afterward.

The canonical Game Review catches the exception per move and falls back rather than failing the whole review. That contains the crash, but it means a deterministic failure can silently become LLM-authored copy.

## Correct deterministic architecture

### 1. Build two verified branch traces

For both the played move and each candidate move, replay the exact stored line and record board events per ply:

- captures and exchanges;
- checks, forced replies, and mating threats;
- promotions and passed-pawn status;
- newly attacked, newly loose, pinned, overloaded, or trapped pieces;
- opened and closed ranks, files, and diagonals;
- legal mobility and king escape-square changes;
- material and, where already stored, evaluation/result transitions.

### 2. Compute the differential fact

The system may speak only about a fact that is:

- present in the candidate branch;
- absent from the played branch;
- connected to a concrete payoff or result-preserving defense;
- visible within the evidence horizon.

This one rule eliminates the most common current failure: narrating something true in the best line that does not distinguish it from what the player did.

### 3. Prove a causal chain

Represent the idea as a short chain, not a sentence template:

`setup event -> forced response or constrained choice -> payoff event`

Examples:

- `Nxc7+ -> king must answer check -> Nxa8 wins rook`
- `Rh8+ sacrifice -> king displaced -> queen forced onto h4 -> Qxh4 wins queen`
- `f5+ clears rook line -> king must move -> Rxd8 wins bishop`
- `Rdxe3 preserves first-rank rook -> g1=Q -> Rxg1 captures promoted queen`

If any edge is unproved, the opportunity is downgraded to caption-only or silent.

### 4. Use composable proof primitives

The first proof families should be:

- direct loose-target capture;
- fork / check-and-attack;
- absolute and relative pin with payoff;
- skewer and x-ray with payoff;
- discovered attack and clearance;
- removal, overload, and deflection of a defender;
- zwischenzug and forcing move-order change;
- decoy and attraction;
- promotion race, promotion stop, and correct-piece geometry;
- key squares, opposition, and king-path geometry;
- trapped-piece mobility collapse;
- back-rank and mating-net geometry.

These are board transformations. Product-friendly labels such as “rook as bait” or “which rook matters” are rendered afterward.

### 5. Separate three output grades

- **Opportunity-grade:** show in the cinematic Hidden Opportunities surface.
- **Caption-grade:** use as a concise correction in the ordinary move story.
- **Evidence-insufficient:** show no causal claim; never fill the silence with a generic motif.

The audit proves this separation is necessary. Only 24 of 100 deliberately selected mistake positions deserved the full opportunity treatment.

### 6. Keep evidence and wording separate

The engine should return typed facts, squares, pieces, branches, and payoff ply. A deterministic renderer then turns those facts into 600–1500 language. It must never invent a motif from prose.

Suggested contract:

```json
{
  "surface_grade": "opportunity",
  "mechanism": "zwischenzug",
  "setup": {"move": "f5+", "fact": "clears d7-g7 rook line"},
  "constraint": {"kind": "check", "reply_required": true},
  "payoff": {"ply": 3, "move": "Rxd8", "wins": "bishop"},
  "played_branch_difference": "Rxd8 immediately misses the checking tempo",
  "proof": {"all_moves_legal": true, "stored_line": true, "fresh_engine_run": false}
}
```

### 7. Multiple candidates come later, under proof

For current stored games, use only available stored lines and say nothing when four plies are insufficient. Do not silently re-run Stockfish.

For future analyses, store MultiPV once in the normal analysis job. Stockfish proves soundness; the opportunity layer chooses the most teachable branch; Maia may rank which sound move a human at this level is likely to find. Maia must not establish chess truth.

## Product surface

Game Review should remain a flowing story, with at most one to three opportunity moments in a game.

At the exact move:

1. Pause with: “There was something beautiful here.”
2. Let the player try the first move on the board.
3. If needed, give a square-based hint—not the motif name.
4. Animate only to the first payoff, usually two or three player moves.
5. Explain the setup, forced response, and payoff in one short coaching paragraph.
6. Ask one recognition question from deterministic options: “What made this work?”
7. Save the pattern to the player's plan only if it is already a verified personal learning target or recurs later.

This should feel like a coach stopping the replay at the one moment worth remembering, not like another engine line drawer.

## Implementation gates before user exposure

1. Fix the current runtime exception and forbid king-as-falling-target output.
2. Build the branch-difference event model.
3. Distill proof families against this blinded gold; do not hand-author final captions first.
4. Require zero false chess claims on adversarial cases.
5. Measure selection precision separately from motif precision and wording quality.
6. Do not wire a proof family to Opportunity-grade until its reviewed packet passes the existing detector-quality promotion discipline.
7. Re-run this exact packet as a locked regression suite.

## Artifacts

- `backend/data/corpus_snapshots/hidden_opportunities_chess_gold_v1_2026-09-02.json`
- `backend/data/corpus_snapshots/hidden_opportunities_chess_gold_annotations_v1_2026-09-03.json`
- `backend/data/corpus_snapshots/hidden_opportunities_current_runtime_comparison_v1_2026-09-03.json`

