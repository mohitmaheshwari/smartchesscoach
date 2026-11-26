/**
 * ACTIVATION HUB — value-first landing for new (and un-activated) users.
 *
 * Replaces the account wall: instead of "link your chess account" first, we
 * give instant value (a Chess-DNA puzzle check or a coached game) and ask to
 * connect later. Built for docs/activation_hub_scope.md (32% dead-on-arrival).
 *
 * Taking ANY primary action marks onboarding_completed (POST /settings/profile
 * sets it server-side) so the redirect-gate doesn't trap the user on /welcome.
 *
 * ───────────────────────────────────────────────────────────────────────────
 * 2026-11-26 — THREE STEPS, not one screen.
 *
 * Mohit: "right now we are doing everything at same step. We should first pull
 * up user reason for joining, once they join us, if they have an online
 * account, and then the third section — show me a few positions or play
 * online."
 *
 * So: why you came → do you already play online → where we start.
 *
 * The one thing that must NOT come back is the account wall. The scope doc
 * (docs/activation_hub_scope.md:9) puts a number on it: 32% of signups were
 * dead on arrival because onboarding demanded a chess account BEFORE giving
 * anything. Step 2 therefore asks about an account but never requires one —
 * "Not yet" is a full-width, equally weighted choice that moves straight on,
 * and nothing in step 3 is gated on having answered anything.
 *
 * Why the self-assessed level moved to step 3 and is only asked of players
 * who say they do not play online: for anyone who connects an account we read
 * the real rating from their games, so asking is asking a question we can
 * already answer. It still decides which tier the diagnostic opens on, and
 * unanswered still falls back to mid.
 */

import { useEffect, useState } from "react";
import { ANALYTICS_EVENTS, track } from "@/lib/analytics";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Sparkles, Swords, ArrowRight, ArrowLeft, Link2, CircleSlash } from "lucide-react";

const WINE = "#0F5B47";
const GOLD_TEXT = "#28745D";
const BORDER = "hsl(35 10% 87%)";
// This page is deliberately light-mode-only (fixed light background, wine/gold
// accents) regardless of the user's global theme — Tailwind's theme-aware
// text-foreground/text-muted-foreground resolve to near-white in dark mode
// (see .dark in index.css), which is nearly invisible against this page's
// always-light background. Pinned to the light-mode --foreground/--muted-foreground
// values directly so the text stays readable no matter which theme is active.
const INK = "hsl(222 47% 11%)";
const INK_MUTED = "hsl(220 9% 46%)";

// Asked here, on the screen a player with no account actually lands on.
// This question used to live on /onboarding -- which is reached ONLY via the
// "Already play on Chess.com or Lichess?" link, so the one question built for
// players without an account was shown only to players who had one. It
// decides which tier the diagnostic opens on; unanswered falls back to mid,
// which is the behaviour that existed before it was asked at all.
const SELF_LEVELS = [
  { value: "learning_moves", label: "I’m still learning how the pieces move" },
  { value: "know_rules", label: "I know the rules and play with friends" },
  { value: "plays_regularly", label: "I play regularly and know some openings" },
  { value: "experienced", label: "I’m experienced — I know my theory" },
];

const MOTIVATIONS = [
  { value: "compete", label: "Prepare for serious games" },
  { value: "improve", label: "Get steadily better" },
  { value: "learn", label: "Learn and enjoy the game" },
  { value: "fun", label: "Just play for fun" },
];

const STEP_TITLE = {
  1: "What brings you here?",
  2: "Do you already play online?",
  3: "Where shall we start?",
};

const STEP_LEDE = {
  1: "It changes what I work on with you. There is no wrong answer.",
  2: "If you do, I’ll read the games you have already played instead of starting you from nothing.",
  3: "Either one tells me something. Pick whichever you feel like right now.",
};

/** Shared choice row: full width, 44px minimum, selected state on the border. */
function Choice({ label, selected, onClick, testId, small }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className="flex w-full min-h-[44px] items-center rounded-lg border px-3.5 py-2.5 text-left transition-colors hover:bg-black/[0.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
      style={{
        borderColor: selected ? WINE : BORDER,
        background: selected ? "rgba(15,91,71,0.05)" : "white",
        color: INK,
        fontSize: small ? "13px" : "14px",
        "--tw-ring-color": WINE,
      }}
    >
      {label}
    </button>
  );
}

