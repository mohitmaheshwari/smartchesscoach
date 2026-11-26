/**
 * A bar that explains why the app is refusing everything.
 *
 * Before this, the guard did its job and the app looked broken: Layout's
 * coach-pulse poll asked three endpoints a minute, each was refused, each 403
 * was swallowed, and the player saw widgets that simply never filled in. The
 * refusal already carried the reason and now carries a destination; this shows
 * them.
 *
 * Two rules it keeps:
 *
 *  - It renders the server's sentence and a link, and nothing about the
 *    position. The entire reason the guard exists is that no evaluation may
 *    reach a player mid-game.
 *  - It takes itself away. While it is on screen — and only then — it asks the
 *    one endpoint playing is allowed to use whether the game is over, so a
 *    finished game clears it without the player doing anything.
 */

import React, { useEffect, useRef } from "react";

const API = process.env.REACT_APP_BACKEND_URL || "";
// Only while the bar is up, and slow: this is "has it finished yet", not a
// board. The board itself polls at 1.5s; nothing here needs that.
const CLEAR_POLL_MS = 8000;

export default function LiveGameBar({ notice, onClear }) {
  const timer = useRef(null);

  useEffect(() => {
    if (!notice || !onClear) return undefined;
    const check = async () => {
      try {
        const response = await fetch(`${API}/api/coach/play/live/state`, {
          credentials: "include",
        });
        if (!response.ok) return;
        const body = await response.json();
        // Gone, or over: either way this bar has nothing left to say.
        if (!body.playing || (body.game && body.game.finished)) onClear();
      } catch (_) {
        // Offline, or the endpoint is unhappy. Leave the bar where it is
        // rather than clearing it on a guess.
      }
    };
    timer.current = setInterval(check, CLEAR_POLL_MS);
    return () => clearInterval(timer.current);
  }, [notice, onClear]);

  if (!notice) return null;
  // On the board itself the screen already says all of this.
  const here = typeof window !== "undefined" ? window.location.pathname : "";
  if (here.startsWith("/play-with-coach")) return null;

  return (
    <div
      className="fixed inset-x-0 top-0 z-[60] flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-b border-emerald-500/40 bg-emerald-950/95 px-4 py-2.5 text-center text-sm text-emerald-50 backdrop-blur"
      role="status"
      data-testid="live-game-bar"
    >
      <span>{notice.message}</span>
      <a
        href={notice.open}
        data-testid="live-game-bar-link"
        className="rounded-lg bg-emerald-500 px-3 py-1 text-xs font-semibold text-emerald-950 hover:bg-emerald-400"
      >
        {notice.label}
      </a>
    </div>
  );
}
