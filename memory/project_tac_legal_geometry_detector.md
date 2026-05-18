---
name: tac-legal-geometry-detector
description: Phase-6.5 detector backlog — TAC_LEGAL_PATTERN encoded as 5 geometric guards, not as historical move-tree. First detector built on the geometric-recognition design law.
metadata:
  type: project
---

Phase-6.5 detector backlog (post-Phase-6 cross-opening themes [[v5-lazy-generation]]). First detector built on the new geometric-recognition design law [[geometric-recognition-over-named-sequences]].

**Detector: TAC_LEGAL_PATTERN** — fires regardless of opening, color, or specific squares.

**Five geometric guards (ALL must be present to fire):**
1. **Pinned knight** — knight pinned to queen (or rook) along a diagonal by an enemy bishop. Relative pin, not absolute.
2. **Forcing jump available** — the pinned knight has a capture/fork/check on the now-vacated diagonal (typically capturing a central pawn like e4/e5/d4/d5 that also opens the queen's diagonal back at the pinning bishop).
3. **Bishop pressure on f2/f7** — pinned side has a bishop (any square: Bc4/Bc5/Bb4/Bf4 etc.) on a diagonal **already aimed at the f2 or f7 square**. Not "must be on g4/g5" — must STARE at f2/f7.
4. **Enemy king uncastled** — pinner's king still on e1/e8.
5. **Forcing continuation after queen-grab** — verifier-stage probe: if pinner plays the greedy queen-capture, pinned side has a forcing sequence (check → check → mate/material) within 3 plies. This separates real Légal geometry from cosmetic look-alikes.

**Why:** Mohit 2026-05-18: "transferable geometry awareness, not move-tree memorization." The geometric compression — "if your bishop already stares at f2/f7, a pinned knight may not really be pinned" — generalizes across openings, colors, and partial versions. Move-tree memorization does not.

**How to apply:**
- Detector lives in caption_facts.py alongside the Phase-6 cross-opening themes (OP_BISHOP_TRADE_DOUBLES_PAWN, OP_F2_F7_STRIKE, OP_TRAPPED_KNIGHT).
- Caption format: name the pattern (Légal) + state the geometry, NOT the historical move sequence. See [[caption-voice]] and [[1200-test]].
- Per-fire audit MUST verify all 5 guards from FEN, then run the 3-ply forcing-continuation probe in code (not LLM) per [[per-fire-audit-pattern]] and [[chess-content-verification]].
- Bump V5_COACHING_VERSION on ship; update audit_legal_pattern.py with 0-mismatch on prod corpus.

**Sister detectors to plan after TAC_LEGAL_PATTERN:**
- TAC_BODEN_PATTERN (two bishops crossfire on castled king)
- TAC_SMOTHERED_PATTERN (knight + queen vs corner king with own pieces blocking)
- TAC_GRECO_PATTERN (Bxh7+ classical greek-gift geometry)
- TAC_FRIED_LIVER_PATTERN (Nxf7 fork against early ...Nxd5 in Italian)

All encoded as geometric guards, never as move sequences.

**Source position confirming the spec:** sinzaizer1 game (game_id `6cd530bf-71aa-48ef-963b-a882d2288797`, played 2026-05-18), Mohit as white's 6.Bg5 in Petroff 3.d3 Bc5 4.Nxe5 line. Stockfish depth-24 verified: 6.Bg5 Nxe4! 7.Bxd8?? Bxf2+ 8.Ke2 Bg4# (mate +2). Opponent missed Nxe4! and played Qd6 instead, returning ~5 pawns of advantage. This game becomes the canonical first-fire example for the detector.

**Corpus validation 2026-05-18 (scan_legal_geometry.py vs prod, 4433 games):**
- Geometric-only (guards 1-4): 128 games / 267 fires (~6% noise).
- Stockfish-approved (jump in engine top-3): 16 fires.
- Full 5-guard (forcing-continuation also validated): **10 fires across 9 unique games**.
- Signal-to-noise: bare geometry too permissive — the 3-ply forcing probe in guard 5 is essential; cuts false-positive rate from 96% to ~4%.
- Structural cluster: 7/10 fires share the Italian/Petroff pattern (white Nf3 pinned by ...Bg4 or ...Bh5, white's Bc4 already attacking f7). The remaining 3 are color-mirrored or different opening shapes — proof the detector is opening-agnostic when encoded as geometry not move-tree.
- Confirmed game IDs (canonical examples for the principle's clickable-rule [[clickable-rule-names]] page): 5e915c5a, ac990fa3, eab71be4, 4244e8f3, bf5227ed (×2), 2085fc68, 3652174f, 55883d22, 6cd530bf (sinzaizer1).

**Ship dependency:** per [[worker-side-detector-migration]], TAC_LEGAL_PATTERN should be the **first detector built directly into the worker** (skip the lazy on-read stage). The forcing-continuation probe is too expensive for read-time.
