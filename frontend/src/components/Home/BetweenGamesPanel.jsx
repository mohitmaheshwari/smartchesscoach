/**
 * BetweenGamesPanel
 *
 * What a coach says between games (docs/coach_pages_scope.md, "Home"), under
 * the plan (CoachPlanCard) and the last game (LastGameCard): whether the last
 * game showed this week's step again (or repeated an opening habit), whether
 * to stop for today, and a position from his own games to play. What to watch
 * for and the opening habit are steps of the plan, so they are not repeated here.
 *
 * Reads the player file (useCoachFile). For a player without the coach pages
 * the server answers {enabled: false} and this renders nothing.
 */
import { Link } from "react-router-dom";

import { useCoachFile } from "@/lib/coachFile";
import { LastGameRepeat, PlayPositions, SittingNote } from "@/components/coachfile/CoachFileBlocks";

export default function BetweenGamesPanel() {
  const data = useCoachFile();
  if (!data || !data.enabled || data.state !== "ready") return null;

  const notation = data.notation !== false;
  const note = data.plan?.last_game_note;
  const lastGame = data.last_game;
  const hasAnything = data.sitting?.show || note || lastGame?.repeat || data.play_positions?.length;
  if (!hasAnything) return null;

  return (
    <section
      data-testid="between-games-panel"
      className="mb-10 overflow-hidden rounded-panel border border-border/70 bg-card p-6 shadow-e2 md:p-8"
    >
      <p className="cg-eyebrow">Before your next game</p>

      <div className="mt-4 space-y-4">
        <SittingNote sitting={data.sitting} />
        {note ? (
          <div data-testid="coach-plan-last-game" className="rounded-card border border-amber-500/30 bg-amber-500/[0.06] p-5">
            <p className="text-body text-foreground">{note}</p>
            {lastGame?.game_id && (
              <Link to={`/game/${lastGame.game_id}`} className="mt-3 inline-flex text-note font-medium text-primary hover:underline">
                See the game
              </Link>
            )}
          </div>
        ) : (
          <LastGameRepeat lastGame={lastGame} notation={notation} />
        )}
      </div>

      {data.play_positions?.length > 0 && (
        <div className="mt-8">
          <h2 className="font-heading text-lead text-foreground">Play a position from your games</h2>
          <div className="mt-4">
            <PlayPositions positions={data.play_positions} limit={2} />
          </div>
        </div>
      )}
    </section>
  );
}
