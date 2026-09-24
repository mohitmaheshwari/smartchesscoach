/**
 * CoachPlayBoard — Left column of the game screen
 *
 * Contains: eval bar, chessboard, teaching overlays, position coaching,
 * pre-move checklist, controls (flip, undo, resign, new game).
 */

import { forwardRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MOTION_TIMING } from "@/lib/motion";
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
    coachingLocked,
    gameOver,
    evaluation,
    selectedColor,
    gameMode,
    unifiedExperience = false,
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
    <div className="flex-1 flex flex-col items-center justify-center p-2 md:p-4 overflow-auto">
      {/* Board column width drives the (CSS-responsive) board size. Caps by the
          available space: on mobile by viewport height minus chrome+coach peek;
          on desktop by the column width (no more 100vw-450px collapse). */}
      {/* The board is the hero, so it takes the space that is actually there.
          It used to be capped at 550px on desktop: on a 1600px screen that
          left ~390px of the board column empty and made the page read as a
          small board with furniture around it, which is the opposite of the
          approved design. It is now bounded by the height available and by
          its own column, whichever runs out first.

          The 230px budget is everything that shares the column: the opponent
          bar above, the player bar and the pre-move checklist below, their
          margins, and the column padding. Measured, not guessed: 150 and 205
          both clipped the opponent bar off the top and the checklist off the
          bottom, because the column centres its content and overflow is lost
          at BOTH ends. 265 is the first value where every row renders. At 150px
          the board grew taller than the column, and because the column
          centres its content, the overflow clipped the TOP of the board --
          rank 8 and the opponent bar both disappeared. */}
      <div className="w-full mx-auto max-w-[min(96vw,calc(100dvh-340px))] lg:max-w-[min(calc(100vh-230px),100%)]">
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

        {/* Board + eval bar. The bar was removed on 2026-04-15 (043cc7fe)
            because "coach doesn't give away the position", and Mohit asked
            for it back on 2026-09-23. It renders ALWAYS ON -- see the note on
            the element below; he was asked directly, with the April removal
            reason quoted back to him, and chose the plain bar.

            That leaves hide_eval with no visible effect on the bar itself. The
            "Find the opportunity!" badge still reads it, and that is kept
            deliberately rather than left over: with the score shown, the bar
            says THAT there is something in the position and the badge says go
            and find it. Those read together. The badge would only be
            incoherent under the assumption that the score was masked.

            `evaluation` has been passed into this component and left unused
            since that removal; this is its first consumer. */}
        <div className="flex gap-2 items-stretch">

          {/* Mohit 2026-09-24, asked directly: always on, not masked. The
              component can mask the score to "?" when the backend sets
              hide_eval, and that is what the April removal note was guarding
              ("coach doesn't give away the position") -- he chose the plain
              bar over that. One prop to put the masking back. */}
          <div className="w-5 md:w-6 shrink-0" data-testid="coach-play-eval-bar">
            <EvalBar
              evaluation={evaluation}
              userColor={selectedColor}
              hidden={false}
            />
          </div>

          <div
            className="experience-board-stage flex-1 relative rounded-lg overflow-hidden aspect-square"
            data-testid="coach-play-board-stage"
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
                (isPlayerTurn && !gameOver && !coachingLocked)
              }
              viewOnly={
                !(
                  isInTeachingMode &&
                  activeLesson &&
                  lessonInstruction?.is_user_move
                ) &&
                (!isPlayerTurn || gameOver)
              }
              showDests={gameMode !== "play"}
              disableArrows={gameMode === "play"}
              moveClassification={moveClassification}
            />

            {/* Board lock — while the coach's feedback must be acknowledged,
                the board dims (fade 150ms). Clicks are already blocked via
                interactive=false; this is the visual cue for why. */}
            <AnimatePresence>
              {coachingLocked && !gameOver && !isInTeachingMode && (
                <motion.div
                  key="board-lock-overlay"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{
                    duration: MOTION_TIMING.micro.duration / 1000,
                    ease: MOTION_TIMING.micro.easing,
                  }}
                  className="absolute inset-0 z-10 bg-black/30 pointer-events-none"
                  data-testid="board-lock-overlay"
                />
              )}
            </AnimatePresence>

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
              <div className="absolute inset-0 z-20 bg-background/80 backdrop-blur-md flex items-center justify-center p-4">
                <div className="bg-card border border-border rounded-2xl shadow-2xl p-6 max-w-sm w-full text-center space-y-4">
                  <div className="mx-auto w-11 h-11 rounded-full bg-primary/15 flex items-center justify-center text-2xl">🎉</div>
                  <div className="space-y-2">
                    <p className="text-[10.5px] uppercase tracking-[0.18em] text-primary font-semibold">
                      Trap complete
                    </p>
                    <p className="text-sm leading-relaxed text-foreground/90 text-left">
                      {String(lessonComplete.message || "")
                        .replace(/^\s*trap complete[!.:\-\s]*/i, "")
                        .trim() || "Nicely played — that's the whole idea of this trap."}
                    </p>
                  </div>
                  <div className="flex gap-2 justify-center pt-1">
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1"
                      onClick={() =>
                        handleExitLesson("continue_game", lessonComplete)
                      }
                    >
                      Continue Game
                    </Button>
                    <Button
                      size="sm"
                      className="flex-1"
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
          {/* One bottom bar instead of three stacked rows. Flip and Resign
              used to sit in their own centered row below this one, so the
              board was pushed up by furniture it did not need. */}
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              <Clock className="w-3 h-3 mr-1" />
              {Math.floor((session?.user_time_remaining || 900) / 60)}:
              {String(
                Math.floor((session?.user_time_remaining || 900) % 60)
              ).padStart(2, "0")}
            </Badge>
            <Button variant="outline" size="sm" onClick={flipBoard} className="h-7 px-2.5">
              <RotateCcw className="w-3.5 h-3.5 mr-1" />
              Flip
            </Button>
            {!gameOver && (
              <Button
                variant="outline"
                size="sm"
                onClick={resignGame}
                data-testid="resign-btn"
                className="h-7 px-2.5 text-muted-foreground"
              >
                <Flag className="w-3.5 h-3.5 mr-1" />
                Resign
              </Button>
            )}
          </div>
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

        {/* Post-game actions only. Flip and Resign moved up into the player
            bar; during a game this row renders nothing and the board keeps
            the height. Undo stays removed - a real coach doesn't let you take
            back moves. */}
        {gameOver && (
        <div className="flex items-center justify-center gap-2 mt-4">
          {gameOver && !unifiedExperience && (
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
        )}
      </div>
    </div>
  );
});

export default CoachPlayBoard;
