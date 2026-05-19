---
name: mobile-app-critical
description: HARD direction 2026-05-19. Mobile app is critical for ChessGuru's success in Indian market — web-only paid subscriptions hit a conversion ceiling. Proposed path: TWA wrap on Play Store first (week 1) → React Native rewrite of high-touch surfaces (weeks 2-9) → native integrations (weeks 10-12).
metadata:
  type: project
---

**HARD direction (Mohit 2026-05-19):** "chess guru on web would fail if we don't release a mobile app." Mobile is NOT a nice-to-have or a Phase-N item. It's existential for the product.

**Why:** Indian market reality — ₹199/month subscriptions have weaker conversion on web. Play Store presence is a major trust + discoverability signal. Mobile-first usage patterns (chess between meetings, on commute) need native UX (real touch, no hover, install icon on home screen, push notifications that survive app-kill, native payment integration for GPay-dominant India).

**Proposed sequenced path (locked 2026-05-19):**

**Sprint 0 — TWA wrap (~1 week)**
Trusted Web Activity wraps the existing React PWA. Result: real Play Store listing, install flow, app icon, basic notifications. Users get a mobile app in days. Buys real mobile-usage data before committing to bigger investment.

**Sprint 1 — React Native rewrite of high-touch surfaces (~6-8 weeks)**
Rewrite ONLY the surfaces where UX quality matters most:
- Play with Coach (board interactions, drag-pieces, touch zones)
- Lab review (multi-move-line replay animations)
- /openings + Your Repertoire
Lower-touch surfaces stay as WebView (Settings, Import, Progress, Reflect). Avoid 100% rewrite trap.

**Sprint 2 — Native integrations (~2-3 weeks)**
- Push notifications surviving app-kill (critical for the daily-ritual product)
- GPay / UPI payment integration (critical for ₹199 monthly conversion)
- Biometric auth

**Total: 9-12 weeks of focused mobile work.** Users on Play Store from week 2.

**Why NOT full native (Kotlin + Swift) from day 1:** 4-6 months before one user benefits. The TWA-first path gets Indian market signal in 1 week at low cost. Native rewrite triggers should be measured (>50% daily-active on mobile, >20% iOS share, etc.).

**Why NOT PWA-only forever:** I (Claude) was wrong about this on the first pass. Indian users distrust PWAs more than US users. Play Store ranking favors native. The ₹199 subscription friction is low enough that mobile-app polish is a meaningful retention lever.

**Companion principles:** [[product-vision]], [[drillable-adaptive-coach]] (the drill UX needs to feel native on mobile — touch-friendly affordances), [[no-gamification]].
