# Week 4 Action 2: Email Campaign (July 20-26)
**Status:** 🟢 READY TO SEND  
**Recipients:** 16 qualified study users  
**Template:** Locked & approved  
**Timeline:** Send by July 24 → Collect opt-ins by July 31

---

## Quick Start

1. **For each recipient below:** Use the email subject + body template (see "Email Template" section)
2. **Customize:** Replace `[USER_NAME]`, `[PATTERN]`, `[OPT_IN_LINK]`
3. **Send:** BCC all recipients (privacy — no recipient list shown)
4. **Track:** Note sent-to count; expect ≥16/16 opt-ins by July 31

---

## Recipients & Opt-In Links

### PIECE_SAFETY (4 users)

| # | user_id | Pattern | Opt-In URL |
|----|---------|---------|-----------|
| 1 | user_b189135388c9 | piece_safety | `https://chessguru.ai/study/opt-in?user_id=user_b189135388c9&pattern=piece_safety` |
| 2 | user_398eda90a293 | piece_safety | `https://chessguru.ai/study/opt-in?user_id=user_398eda90a293&pattern=piece_safety` |
| 3 | user_46f04c4f3b21 | piece_safety | `https://chessguru.ai/study/opt-in?user_id=user_46f04c4f3b21&pattern=piece_safety` |
| 4 | user_3d451aa18861 | piece_safety | `https://chessguru.ai/study/opt-in?user_id=user_3d451aa18861&pattern=piece_safety` |

### MISSED_TACTIC (4 users)

| # | user_id | Pattern | Opt-In URL |
|----|---------|---------|-----------|
| 1 | user_f7e92a45149c | missed_tactic | `https://chessguru.ai/study/opt-in?user_id=user_f7e92a45149c&pattern=missed_tactic` |
| 2 | user_3798d8af93ed | missed_tactic | `https://chessguru.ai/study/opt-in?user_id=user_3798d8af93ed&pattern=missed_tactic` |
| 3 | user_614cc832fc89 | missed_tactic | `https://chessguru.ai/study/opt-in?user_id=user_614cc832fc89&pattern=missed_tactic` |
| 4 | user_8b599930d7ef | missed_tactic | `https://chessguru.ai/study/opt-in?user_id=user_8b599930d7ef&pattern=missed_tactic` |

### KING_SAFETY (4 users)

| # | user_id | Pattern | Opt-In URL |
|----|---------|---------|-----------|
| 1 | user_a66b5bb10c86 | king_safety | `https://chessguru.ai/study/opt-in?user_id=user_a66b5bb10c86&pattern=king_safety` |
| 2 | user_76ee10b87522 | king_safety | `https://chessguru.ai/study/opt-in?user_id=user_76ee10b87522&pattern=king_safety` |
| 3 | user_3e1eaba9e5ad | king_safety | `https://chessguru.ai/study/opt-in?user_id=user_3e1eaba9e5ad&pattern=king_safety` |
| 4 | user_e6de078c2508 | king_safety | `https://chessguru.ai/study/opt-in?user_id=user_e6de078c2508&pattern=king_safety` |

### CALCULATION_DEPTH (4 users)

| # | user_id | Pattern | Opt-In URL |
|----|---------|---------|-----------|
| 1 | user_df228c5293ea | calculation_depth | `https://chessguru.ai/study/opt-in?user_id=user_df228c5293ea&pattern=calculation_depth` |
| 2 | user_d9c030e9167c | calculation_depth | `https://chessguru.ai/study/opt-in?user_id=user_d9c030e9167c&pattern=calculation_depth` |
| 3 | user_0bffabdb44f6 | calculation_depth | `https://chessguru.ai/study/opt-in?user_id=user_0bffabdb44f6&pattern=calculation_depth` |
| 4 | user_58dc26172549 | calculation_depth | `https://chessguru.ai/study/opt-in?user_id=user_58dc26172549&pattern=calculation_depth` |

---

## Email Template

### Subject Line

```
You're Invited to Help ChessGuru Get Better (Study)
```

### Email Body

```
Hi [USER_NAME],

We're running a 12-week study to prove that ChessGuru coaching actually reduces your chess mistakes. You've been selected as one of 16 players to help us.

### What We're Testing

We want to know: When you solve 3+ puzzles on a weakness pattern, do you make fewer mistakes in that pattern in future games?

Example: If you solve puzzles on [PATTERN], we'll measure whether you make fewer mistakes in that area in your next 10+ games.

### Your Role

Weeks 1-2 (July 20 – Aug 2):
- We capture your current mistake rate (baseline)
- No action needed from you

Weeks 3-10 (Aug 3 – Sep 26):
- You train normally: solve puzzles on your assigned focus pattern
- We track every solve
- That's it—just play and train as usual

Weeks 11-16 (Sep 27 – Oct 9):
- We measure your new mistake rate
- Compare: did it improve?

### Why This Matters

Right now, we say "ChessGuru improves your chess." But we haven't *proven* it yet. This study changes that.

If we succeed: We can say "puzzle training on [PATTERN] reduces mistakes by 20%+" — and you helped us prove it.

If we fail: We find out what's broken and fix it.

Either way, you're helping us build a coaching platform that actually works.

### Your Commitment

- Time: ~2 minutes to opt in. Then just train normally.
- Data: We'll track your games and puzzle attempts (already happening anyway)
- Benefit: You'll know if your training is working; we'll tell you the results in Week 16
- Anonymity: All results are aggregated; your individual data stays private

### Your Assigned Focus Pattern

You'll focus on: [PATTERN]

This was chosen because you have recent mistakes in this area—exactly what we want to test if training improves.

### Opt In?

Click the link below to confirm:

[OPT_IN_LINK]

That's it. From Week 3 onward, you're in the study.

### Questions?

Reply to this email. We'll answer anything.

Thanks for helping us prove that coaching works.

— Mohit & the ChessGuru Team
```

