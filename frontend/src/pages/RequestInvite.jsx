/**
 * Request an invite.
 *
 * ChessGuru is invite-only before launch: the landing page's calls to action
 * come here instead of starting Google sign-in, and anyone who tries to sign
 * in with an uninvited account is bounced here with ?status=not_invited
 * rather than shown an error. See docs/invite_only_signup_scope.md.
 *
 * The page reads /api/signup-status, so on the day Mohit sets
 * SIGNUPS_OPEN=true it offers sign-in instead of the form with no code change.
 */

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Check, Loader2 } from "lucide-react";
import { API } from "@/App";

export default function RequestInvite() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const bouncedFromSignIn = params.get("status") === "not_invited";

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [signupsOpen, setSignupsOpen] = useState(false);

  useEffect(() => {
    fetch(`${API}/signup-status`)
      .then((r) => r.json())
      .then((d) => setSignupsOpen(d.signups_open === true))
      .catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          name,
          note,
          source: bouncedFromSignIn ? "signin_bounce" : "landing",
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Something went wrong");
      setDone(true);
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#071411] px-5 py-16 text-white">
      <div className="mx-auto w-full max-w-md">
        <button
          type="button"
          onClick={() => navigate("/")}
          className="text-sm text-white/50 transition-colors hover:text-white"
        >
          ← ChessGuru
        </button>

        {done ? (
          <div className="mt-10" data-testid="invite-done">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#7FB069]">
              <Check className="h-6 w-6 text-[#071411]" />
            </div>
            <h1 className="mt-6 font-heading text-3xl font-semibold">You're on the list.</h1>
            <p className="mt-4 leading-7 text-white/70">
              We're letting people in a few at a time so we can actually read the
              feedback. When it's your turn you'll get an email, and you'll sign
              in with the same address you gave us.
            </p>
          </div>
        ) : (
          <>
            <p className="mt-10 text-[10px] font-bold uppercase tracking-[0.22em] text-[#7FB069]">
              Opening soon
            </p>
            <h1 className="mt-4 font-heading text-3xl font-semibold leading-tight sm:text-4xl">
              {bouncedFromSignIn ? "You're not on the list yet" : "Ask for an invite"}
            </h1>
            <p className="mt-4 leading-7 text-white/70">
              {bouncedFromSignIn
                ? "ChessGuru is invite-only while we're still building. Leave your details and we'll add you."
                : "ChessGuru is invite-only for now. Tell us where to reach you and we'll open it up to you soon."}
            </p>

            <form onSubmit={submit} className="mt-8 space-y-4" data-testid="invite-form">
              <div>
                <label htmlFor="inv-email" className="text-sm text-white/60">Email</label>
                <input
                  id="inv-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="mt-1.5 w-full rounded-xl border border-white/15 bg-white/5 px-4 py-3 text-white placeholder-white/30 focus:border-[#7FB069] focus:outline-none"
                />
                <p className="mt-1.5 text-xs text-white/40">
                  Use the address you'd sign in with — Google works best.
                </p>
              </div>
              <div>
                <label htmlFor="inv-name" className="text-sm text-white/60">Name</label>
                <input
                  id="inv-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  className="mt-1.5 w-full rounded-xl border border-white/15 bg-white/5 px-4 py-3 text-white placeholder-white/30 focus:border-[#7FB069] focus:outline-none"
                />
              </div>
              <div>
                <label htmlFor="inv-note" className="text-sm text-white/60">
                  Anything about your chess? <span className="text-white/35">(optional)</span>
                </label>
                <textarea
                  id="inv-note"
                  rows={3}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Rating, where you play, what you're stuck on"
                  className="mt-1.5 w-full rounded-xl border border-white/15 bg-white/5 px-4 py-3 text-white placeholder-white/30 focus:border-[#7FB069] focus:outline-none"
                />
              </div>

              {error && <p className="text-sm text-red-300" data-testid="invite-error">{error}</p>}

              <button
                type="submit"
                disabled={submitting}
                data-testid="invite-submit"
                className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-[#7FB069] px-6 py-3.5 text-sm font-bold text-[#071411] transition-transform hover:-translate-y-0.5 disabled:opacity-60"
              >
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {submitting ? "Sending…" : "Request an invite"}
              </button>
            </form>

            <p className="mt-6 text-sm text-white/45">
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => navigate("/login")}
                className="font-semibold text-white underline decoration-[#7FB069] decoration-2 underline-offset-4"
                data-testid="invite-signin-link"
              >
                Sign in
              </button>
            </p>
            {signupsOpen && (
              <p className="mt-3 text-sm text-[#7FB069]" data-testid="invite-open-notice">
                ChessGuru is open now — you can sign in directly.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
