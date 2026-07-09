# Behavior Validation Study: Consent Email

**Subject:** You're Invited to Help ChessGuru Get Better (Study)

---

## Email Template

Hi [USER_NAME],

We're running a **12-week study** to prove that ChessGuru coaching actually reduces your chess mistakes. You've been selected as one of 20 players to help us.

### What We're Testing

We want to know: **When you solve 3+ puzzles on a weakness pattern, do you make fewer mistakes in that pattern in future games?**

Example: If you solve puzzles on piece_safety, we'll measure whether you hang pieces less often in the next 10+ games.

### Your Role

**Weeks 1-2 (Jan 20-31):**
- We capture your *current* mistake rate (baseline)
- No action needed from you

**Weeks 3-10 (Feb 1 – Mar 26):**
- You train normally: solve puzzles on your assigned focus pattern
- We track every solve
- That's it—just play and train as usual

**Weeks 11-16 (Mar 27 – Apr 2):**
- We measure your new mistake rate
- Compare: did it improve?

### Why This Matters

Right now, we say "ChessGuru improves your chess." But we haven't *proven* it yet. This study changes that.

**If we succeed:** We can say "puzzle training on piece_safety reduces mistakes by 20%+" — and you helped us prove it.

**If we fail:** We find out what's broken and fix it.

Either way, you're helping us build a coaching platform that actually works.

### Your Commitment

- **Time:** ~5 minutes to opt in. Then just train normally.
- **Data:** We'll track your games and puzzle attempts (already happening anyway)
- **Benefit:** You'll know if your training is working; we'll tell you the results in Week 16
- **Anonymity:** All results are aggregated; your individual data stays private

### Will I See Any Changes?

No. Everything looks the same. Your assigned puzzle pattern will show up on your Training page (it already does). We're just measuring what happens.

### Your Assigned Focus Pattern

You'll focus on: **[PATTERN]**

This was chosen because you have recent mistakes in this area—exactly what we want to test if training improves.

### Opt In?

Reply to this email or click the link below to confirm:

**[OPT_IN_LINK]**

That's it. From Week 3 onward, you're in the study.

### Questions?

Reply to this email. We'll answer anything.

Thanks for helping us prove that coaching works.

— Mohit & the ChessGuru Team

---

## Implementation Notes

### Email Recipients

Run the `identify_study_users.py` script to generate the recipient list:

```bash
cd /app && python3 backend/scripts/identify_study_users.py
```

This outputs a table with:
- user_id
- email (from users collection)
- assigned_pattern
- current_rating
- mistake_count_in_pattern

### Template Variables to Replace

For each recipient:
- `[USER_NAME]`: First name from user profile (or "Friend" fallback)
- `[PATTERN]`: Their assigned pattern (e.g., "piece_safety")
- `[OPT_IN_LINK]`: Link to `/study/opt-in?user_id=xxx&pattern=yyy`

### Opt-In Endpoint

Create backend endpoint: `POST /study/opt-in`

```python
@router.post("/study/opt-in")
async def opt_in_to_study(
    user_id: str,
    pattern: str,
    user: User = Depends(get_current_user)
):
    """
    User opts into behavior validation study.
    
    Creates entry in `study_participants` collection:
    {
        "user_id": user_id,
        "pattern": pattern,
        "status": "enrolled",
        "opted_in_at": datetime.now(),
        "baseline_window": "2026-01-27 to 2026-01-31",
        "intervention_window": "2026-02-01 to 2026-03-26",
        "outcome_window": "2026-03-27 to 2026-04-02"
    }
    """
    if user.user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    await db.study_participants.insert_one({
        "user_id": user_id,
        "pattern": pattern,
        "status": "enrolled",
        "opted_in_at": datetime.now(timezone.utc),
        "baseline_window": {"start": "2026-01-27", "end": "2026-01-31"},
        "intervention_window": {"start": "2026-02-01", "end": "2026-03-26"},
        "outcome_window": {"start": "2026-03-27", "end": "2026-04-02"}
    })
    
    return {"status": "enrolled", "pattern": pattern}
```

### Sending Emails

**Option 1: Manual (Week 4)**
- Run identify script
- Export CSV
- Use email service (Gmail, SendGrid, etc.)
- BCC recipients (privacy)

**Option 2: Automated**
- Create `backend/scripts/send_study_invites.py`
- Uses `db.users` + identify script output
- Sends via SMTP (configured in .env)
- Logs opt-in links to console

### Timeline

| Week | Task | Owner | Date |
|------|------|-------|------|
| 4 | Run identify script → get 20 users | Claude | Jan 20-24 |
| 4 | Draft + approve email | Mohit | Jan 20-24 |
| 4 | Send invites | Claude/Mohit | Jan 24-27 |
| 5 | Collect opt-ins | (Users) | Jan 27-31 |
| 5 | Measure baseline | Claude | Jan 27-31 |
| 6-15 | Intervention runs | (Users) | Feb 1 – Mar 26 |
| 15 | Measure outcome | Claude | Mar 27 – Apr 2 |
| 16 | Analyze + report | Claude | Apr 3-9 |

---

## Checklist Before Sending

- [ ] Identify script runs successfully → 20 users found
- [ ] Email template reviewed by Mohit
- [ ] Opt-in endpoint created + tested
- [ ] study_participants collection exists in MongoDB
- [ ] Baseline measurement script is ready (separate task)
- [ ] All 20 users have email addresses in DB
- [ ] Legal review (if needed) ✅ Approved

