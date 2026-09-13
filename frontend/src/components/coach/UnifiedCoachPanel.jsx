import { AlertTriangle, Brain, CheckCircle2, RotateCcw, Target } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";


const UnifiedCoachPanel = ({
  gameMode,
  coachingContext,
  activeMoment,
  stripMoment,
  pendingMove,
  isPlayerTurn,
  isCoachThinking,
  gameOver,
  gameResult,
  summary,
  onTryAnother,
  onPlayAnyway,
  onNewGame,
}) => {
  const navigate = useNavigate();
  const primaryFocus = coachingContext?.primary_focus;
  const verdict = summary?.pattern_verdict;
  const visibleMoment = activeMoment || stripMoment;

  if (gameOver) {
    const story = verdict?.message
      || summary?.coach_summary
      || (gameResult === "win"
        ? "You finished the game. I’m checking what changed in your thinking."
        : "The game is over. I’m checking the moment that will help most next time.");
    const detail = verdict?.detail || summary?.instruction_verdict?.message || null;
    const actionLabel = verdict?.cta_label
      || (summary?.has_data ? "Use the next step" : "Play another game");

    const takeNextAction = () => {
      if (verdict?.cta_href) {
        navigate(verdict.cta_href);
      } else {
        onNewGame();
      }
    };

    return (
      <section className="space-y-4 p-5" data-testid="unified-coach-panel">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-emerald-600" />
          <p className="cg-eyebrow !mb-0">Your game, one clear takeaway</p>
        </div>
        <p className="font-serif text-xl leading-snug text-foreground">{story}</p>
        {detail && (
          <p className="text-sm leading-relaxed text-muted-foreground">{detail}</p>
        )}
        <Button className="w-full" onClick={takeNextAction}>
          {actionLabel}
        </Button>
      </section>
    );
  }

  if (gameMode === "play") {
    return (
      <section className="space-y-4 p-5" data-testid="unified-coach-panel">
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-muted-foreground" />
          <p className="cg-eyebrow !mb-0">Play a Game</p>
        </div>
        <p className="font-serif text-xl text-foreground">Your game. No hints.</p>
        <p className="text-sm leading-relaxed text-muted-foreground">
          I’m saving every coaching comment for the review after the game.
        </p>
      </section>
    );
  }

  return (
    <section
      className="flex min-h-[280px] flex-col p-5"
      data-testid="unified-coach-panel"
      aria-live="polite"
    >
      <div className="border-b border-border pb-4">
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-emerald-700" />
          <p className="cg-eyebrow !mb-0">Today’s work</p>
        </div>
        <p className="mt-2 font-serif text-lg font-semibold text-foreground">
          {primaryFocus?.label || "One useful idea from this game"}
        </p>
        {primaryFocus?.instruction_text && (
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            {primaryFocus.instruction_text}
          </p>
        )}
      </div>

      {activeMoment && pendingMove ? (
        <div className="mt-5 rounded-2xl border border-red-300 bg-red-50/80 p-4 dark:bg-red-950/20">
          <div className="flex items-center gap-2 text-red-700 dark:text-red-300">
            <AlertTriangle className="h-4 w-4" />
            <p className="text-xs font-semibold uppercase tracking-wider">
              Pause before {pendingMove.san}
            </p>
          </div>
          <p className="mt-3 text-sm font-medium leading-relaxed text-foreground">
            {activeMoment.text}
          </p>
          {activeMoment.instruction
            && !activeMoment.text?.includes(activeMoment.instruction) && (
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {activeMoment.instruction}
              </p>
            )}
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Button variant="outline" onClick={onTryAnother} data-testid="unified-try-another">
              <RotateCcw className="mr-2 h-4 w-4" />
              Try another
            </Button>
            <Button onClick={onPlayAnyway} data-testid="unified-play-anyway">
              Play it anyway
            </Button>
          </div>
        </div>
      ) : visibleMoment?.text ? (
        <div className="mt-5 rounded-2xl border border-emerald-700/20 bg-emerald-50/60 p-4 dark:bg-emerald-950/20">
          <p className="cg-eyebrow !mb-2">Coach’s note</p>
          <p className="text-sm leading-relaxed text-foreground">
            {visibleMoment.text}
          </p>
        </div>
      ) : (
        <div className="flex flex-1 items-center py-8">
          <div>
            <p className="font-serif text-xl text-foreground">
              {isCoachThinking
                ? "I’m choosing my reply."
                : isPlayerTurn
                  ? "Your turn. Take your time."
                  : "I’m watching the position."}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              I’ll interrupt only when the position gives us something worth learning.
            </p>
          </div>
        </div>
      )}
    </section>
  );
};


export default UnifiedCoachPanel;
