import { AlertTriangle, Brain, CheckCircle2, RotateCcw, Target } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { invalidatePersonalCurriculum } from "@/lib/personalCurriculum";


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
  canExplainLastMove,
  helpAnswer,
  helpLoading,
  onAskCoach,
  onDismissHelp,
  onTryAnother,
  onPlayAnyway,
  onNewGame,
  onPostgameAction,
}) => {
  const navigate = useNavigate();
  const [helpOpen, setHelpOpen] = useState(false);
  const primaryFocus = coachingContext?.primary_focus;
  const verdict = summary?.pattern_verdict;
  const visibleMoment = activeMoment || stripMoment;

  useEffect(() => {
    // The game may end before its summary arrives; refresh again when it does.
    if (gameOver) invalidatePersonalCurriculum();
  }, [gameOver, summary]);

  if (gameOver) {
    const unifiedSummary = summary?.unified_summary;
    const story = unifiedSummary?.story
      || verdict?.message
      || summary?.coach_summary
      || (gameResult === "win"
        ? "You finished the game. I’m checking what changed in your thinking."
        : "The game is over. I’m checking the moment that will help most next time.");
    const detail = unifiedSummary?.detail
      || verdict?.detail
      || summary?.instruction_verdict?.message
      || null;
    // A label must come from the same recommendation as its destination.
    const action = unifiedSummary?.next_action?.href
      ? unifiedSummary.next_action
      : verdict?.cta_href
        ? { href: verdict.cta_href, label: verdict.cta_label }
        : null;
    const actionLabel = action ? action.label || "Continue with your coach" : "Play another game";

    const takeNextAction = () => {
      const actionHref = action?.href;
      onPostgameAction?.(
        actionHref ? "recommended_next_action" : "new_game"
      );
      if (actionHref) {
        navigate(actionHref);
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
        {unifiedSummary?.focus_label && (
          <p className="text-sm font-medium text-emerald-800 dark:text-emerald-300">
            Today’s work: {unifiedSummary.focus_label}
          </p>
        )}
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
          I’m saving the game for a full review afterward.
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
      ) : helpAnswer?.answer ? (
        <div className="mt-5 rounded-2xl border border-blue-700/20 bg-blue-50/60 p-4 dark:bg-blue-950/20">
          <p className="cg-eyebrow !mb-2">Coach’s answer</p>
          <p className="text-sm leading-relaxed text-foreground">
            {helpAnswer.answer}
          </p>
          {helpAnswer.instruction
            && !helpAnswer.answer.includes(helpAnswer.instruction) && (
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {helpAnswer.instruction}
              </p>
            )}
          <Button
            variant="ghost"
            size="sm"
            className="mt-3"
            onClick={onDismissHelp}
          >
            Got it
          </Button>
        </div>
      ) : (
        <div className="flex flex-1 items-center py-8">
          <div className="w-full">
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
            {helpOpen ? (
              <div className="mt-5 grid gap-2" data-testid="unified-help-actions">
                {canExplainLastMove && (
                  <Button
                    variant="outline"
                    disabled={helpLoading}
                    onClick={() => onAskCoach("explain_last_move")}
                  >
                    Explain their move
                  </Button>
                )}
                <Button
                  variant="outline"
                  disabled={helpLoading}
                  onClick={() => onAskCoach("focus_check")}
                >
                  Remind me what to check
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={helpLoading}
                  onClick={() => setHelpOpen(false)}
                >
                  Never mind
                </Button>
              </div>
            ) : (
              <Button
                variant="outline"
                className="mt-5"
                onClick={() => setHelpOpen(true)}
                data-testid="unified-ask-coach"
              >
                Ask coach
              </Button>
            )}
          </div>
        </div>
      )}
    </section>
  );
};


export default UnifiedCoachPanel;
