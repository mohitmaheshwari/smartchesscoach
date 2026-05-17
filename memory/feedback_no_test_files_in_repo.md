---
name: Don't commit test files to the repo
description: Tests are for the assistant's own verification — never added to the repo. Verify in-memory or via throwaway scripts, don't persist test files.
type: feedback
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
Do not add new test files to `backend/tests/` (or any repo directory). Tests are tools for the assistant's verification during work; they are not product artifacts the user wants pushed.

**Why:** The user has an existing test suite of ~150 files already committed. They've stated: *"don't push any test files, they are only for you to verify and we have things."* Adding more pytest-style files clutters the repo with things they don't intend to maintain. The assistant was over-eager and added four test files (test_meta_patterns.py, test_focus_resolver.py, test_focus_sync.py, test_engine2_recording.py) that got committed before this rule was stated.

**How to apply:**
- When verification is needed, prefer one of:
  1. An inline `python -c "..."` command in bash to exercise the logic
  2. A throwaway script in a temp directory that is never staged
  3. Running existing test suites (the user already has them)
- If a test file is genuinely needed during the session, create it outside `backend/tests/` (e.g., `/tmp/verify.py`) or delete it before finishing the task.
- Never add files to `backend/tests/` without explicit user request for that specific test.
- Previously committed test files can stay (removing them now is noisy churn); the rule applies to *new* additions.
- When a user asks "verify this works," run the check inline — don't silently write a new test file as a side effect.
