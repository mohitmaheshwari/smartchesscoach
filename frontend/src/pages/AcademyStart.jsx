/**
 * /academy/start — the first ten minutes for a coach, or for a parent.
 *
 * Mohit, 2026-11-27: "i don't see the onboarding flow created for a academy,
 * right now i only see the flow created for a chess player... also please make
 * sure the UX is top notch, not any rough UX."
 *
 * He was right. A player got ActivationHub: three steps, one question per
 * screen, a progress rail, Back, every control 44px. A coach got
 * /academy — two stacked cards, placeholder-only inputs, five controls at
 * 40-42px, and the parent card sitting above the academy card no matter which
 * button they had just pressed on the landing page.
 *
 * Why the wrong card was on top: Landing.jsx asks the right question and then
 * throws the answer away. `startAcademy(source)` passes `source` to track()
 * and sends both buttons to the identical URL, so /academy cannot know who
 * arrived and has to show both. That is fixed at the source; this page reads
 * ?who= and only asks when nobody told it.
 *
 * Scope: docs/academy_onboarding_scope.md. Deliberately matched to
 * ActivationHub's shell, type and colours, because a product where the
 * coach's welcome and the player's welcome look like different websites is
 * two products.
 *
 * What this page is actually for. Production on 2026-11-27: one academy
 * (Mohit's own test), two children, and ZERO parents who have ever agreed.
 * Every surface behind that agreement -- reports, homework, class games --
 * has never been reached by a real family. So the flow does not end on
 * "well done"; it ends on the message that goes to a parent, with WhatsApp as
 * the primary action, because that is the step the whole product is stuck
 * behind.
 *
 * No backend was added for any of this. The three endpoints already existed,
 * and add-student already returns a ready wa.me link with the consent message
 * written into it (routes/academy.py:484).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { ArrowLeft, Check, Copy, Plus, Users, User as UserIcon } from "lucide-react";

// Same palette as ActivationHub, for the same reason: this page is
// light-mode-only, so theme-aware tokens would resolve to near-white text on
// a light background in dark mode.
const WINE = "#0F5B47";
const BORDER = "hsl(35 10% 87%)";
const INK = "hsl(222 47% 11%)";
const INK_MUTED = "hsl(220 9% 46%)";

const WHO_KEY = "chessguru.academy_who";

/** The server rejects a student with no name or no phone, so the form must. */
const looksLikePhone = (raw) => {
  const digits = String(raw || "").replace(/\D/g, "");
  return digits.length >= 10 && digits.length <= 15;
};

