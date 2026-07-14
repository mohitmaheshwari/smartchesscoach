# Activation Scope — the 90-second aha + post-game return emails

*2026-07-14. Signed off by Mohit ("go as per recommendation") after the "people
don't sink in" discussion. Two features, one goal: arrivals reach the personal
aha fast, and their existing chess.com/lichess habit pulls them back.*

## 0. Existing surfaces audit
- Onboarding already links accounts + calls /games/sync + instant-DNA (Onboarding.jsx).
- analysis_worker drains analysis_queue atomically; no priority lane today.
- /game/:id (LabV2 → GameDecryptionV5) already renders decoded moments.
- server.py already runs background schedulers (sync 6h, quick-sync 5m).
- Email: SMTP (Zoho) works; send_* scripts are hand-run, hardcoded users;
  email→page contract requires the CTA to deliver exactly what's promised.
- PostHog funnel events live as of tonight. → EXTEND all of these; nothing parallel.

## 1. What it is
**A. First-loss fast-path:** the moment a new user links their account, ChessGuru
grabs their most recent LOSS, analyzes it ahead of everything else, and drops
the user straight into that decoded game. First session = the product talking
about THEIR game within ~90 seconds.
**B. Post-game digest email:** after the nightly sync analyzes yesterday's games,
each user with something worth saying gets ONE short email — what they dodged,
what leaked, one CTA into that exact decoded moment.

## 2. What the user sees
A: Link account → "Analyzing your last game…" progress → lands on /game/:id with
the worst moment highlighted: "Here's where Saturday's game slipped — Qd7 let
Qxd4 win a knight. You've done this in 4 of your last 10 games."
B (email): Subject: "Yesterday's games: your fork radar worked ✓"
Body: "You avoided your fork leak twice. But in one game the queen came out
early again — 2-minute review → [See the moment]" (links directly to the game).

## 3. In scope (V1)
- Priority lane in analysis_queue (priority field; worker claims priority first).
- POST /journey/first-aha: import + enqueue most recent loss (fallback: any most
  recent game), return game_id; frontend polls analysis status → navigates.
- Onboarding wires the fast-path after successful link; funnel_first_aha event.
- Nightly digest job (extends the existing scheduler): per user with games
  analyzed in last 24h, compose dodged/leaked summary from analyses + decay
  data; send via existing SMTP; max 1/day; skip when nothing to say.
- Rollout: DIGEST_EMAILS_MODE env = dry | pilot (Mohit only) | live. Ships in
  **pilot** — Mohit reviews the real email, flips to live in .env (no rebuild).

## 4. Out of scope (V1)
Push notifications; digest personalization beyond dodged/leaked/moment-link;
unsubscribe page (V1 honors a users.email_opt_out field if present); Today-rail
redesign (separate scope); paid-user variants.

## 5. Success criteria (pass bars set BEFORE the 20-30 player test)
- Activation (funnel_first_aha within first session) ≥ 50% of linkers.
- D7 return ≥ 25% of activated users.
- Digest CTR ≥ 20% (pilot then live).

## 6. Open questions
- Digest send hour (default 07:30 IST) — Mohit may adjust in .env.
- Whether losses-only fast-path frustrates users who only have wins recently
  (V1 falls back to most recent game).

## 7. Pre-code requirements
✅ scope on the table + Mohit's "go" · ✅ funnel events live · ✅ SMTP verified.
