---
name: memory-voice-competence-not-history
description: Cross-game memory references must be COMPETENCE-based, not game-history-based. 1500-and-below players don't remember games / opponents / move sequences. The reference should be to their proven competence with a principle, not to a specific past event.
metadata:
  type: feedback
---

Cross-game memory in coach voice must be **competence-based, not history-based**.

**Why:** Mohit correction 2026-05-19. 1500-and-below players literally cannot recall their past games, opponents, or move sequences — even from yesterday. Saying "you missed this Bg5-pin against sinzaizer1 last Tuesday" feels foreign because they don't remember the game existed. Per [[sub1500-memory-anchors]] they remember **named principles + geometric shapes + process habits**, not events. A memory reference framed as "you have a past game where X happened" lands as a database citation, not as coaching. A memory reference framed as "you've shown you know this rule" lands because it speaks to who they ARE as a chess player, not what they DID.

**How to apply:** When the system has data showing a user has encountered a principle before, the voice should NOT reference:
- Specific opponent names ("vs sinzaizer1")
- Specific timestamps ("4 days ago", "earlier today")
- Specific past games ("in your last Italian Game")

The voice SHOULD reference their relationship to the principle:
- ✅ "You've shown you know this rule. Apply it here."
- ✅ "This is the same pin pattern you've executed before — stay consistent."
- ✅ "You've handled this shape correctly before; don't miss it now."
- ✅ "Watch out — this principle has caught you before. Apply it this time."

The information being conveyed is the SAME (the user has history with this principle). The framing is what changes: from "here's a record of when" to "here's evidence of what you know." The latter is competence; the former is a citation.

**Concrete pending fix:** the Phase-2 recall block voice (`services/teaching_recall.py:_build_recall_voice`) currently uses time-references ("earlier today", "4 days ago", "a week ago"). All four templates need rewriting to competence-framing. Pending ship as of 2026-05-19.

Companion: [[sub1500-memory-anchors]] (the underlying principle this corrects to), [[teaching-not-reading]] (voice rules), [[1200-test]] (concreteness without overclaiming history).
