/**
 * CoachPlayBoard — Left column of the game screen
 *
 * Contains: eval bar, chessboard, teaching overlays, position coaching,
 * pre-move checklist, controls (flip, undo, resign, new game).
 */

import { forwardRef } from "react";
import LichessBoard from "@/components/LichessBoard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import PreMoveChecklist from "@/components/coach/PreMoveChecklist";
import { OpeningCorrectionDialog } from "@/components/openings/OpeningCorrectionDialog";
import {
  EvalBar,
  PositionCoachingPanel,
} from "@/components/coach-play";
import {
  Brain,
  Clock,
  Lightbulb,
  Loader2,
  RotateCcw,
  Flag,
  Play,
  BookOpen,
  X,
} from "lucide-react";

const CoachPlayBoard = forwardRef(function CoachPlayBoard(
  {
    /* game state */
    session,
    currentFen,
    boardOrientation,
    lastMove,
    isPlayerTurn,
    gameOver,
    evaluation,
    selectedColor,
    /* teaching state */
    isInTeachingMode,
    activeLesson,
    lessonInstruction,
    lessonComplete,
    inlineOpening,
    inlineTrap,
    setInlineOpening,
    setInlineTrap,
    openingGuidance,
    openingCorrectionCount,
    setOpeningCorrectionCount,
    /* UI state */
    hideEvalBar,
    coachArrows,
    coachThinking,
    undoLoading,
    hasCastled,
    developedPieces,
    playerWeaknesses,
    showChecklist,
    setShowChecklist,
    positionCoaching,
    setPositionCoaching,
    setChatMessages,
    /* handlers */
    makeMove,
    flipBoard,
    resignGame,
    newGame,
    canUndoLastMove,
    handleUndoMove,
    handleExitLesson,
    triggerCoachMove,
    handleStartLesson,
    moveClassification,
  },
  boardRef
) {
  return (
    <div className="flex-1 flex flex-col items-center p-2 md:p-4 overflow-auto">
      <div className="w-full max-w-[min(550px,calc(100vh-180px),calc(100vw-450px))]">
        {/* Coach info bar */}
        <div className="flex items-center justify-between mb-2 p-2 rounded-lg bg-muted/50 text-sm">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-primary" />
            <span className="font-medium">Coach</span>
          </div>
          <Badge variant="outline" className="text-xs">
            <Clock className="w-3 h-3 mr-1" />
            {Math.floor((session?.coach_time_remaining || 900) / 60)}:
            {String(
              Math.floor((session?.coach_time_remaining || 900) % 60)
            ).padStart(2, "0")}
          </Badge>
        </div>

        {/* Board (eval bar removed — coach doesn't give away the position) */}
        <div className="flex gap-2 items-stretch">

          <div
            className="flex-1 relative rounded-lg overflow-hidden aspect-square"
            style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.3)" }}
          >
            <LichessBoard
              ref={boardRef}
              fen={currentFen}
              orientation={boardOrientation}
              lastMove={lastMove}
              arrows={coachArrows || []}
              onMove={(moveData) => {
                const canMoveInTeaching =
                  isInTeachingMode &&
                  activeLesson &&
                  lessonInstruction?.is_user_move;
                if (
                  (canMoveInTeaching || (isPlayerTurn && !gameOver)) &&
                  moveData
                ) {
                  makeMove(moveData.from, moveData.to);
                }
              }}
              interactive={
                (isInTeachingMode &&
                  activeLesson &&
                  lessonInstruction?.is_user_move) ||
                (isPlayerTurn && !gameOver)
              }
              viewOnly={
                !(
                  isInTeachingMode &&
                  activeLesson &&
                  lessonInstruction?.is_user_move
                ) &&
                (!isPlayerTurn || gameOver)
              }
              showDests={true}
              moveClassification={moveClassification}
            />

            {/* Pedagogical Opportunity Hint Overlay */}
            {hideEvalBar && isPlayerTurn && !gameOver && (
              <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10">
                <div className="px-3 py-1.5 rounded-full bg-amber-500/90 text-white text-xs font-medium shadow-lg animate-pulse">
                  <Lightbulb className="w-3 h-3 inline mr-1" />
                  Find the opportunity!
                </div>
              </div>
            )}

            {/* Lesson Complete Overlay */}
            {lessonComplete && (
              <div className="absolute inset-0 bg-black/80 flex items-center justify-center p-4">
                <div className="bg-card rounded-lg p-4 max-w-xs text-center space-y-3">
                  <div className="text-2xl">🎉</div>
                  <p className="font-medium">{lessonComplete.message}</p>
                  <div className="flex gap-2 justify-center">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        handleExitLesson("continue_game", lessonComplete)
                      }
                    >
                      Continue Game
                    </Button>
                    <Button
                      size="sm"
                      onClick={() =>
                        handleExitLesson("new_game", lessonComplete)
                      }
                    >
                      New Game
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Teaching Mode Instruction Bar */}
        {isInTeachingMode &&
          activeLesson &&
          lessonInstruction &&
          !lessonComplete && (
            <div className="mt-2 p-3 rounded-lg bg-amber-50 border border-amber-200">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <BookOpen className="w-4 h-4 text-amber-500 shrink-0" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-amber-500">
                        {activeLesson.lesson_name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        ({lessonInstruction.remaining} left)
                      </span>
                    </div>
                    <p className="text-sm font-medium">
                      {lessonInstruction.is_user_move
                        ? `Your turn → play ${lessonInstruction.move}`
                        : `Coach plays ${lessonInstruction.move}...`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <OpeningCorrectionDialog
                    sourceContext="play_with_coach"
                    openingKey={
                      session?.teaching_opening ||
                      openingGuidance?.opening_key ||
                      inlineOpening?.key
                    }
                    openingName={
                      activeLesson?.opening_name ||
                      openingGuidance?.opening_name ||
                      inlineOpening?.name
                    }
                    variationName={
                      activeLesson?.mode === "main_line"
                        ? activeLesson?.lesson_name
                        : null
                    }
                    trapName={
                      activeLesson?.mode === "trap"
                        ? activeLesson?.lesson_name
                        : null
                    }
                    currentMoves={(session?.move_history || []).map(
                      (move) => move.move
                    )}
                    currentFen={currentFen}
                    triggerLabel="Fix line"
                    compact={true}
                    onSubmitted={() =>
                      setOpeningCorrectionCount((c) => c + 1)
                    }
                  />
                  <Button
                    size="sm"
                    variant="ghost"
                    className="shrink-0"
                    onClick={() => handleExitLesson("continue_game", {})}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          )}

        {/* Position Coaching Panel */}
        {session &&
          positionCoaching &&
          !isInTeachingMode &&
          !gameOver &&
          !inlineOpening &&
          !inlineTrap && (
            <div className="mt-3">
              <PositionCoachingPanel
                coaching={positionCoaching}
                onDismiss={() => setPositionCoaching(null)}
                onLearnPlan={(plan) => {
                  setChatMessages((prev) => [
                    ...prev,
                    {
                      id: `plan-${Date.now()}`,
                      type: "coach",
                      message: `${plan.name}: ${plan.teaching_explanation}`,
                      trigger: "strategic_plan",
                      timestamp: Date.now(),
                    },
                  ]);
                  setPositionCoaching(null);
                }}
                onShowTactics={(insights) => {
                  const tacticsMsg = insights
                    .map((i) => i.message)
                    .join("\n\n");
                  setChatMessages((prev) => [
                    ...prev,
                    {
                      id: `tactics-${Date.now()}`,
                      type: "coach",
                      message: `Tactical Themes:\n${
                        tacticsMsg ||
                        "No specific tactical patterns detected right now."
                      }`,
                      trigger: "tactical_themes",
                      timestamp: Date.now(),
                    },
                  ]);
                  setPositionCoaching(null);
                }}
                onCheckSafety={(features) => {
                  setChatMessages((prev) => [
                    ...prev,
                    {
                      id: `safety-${Date.now()}`,
                      type: "coach",
                      message: `Piece Safety Check: You have ${
                        features.undefended_pieces || 0
                      } undefended pieces. Make sure all your pieces are protected before continuing!`,
                      trigger: "piece_safety",
                      timestamp: Date.now(),
                    },
                  ]);
                  setPositionCoaching(null);
                }}
              />
            </div>
          )}

        {/* Player info bar */}
        <div className="flex items-center justify-between mt-2 p-2 rounded-lg bg-muted/50 text-sm">
          <div className="flex items-center gap-2">
            <div
              className={`w-4 h-4 rounded-full ${
                selectedColor === "white" ? "bg-white border" : "bg-gray-900"
              }`}
            />
            <span className="font-medium">You</span>
            {isPlayerTurn && !gameOver && (
              <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-xs">
                Your turn
              </Badge>
            )}
            {!isPlayerTurn && !gameOver && !coachThinking && (
              <Badge className="bg-amber-500/20 text-amber-500 border-amber-200 text-xs">
                Coach's turn
              </Badge>
            )}
            {coachThinking && (
              <Badge className="bg-blue-500/20 text-blue-500 border-blue-500/30 text-xs animate-pulse">
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                Thinking...
              </Badge>
            )}
          </div>
          <Badge variant="outline" className="text-xs">
            <Clock className="w-3 h-3 mr-1" />
            {Math.floor((session?.user_time_remaining || 900) / 60)}:
            {String(
              Math.floor((session?.user_time_remaining || 900) % 60)
            ).padStart(2, "0")}
          </Badge>
        </div>

        {/* Pre-Move Checklist */}
        {session &&
          showChecklist &&
          isPlayerTurn &&
          !gameOver &&
          !isInTeachingMode && (
            <div className="mt-2">
              <PreMoveChecklist
                moveNumber={
                  Math.floor((session?.move_history?.length || 0) / 2) + 1
                }
                hasCastled={hasCastled}
                developedPieces={developedPieces}
                playerWeaknesses={playerWeaknesses}
                isPlayerTurn={isPlayerTurn}
                onDismiss={() => setShowChecklist(false)}
                compact={true}
              />
            </div>
          )}

        {/* Coach turn prompt */}
        {!isPlayerTurn && !gameOver && !coachThinking && session && (
          <div className="mt-2 p-3 rounded-lg bg-amber-50 border border-amber-200 text-center">
            <p className="text-sm text-amber-500 mb-2">
              It's the coach's turn. The game may have been interrupted.
            </p>
            <Button
              size="sm"
              variant="outline"
              className="border-amber-500/50 text-amber-500 hover:bg-amber-500/20"
              onClick={() => triggerCoachMove(session.session_id)}
              data-testid="let-coach-play-btn"
            >
              <Play className="w-4 h-4 mr-1" />
              Let Coach Play
            </Button>
          </div>
        )}

        {/* Controls */}
        <div className="flex items-center justify-center gap-2 mt-4">
          <Button variant="outline" size="sm" onClick={flipBoard}>
            <RotateCcw className="w-4 h-4 mr-1" />
            Flip
          </Button>
          {!gameOver && canUndoLastMove() && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleUndoMove}
              disabled={undoLoading}
              data-testid="undo-move-btn"
            >
              {undoLoading ? (
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
              ) : (
                <RotateCcw className="w-4 h-4 mr-1" />
              )}
              Undo Move
            </Button>
          )}
          {!gameOver && (
            <Button
              variant="destructive"
              size="sm"
              onClick={resignGame}
              data-testid="resign-btn"
            >
              <Flag className="w-4 h-4 mr-1" />
              Resign
            </Button>
          )}
          {gameOver && (
            <Button
              variant="default"
              size="sm"
              onClick={newGame}
              data-testid="new-game-btn"
            >
              <Play className="w-4 h-4 mr-1" />
              New Game
            </Button>
          )}
        </div>
      </div>
    </div>
  );
});

export default CoachPlayBoard;
