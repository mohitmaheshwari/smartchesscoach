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

import { useState } from "react";
import { track } from "@/lib/analytics";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Sparkles, Swords, ArrowRight } from "lucide-react";

const WINE = "#722F37";
const GOLD_TEXT = "#8B6F1F";
const BORDER = "hsl(35 10% 87%)";

const MOTIVATIONS = [
  { value: "compete", label: "Compete and climb the ratings" },
  { value: "improve", label: "Get steadily better" },
  { value: "learn", label: "Learn and enjoy the game" },
  { value: "fun", label: "Just play for fun" },
];

const ActivationHub = () => {
  const navigate = useNavigate();
  const [motivation, setMotivation] = useState("");
  const [busy, setBusy] = useState(false);

  // Mark onboarding seen (clears the redirect-gate) + save motivation if picked.
  const markSeen = async () => {
    try {
      await fetch(`${API}/settings/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ player_motivation: motivation || null }),
      });
    } catch (e) { /* best-effort — never block the action */ }
  };

  const go = async (path) => {
    if (busy) return;
    setBusy(true);
    await markSeen();
    navigate(path);
  };

  return (
    <div className="min-h-screen bg-[hsl(40_30%_98%)] flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-[520px]">
        <p className="text-[13px] text-muted-foreground mb-1">Welcome to ChessGuru 👋</p>
        <h1 className="font-serif text-[28px] md:text-[32px] leading-tight text-foreground mb-2">
          Let's see how you play.
        </h1>
        <p className="text-[14px] text-muted-foreground mb-8 leading-relaxed">
          No account needed yet — start with a quick check or a game, and your coach
          gets to work right away.
        </p>

        {/* PRIMARY — Chess DNA (instant, unlimited) */}
        <button
          onClick={() => { track("funnel_activation_cta", { cta: "diagnostic" }); go("/diagnostic"); }}
          disabled={busy}
          className="w-full text-left rounded-sm border p-4 mb-3 transition-all hover:bg-black/[0.02] disabled:opacity-50 cursor-pointer group"
          style={{ borderColor: WINE, background: "rgba(114,47,55,0.03)" }}
          data-testid="hub-diagnostic"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Sparkles className="w-5 h-5 shrink-0" style={{ color: WINE }} />
              <div>
                <div className="text-[15px] font-medium text-foreground">Get your free Chess DNA</div>
                <div className="text-[12.5px] text-muted-foreground">A few quick puzzles — find your level and your weak spots.</div>
              </div>
            </div>
            <ArrowRight className="w-4 h-4 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: WINE }} />
          </div>
        </button>

        {/* SECONDARY — play a coached game */}
        <button
          onClick={() => { track("funnel_activation_cta", { cta: "coached_game" }); go("/play-with-coach"); }}
          disabled={busy}
          className="w-full text-left rounded-sm border p-4 mb-6 transition-all hover:bg-black/[0.02] disabled:opacity-50 cursor-pointer group"
          style={{ borderColor: BORDER, background: "white" }}
          data-testid="hub-play"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Swords className="w-5 h-5 shrink-0" style={{ color: GOLD_TEXT }} />
              <div>
                <div className="text-[15px] font-medium text-foreground">Play a game with your coach</div>
                <div className="text-[12.5px] text-muted-foreground">Guided game — your coach talks you through it.</div>
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
              className="text-[12.5px] font-light px-3 py-2 rounded-sm border text-left text-foreground/85 transition-colors"
              style={{
                borderColor: motivation === m.value ? WINE : BORDER,
                background: motivation === m.value ? "rgba(114,47,55,0.04)" : "white",
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
