---
name: Concept + consequence rule for chess captions
description: Chess concept words (outpost, luft, fianchetto) are good pedagogy when paired with a verifiable concrete consequence. The failure mode is captions with neither — empty verbs like "repositions / activates / tests".
type: feedback
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
A 1200-rated player who's working on improvement *wants* to learn chess vocabulary. Introducing concept words ("outpost", "luft", "back rank", "minority attack") is how players grow. The product vision is teaching, so concept words are part of the toolkit — not banned.

**The rule:** Every caption must EITHER pair the concept with a concrete consequence verifiable on the board, OR not use the concept at all. Never use a chess term without saying what it means in this position.

**Good pedagogy — concept + concrete consequence:**
  - "Plants the knight on d5 — secure outpost. No enemy pawn can chase it." (outpost + verifiable: check the board, no enemy pawn on c-file or e-file ahead)
  - "Pawn to h3 — gives the king luft. No back-rank surprises now." (luft + verifiable: king now has h2 to escape)
  - "Heavy piece to e7 — eyes their back rank. Their king has no luft." (re-uses concept after introducing it)
  - "Bishop to g2 — fianchetto. From here it sweeps the long diagonal toward Black's queenside rook." (concept + concrete piece named on the diagonal)

**The actual failure mode — neither concept nor concrete:**
  - ❌ "Knight to g4 — repositions." (middlegame:piece_maneuver, ~2,777 hits — empty verb)
  - ❌ "Engine prefers c6 over h5 — different pawn, different idea." (no concept, no concrete)
  - ❌ "Pawn to b3. Holds the structure." (vague)

**Borderline — concept used but consequence too vague:**
  - 🟡 "Minority attack — pushing a3 to create weaknesses on their queenside." → tighten to "weakening their c6 pawn" or similar concrete target
  - 🟡 "Central pawn push to f3. Tests their pawn structure." → "tests" is empty; replace with concrete intent or strip
  - 🟡 "Fianchetto — bishop to g2. Eyes the a1-h8 diagonal." → name what's on the diagonal

**How to apply:**
  - When reviewing a caption: spot the chess concept (if any). Ask: "does the rest of the sentence let a 1200 verify the concept on this specific board?" If no, rewrite or remove.
  - Empty verbs ("repositions", "activates", "tests", "explores", "coordinates") with no concrete object are never acceptable — those go to review_needed.
  - Concept words on their own ("This is a fianchetto.") are not enough. Always pair.
  - When the concrete consequence isn't mechanically derivable in the current detector, prefer review_needed over a hollow concept caption.
