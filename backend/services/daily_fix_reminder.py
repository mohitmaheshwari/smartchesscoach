"""
Daily Fix reminder (docs/daily_fix_scope.md §3) — the daily-return nudge.

Sends a small email to bring users back to their daily fix. Deliberately
conservative for a first automated program:
  - PRIMARY message = "streak at risk" — only users who ACTUALLY hold a streak
    that will break if they don't act today. High-value, low-volume, wanted.
  - Optional "fix ready" nudge (held behind include_fix_ready=False by default).

Responsible-send scaffolding is reused from the digest service:
  - respects users.email_opt_out
  - dedups via daily_fix_reminder_log (one reminder per user per day)
  - dry_run=True by default (targets + composes, never sends)
  - reuses the proven Zoho SMTP sender (services.digest_email_service._send_smtp)

Turning on live sends to real users is a separate, gated decision (audience,
frequency, unsubscribe link, deliverability) — NOT flipped on by building this.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.mistake_streak_service import practice_streak_view

logger = logging.getLogger(__name__)

SITE = "https://chessguru.ai"
REMINDER_LOG = "daily_fix_reminder_log"


def _first_name(user: Dict[str, Any]) -> str:
    raw = (user.get("display_name") or user.get("name")
           or (user.get("email") or "").split("@")[0] or "")
    part = next((p for p in raw.replace(".", " ").replace("_", " ").split() if p), "")
    return part[:1].upper() + part[1:].lower() if part else "there"


def compose_reminder(message_type: str, streak: Dict[str, Any], first_name: str,
                     fix_url: str) -> Dict[str, str]:
    """Pure: build (subject, html) for a reminder. Voice: warm, plain English,
    no chess jargon. Leads with the momentum, not notation."""
    n = int(streak.get("current", 0) or 0)
    if message_type == "streak_at_risk":
        subject = f"Don't lose your {n}-day streak 🔥"
        line = (f"Hi {first_name} — your {n}-day practice streak is about to break. "
                f"A quick fix on the one thing holding your game back keeps it alive.")
        cta = "Do today's fix"
    else:  # fix_ready
        subject = "Your daily fix is ready"
        line = (f"Hi {first_name} — a few minutes on the exact pattern you keep "
                f"repeating. Small and specific, from your own games.")
        cta = "Start today's fix"

    html = (
        f'<div style="font-family:Inter,Arial,sans-serif;max-width:480px;margin:0 auto;'
        f'color:#1f2937;line-height:1.6">'
        f'<p style="font-size:15px">{line}</p>'
        f'<p style="margin:24px 0">'
        f'<a href="{fix_url}" style="background:#d97706;color:#fff;text-decoration:none;'
        f'padding:10px 18px;border-radius:8px;font-weight:600;font-size:14px">{cta} →</a></p>'
        f'<p style="font-size:12px;color:#6b7280">You\'re getting this because you '
        f'started a practice streak on ChessGuru.</p></div>'
    )
    return {"subject": subject, "html": html}


def _classify(streak_view: Dict[str, Any]) -> Optional[str]:
    """Decide which reminder (if any) a user should get today.
    Returns 'streak_at_risk', 'fix_ready', or None (skip)."""
    if streak_view.get("done_today"):
        return None                      # already did it — never nudge
    current = int(streak_view.get("current", 0) or 0)
    if current <= 0:
        return None                      # no live streak (never started, or already lost) — skip
    if streak_view.get("at_risk"):
        return "streak_at_risk"          # will break today if they don't act
    return "fix_ready"                    # mid-streak, has buffer — gentle nudge


async def find_reminder_recipients(db, today: Optional[str] = None,
                                   include_fix_ready: bool = False) -> List[Dict[str, Any]]:
    """Read-only: who should get a reminder today, and which one. Conservative —
    only users who hold a live practice streak (they've engaged) and aren't
    opted out. `include_fix_ready` gates the broader (non-at-risk) nudge."""
    today = today or datetime.now(timezone.utc).date().isoformat()
    out: List[Dict[str, Any]] = []
    async for u in db.users.find(
        {"practice_streak": {"$exists": True}},
        {"_id": 0, "user_id": 1, "email": 1, "display_name": 1, "name": 1,
         "email_opt_out": 1, "practice_streak": 1},
    ):
        email = (u.get("email") or "").strip()
        if not email or u.get("email_opt_out"):
            continue
        view = practice_streak_view(u.get("practice_streak"), today)
        mtype = _classify(view)
        if mtype is None:
            continue
        if mtype == "fix_ready" and not include_fix_ready:
            continue
        out.append({"user_id": u["user_id"], "email": email,
                    "first_name": _first_name(u), "message_type": mtype, "streak": view})
    return out


async def run_daily_fix_reminders(db, dry_run: bool = True, today: Optional[str] = None,
                                  include_fix_ready: bool = False) -> Dict[str, Any]:
    """Send (or dry-run) the daily reminders. Dedups per user per day. Returns
    counts for the cron log. dry_run=True never contacts SMTP."""
    today = today or datetime.now(timezone.utc).date().isoformat()
    recipients = await find_reminder_recipients(db, today, include_fix_ready)
    sent = skipped = failed = 0
    plan: List[Dict[str, Any]] = []

    for r in recipients:
        if await db[REMINDER_LOG].find_one({"user_id": r["user_id"], "date": today}):
            skipped += 1
            continue
        fix_url = f"{SITE}/home"  # daily-fix card lives on /home; drill deep-link is a follow-up
        msg = compose_reminder(r["message_type"], r["streak"], r["first_name"], fix_url)
        plan.append({"email": r["email"], "type": r["message_type"], "subject": msg["subject"]})

        if dry_run:
            continue
        from services.digest_email_service import _send_smtp
        ok = await _send_smtp(r["email"], msg["subject"], msg["html"])
        if ok:
            sent += 1
            await db[REMINDER_LOG].insert_one(
                {"user_id": r["user_id"], "date": today, "type": r["message_type"],
                 "sent_at": datetime.now(timezone.utc).isoformat()})
        else:
            failed += 1

    result = {"dry_run": dry_run, "recipients": len(recipients),
              "sent": sent, "skipped": skipped, "failed": failed, "plan": plan}
    logger.info(f"[daily-fix-reminder] {result}")
    return result
