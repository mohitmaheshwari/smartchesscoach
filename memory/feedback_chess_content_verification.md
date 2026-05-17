---
name: Chess content verification — verify the user-facing claim, not the code internal
description: Hard rule. Don't claim any coaching layer is "verified" without running real coaching strings through real positions and confirming every chess claim is true on the board. Born from a trust break in May 2026 — I claimed multiple "verified clean" states (1000-game gap audit, 22/22 geometry rules, mock 100%/100%, voice templates clean) that all measured internal correctness while the product still shipped wrong text to users.
type: feedback
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
When auditing any coaching surface, the audit must verify the **rendered output is factually true about the actual position**, not just that internals are clean.

**Why:** Parth's 117-bug audit (May 2026) landed because every previous "audit" I ran measured internals — detector correctness on canonical FENs (verify_geometry_full), tag classification on 1000 games (gap_audit_1000), template scans for banned voice (pwc_voice_audit), mock-corpus correctness (mock_correctness_audit). NONE of them verified whether a real user opening a real game review would see chess claims that match the actual board. So the product shipped:
  - "Equal trade" on a Rxc3 that allowed mate in 2
  - "Your pawn on f4 is in trouble" when there was no pawn on f4
  - "Played Bg5" when the move was Nc3
  - Petrov's Defense (1.e4 e5 2.Nf3 Nf6) labelled as a mistake with best=Nc6
  - "Knight on e5 gets taken" with no explanation of *why this move caused that*
The user trusted my "verified" claims and the trust broke.

**How to apply:**

1. **Audit at the rendering layer, not the data layer.** Take the actual user-facing string and verify each chess claim against the actual FEN. Not the template. Not the dataclass. The string the user sees.

2. **Every "your X on Y" claim must verify** — does a piece of type X actually sit on square Y in the FEN? If not, the coaching is hallucinating. Same for "their X on Y", "after [move sequence]", "Played [move]".

3. **Every "best is X" claim must verify** — match against engine analysis at sufficient depth (≥ 4 ply, deeper for tactical positions). The engine's pick must agree, OR the audit must explain the disagreement.

4. **Severity must match true tactical state, not just cp_loss.** Forced mates, perpetuals, and stalemate-based draws need separate detection. "Good" / "equal trade" cannot be assigned to a position with a forced mate that the played move walks into.

5. **Use real ground-truth corpora.** Mock data tests detector logic; it does not test correctness on real games. Production audits run on real-game positions or labelled bug reports (like Parth's 117).

6. **When stating "verified," name scope explicitly.** Always: "verified — covered X. Not covered: Y, Z." If I can't name what's not covered, I haven't audited anything. Phrases like "1000 games audited" must say what was audited (gap classifier vs explanation correctness vs anything else).

7. **Shipping or charging is gated on content correctness audits being green** for any surface a paying user will see. No exceptions. If the audit isn't built yet, the surface isn't premium-ready.

**The structural fix:** every coaching surface that emits user-visible chess claims gets a `verify_<surface>_correctness.py` script that runs on real positions and reports per-claim verdicts. Same discipline as `gap_audit` and `verify_geometry_full`, but pointed at the layer where users actually see content.
