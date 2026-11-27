# Academy onboarding: the first ten minutes

Mohit, 2026-11-27: *"i don't see the onboarding flow created for a academy,
right now i only see the flow created for a chess player, are you with me,
also please make sure the UX is top notch, not any rough UX."*

He is right. A player gets a three-step welcome. A coach gets an admin form.

**Sign-off.** Mohit, 2026-11-27: "okay, go ahead please", in answer to this
document and the two open questions in section 6. Recorded as the explicit
sign-off. He did not answer the two questions one by one, so V1 ships the
position each of them already states here, and both are revisited on the
first real pilot rather than guessed at again.

---

## 0. Existing surfaces audit

Checked in the code at `79864287` and against production (read-only) on
2026-11-27.

| Need | What already exists | Overlap |
|---|---|---|
| A way in for a coach | `Landing.jsx:333` — a "For coaches and academies" card whose button calls `startAcademy("families_coach")` | **Exists and works.** Nothing to build. |
| A way in for a parent | `Landing.jsx:332` — "For parents", `startAcademy("families_parent")` | **Exists and works.** |
| Carrying WHO they are into the product | **Nothing.** `Landing.jsx:253-261`: `source` is passed to `track()` and then discarded. Both buttons navigate to the identical URL, `/login?signup=1&redirect_to=/academy`. | The landing page asks the right question and throws the answer away. |
| Setting up an academy | `Academy.jsx:155-170` — a card with two placeholder-only inputs and a Create button | Exists as a **form**, not as a flow. |
| Setting up a parent's own child | `Academy.jsx:143-153` — a card with one button, `POST /academy {kind:"family"}` | Exists. Shown **above** the academy card, to everyone. |
| Batches, children, coaches, consent, reports, homework, class games | `routes/academy.py` (34 endpoints), `Academy.jsx`, `AcademyFamily.jsx`, `FirstStepsClass.jsx`, `ClassReflect.jsx`, `MyClass.jsx` | **All of it exists and is signed off** in `docs/academy_pilot_scope.md`. Not touched by this document. |
| A player's onboarding, for comparison | `ActivationHub.jsx` — three steps, one question per screen, progress, back, every control 44px | The standard this document is trying to meet. |

### What production says

| | |
|---|---|
| academies | **1** — "Test academy (Mohit)", created 2026-11-05 |
| academy_staff / batches | 1 / 1 |
| academy_students | 2 |
| **students whose parent has agreed** | **0** |

No academy that is not Mohit's own test has ever been created, and no parent
has ever agreed. The chain stops at the first human step. Every surface behind
that step — reports, homework, class games — has never been reached by a real
family. That is the thing this document is for.

### Measured defects on `/academy` today

Rendered at 390x844 and 1280x900 with the API mocked:

- **5 controls at 40-42px**, under the 44px floor: batch name, coach's name,
  Add batch, coach's email, Add coach. The empty state has 4 more.
- **No visible labels.** Every input is placeholder-only, so the label
  disappears the moment anyone types.
- **The parent card sits above the academy card**, for everyone, including
  somebody who just pressed "I'm a coach or academy".
- **No flow.** No welcome, no progress, no next step, no finish.

Checked and *not* a defect: the fixed bottom nav appears to cover the coach
list in a full-page screenshot. `elementFromPoint` at the real scroll position
reports `covered: []` at both widths. It is a screenshot artefact of
`position: fixed`, and `Layout.jsx:550` already reserves `pb-20`.

### Decision: **EXTEND**

Nothing here justifies a parallel system. The backend does everything already;
the admin pages are correct; what is missing is the ten minutes in front of
them. V1 adds one guided route and tidies the page it hands over to.

---

## 1. What it is

A coach who presses "I'm a coach or academy" on the landing page, and a parent
who presses "Set up my child", are two different people with two different
jobs — and from the moment they create an account, ChessGuru treats them the
same and shows them a form. This gives each of them a short guided setup that
knows which one they are, asks one thing per screen, and ends by telling them
exactly what happens next and who they need to send a link to.

