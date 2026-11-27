/**
 * /academy2 — the academy set-up flow, every step, no backend.
 *
 * Same reason /lobby2 and /result2 exist: the only way to see this screen for
 * real is to create an account, press the right landing button, and then make
 * a real academy with real children in the production database. That makes a
 * visual bug expensive to catch, and this flow has exactly one chance to go
 * well — production has one academy (Mohit's own test) and zero parents who
 * have ever agreed.
 *
 * Renders the REAL AcademyStart with `fetch` stubbed, so every step, the
 * finish screen and both personas can be looked at in one place. Nothing
 * leaves the browser.
 *
 * Unauthenticated and unlinked, like /shell2, /theme2, /lobby2 and /result2.
 */
import React, { useEffect, useState } from "react";
import AcademyStart from "./AcademyStart";

const WHO = [
  ["coach", "A coach / academy — 3 steps"],
  ["parent", "A parent — 1 step"],
  ["ask", "Nobody told us — it asks"],
];

/**
 * Answers exactly what the flow asks for, in the shape the real API returns
 * (routes/academy.py:390, :435, :452). A wrong shape here would make the
 * preview lie, which is worse than not having one.
 */
function stubFetch() {
  let kid = 0;
  return (url, options) => {
    const path = String(url);
    const body = options && options.body ? JSON.parse(options.body) : {};
    const json = (data) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(data) });

    if (path.includes("/auth/me")) return json({ user_id: "u1", name: "Priya Nair" });

    if (/\/api\/academy$/.test(path)) {
      const family = body.kind === "family";
      return json({
        academy_id: "acad_preview",
        name: family ? "Priya Nair's family" : body.name,
        city: body.city || "",
        kind: family ? "family" : "academy",
        ...(family ? { batch_id: "batch_home" } : {}),
      });
    }
    if (path.includes("/batches")) {
      return json({ batch_id: "batch_preview", name: body.name, coach_name: body.coach_name });
    }
    if (path.includes("/students")) {
      kid += 1;
      const token = `preview${kid}`;
      return json({
        student_id: `kid_${kid}`,
        links: {
          consent: `https://chessguru.ai/consent/${token}`,
          report: `https://chessguru.ai/r/${token}`,
          homework: `https://chessguru.ai/homework/${token}`,
        },
        whatsapp: `https://wa.me/919876543210?text=${encodeURIComponent(
          "Hello. Knight School Pune uses ChessGuru for your child's chess lessons."
        )}`,
      });
    }
    return json({});
  };
}

/**
 * AcademyStart reads ?who= ONCE, in a useState initialiser, so the URL has to
 * be right BEFORE it mounts. Writing it from an effect does not work: the
 * child renders first and sees the old value, which is why the first version
 * of this page always showed the "who are you" screen whatever was selected.
 * Synchronous, every time, including the very first render.
 */
function writeWho(who) {
  const url = new URL(window.location.href);
  if (who === "ask") url.searchParams.delete("who");
  else url.searchParams.set("who", who);
  window.history.replaceState({}, "", url);
  try {
    if (who === "ask") window.sessionStorage.removeItem("chessguru.academy_who");
    else window.sessionStorage.setItem("chessguru.academy_who", who);
  } catch (e) { /* storage blocked */ }
}

export default function AcademyStartPreview() {
  const [who, setWho] = useState(() => {
    writeWho("coach");
    return "coach";
  });
  const [nonce, setNonce] = useState(0);

  // Stubbed before the first child render for the same reason.
  const [, setStubbed] = useState(() => {
    window.fetch = stubFetch();
    return true;
  });

  useEffect(() => () => setStubbed(false), []);

  const choose = (value) => {
    writeWho(value);
    setWho(value);
    setNonce((n) => n + 1);
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-2 px-4 py-4">
        {WHO.map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => choose(value)}
            className={`flex min-h-[44px] items-center rounded-lg border px-3 text-sm ${
              value === who
                ? "border-primary bg-primary/10 font-medium text-foreground"
                : "border-border text-muted-foreground"
            }`}
          >
            {label}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setNonce((n) => n + 1)}
          className="flex min-h-[44px] items-center rounded-lg border border-border px-3 text-sm text-muted-foreground"
        >
          Start over
        </button>
      </div>
      <AcademyStart key={`${who}-${nonce}`} />
    </div>
  );
}
