# Behavior Validation Study: Confirmed Roster
**Date Identified:** July 9, 2026  
**Total Participants:** 16 users (4 patterns)  
**Status:** ✅ READY FOR WEEK 4 ENROLLMENT

---

## Summary
16 qualified users identified across 4 focus patterns. Each user has:
- ≥20 games analyzed in last 60 days (active)
- Rating 600-1900 (target audience)
- ≥10 mistakes in assigned pattern (signal to measure)
- <80% puzzle solve rate (new training effect measurable)

Note: time_pressure pattern deferred (0 candidates found). Will revisit in future cohort.

---

## PIECE_SAFETY (4 users)

| # | user_id | Rating | Mistakes | Puzzle % | Status |
|----|---------|--------|----------|----------|--------|
| 1 | user_b189135388c9 | 1369 | 1571 | 0.0% | ✅ Ready |
| 2 | user_398eda90a293 | 1734 | 1211 | 0.0% | ✅ Ready |
| 3 | user_46f04c4f3b21 | 786 | 1006 | 0.0% | ✅ Ready |
| 4 | user_3d451aa18861 | 1330 | 934 | 0.0% | ✅ Ready |

---

## MISSED_TACTIC (4 users)

| # | user_id | Rating | Mistakes | Puzzle % | Status |
|----|---------|--------|----------|----------|--------|
| 1 | user_f7e92a45149c | 1013 | 277 | 0.0% | ✅ Ready |
| 2 | user_3798d8af93ed | 1341 | 250 | 0.0% | ✅ Ready |
| 3 | user_614cc832fc89 | 1247 | 224 | 0.0% | ✅ Ready |
| 4 | user_8b599930d7ef | 1241 | 187 | 50.7% | ✅ Ready |

---

## KING_SAFETY (4 users)

| # | user_id | Rating | Mistakes | Puzzle % | Status |
|----|---------|--------|----------|----------|--------|
| 1 | user_a66b5bb10c86 | 1214 | 290 | 0.0% | ✅ Ready |
| 2 | user_76ee10b87522 | 1064 | 266 | 0.0% | ✅ Ready |
| 3 | user_3e1eaba9e5ad | 1593 | 249 | 0.0% | ✅ Ready |
| 4 | user_e6de078c2508 | 1879 | 154 | 0.0% | ✅ Ready |

---

## CALCULATION_DEPTH (4 users)

| # | user_id | Rating | Mistakes | Puzzle % | Status |
|----|---------|--------|----------|----------|--------|
| 1 | user_df228c5293ea | 751 | 55 | 0.0% | ✅ Ready |
| 2 | user_d9c030e9167c | 1423 | 50 | 33.3% | ✅ Ready |
| 3 | user_0bffabdb44f6 | 772 | 36 | 0.0% | ✅ Ready |
| 4 | user_58dc26172549 | 871 | 31 | 0.0% | ✅ Ready |

---

## STATISTICS

- **Total users:** 16
- **Average rating:** 1,186
- **Rating range:** 751–1,879
- **Total mistakes tracked:** 6,632 (average 414 per user)
- **Puzzle history:** 15/16 users (0% solve rate, ready for intervention)

---

## DEFERRED

### time_pressure (0/4)
**Status:** ⏸️ Deferred to future cohort  
**Reason:** No users found with ≥10 mistakes in time_pressure gap  
**Investigation needed:** Check if time_pressure detection/tracking is working correctly

---

## NEXT STEPS (Week 4: July 20-26)

### Week 4 Action 2: Customize & Send Consent Emails
- Template: `docs/behavior_study_consent_email.md`
- For each user: Replace `[USER_NAME]` + `[PATTERN]` + generate opt-in URL
- Deadline: July 24
- Target: 80%+ enrollment (≥13/16 users)

### Week 4 Action 3: Monitor Opt-In Responses
- Track opt-in confirmations
- Goal: All 16 users enrolled by July 31
- Success: ≥13/16 enrolled in `study_participants` collection

---

## ENROLLMENT TEMPLATE

```
Email Subject: You're Invited to Help ChessGuru Get Better (Study)

Hi [USER_NAME],

You've been selected as one of 16 players to help us prove that ChessGuru coaching actually reduces your chess mistakes.

Your assigned focus pattern: [PATTERN]

Over 12 weeks, we'll measure whether solving puzzles on this pattern reduces your mistakes in that area.

Opt in here: https://chessguru.ai/study/opt-in?user_id=USER_ID&pattern=[PATTERN]

No action needed during the study — just train normally. We'll measure your progress.

— Mohit & the ChessGuru Team
```

---

## CONFIDENTIALITY & ETHICS

- All data stored in `study_participants`, `study_baseline`, `study_outcome` collections
- User IDs only (no PII)
- Results published as aggregated findings only
- Individual user data remains private