async function call(path, body) {
  const res = await fetch(`${API}/api${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    data = null;
  }
  if (!res.ok) {
    throw new Error((data && (data.detail?.message || data.detail)) || "That did not save.");
  }
  return data;
}

/* ---------------------------------------------------------------- bits */

function Field({ id, label, hint, value, onChange, placeholder, type = "text", autoFocus, inputRef }) {
  return (
    <label className="grid gap-1.5" htmlFor={id}>
      {/* A visible label, not a placeholder. A placeholder disappears the
          moment anyone types, which is when they most need to know what the
          box is for. All five inputs on /academy were placeholder-only. */}
      <span className="text-sm font-medium" style={{ color: INK }}>
        {label}
      </span>
      <input
        id={id}
        ref={inputRef}
        type={type}
        value={value}
        autoFocus={autoFocus}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-[48px] w-full rounded-xl border bg-white px-3.5 text-base outline-none transition-colors focus:border-[#0F5B47] focus-visible:ring-2"
        style={{ borderColor: BORDER, color: INK, "--tw-ring-color": WINE }}
      />
      {hint ? (
        <span className="text-xs" style={{ color: INK_MUTED }}>
          {hint}
        </span>
      ) : null}
    </label>
  );
}

function Primary({ children, onClick, disabled, testId, type = "button" }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
      className="flex min-h-[52px] w-full items-center justify-center gap-2 rounded-xl px-5 text-base font-semibold text-white transition-opacity hover:opacity-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-40"
      style={{ background: WINE, "--tw-ring-color": WINE }}
    >
      {children}
    </button>
  );
}

function Quiet({ children, onClick, testId }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className="min-h-[44px] self-start px-1 text-sm underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2"
      style={{ color: INK_MUTED, "--tw-ring-color": WINE }}
    >
      {children}
    </button>
  );
}

/** One of the two people this page serves, when nobody told us which. */
function WhoChoice({ icon: Icon, title, body, onClick, testId }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className="flex min-h-[44px] w-full items-start gap-3 rounded-xl border bg-white p-4 text-left transition-all hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
      style={{ borderColor: BORDER, "--tw-ring-color": WINE }}
    >
      <span
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
        style={{ background: "rgba(15,91,71,0.09)", color: WINE }}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0">
        <span className="block text-base font-medium" style={{ color: INK }}>
          {title}
        </span>
        <span className="block text-xs" style={{ color: INK_MUTED }}>
          {body}
        </span>
      </span>
    </button>
  );
}

function CopyButton({ text, testId }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
        } catch (_) {
          // Clipboard is blocked in some browsers and every preview frame.
          // The link is on screen either way, so this never breaks the step.
        }
        setDone(true);
        setTimeout(() => setDone(false), 1600);
      }}
      className="flex min-h-[44px] shrink-0 items-center gap-1.5 rounded-lg border bg-white px-3 text-sm font-medium transition-colors"
      style={{ borderColor: BORDER, color: INK }}
    >
      {done ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {done ? "Copied" : "Copy link"}
    </button>
  );
}

/* ---------------------------------------------------------------- page */

const COACH_STEPS = ["academy", "batch", "children"];
const PARENT_STEPS = ["child"];

/**
 * The frame every step shares: progress, Back, title, lede, error.
 *
 * At module scope on purpose -- see the note where it is bound below.
 */
function StartShell({ children, step, total, title, lede, canBack, error, onBack }) {
  return (
    <div className="experience-page experience-activation-page flex min-h-screen items-center justify-center bg-[#F4EFE4] px-5 py-10 md:px-6 md:py-12">
      <div className="experience-activation-shell w-full max-w-[620px] cg-panel !p-6 md:!p-10">
        <div className="mb-6 flex items-center justify-between gap-4">
          {step ? (
            <p className="cg-eyebrow !mb-0" data-testid="start-step">
              Step {step} of {total}
            </p>
          ) : (
            <p className="cg-eyebrow !mb-0">ChessGuru for academies</p>
          )}
          {step ? (
            <div className="flex items-center gap-1.5" aria-hidden="true">
              {Array.from({ length: total }, (_, n) => n + 1).map((n) => (
                <span
                  key={n}
                  className="h-1 rounded-full transition-all"
                  style={{ width: n === step ? 22 : 10, background: n <= step ? WINE : BORDER }}
                />
              ))}
            </div>
          ) : null}
        </div>

        {canBack ? (
          <button
            type="button"
            onClick={onBack}
            data-testid="start-back"
            className="mb-3 -ml-1 inline-flex min-h-[44px] items-center gap-1.5 px-1 text-sm focus-visible:outline-none focus-visible:ring-2"
            style={{ color: INK_MUTED, "--tw-ring-color": WINE }}
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back
          </button>
        ) : null}

        <h1 className="cg-title !mt-0" style={{ color: INK }}>{title}</h1>
        {lede ? (
          <p className="cg-lede mb-7" style={{ color: INK_MUTED }}>{lede}</p>
        ) : (
          <div className="mb-7" />
        )}

        {error ? (
          <p
            className="mb-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700"
            data-testid="start-error"
          >
            {error}
          </p>
        ) : null}

        {children}
      </div>
    </div>
  );
}

export default function AcademyStart() {
  const navigate = useNavigate();

  // Who arrived. The landing page knows; it just never used to say.
  const [who, setWho] = useState(() => {
    try {
      const fromUrl = new URLSearchParams(window.location.search).get("who");
      if (fromUrl === "coach" || fromUrl === "parent") return fromUrl;
      const remembered = window.sessionStorage.getItem(WHO_KEY);
      if (remembered === "coach" || remembered === "parent") return remembered;
    } catch (_) { /* storage blocked */ }
    return null;
  });

  const [idx, setIdx] = useState(0);
  const [academy, setAcademy] = useState({ name: "", city: "" });
  const [batch, setBatch] = useState({ name: "", coach_name: "" });
  const [kids, setKids] = useState([{ display_name: "", parent_phone: "" }]);
  const [made, setMade] = useState(null); // { academy, batch_id, students: [] }
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [finished, setFinished] = useState(false);
  const madeRef = useRef({ academy_id: null, batch_id: null });

  const steps = who === "parent" ? PARENT_STEPS : COACH_STEPS;
  const stepKey = steps[idx];
  const total = steps.length;

  useEffect(() => {
    if (!who) return;
    try { window.sessionStorage.setItem(WHO_KEY, who); } catch (_) { /* blocked */ }
  }, [who]);

  // Their own name is the likeliest answer to "who coaches it", so offer it
  // rather than making them type it. Best-effort: a failure costs a prefill.
  useEffect(() => {
    let alive = true;
    fetch(`${API}/api/auth/me`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((u) => {
        if (alive && u && u.name) setBatch((b) => (b.coach_name ? b : { ...b, coach_name: u.name }));
      })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const back = () => {
    setError("");
    if (idx > 0) setIdx(idx - 1);
    else setWho(null);
  };

  /* -- the steps, each one a single question ------------------------- */

  const saveAcademy = () =>
    run(async () => {
      if (!madeRef.current.academy_id) {
        const out = await call("/academy", { name: academy.name.trim(), city: academy.city.trim() });
        madeRef.current.academy_id = out.academy_id;
        setMade((m) => ({ ...(m || {}), academy: out }));
      }
      setIdx(1);
    });

  const saveBatch = (skip) =>
    run(async () => {
      if (!skip && !madeRef.current.batch_id) {
        const out = await call(`/academy/${madeRef.current.academy_id}/batches`, {
          name: batch.name.trim(),
          coach_name: batch.coach_name.trim(),
        });
        madeRef.current.batch_id = out.batch_id;
      }
      if (skip) {
        setFinished(true);
        return;
      }
      setIdx(2);
    });

  const saveKids = (skip) =>
    run(async () => {
      if (skip) {
        setFinished(true);
        return;
      }
      const ready = kids.filter((k) => k.display_name.trim() && looksLikePhone(k.parent_phone));
      const students = [];
      for (const k of ready) {
        const out = await call(`/academy/batch/${madeRef.current.batch_id}/students`, {
          display_name: k.display_name.trim(),
          parent_phone: k.parent_phone.trim(),
        });
        students.push({ ...out, display_name: k.display_name.trim() });
      }
      setMade((m) => ({ ...(m || {}), students }));
      setFinished(true);
    });

  // A parent is the same three calls with the questions they can answer:
  // kind:"family" makes the academy and its one "Home" batch in one go.
  const saveFamily = () =>
    run(async () => {
      const home = await call("/academy", { kind: "family" });
      const out = await call(`/academy/batch/${home.batch_id}/students`, {
        display_name: kids[0].display_name.trim(),
        parent_phone: kids[0].parent_phone.trim(),
      });
      madeRef.current = { academy_id: home.academy_id, batch_id: home.batch_id };
      setMade({ academy: home, students: [{ ...out, display_name: kids[0].display_name.trim() }] });
      setFinished(true);
    });

  const kidsReady = useMemo(
    () => kids.some((k) => k.display_name.trim() && looksLikePhone(k.parent_phone)),
    [kids]
  );

  const setKid = (i, patch) =>
    setKids(kids.map((k, n) => (n === i ? { ...k, ...patch } : k)));

  /* -- shell --------------------------------------------------------- */

  // Spread into StartShell at each step, NOT wrapped in a local component.
  // Any component expression created during render -- even a one-line arrow
  // that just forwards props -- is a new type on every render, so React
  // unmounts and remounts the whole subtree and the input being typed into
  // loses focus after every keystroke. A plain object has no such problem.
  const shell = { total, error, onBack: back };

  /* -- finished ------------------------------------------------------ */

  if (finished) {
    const students = (made && made.students) || [];
    const name = (made && made.academy && made.academy.name) || "Your academy";
    return (
      <StartShell {...shell}
        title={who === "parent" ? "That's it." : `${name} is set up.`}
        lede={
          students.length
            ? "One thing left, and it is the one that matters. We do not read a child's games until a parent agrees."
            : "You can add your children whenever you are ready."
        }
      >
        {students.length ? (
          <div className="grid gap-2.5" data-testid="start-parent-links">
            {students.map((s) => (
              <div
                key={s.student_id}
                className="grid gap-2.5 rounded-xl border bg-white p-4 sm:flex sm:items-center sm:justify-between"
                style={{ borderColor: BORDER }}
              >
                <span className="text-base font-medium" style={{ color: INK }}>
                  {s.display_name}
                </span>
                <span className="flex flex-wrap gap-2">
                  {s.whatsapp ? (
                    <a
                      href={s.whatsapp}
                      target="_blank"
                      rel="noreferrer"
                      data-testid="start-whatsapp"
                      className="flex min-h-[44px] items-center rounded-lg px-3.5 text-sm font-semibold text-white"
                      style={{ background: WINE }}
                    >
                      Send on WhatsApp
                    </a>
                  ) : null}
                  {s.links && s.links.consent ? (
                    <CopyButton text={s.links.consent} testId="start-copy" />
                  ) : null}
                </span>
              </div>
            ))}
            <p className="mt-1 text-xs" style={{ color: INK_MUTED }}>
              Once a parent agrees, their child's games start being read, and
              your first report is ready the Sunday after.
            </p>
          </div>
        ) : null}

        <div className="mt-7">
          <Primary onClick={() => navigate("/academy")} testId="start-open-academy">
            {who === "parent" ? "Open my child's page" : "Open my academy"}
          </Primary>
        </div>
      </StartShell>
    );
  }

  /* -- who are you, only when nobody said -------------------------- */

  if (!who) {
    return (
      <StartShell {...shell} title="Who are you setting up?" lede="It changes what we ask you next, and nothing else.">
        <div className="grid gap-2.5">
          <WhoChoice
            icon={Users}
            title="I coach, or I run an academy"
            body="Batches, children, and a weekly report you approve for each parent."
            testId="start-who-coach"
            onClick={() => { setWho("coach"); setIdx(0); }}
          />
          <WhoChoice
            icon={UserIcon}
            title="I am a parent setting up my child"
            body="One child at home. You get the same weekly report an academy's parents get."
            testId="start-who-parent"
            onClick={() => { setWho("parent"); setIdx(0); }}
          />
        </div>
      </StartShell>
    );
  }

  /* -- parent: one question ---------------------------------------- */

  if (stepKey === "child") {
    const ready = kids[0].display_name.trim() && looksLikePhone(kids[0].parent_phone);
    return (
      <StartShell {...shell} step={1} title="Who are we coaching?" lede="Just the two things we cannot work without." canBack>
        <form
          className="grid gap-4"
          onSubmit={(e) => { e.preventDefault(); if (ready) saveFamily(); }}
        >
          <Field
            id="start-child-name"
            label="Your child's first name"
            value={kids[0].display_name}
            onChange={(v) => setKid(0, { display_name: v })}
            placeholder="Aarav"
            autoFocus
          />
          <Field
            id="start-child-phone"
            label="Your WhatsApp number"
            hint="This is where the weekly report goes. Nothing else is sent here."
            type="tel"
            value={kids[0].parent_phone}
            onChange={(v) => setKid(0, { parent_phone: v })}
            placeholder="98765 43210"
          />
          <Primary type="submit" disabled={!ready || busy} testId="start-finish-parent">
            {busy ? "Setting up…" : "Finish"}
          </Primary>
        </form>
      </StartShell>
    );
  }

  /* -- coach: three questions -------------------------------------- */

  if (stepKey === "academy") {
    const ready = academy.name.trim().length >= 2;
    return (
      <StartShell {...shell}
        step={1}
        title="What is your academy called?"
        lede="This is the name parents will see on their child's weekly report."
        canBack
      >
        <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); if (ready) saveAcademy(); }}>
          <Field
            id="start-academy-name"
            label="Academy name"
            value={academy.name}
            onChange={(v) => setAcademy({ ...academy, name: v })}
            placeholder="Knight School Pune"
            autoFocus
          />
          <Field
            id="start-academy-city"
            label="City"
            hint="Optional."
            value={academy.city}
            onChange={(v) => setAcademy({ ...academy, city: v })}
            placeholder="Pune"
          />
          <Primary type="submit" disabled={!ready || busy} testId="start-academy-next">
            {busy ? "Saving…" : "Continue"}
          </Primary>
        </form>
      </StartShell>
    );
  }

  if (stepKey === "batch") {
    const ready = batch.name.trim().length >= 2;
    return (
      <StartShell {...shell}
        step={2}
        title="Which batch shall we start with?"
        lede="You can add the rest later. One is enough to get going."
        canBack
      >
        <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); if (ready) saveBatch(false); }}>
          <Field
            id="start-batch-name"
            label="Batch name"
            value={batch.name}
            onChange={(v) => setBatch({ ...batch, name: v })}
            placeholder="Saturday batch"
            autoFocus
          />
          <Field
            id="start-batch-coach"
            label="Who coaches it"
            value={batch.coach_name}
            onChange={(v) => setBatch({ ...batch, coach_name: v })}
            placeholder="Coach Priya"
          />
          <Primary type="submit" disabled={!ready || busy} testId="start-batch-next">
            {busy ? "Saving…" : "Continue"}
          </Primary>
          <Quiet onClick={() => saveBatch(true)} testId="start-batch-skip">
            I'll set up my batches later
          </Quiet>
        </form>
      </StartShell>
    );
  }

  // children
  return (
    <StartShell {...shell}
      step={3}
      title="Add your first children"
      lede="We need a parent's WhatsApp number for each one — that is where we ask them to agree, and where their report goes."
      canBack
    >
      <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); if (kidsReady) saveKids(false); }}>
        {kids.map((k, i) => (
          <div
            key={i}
            className="grid gap-3 rounded-xl border p-4 sm:grid-cols-2"
            style={{ borderColor: BORDER, background: "white" }}
            data-testid="start-kid-row"
          >
            <Field
              id={`start-kid-name-${i}`}
              label="Child's first name"
              value={k.display_name}
              onChange={(v) => setKid(i, { display_name: v })}
              placeholder="Aarav"
              autoFocus={i === 0}
            />
            <Field
              id={`start-kid-phone-${i}`}
              label="Parent's WhatsApp"
              type="tel"
              value={k.parent_phone}
              onChange={(v) => setKid(i, { parent_phone: v })}
              placeholder="98765 43210"
            />
          </div>
        ))}

        <button
          type="button"
          onClick={() => setKids([...kids, { display_name: "", parent_phone: "" }])}
          data-testid="start-add-kid"
          className="flex min-h-[44px] items-center gap-1.5 self-start rounded-lg border bg-white px-3.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2"
          style={{ borderColor: BORDER, color: INK, "--tw-ring-color": WINE }}
        >
          <Plus className="h-3.5 w-3.5" /> Add another child
        </button>

        <Primary type="submit" disabled={!kidsReady || busy} testId="start-finish-coach">
          {busy ? "Adding…" : "Finish"}
        </Primary>
        <Quiet onClick={() => saveKids(true)} testId="start-kids-skip">
          I'll add my children later
        </Quiet>
      </form>
    </StartShell>
  );
}