const ActivationHub = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [motivation, setMotivation] = useState("");
  const [selfLevel, setSelfLevel] = useState("");
  const [busy, setBusy] = useState(false);
  // Until this resolves we render nothing, so an already-activated user never
  // sees "Let's build a plan from your chess" flash before being sent home.
  const [checking, setChecking] = useState(true);

  // /welcome is mounted with skipOnboardingCheck, so ProtectedRoute's gate is
  // deliberately off here -- which means this page must ask for itself. Every
  // sign-in entry point on the landing page used to land returning users here,
  // and with no check they were asked to start over on top of a full history.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/onboarding/status`, {
          credentials: "include",
        });
        if (cancelled) return;
        if (res.ok) {
          const data = await res.json();
          if (data.needs_onboarding === false) {
            navigate("/home", { replace: true });
            return;
          }
        }
      } catch (e) {
        // Never trap the user on a blank page because the check failed --
        // fall through and show the hub.
      }
      if (!cancelled) setChecking(false);
    })();
    return () => { cancelled = true; };
  }, [navigate]);

  // Mark onboarding seen (clears the redirect-gate) + save what was picked.
  const markSeen = async (level) => {
    try {
      await fetch(`${API}/settings/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        keepalive: true,
        body: JSON.stringify({
          player_motivation: motivation || null,
          self_assessed_level: (level ?? selfLevel) || null,
        }),
      });
    } catch (e) { /* best-effort — never block the action */ }
  };

  const go = (path) => {
    if (busy) return;
    setBusy(true);
    // The value action must not depend on a profile-write round trip. Start
    // the authenticated save first (keepalive lets it finish after unmount),
    // then navigate immediately. The route state skips exactly this one
    // onboarding check; authentication is still required.
    void markSeen();
    navigate(path, { state: { fromActivationHub: true } });
  };

  if (checking) return null;

  return (
    <div className="experience-page experience-activation-page min-h-screen bg-[#F4EFE4] flex items-center justify-center px-5 py-10 md:px-6 md:py-12">
      <div className="experience-activation-shell w-full max-w-[620px] cg-panel !p-6 md:!p-10">

        {/* ── where you are ─────────────────────────────────── */}
        <div className="mb-6 flex items-center justify-between gap-4">
          <p className="cg-eyebrow !mb-0" data-testid="hub-step">
            Step {step} of 3
          </p>
          <div className="flex items-center gap-1.5" aria-hidden="true">
            {[1, 2, 3].map((n) => (
              <span
                key={n}
                className="h-1 rounded-full transition-all"
                style={{
                  width: n === step ? 22 : 10,
                  background: n <= step ? WINE : BORDER,
                }}
              />
            ))}
          </div>
        </div>

        <h1 className="cg-title !mt-0" style={{ color: INK }}>
          {STEP_TITLE[step]}
        </h1>
        <p className="cg-lede mb-7" style={{ color: INK_MUTED }}>
          {STEP_LEDE[step]}
        </p>

        {/* ── 1. why you came ───────────────────────────────── */}
        {step === 1 && (
          <div className="grid grid-cols-1 gap-2.5">
            {MOTIVATIONS.map((m) => (
              <Choice
                key={m.value}
                label={m.label}
                selected={motivation === m.value}
                testId={`hub-motivation-${m.value}`}
                onClick={() => {
                  setMotivation(m.value);
                  setStep(2);
                }}
              />
            ))}
            <button
              type="button"
              onClick={() => setStep(2)}
              data-testid="hub-skip-motivation"
              className="mt-1 min-h-[44px] self-start px-1 text-[13px] underline-offset-4 hover:underline"
              style={{ color: INK_MUTED }}
            >
              I’d rather not say
            </button>
          </div>
        )}

        {/* ── 2. an account, offered but never demanded ─────── */}
        {step === 2 && (
          <div className="grid grid-cols-1 gap-3">
            {/* Does NOT call markSeen(): connecting is only finished once an
                account is verified and its games import, and Onboarding
                completes it there. Someone who opens this and backs out is
                not activated. */}
            <button
              onClick={() => {
                track(ANALYTICS_EVENTS.FUNNEL_ACTIVATION_CTA, { cta: "connect_games" });
                navigate("/onboarding");
              }}
              disabled={busy}
              data-testid="hub-connect"
              className="group w-full rounded-xl border p-4 text-left transition-all hover:-translate-y-0.5 hover:bg-black/[0.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50"
              style={{ borderColor: WINE, background: "white", "--tw-ring-color": WINE }}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <span
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                    style={{ background: "rgba(15,91,71,0.09)", color: WINE }}
                  >
                    <Link2 className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="text-[15px] font-medium" style={{ color: INK }}>
                      Yes — connect Chess.com or Lichess
                    </div>
                    <div className="text-[12.5px]" style={{ color: INK_MUTED }}>
                      I’ll study the games you already played and build your plan from those.
                    </div>
                  </div>
                </div>
                <ArrowRight className="h-4 w-4 shrink-0 opacity-60 transition-all group-hover:translate-x-0.5 group-hover:opacity-100" style={{ color: WINE }} />
              </div>
            </button>

            <button
              onClick={() => setStep(3)}
              disabled={busy}
              data-testid="hub-no-account"
              className="group w-full rounded-xl border p-4 text-left transition-all hover:-translate-y-0.5 hover:bg-black/[0.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50"
              style={{ borderColor: BORDER, background: "white", "--tw-ring-color": WINE }}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <span
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                    style={{ background: "rgba(0,0,0,0.04)", color: INK_MUTED }}
                  >
                    <CircleSlash className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="text-[15px] font-medium" style={{ color: INK }}>
                      Not yet
                    </div>
                    <div className="text-[12.5px]" style={{ color: INK_MUTED }}>
                      Then we start from how you play with me. You can connect later.
                    </div>
                  </div>
                </div>
                <ArrowRight className="h-4 w-4 shrink-0 opacity-60 transition-all group-hover:translate-x-0.5 group-hover:opacity-100" style={{ color: INK_MUTED }} />
              </div>
            </button>
          </div>
        )}

        {/* ── 3. the first thing we actually do ─────────────── */}
        {step === 3 && (
          <>
            {/* Only asked of players with no account to read a rating from. */}
            <p className="mb-1 text-[12px] uppercase tracking-wider" style={{ color: GOLD_TEXT }}>
              Where are you with chess right now?
            </p>
            <p className="mb-2.5 text-[12px]" style={{ color: INK_MUTED }}>
              No wrong answer. It only decides where I start.
            </p>
            <div className="mb-7 grid grid-cols-1 gap-2">
              {SELF_LEVELS.map((l) => (
                <Choice
                  key={l.value}
                  small
                  label={l.label}
                  selected={selfLevel === l.value}
                  testId={`hub-self-level-${l.value}`}
                  onClick={() => setSelfLevel(l.value)}
                />
              ))}
            </div>

            {/* PRIMARY — Chess DNA (instant, unlimited). The elevated
                treatment belongs on the action the scope doc names primary. */}
            <button
              onClick={() => { track(ANALYTICS_EVENTS.FUNNEL_ACTIVATION_CTA, { cta: "diagnostic" }); go("/diagnostic"); }}
              disabled={busy}
              className="experience-activation-primary group relative mb-3 w-full overflow-hidden rounded-2xl border-2 p-5 text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50 md:p-6"
              style={{
                borderColor: WINE,
                background: "linear-gradient(135deg, rgba(182,255,61,0.22) 0%, rgba(232,255,200,0.5) 48%, rgba(255,255,255,0.96) 100%)",
                boxShadow: "0 18px 45px rgba(15, 91, 71, 0.12)",
                "--tw-ring-color": WINE,
              }}
              data-testid="hub-diagnostic"
            >
              <div
                aria-hidden="true"
                className="absolute -right-10 -top-12 h-32 w-32 rounded-full blur-2xl"
                style={{ background: "rgba(182,255,61,0.35)" }}
              />
              <div className="relative flex items-center justify-between gap-4">
                <div className="flex min-w-0 items-start gap-4">
                  <span
                    className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
                    style={{ background: WINE, color: "white" }}
                  >
                    <Sparkles className="h-5 w-5" />
                  </span>
                  <div className="min-w-0">
                    <span
                      className="mb-2 inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]"
                      style={{ background: "rgba(15,91,71,0.1)", color: WINE }}
                    >
                      Start here
                    </span>
                    <div className="text-[17px] font-semibold leading-snug md:text-[19px]" style={{ color: INK }}>
                      Show me a few positions
                    </div>
                    <div className="mt-1.5 max-w-[420px] text-[13px] leading-relaxed" style={{ color: INK_MUTED }}>
                      No timer. I’ll watch what you notice and what you overlook.
                    </div>
                  </div>
                </div>
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-transform group-hover:translate-x-1"
                  style={{ background: "#B6FF3D", color: "#071B14" }}
                >
                  <ArrowRight className="h-4 w-4" />
                </span>
              </div>
            </button>

            {/* SECONDARY — play a coached game */}
            <button
              onClick={() => { track(ANALYTICS_EVENTS.FUNNEL_ACTIVATION_CTA, { cta: "coached_game" }); go("/play-with-coach"); }}
              disabled={busy}
              className="experience-activation-secondary group w-full rounded-xl border p-4 text-left transition-all hover:-translate-y-px hover:bg-black/[0.02] hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50"
              style={{ borderColor: BORDER, background: "white", "--tw-ring-color": WINE }}
              data-testid="hub-play"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <Swords className="h-5 w-5 shrink-0" style={{ color: GOLD_TEXT }} />
                  <div>
                    <div className="text-[15px] font-medium" style={{ color: INK }}>Play a game with your coach</div>
                    <div className="text-[12.5px]" style={{ color: INK_MUTED }}>Make the moves yourself; your coach steps in only when it matters.</div>
                  </div>
                </div>
                <ArrowRight className="h-4 w-4 shrink-0 opacity-60 transition-all group-hover:translate-x-0.5 group-hover:opacity-100" style={{ color: GOLD_TEXT }} />
              </div>
            </button>
          </>
        )}

        {/* ── back ──────────────────────────────────────────── */}
        {step > 1 && (
          <button
            type="button"
            onClick={() => setStep(step - 1)}
            data-testid="hub-back"
            className="mt-6 inline-flex min-h-[44px] items-center gap-1.5 text-[13px] underline-offset-4 hover:underline"
            style={{ color: INK_MUTED }}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back
          </button>
        )}
      </div>
    </div>
  );
};

export default ActivationHub;
