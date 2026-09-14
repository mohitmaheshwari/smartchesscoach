/**
 * ACTIVATION HUB — value-first landing for new (and un-activated) users.
 *
 * Replaces the account wall: instead of "link your chess account" first, we
 * give instant value (a Chess-DNA puzzle check or a coached game) and ask to
 * connect later. Built for docs/activation_hub_scope.md (32% dead-on-arrival).
 *
 * Taking ANY primary action marks onboarding_completed (POST /settings/profile
 * sets it server-side) so the redirect-gate doesn't trap the user on /welcome.
 */

import { useEffect, useState } from "react";
import { ANALYTICS_EVENTS, track } from "@/lib/analytics";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Sparkles, Swords, ArrowRight } from "lucide-react";

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

const ActivationHub = () => {
  const navigate = useNavigate();
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

  // Mark onboarding seen (clears the redirect-gate) + save motivation if picked.
  const markSeen = async () => {
    try {
      await fetch(`${API}/settings/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        keepalive: true,
        body: JSON.stringify({
          player_motivation: motivation || null,
          self_assessed_level: selfLevel || null,
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
    <div className="experience-page experience-activation-page min-h-screen bg-[#F4EFE4] flex items-center justify-center px-6 py-12">
      <div className="experience-activation-shell w-full max-w-[620px] cg-panel !p-7 md:!p-10">
        <p className="cg-eyebrow">Welcome to ChessGuru</p>
        <h1 className="cg-title" style={{ color: INK }}>
          Let’s build a plan from your chess.
        </h1>
        <p className="cg-lede mb-8" style={{ color: INK_MUTED }}>
          You don’t need to know what is holding you back. That is my job. Show me how you think, and I’ll choose where we begin.
        </p>

        {/* Asked before the doors, not after: "Show me a few positions"
            starts the diagnostic immediately, so an answer collected below it
            arrives too late to choose the opening tier. Optional -- neither
            door is gated on it. */}
        <p className="text-[12px] uppercase tracking-wider mb-1" style={{ color: GOLD_TEXT }}>
          Where are you with chess right now?
        </p>
        <p className="text-[12px] mb-2.5" style={{ color: INK_MUTED }}>
          No wrong answer. It only decides where I start.
        </p>
        <div className="grid grid-cols-1 gap-2 mb-6">
          {SELF_LEVELS.map((l) => (
            <button
              key={l.value}
              type="button"
              onClick={() => setSelfLevel(l.value)}
              className="text-[13px] px-3 py-2.5 rounded-lg border text-left transition-colors"
              style={{
                borderColor: selfLevel === l.value ? WINE : BORDER,
                background: selfLevel === l.value ? "rgba(114,47,55,0.04)" : "white",
                color: INK,
              }}
              data-testid={`hub-self-level-${l.value}`}
            >
              {l.label}
            </button>
          ))}
        </div>

        {/* PRIMARY — Chess DNA (instant, unlimited) */}
        <button
          onClick={() => { track(ANALYTICS_EVENTS.FUNNEL_ACTIVATION_CTA, { cta: "diagnostic" }); go("/diagnostic"); }}
          disabled={busy}
          className="experience-activation-primary w-full text-left rounded-xl border p-4 mb-3 transition-all hover:bg-black/[0.02] disabled:opacity-50 cursor-pointer group"
          style={{ borderColor: WINE, background: "rgba(114,47,55,0.03)" }}
          data-testid="hub-diagnostic"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Sparkles className="w-5 h-5 shrink-0" style={{ color: WINE }} />
              <div>
                <div className="text-[15px] font-medium" style={{ color: INK }}>Show me a few positions</div>
                <div className="text-[12.5px]" style={{ color: INK_MUTED }}>No timer. I’ll watch what you notice and what you overlook.</div>
              </div>
            </div>
            <ArrowRight className="w-4 h-4 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: WINE }} />
          </div>
        </button>

        {/* SECONDARY — play a coached game */}
        <button
          onClick={() => { track(ANALYTICS_EVENTS.FUNNEL_ACTIVATION_CTA, { cta: "coached_game" }); go("/play-with-coach"); }}
          disabled={busy}
          className="experience-activation-secondary w-full text-left rounded-xl border p-4 mb-6 transition-all hover:bg-black/[0.02] disabled:opacity-50 cursor-pointer group"
          style={{ borderColor: BORDER, background: "white" }}
          data-testid="hub-play"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Swords className="w-5 h-5 shrink-0" style={{ color: GOLD_TEXT }} />
              <div>
                <div className="text-[15px] font-medium" style={{ color: INK }}>Play a game with your coach</div>
                <div className="text-[12.5px]" style={{ color: INK_MUTED }}>Make the moves yourself; your coach steps in only when it matters.</div>
              </div>
            </div>
            <ArrowRight className="w-4 h-4 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: GOLD_TEXT }} />
          </div>
        </button>

        {/* Motivation (optional, segments the base) */}
        <p className="text-[12px] uppercase tracking-wider mb-2.5" style={{ color: GOLD_TEXT }}>
          What brings you here?
        </p>
        <div className="grid grid-cols-1 gap-2 mb-7">
          {MOTIVATIONS.map((m) => (
            <button
              key={m.value}
              onClick={() => setMotivation(m.value)}
              className="text-[12.5px] font-light px-3 py-2 rounded-sm border text-left transition-colors"
              style={{
                borderColor: motivation === m.value ? WINE : BORDER,
                background: motivation === m.value ? "rgba(114,47,55,0.04)" : "white",
                color: INK,
                opacity: 0.85,
              }}
              data-testid={`hub-motivation-${m.value}`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Soft, benefit-framed account link */}
        <button
          onClick={() => navigate("/onboarding")}
          className="text-[13px] inline-flex items-center gap-1.5 transition-colors hover:underline"
          style={{ color: WINE }}
          data-testid="hub-connect"
        >
          Already play on Chess.com or Lichess? Connect so your coach can analyze your real games
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};

export default ActivationHub;