For an academy that is: name your academy, name your first batch, add your
first children. For a parent it is: tell us your child's name. Both finish on
the one thing that actually matters and that nobody has ever completed — the
message that goes to a parent asking them to agree.

## 2. What the user sees

### A coach, arriving from the landing page

```
  ┌──────────────────────────────────────┐
  │  Step 1 of 3                   Back  │
  │                                      │
  │  What is your academy called?        │
  │  This is the name parents will see   │
  │  on their child's weekly report.     │
  │                                      │
  │  Academy name                        │
  │  ┌────────────────────────────────┐  │
  │  │ Knight School Pune             │  │
  │  └────────────────────────────────┘  │
  │  City (optional)                     │
  │  ┌────────────────────────────────┐  │
  │  │ Pune                           │  │
  │  └────────────────────────────────┘  │
  │                                      │
  │  [            Continue            ]  │
  └──────────────────────────────────────┘

  Step 2 of 3 — "Which batch shall we start with?"
      Batch name      [ Saturday batch        ]
      Who coaches it  [ Priya Nair            ]   ← prefilled with their name
      [ Continue ]        Skip for now

  Step 3 of 3 — "Add your first children"
      ┌─ Child's name ──────┬─ Parent's WhatsApp ─┐
      │ Aarav               │ +91 98765 43210     │
      └─────────────────────┴─────────────────────┘
      + Add another child
      [ Finish ]          I'll add them later

      Both fields are REQUIRED, and that is the server's rule, not a
      choice made here: routes/academy.py:458-461 rejects a student with
      no name ("Enter the child's first name.") or no phone ("Enter the
      parent's WhatsApp number."). The flow must say so before the user
      presses anything, rather than letting the server say it after.
```

### The finish screen — the one that matters

```
  ┌──────────────────────────────────────┐
  │  Knight School Pune is set up.       │
  │                                      │
  │  One thing left. Each parent has to  │
  │  agree before we read their child's  │
  │  games. Send them this link.         │
  │                                      │
  │  Aarav   [ Send on WhatsApp ] [Copy] │
  │  Diya    [ Send on WhatsApp ] [Copy] │
  │                                      │
  │  Once a parent agrees, their child's │
  │  games start being read, and your    │
  │  first batch report is ready the     │
  │  Sunday after.                       │
  │                                      │
  │  [        Open my academy         ]  │
  └──────────────────────────────────────┘
```

### A parent, arriving from the landing page

```
  Step 1 of 1 — "What is your child's name?"
      [ Aarav                              ]
      [ Continue ]

  Done — "Aarav is set up."
      You need to agree before we read Aarav's games.
      [ Agree now ]          ← their own consent page
```

## 3. In scope (V1)

- The landing page's parent-or-coach choice survives signup and reaches the
  flow, so the flow never asks a question the user has already answered.
- A new route, `/academy/start`, with the steps above: one question per
  screen, a step counter, Back, and an honest skip on every step that is not
  required.
- Every control at least 44px. Every input a visible `<label>`, not a
  placeholder.
- The flow asks who they are **only** when the landing choice is missing (a
  direct link, a returning user, a lost session).
- A finish screen whose main content is the parent links, because that is the
  step the whole product is currently stuck behind.
- `/academy` itself: one heading, and an empty state that points at the flow
  instead of showing two raw forms. Its existing forms get visible labels and
  44px controls.
- `/academy2` — a preview route rendering every step with no backend, the way
  `/lobby2` and `/result2` do.
- Tests in the house style, and a rendered check at 390 and 1280: zero
  overflow, zero controls under 44px, zero occluded controls, no JS errors.

## 4. Explicitly out of scope (V1)

- **Any backend change.** All 34 endpoints exist and do what is needed. If the
  flow needs something the API cannot do, that is a finding for Mohit, not a
  silent addition.
- **Billing or payment.** The direction note says the bar is one paid pilot;
  taking money is not part of getting set up.
- **Bulk import of children** (CSV, paste-a-list). Worth having, not worth
  blocking the first academy on.
- **Sending the parent message for them.** V1 gives a link to copy. WhatsApp
  sending already exists elsewhere and wiring it is a separate decision.
