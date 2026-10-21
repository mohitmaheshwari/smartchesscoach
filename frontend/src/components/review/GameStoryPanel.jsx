/**
 * GameStoryPanel
 *
 * What this game left the player, at the top of the review before the
 * walkthrough. docs/game_story_on_screen_scope.md, signed off 2026-10-21.
 *
 * The story says WHERE to look; the move card the row opens says WHY, with
 * the pieces and squares, checked against the board. So a row here is short
 * on purpose: the move, and one plain line.
 *
 * Rules it keeps, all decided server-side by services/game_story.py:
 *   - each line is located by the move itself ("Kg3"), never a move number
 *   - a lost game never leads with a compliment
 *   - a mistake the coach cannot yet name is still shown, by where it
 *     happened, never by a guessed cause
 *
 * It fetches on its own and renders nothing until it has something to say,
 * so it can never hold up or break the start card.
 */
import { useEffect, useState } from "react";

import { API } from "@/App";
import { ANALYTICS_EVENTS, track } from "@/lib/analytics";

export default function GameStoryPanel({ gameId, onOpenMove }) {
  const [story, setStory] = useState(null);

  useEffect(() => {
    if (!gameId) return undefined;
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API}/games/${gameId}/story`, { credentials: "include" });
        if (!alive || !res.ok) return;
        const body = await res.json();
        if (alive && body) setStory(body);
      } catch {
        /* The review must render without the story. */
      }
    })();
    return () => { alive = false; };
  }, [gameId]);

  if (!story) return null;
  const moments = (story.moments_showable || []).filter((m) => m.display_name && m.move_san);
  const stretches = (story.spans || []).filter((s) => s.display_name);
  if (!moments.length && !stretches.length) return null;

  const open = (moment, index) => {
    track(ANALYTICS_EVENTS.GAME_STORY_LINE_OPENED, {
      source: "review",
      content_kind: moment.polarity,
      content_id: moment.id,
      position_index: index,
    });
    if (onOpenMove) onOpenMove(moment);
  };

  return (
    <div className="rounded-lg border border-border bg-background p-4" data-testid="game-story-panel">
      {moments.length > 0 && (
        <>
          <p className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground mb-2">
            What this game left you
          </p>
          <ul className="space-y-1">
            {moments.map((m, i) => {
              const good = m.polarity === "positive";
              return (
                <li key={`${m.id}-${m.move_san}-${i}`}>
                  <button
                    type="button"
                    onClick={() => open(m, i)}
                    className="group flex w-full items-start gap-2.5 rounded-md px-2 py-1.5 text-left hover:bg-muted/50 transition-colors"
                    data-testid="game-story-moment"
                  >
                    <span
                      aria-hidden="true"
                      className={`mt-0.5 w-4 shrink-0 text-center text-xs font-semibold ${
                        good ? "text-emerald-500" : "text-red-500"
                      }`}
                    >
                      {good ? "✓" : "✗"}
                    </span>
                    <span className="font-mono text-sm w-14 shrink-0 text-foreground">{m.move_san}</span>
                    <span className="min-w-0 flex-1">
                      {/* A row is a title, so no full stop. The names come
                          from three owners and only some carry one. */}
                      <span className="block text-sm text-foreground leading-snug">
                        {String(m.display_name).replace(/[.]+$/, "")}
                      </span>
                      {m.display_detail && (
                        <span className="block text-xs text-muted-foreground leading-relaxed mt-0.5">
                          {m.display_detail}
                        </span>
                      )}
                    </span>
                    <span aria-hidden="true" className="text-muted-foreground/60 group-hover:text-foreground text-sm">
                      ›
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {stretches.length > 0 && (
        <div className={moments.length > 0 ? "mt-4" : ""}>
          <p className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground mb-2">
            All game long
          </p>
          <ul className="space-y-1.5" data-testid="game-story-stretches">
            {stretches.map((s, i) => (
              <li key={`${s.id}-${i}`} className="flex items-start gap-2.5 px-2 text-sm text-foreground/90 leading-snug">
                <span aria-hidden="true" className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                <span>{s.display_name}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
