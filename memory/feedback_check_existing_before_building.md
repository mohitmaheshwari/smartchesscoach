---
name: Always audit existing code before building new
description: Before writing any new service, helper, or abstraction, grep the codebase for similar existing implementations. Never start fresh when something similar exists.
type: feedback
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
Before building any new helper/service/abstraction, do a grep pass for similar functionality in the existing codebase. Reuse or extend what's there rather than starting fresh.

**Why:** The user has multiple times caught me building parallel systems when the same thing already existed — rating bands (3 existing implementations when I was about to add a 4th), focus systems (4 existing systems when I was extending the behavior), etc. It wastes their time and adds technical debt. They've explicitly asked me to "always confirm what we have" before building.

**How to apply:**
- Before writing a new function that sounds like it could already exist (`get_rating_band`, `compute_X`, `is_Y`, etc.), run `grep -rn "def.*<name>\|<name>\s*="` across the codebase.
- Before writing a new dict/constant (`RATING_BANDS`, `PATTERN_MAP`, `WEAKNESS_LABELS`), grep for the constant name first.
- If multiple implementations exist, check CLAUDE.md or the most-imported version to pick the canonical one.
- Tell the user up front: "I see X already exists in `file:line` — I'll use that" rather than silently building fresh.
- Only build new when no existing implementation can be extended reasonably.
