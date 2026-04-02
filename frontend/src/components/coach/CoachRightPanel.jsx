/**
 * CoachRightPanel — The right side panel for Play with Coach
 * 
 * Contains: Coach Panel (guidance/feedback), Read the Board, 
 * V5 coaching, behavioral coaching, game over panel
 */

import CoachPanel from "@/components/CoachPanel";
import V5CoachingCard from "@/components/shared/V5CoachingCard";

const CoachRightPanel = ({
  session,
  currentFen,
  isPlayerTurn,
  gameOver,
  gameResult,
  isCoachThinking,
  curriculumFeedback,
  lastCoachMoveSan,
  coachIntroMessage,
  openingKey,
  // V5 coaching (non-curriculum)
  v5Coaching,
  behavioralCoaching,
  acknowledgedConcepts,
  onAcknowledge,
  onMoveClick,
  // Game over
  onResign,
  onNewGame,
  children,
}) => {
  const isCurriculum = session?.curriculum_active || session?.teaching_opening;

  return (
    <div className="w-[380px] flex flex-col bg-background border-l border-border" data-testid="coach-right-panel">
      {/* Header */}
      <div className="p-3 border-b border-border flex items-center justify-between shrink-0">
        <h2 className="text-sm font-medium text-foreground">Your Coach</h2>
        {!gameOver && (
          <button
            onClick={onResign}
            className="text-xs text-muted-foreground hover:text-destructive transition-colors"
            data-testid="resign-btn"
          >
            Resign
          </button>
        )}
      </div>

      {/* Main Content - Scrollable */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Coach Panel — curriculum guidance, feedback, opponent moves, Read the Board */}
        {!gameOver && (
          <CoachPanel
            sessionId={session?.session_id}
            fen={currentFen}
            isPlayerTurn={isPlayerTurn}
            openingKey={openingKey}
            introMessage={coachIntroMessage}
            curriculumFeedback={curriculumFeedback}
            lastCoachMove={lastCoachMoveSan}
          />
        )}

        {/* V5 Coaching — hide during curriculum */}
        {v5Coaching && !isCurriculum && (
          <V5CoachingCard
            coaching={v5Coaching}
            isAcknowledged={acknowledgedConcepts?.has(v5Coaching.concept_id)}
            onAcknowledge={onAcknowledge}
            onMoveClick={onMoveClick}
          />
        )}

        {/* Behavioral Coaching — hide during curriculum */}
        {behavioralCoaching && !isCurriculum && (
          <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <p className="text-xs font-medium text-amber-600 mb-1">{behavioralCoaching.pattern}</p>
            <p className="text-sm text-foreground">{behavioralCoaching.message}</p>
          </div>
        )}

        {/* Analyzing indicator — hide during curriculum */}
        {isCoachThinking && !v5Coaching && !isCurriculum && (
          <div className="text-center py-4 animate-pulse">
            <p className="text-xs text-muted-foreground">Analyzing your move...</p>
          </div>
        )}

        {/* Extra children (game over panel, etc.) */}
        {children}
      </div>
    </div>
  );
};

export default CoachRightPanel;
