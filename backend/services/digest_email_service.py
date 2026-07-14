"""Post-game digest email (docs/activation_scope.md, 2026-07-14).

After the nightly sync analyzes yesterday's games, each user with something
worth saying gets ONE short email: what they dodged, what leaked, one CTA into
the exact decoded game (email→page contract: the link delivers precisely what
the email promises). Rides the user's existing chess.com/lichess habit — the
return trigger the product was missing.

Rollout via DIGEST_EMAILS_MODE env:
  dry   — compose + log only (default)
  pilot — send ONLY to PILOT_EMAILS (Mohit) for review
  live  — send to every eligible user
Kill/adjust without rebuild: values read from .env at send time.
Guards: max 1 digest per user per day; skip when nothing to say; honors
users.email_opt_out.
"""
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

PILOT_EMAILS = {"bhutramohit@gmail.com"}
FRONTEND = os.environ.get("FRONTEND_URL", "https://chessguru.ai")


def _mode() -> str:
    return os.environ.get("DIGEST_EMAILS_MODE", "dry").strip().lower()


async def _yesterday_summary(db, user_id: str):
    """(games_count, leaked_pattern, worst_game_id, dodged_pattern) from the
    last 24h of analyzed games + the persisted decay state."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    game_ids = [g["game_id"] async for g in db.games.find(
        {"user_id": user_id}, {"_id": 0, "game_id": 1, "imported_at": 1})]
    if not game_ids:
        return None
    analyses = await db.game_analyses.find(
        {"game_id": {"$in": game_ids}, "analyzed_at": {"$gte": cutoff.isoformat()}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ).to_list(50)
    if not analyses:
        # analyzed_at may be a datetime in some docs — retry with datetime match
        analyses = await db.game_analyses.find(
            {"game_id": {"$in": game_ids}, "analyzed_at": {"$gte": cutoff}},
            {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
        ).to_list(50)
    if not analyses:
        return None

    gap_cp, worst = {}, (None, 0)
    for a in analyses:
        game_cp = 0
        for m in a.get("stockfish_analysis", {}).get("move_evaluations", []):
            if m.get("is_opponent_move"):
                continue
            gap, cp = m.get("cognitive_gap"), (m.get("cp_loss") or 0)
            if gap and cp > 0:
                gap_cp[gap] = gap_cp.get(gap, 0) + cp
                game_cp += cp
        if game_cp >= worst[1]:
            worst = (a["game_id"], game_cp)

    leaked = max(gap_cp, key=gap_cp.get) if gap_cp else None
    dodged = None
    decay = await db.user_pattern_decay.find_one({"user_id": user_id})
    if decay:
        for pat, sc in sorted((decay.get("scores") or {}).items(),
                              key=lambda kv: -kv[1].get("weighted_score", 0)):
            if pat not in gap_cp and sc.get("state") == "active":
                dodged = pat
                break
    return {"games": len(analyses), "leaked": leaked, "dodged": dodged,
            "worst_game_id": worst[0]}


def _compose(summary):
    n = summary["games"]
    label = lambda p: p.replace("_", " ")
    parts = []
    if summary["dodged"]:
        parts.append(f"Your {label(summary['dodged'])} radar held up — it didn't cost you anything yesterday. ✓")
    if summary["leaked"]:
        parts.append(f"But {label(summary['leaked'])} showed up again — worth two minutes to see exactly where.")
    if not parts:
        return None, None
    subject = (f"Yesterday's game{'s' if n != 1 else ''}: "
               + (f"your {label(summary['dodged'])} radar worked ✓" if summary["dodged"]
                  else f"{label(summary['leaked'])} showed up again"))
    cta = f"{FRONTEND}/game/{summary['worst_game_id']}" if summary["worst_game_id"] else f"{FRONTEND}/home"
    html = f"""
    <div style="font-family:Georgia,serif;max-width:520px;margin:auto;color:#222">
      <p>We analyzed {n} game{'s' if n != 1 else ''} from yesterday.</p>
      <p>{'</p><p>'.join(parts)}</p>
      <p><a href="{cta}" style="background:#0f766e;color:#fff;padding:10px 18px;
         border-radius:8px;text-decoration:none">See the moment →</a></p>
      <p style="color:#888;font-size:12px">ChessGuru — your games are the curriculum.</p>
    </div>"""
    return subject, html


async def _send_smtp(to_email: str, subject: str, html: str) -> bool:
    """Zoho SMTP send — same proven pattern as the reengagement scripts
    (email_service.py is an unconfigured SendGrid stub; SMTP_* is what works).
    Runs in a thread so the blocking socket never stalls the event loop."""
    import asyncio, smtplib, ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    port = int(os.environ.get("SMTP_PORT", "465"))
    from_name = os.environ.get("SMTP_FROM_NAME", "ChessGuru Coach")
    if not (host and user and password):
        logger.warning("[digest] SMTP not configured — skipping send")
        return False

    def _send():
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{user}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as smtp:
            smtp.login(user, password)
            smtp.sendmail(user, [to_email], msg.as_string())
        return True

    try:
        return await asyncio.to_thread(_send)
    except Exception as e:
        logger.warning(f"[digest] SMTP send failed for {to_email}: {e}")
        return False


async def run_daily_digest(db) -> dict:
    """Compose + (per mode) send digests. Returns counts for the log."""
    mode = _mode()
    sent = skipped = composed = 0
    today = datetime.now(timezone.utc).date().isoformat()

    async for u in db.users.find({}, {"_id": 0, "user_id": 1, "email": 1, "email_opt_out": 1}):
        uid, email = u.get("user_id"), (u.get("email") or "").strip()
        if not uid or not email or u.get("email_opt_out"):
            skipped += 1
            continue
        already = await db.digest_email_log.find_one({"user_id": uid, "date": today})
        if already:
            skipped += 1
            continue
        try:
            summary = await _yesterday_summary(db, uid)
        except Exception as e:
            logger.warning(f"digest summary failed for {uid}: {e}")
            continue
        if not summary:
            continue
        subject, html = _compose(summary)
        if not subject:
            continue
        composed += 1
        deliver = (mode == "live") or (mode == "pilot" and email.lower() in PILOT_EMAILS)
        if deliver:
            ok = await _send_smtp(email, subject, html)
            if ok:
                sent += 1
                await db.digest_email_log.insert_one(
                    {"user_id": uid, "date": today, "subject": subject,
                     "sent_at": datetime.now(timezone.utc).isoformat()})
        else:
            logger.info(f"[digest:{mode}] would send to {uid}: {subject}")

    logger.info(f"[digest] mode={mode} composed={composed} sent={sent} skipped={skipped}")
    return {"mode": mode, "composed": composed, "sent": sent, "skipped": skipped}