---

## Sending Instructions

### Manual Process (Recommended for first campaign)

1. **Copy the email body** above
2. **For each user** (repeat 16 times):
   - Set To: [user email from DB]
   - Set Subject: "You're Invited to Help ChessGuru Get Better (Study)"
   - Replace `[USER_NAME]` with first name (or "Friend" fallback)
   - Replace `[PATTERN]` with their assigned pattern
   - Replace `[OPT_IN_LINK]` with their unique URL from the table above
   - **Add all recipients to BCC** to protect privacy
   - Send

3. **Log each send:**
   - Note recipient name + pattern
   - Record send time
   - Verify no bounces

### Batch Email Service (Alternative)

If using SendGrid / Mailgun / Brevo:
- Use `email` field from recipients table
- Use template substitution for `[USER_NAME]`, `[PATTERN]`, `[OPT_IN_LINK]`
- Set BCC to track bounces
- Enable click tracking on opt-in links (optional)

---

## Enrollment Tracking

### Create Tracking Sheet (Google Sheets / CSV)

| user_id | pattern | email_sent | opt_in_confirmed | date_opted_in | status |
|---------|---------|-----------|-----------------|---------------|--------|
| user_b189135388c9 | piece_safety | 2026-07-24 | ☑️ | 2026-07-26 | ✅ enrolled |
| user_398eda90a293 | piece_safety | 2026-07-24 | ☐ | — | ⏳ pending |
| ... | ... | ... | ... | ... | ... |

### Opt-In Verification

After emails are sent:
- Users click `[OPT_IN_LINK]`
- Backend creates record in `study_participants` collection
- Status changes to "enrolled"
- Update tracking sheet

### Success Criteria (Week 4 Action 3)

- **Week 4 End Goal:** ≥13/16 users enrolled (81%)
- **Week 5 Start Gate:** ALL 16 users enrolled before baseline measurement

If enrollment < 80%:
1. Send reminder email (July 29)
2. Check for bounced emails
3. Extend window to Aug 2

---

## Pre-Send Checklist

Before clicking "send" on any emails, verify:

- [ ] All 16 opt-in URLs are correct (copy from table above)
- [ ] Email template reviewed and approved
- [ ] Recipient email addresses exist in MongoDB (`db.users.email`)
- [ ] Backend opt-in endpoint is live (`POST /api/study/opt-in`)
- [ ] study_participants collection exists in MongoDB
- [ ] BCC field configured (privacy protection)
- [ ] Tracking sheet created and shared with team
- [ ] Fallback plan if email service fails

---

## Timeline & Ownership

| Date | Action | Owner | Target |
|------|--------|-------|--------|
| July 24 | Send 16 invite emails | Mohit | All 16 sent |
| July 24-30 | Monitor opt-in responses | Mohit + Claude | Track enrolled |
| July 31 | Deadline for opt-in | (Users) | ≥13/16 enrolled |
| Aug 2 | Verify all 16 enrolled | Claude | 100% enrollment gate |
| Aug 2 | Baseline measurement script ready | Claude | Ready to run Week 5 |

---

## Expected Opt-In Rate

Based on typical user engagement:
- **Conservative (60%):** 10/16 users opt in
- **Expected (75-80%):** 12-13/16 users opt in
- **Optimistic (90%+):** 14-16/16 users opt in

**Contingency:** If enrollment falls below 80% by July 31:
1. Send reminder on July 28 ("Last chance to join the study")
2. Extend opt-in window to Aug 2
3. If still <80%, accept smaller cohort + note in results

---

## Next Steps (Week 4 Action 3)

### Monitor Opt-In Responses (July 24-31)

Track opt-in link clicks + confirmations:
- Check backend logs for `POST /api/study/opt-in` calls
- Query `db.study_participants` collection
- Match opted-in user_ids against sending list

### Success = Ready for Week 5

When ≥13/16 users are enrolled:
- **Week 5 Action:** Run baseline measurement
  ```bash
  cd /app && python3 backend/scripts/measure_baseline_for_all_users.py
  ```
- Capture mistake rate for each user in their assigned pattern
- Store in `study_baseline` collection

---

## Contact Info for Replies

When users reply "I want to join," they might ask:
- **"What if I don't want to train?"** → "No pressure, you can still participate. We'll just measure your baseline."
- **"Can I train a different pattern?"** → "This one was chosen for you, but if you strongly prefer another, reply and we'll discuss."
- **"Will this affect my rating?"** → "No, this is just puzzle training. Your rating is separate."
- **"When do I see results?"** → "Week 16 (Oct 9). We'll email everyone their results."

Reply template:
```
Thanks for your interest! We're excited to have you. Here's what happens next:

[Reiterate their assigned pattern]

No action needed from you until training starts Week 3 (Aug 3). Just train normally when the time comes.

See you in the study!
— Mohit
```

---

## Email Archive

After campaign ends, save all sent emails to:
- `docs/WEEK4_EMAIL_CAMPAIGN_SENT.txt` (archive of what was sent)
- `study_campaign_tracking.csv` (enrollment data)

This creates an auditable record of who was invited and when.