- **Inviting co-coaches during setup.** It stays on `/academy`, where it is.
- **Multi-academy switching.** One account, one academy, until someone has two.
- **Re-designing the batch, student, consent, report or homework pages.** They
  are signed off in `docs/academy_pilot_scope.md`.

## 5. Success criteria

The current numbers are 1 academy (Mohit's own) and **0 parent agreements**,
so the honest bar is a first, not a percentage:

1. **One real academy, not Mohit's, completes setup and reaches the finish
   screen** — measurable as an `academies` row whose `owner_user_id` is not
   Mohit's with at least one `academy_students` row.
2. **One parent agrees** — one `academy_students` row at `consent: "given"`.
   This has never happened. It is the single number that says the chain works.
3. Nobody has to be told how. No step in the flow needs an explanation from
   Mohit over WhatsApp for the first pilot academy to finish it.

Deliberately *not* success: that the flow renders, or that the pages look
better. Those are the work, not the result.

## 6. Open questions

~~**Question:** Should the finish screen offer to send the parent message over
WhatsApp, rather than a link to copy?~~ **Answered by the code, not by me.**
`POST /batch/{id}/students` already returns a `whatsapp` field:
`academy_service.whatsapp_link()` builds a `wa.me/<phone>?text=...`
click-to-chat URL with `_consent_message()` already written into it
(`routes/academy.py:484`, `services/academy_service.py:130-135`). The coach
presses send; nothing is sent automatically, and no WhatsApp Business number
is involved. So V1 makes "Send on WhatsApp" the primary action on the finish
screen with "Copy link" beside it, and this needed no decision.

- **Question:** A coach with no children yet — should the flow let them finish
  with an empty batch?
  **Why unresolved:** Finishing empty is friendlier; finishing empty also
  means they see nothing on `/academy` and may not come back.
  **Unblocking step:** V1 allows it (a flow that traps you is worse), and the
  finish screen names the missing step. Revisit on the first real pilot.

- **Question:** Does a parent who set up at home need the same weekly report
  rhythm as an academy's parent, or something quieter?
  **Why unresolved:** No parent has ever reached the report, so there is no
  evidence either way.
  **Unblocking step:** The first family to agree.

## 7. Pre-code requirements

- [x] Section 0 audit done against code and production.
- [x] The route is chosen: `/academy/start`, with `/academy2` as its preview.
- [x] Confirmed no backend change is needed: `POST /academy`,
      `POST /{id}/batches`, `POST /batch/{id}/students` cover every step, and
      the add-student response hands back `links.consent` AND a ready
      `whatsapp` click-to-chat URL, which is exactly what the finish screen
      needs.
- [x] A rendered-check harness exists (`playwright-core` in the scratchpad)
      that measures overflow, the 44px floor and real occlusion.
- [x] **Mohit's sign-off on this document** (2026-11-27, above).

---

## Built

Shipped in `55098ecf`. Nothing in section 4 crept in, and no backend was
touched: `POST /academy`, `POST /{id}/batches` and
`POST /batch/{id}/students` were enough, exactly as section 7 predicted.

Verified by walking the real flow in a browser at 390x844 and 1280x900 --
nine screens, both personas, and the "nobody told us" case: 0 horizontal
overflow, 0 controls under 44px, 0 controls actually covered
(`elementFromPoint`, not a screenshot), 0 inputs without a real label, no JS
errors. 35 tests across the five suites this touched.

Two defects were written and caught by looking rather than by testing, which
is the argument for `/academy2` existing at all:

- `Shell` was defined inside the component, so every keystroke created a new
  component type, React remounted the subtree, and the input being typed into
  lost focus. There is now a test that types and asserts focus survived.
- The preview wrote `?who=` from an effect, after the child had already read
  it in a `useState` initialiser, so it always showed the "who are you"
  screen whichever persona was selected.

One thing that looked like a defect and was not: the fixed bottom nav appears
to sit on top of the coach list in a full-page screenshot. It does not --
`elementFromPoint` at the real scroll position reports nothing covered. A
full-page screenshot paints a `position: fixed` element once, at its viewport
position, and stitches it into the middle of the image.
