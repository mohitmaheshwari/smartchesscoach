# Audit Triage Quality

Verify that LLM Exposer feedback classifications are correct before shipping captions or filing patterns.

## When to use

- After running triage-batched.py, before shipping results
- When surprised by LLM classifications ("why did it mark this as AUTHORING?")
- Before filing patterns in CAPTION_BACKLOG (ensure classifications are sound)
- As a safety gate before auto-shipping captions to production

## What it checks

1. **Data Consistency** — Are the feedback IDs sent to LLM Exposer actually in the database?
2. **Field Presence** — Do feedbacks have required fields (severity, cp_loss, user_note)?
3. **AUTHORING Quality** — Do "AUTHORING" items have actual `suggested_caption` text?
4. **Classification Audit** — Sample-check LLM classifications against actual feedback content
5. **Chess Verification** — Engine-check claims about piece safety, tactics, etc.

## How to run

```bash
# Full audit
docker exec chess-coach-backend python scripts/verify_triage_quality.py

# With sample size (for deep dive)
docker exec chess-coach-backend python scripts/verify_triage_quality.py --sample-size 20
```

## Expected output

```
DATA CONSISTENCY CHECK
✅ Total pending feedbacks: 251
✅ Already processed (batches 1-2): 120
✅ New feedbacks for batch 3: 131

📋 Sample of NEW pending feedbacks:
  fb_d1c2f1fd610c:
    move_san: Be7
    severity: good
    cp_loss: 45
    user_note: "why not Bd6 here?"
    is_authoring_submission: false
    suggested_caption: NO

⚠️ Data Quality Issues Found:
  - missing_severity: 3

LLM EXPOSER TRIAGE RESULTS
✅ 80 items classified (4/5 batches successful)
⚠️ 20 items need clarification (batch 3)

📊 Classification breakdown:
  AUTHORING       19 items
  CLASS_B         18 items
  CLASS_A         15 items
  DISMISS         18 items
  CLASS_D          6 items

AUTHORING ITEMS QUALITY CHECK
✅ Captions already shipped: 49

📋 Sample of authoring items:
  fb_88e2930b64db: ✅ READY TO SHIP (has caption)
  fb_ca9e14e589f9: ❌ NO CAPTION (can't ship)

⚠️ RECOMMENDATION:
  1. DO NOT ship unverified LLM results
  2. Verify batch 3 feedback IDs match DB
  3. Sample-check 10-20% of classifications
  4. Engine-verify chess claims
  5. Only ship AUTHORING with suggested_caption
```

## Key gates

- ❌ STOP if missing_severity > 5% of sample
- ❌ STOP if AUTHORING items missing suggested_caption
- ⚠️ FLAG if batch 3 feedback IDs don't match database
- ⚠️ FLAG if LLM asked for clarification (category definitions unclear)

## Notes

- Run this BEFORE `ship_authoring_submissions.py`
- Run this BEFORE filing patterns in CAPTION_BACKLOG
- Sample-check findings with `/probe-game` or `/audit-flagged-caption` if needed
- If audit fails, re-run triage with corrected inputs

## Related

- `/triage-feedback` — Main triage skill (sends to LLM Exposer)
- `/probe-game` — Engine verification of chess claims
- `/audit-flagged-caption` — Deep-dive on single feedback
