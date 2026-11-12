/**
 * BetweenGamesPanel
 *
 * What a coach says between games (docs/coach_pages_scope.md, "Home"):
 * whether the last game repeated one of his habits, what to watch for in the
 * next one, his costliest opening habit, whether to stop for today, and a
 * position from his own games to play. The last game itself is told by
 * LastGameCard just above; this panel adds only what that card cannot.
 *
 * Reads the player file (useCoachFile), which the analysis worker keeps
 * current, so this never computes anything. For a player without the coach
 * pages the server answers {enabled: false} and this renders nothing.
 */
import { Link } from "react-router-dom";

import { useCoachFile } from "@/lib/coachFile";
import {
  LastGameRepeat,
  OpeningHabit,
  PlayPositions,
  SittingNote,
  WatchFor,
} from "@/components/coachfile/CoachFileBlocks";

export default function BetweenGamesPanel() {
  const data = useCoachFile();

  if (!data || !data.enabled) return null;

  if (data.state === "building") {
    return (
      <section
        data-testid="between-games-building"
        className="mb-10 rounded-panel border border-border/70 bg-card p-6 md:p-8"
      >
        <p className="cg-eyebrow">Between games</p>
        <p className="mt-3 text-body text-muted-foreground">
          Your coach is reading your games. This takes a moment the first time.
        </p>
      </section>
    );
  }

  const openings = Array.isArray(data.openings) ? data.openings : [];
  const notation = data.notation !== false;
  const hasAnything =
    data.sitting?.show || data.habit || openings.length || data.last_game?.repeat || data.play_positions?.length;
  if (!hasAnything) return null;

  return (
    <section
      data-testid="between-games-panel"
      className="mb-10 overflow-hidden rounded-panel border border-border/70 bg-card p-6 shadow-e2 md:p-8"
    >
      <p className="cg-eyebrow">Before your next game</p>

      <div className="mt-4 space-y-4">
        <SittingNote sitting={data.sitting} />
        <LastGameRepeat lastGame={data.last_game} notation={notation} />
        <WatchFor habit={data.habit} />
      </div>

      {openings.length > 0 && (
        <div className="mt-9">
          <div className="flex items-baseline justify-between gap-4">
            <h2 className="font-heading text-lead text-foreground">
              Your openings
            </h2>
            <Link to="/learn" className="text-note font-medium text-primary hover:underline" data-testid="between-games-opening-file">
              Your opening file
            </Link>
          </div>
          <div className="mt-6">
            <OpeningHabit habit={openings[0]} notation={notation} />
          </div>
        </div>
      )}

      {data.play_positions?.length > 0 && (
        <div className="mt-9">
          <h2 className="font-heading text-lead text-foreground">
            Play a position from your games
          </h2>
          <div className="mt-4">
            <PlayPositions positions={data.play_positions} limit={2} />
          </div>
        </div>
      )}
    </section>
  );
}
