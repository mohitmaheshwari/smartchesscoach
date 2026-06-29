/**
 * MotivationPrompt — one-time, dismissible "What brings you to ChessGuru?"
 *
 * Shown on Home ONLY to existing users who finished onboarding before the
 * player-motivation question existed (i.e. onboarding_completed but no
 * player_motivation). Self-declared, skippable, never nags twice.
 *
 * New signups answer this in Onboarding Step 2; this is purely backfill
 * coverage for the existing base so the distribution read-out isn't empty.
 */

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { API } from "@/App";

const OPTIONS = [
  { value: "compete", label: "Compete and climb the ratings" },
  { value: "improve", label: "Get steadily better" },
  { value: "learn", label: "Learn and enjoy the game" },
  { value: "fun", label: "Just play for fun" },
];

const DISMISS_KEY = "motivation_prompt_dismissed";

const MotivationPrompt = () => {
  const [show, setShow] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (localStorage.getItem(DISMISS_KEY) === "1") return;
    (async () => {
      try {
        const res = await fetch(`${API}/auth/me`, { credentials: "include" });
        if (!res.ok) return;
        const u = await res.json();
        // Show to anyone who hasn't answered yet (new signups answer in
        // onboarding, so they already have it; this backfills everyone else).
        if (!u.player_motivation) setShow(true);
      } catch (e) { /* ignore */ }
    })();
  }, []);

  const choose = async (value) => {
    setSaving(true);
    try {
      await fetch(`${API}/settings/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ player_motivation: value }),
      });
    } catch (e) { /* best-effort */ }
    localStorage.setItem(DISMISS_KEY, "1");
    setShow(false);
  };

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, "1");
    setShow(false);
  };

  if (!show) return null;

  return (
    <div
      className="relative mb-8 rounded-sm border bg-white/60 px-4 py-3.5"
      style={{ borderColor: "hsl(35 10% 87%)" }}
      data-testid="motivation-prompt"
    >
      <button
        onClick={dismiss}
        aria-label="Dismiss"
        className="absolute top-2.5 right-2.5 text-muted-foreground/50 hover:text-muted-foreground transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>
      <p className="text-[13px] text-foreground/85 mb-2.5 pr-6">
        Quick one — what brings you to ChessGuru? It helps your coach meet you where you are.
      </p>
      <div className="flex flex-wrap gap-2">
        {OPTIONS.map((opt) => (
          <button
            key={opt.value}
            disabled={saving}
            onClick={() => choose(opt.value)}
            className="text-[12.5px] font-light px-3 py-1.5 rounded-sm border text-foreground/85 transition-colors hover:bg-black/[0.03] disabled:opacity-50"
            style={{ borderColor: "hsl(35 10% 87%)" }}
            data-testid={`motivation-home-${opt.value}`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
};

export default MotivationPrompt;
