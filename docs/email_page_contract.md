# Email → Page Contract

**Rule.** Every coaching email's CTA must link to a page that **delivers exactly what the email promised**. No "the email says 3 specific moments, the link goes to a generic dashboard."

This document is the standing process that prevents that. It exists because we shipped the Shobhit and Mohit re-engagement emails on 2026-06-29 with a CTA promise ("3 specific moments from your games this week") and the original link went to `/lab` — a generic page that doesn't deliver three specific moments. That's a credibility crater the first time a user clicks. We caught it before it happened to a real user, but we won't always catch it. So now there's a process.

## How it works

1. **Single source of truth**: [`backend/services/moments_topic_registry.py`](../backend/services/moments_topic_registry.py) holds `TOPICS` — every topic an email is allowed to CTA into.

2. **One page renders all topics**: [`frontend/src/pages/PersonalMoments.jsx`](../frontend/src/pages/PersonalMoments.jsx) at route `/coach/moments/:topic` consumes `GET /api/coach/personal-moments/{topic}`. The endpoint pulls the topic definition from the registry and runs the topic's filter against the logged-in user's recent games.

3. **Email scripts declare `CTA_TOPIC`**: every script in `backend/scripts/send_*_reengagement.py` MUST set `CTA_TOPIC = "..."` near the top and uses that string in the email body URL. The script's `main_async()` validates `CTA_TOPIC in list_topics()` before sending. If you typo the topic, or write a script that references a topic that hasn't been built yet, **the script refuses to run**.

## Adding a new topic — the canonical 4-step

| Step | What | Where |
|---|---|---|
| 1 | Write a `_filter_<topic>(db, user_id, limit=3)` async fn that returns up to 3 moments | `backend/services/moments_topic_registry.py` |
| 2 | Add an entry to `TOPICS` dict — key, label, subtitle, filter, explainer | same file |
| 3 | Write your email script with `CTA_TOPIC = "<your new topic>"` and the URL `https://chessguru.ai/coach/moments/<your new topic>` | `backend/scripts/send_*_reengagement.py` |
| 4 | Add a one-liner to this doc under "Active topics" so the registry stays discoverable | `docs/email_page_contract.md` (this file) |

The frontend page auto-renders any new topic. No JS changes needed for new topics.

## Active topics

| Key | Used by email | What it shows |
|---|---|---|
| `piece_safety` | `send_shobhit_reengagement.py` | 3 winning positions where the user hung a piece (200+ cp loss with eval_before ≥ +0.5) |
| `long_game_conversion` | `send_mohit_reengagement.py` | 3 moments past move 25 from games the user lost despite having a ≥ +0.3 eval before |

## What NOT to do

- ❌ Don't write an email body that links to `/lab`, `/home`, or any other generic page when the email promises specific content. Either deliver the specific content (via a registered topic) or change the promise.
- ❌ Don't add a topic to the registry without a filter function. The script will still validate it but the page will crash on load.
- ❌ Don't change a topic's `key` after emails have been sent. Old URLs become broken. Add a new key instead.

## When the page returns 0 moments

The page handles this gracefully — shows "Good news, no matching moments — keep playing." That's an honest answer when the filter genuinely finds nothing.

## Testing a new topic locally

```bash
# Backend
curl -s "http://localhost:8002/api/coach/personal-moments/piece_safety" \
  -H "Cookie: dev_mode=true" | jq .

# Frontend
# Open http://localhost:3000/coach/moments/piece_safety
```
