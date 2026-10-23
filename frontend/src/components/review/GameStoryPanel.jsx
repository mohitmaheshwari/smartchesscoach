/**
 * GameStoryPanel
 *
 * The story of the game, at the top of the review before the walkthrough.
 * docs/game_story_on_screen_scope.md (signed off 2026-10-21) and
 * docs/game_story_by_phase_scope.md v2 (signed off 2026-10-22).
 *
 * Two reading modes from the same ledger:
 *   - Story: a title, then the start, the middle and the finish in plain
 *     sentences, and a lesson only when the game earned one.
 *   - Coach notes: the same moments as concrete study notes -- what was
 *     played, what was best, what the other side could have done.
 *
 * Every line that names a move opens that move in the walkthrough, the
 * player's or the opponent's. The move card there explains it with the
 * pieces and squares, checked against the board.
 *
 * Rules it keeps, all decided server-side (services/game_ledger.py and
 * services/game_story_plan.py): no numbers, a lost game never leads with a
 * compliment, a mistake the coach cannot yet name is still told by where it
 * happened, and nothing is claimed that the ledger does not hold.
 *
 * Stories stored before the ledger existed have no plan; they render as the
 * earlier moment list.
 *
 * It fetches on its own and renders nothing until it has something to say,
 * so it can never hold up or break the start card.
 */
import { useEffect, useState } from "react";

import { API } from "@/App";
import { ANALYTICS_EVENTS, track } from "@/lib/analytics";

const MARK = {
  positive: { glyph: "✓", tone: "text-emerald-500" },
  negative: { glyph: "✗", tone: "text-red-500" },
  neutral: { glyph: "·", tone: "text-muted-foreground" },
};

export default function GameStoryPanel({ gameId, onOpenMove }) {
  const [story, setStory] = useState(null);
  const [mode, setMode] = useState("story");

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

  const open = (line, index, source) => {
    track(ANALYTICS_EVENTS.GAME_STORY_LINE_OPENED, {
      source,
      content_kind: line.kind || line.polarity,
      content_id: line.id || line.kind,
      position_index: index,
    });
    if (onOpenMove) {
      onOpenMove({
        move_number: line.move_number,
        move_san: line.move_san || line.san,
        side: line.side === "them" ? "them" : "you",
      });
    }
  };

  const stretches = (story.spans || []).filter((s) => s.display_name);
  const plan = story.plan;

  if (plan && Array.isArray(plan.chapters) && plan.chapters.length) {
    let lineIndex = -1;
    return (
      <div className="rounded-lg border border-border bg-background p-4" data-testid="game-story-panel">
        <div className="flex items-start justify-between gap-3">
          {/* The game's title and teaching (services/game_headline.py), the
              same ones the home card shows; the story type becomes the small
              label above. Without a written headline the type is the title. */}
          <div className="min-w-0">
            {story.headline?.title && plan.type?.title && (
              <p className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground mb-0.5">
                {plan.type.title}
              </p>
            )}
            <h3 className="font-heading text-base font-semibold text-foreground" data-testid="game-story-title">
              {story.headline?.title || plan.type?.title}
            </h3>
            {story.headline?.teaching && (
              <p className="mt-1 text-sm text-muted-foreground leading-snug" data-testid="game-story-teaching">
                {story.headline.teaching}
              </p>
            )}
          </div>
          <div className="flex shrink-0 rounded-md border border-border p-0.5 text-[11px]">
            {["story", "coach"].map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`rounded px-2 py-0.5 ${mode === m ? "bg-muted text-foreground" : "text-muted-foreground"}`}
                data-testid={`game-story-mode-${m}`}
              >
                {m === "story" ? "Story" : "Coach notes"}
              </button>
            ))}
          </div>
        </div>

        {mode === "story" ? (
          <div className="mt-3 space-y-3">
            {plan.chapters.map((chapter) => (
              <div key={chapter.id}>
                <p className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground mb-1">
                  {chapter.title}
                </p>
                <ul className="space-y-0.5">
                  {chapter.lines.map((line) => {
                    lineIndex += 1;
                    const index = lineIndex;
                    const mark = MARK[line.polarity] || MARK.neutral;
                    const body = (
                      <>
                        <span aria-hidden="true" className={`mt-0.5 w-4 shrink-0 text-center text-xs font-semibold ${mark.tone}`}>
                          {mark.glyph}
                        </span>
                        <span className="min-w-0 flex-1 text-sm text-foreground leading-snug">{line.text}</span>
                      </>
                    );
                    return (
                      <li key={`${chapter.id}-${index}`}>
                        {line.san ? (
                          <button
                            type="button"
                            onClick={() => open(line, index, "review_story")}
                            className="group flex w-full items-start gap-2 rounded-md px-1.5 py-1 text-left hover:bg-muted/50 transition-colors"
                            data-testid="game-story-line"
                          >
                            {body}
                            <span aria-hidden="true" className="text-muted-foreground/60 group-hover:text-foreground text-sm">›</span>
                          </button>
                        ) : (
                          <div className="flex items-start gap-2 px-1.5 py-1" data-testid="game-story-line">
                            {body}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
            {plan.lesson?.text && (
              <div className="rounded-md bg-muted/40 px-3 py-2" data-testid="game-story-lesson">
                <p className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground mb-0.5">
                  What to take from this game
                </p>
                <p className="text-sm text-foreground leading-snug">{plan.lesson.text}</p>
              </div>
            )}
          </div>
        ) : (
          <ul className="mt-3 space-y-1" data-testid="game-story-coach-notes">
            {(plan.coach_notes || []).map((note, i) => {
              const mark = MARK[note.polarity] || MARK.neutral;
              return (
                <li key={`${note.san}-${i}`}>
                  <button
                    type="button"
                    onClick={() => open(note, i, "review_coach_notes")}
                    className="group flex w-full items-start gap-2.5 rounded-md px-1.5 py-1 text-left hover:bg-muted/50 transition-colors"
                    data-testid="game-story-coach-note"
                  >
                    <span aria-hidden="true" className={`mt-0.5 w-4 shrink-0 text-center text-xs font-semibold ${mark.tone}`}>
                      {mark.glyph}
                    </span>
                    <span className="font-mono text-sm w-14 shrink-0 text-foreground">{note.san}</span>
                    <span className="min-w-0 flex-1 text-sm text-foreground/90 leading-snug">
                      {note.side === "them" ? "Their move. " : ""}{note.text}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        {stretches.length > 0 && (
          <div className="mt-4">
            <p className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground mb-1.5">
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

  // A story stored before the ledger existed: the earlier moment list.
  const moments = (story.moments_showable || []).filter((m) => m.display_name && m.move_san);
  if (!moments.length && !stretches.length) return null;

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
                    onClick={() => open({ ...m, side: "you" }, i, "review")}
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
