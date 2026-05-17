---
name: Don't fragment surfaces
description: When adding a feature that overlaps an existing page/endpoint, extend it; never add a parallel route/service that does the same thing differently
type: feedback
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
Product surfaces fragment when new features get added as parallel routes instead of extensions of existing ones. Training routes were the canonical example: `/training/pattern/:pattern`, `/training/prescribed?weakness=X`, and `/training` all solved the same user problem ("show me puzzles for a weakness") with different URL shapes and different backend endpoints — classic drift.

**Why:** Mohit explicitly called this out: *"we start clean and you then fuck it up, why?"* This erodes trust in the codebase and forces periodic consolidation passes.

**How to apply:**
- Before creating a new route or backend endpoint, grep for existing ones doing the same job. If one exists, extend it (add a query param, a mode flag, a discriminator) rather than adding a parallel.
- When consolidating, follow the `verify before deleting` rule — grep all callers/links before removing; redirect for one release cycle when the route was public.
- If a new feature REQUIRES a new surface, be explicit in the rationale: what does the existing surface fail to express?
- Especially watch out in `routes/training.py` + `routes/training_advanced.py` split, and anywhere that has multiple endpoints serving puzzles, multiple endpoints serving coaching, etc.
