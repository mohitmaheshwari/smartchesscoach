/**
 * CoachPlaySidebar — Right column of the game screen
 *
 * Contains two modes:
 *   1. Clean UI — Focused coaching experience (default)
 *   2. Legacy UI — Full chat + panels fallback
 *
 * Both share: guardian intervention, feedback modal, post-game lesson,
 * game-over summary, move history, and enforcement modals.
 */

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useState } from "react";
import { API } from "@/App";
import LessonPicker from "@/components/coach/LessonPicker";
import EscapeSquaresQuiz from "@/components/coach/EscapeSquaresQuiz";
import CoachPanel from "@/components/CoachPanel";
import V5CoachingCard from "@/components/shared/V5CoachingCard";
import EvalBadge from "@/components/shared/EvalBadge";
import DeepMemoryPanel from "@/components/DeepMemoryPanel";
import PostGameLesson from "@/components/PostGameLesson";
import PostGameReflection from "@/components/coach/PostGameReflection";
import CoachTimelinePanel from "@/components/coach/CoachTimelinePanel";
import ActiveCoachStrip from "@/components/coach/ActiveCoachStrip";
import ActiveCoachingCard from "@/components/coach/ActiveCoachingCard";
import LiveChecklist from "@/components/coach/LiveChecklist";
import EmotionalStateIndicator from "@/components/coach/EmotionalStateIndicator";
import OpeningGuidePanel from "@/components/coach/OpeningGuidePanel";
import { FlagMoveButton } from "@/components/shared/FlagMoveDialog";
import {
  OpeningTeachingOffer,
} from "@/components/coach/OpeningTeachingPanel";
import {
  TrapAlert,
  MoveHistorySection,
  MoveFeedbackPanel,
  ConsequenceFeedback,
} from "@/components/coach-play";
import {
  Brain,
  Loader2,
  AlertTriangle,
  Lightbulb,
  RotateCcw,
  ShieldAlert,
  BookOpen,
  Swords,
  ThumbsDown,
  MessageCircle,
  X,
  Trophy,
  XCircle,
  CheckCircle2,
  Clock,
  Target,
  Download,
} from "lucide-react";

/* ── Guardian Intervention Panel ── */
const GuardianPanel = ({
  guardianIntervention,
  pendingMove,
  cancelRiskyMove,
  confirmRiskyMove,
}) => {
  if (!guardianIntervention || !pendingMove) return null;

  return (
    <div
      data-testid="guardian-intervention-inline"
      className={`p-4 rounded-lg border-2 ${
        guardianIntervention.risk_level === "critical"
          ? "border-red-500 bg-red-500/10"
          : guardianIntervention.risk_level === "high"
          ? "border-orange-500 bg-orange-500/10"
          : "border-yellow-500 bg-yellow-50"
      }`}
    >
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle
          className={`w-6 h-6 ${
            guardianIntervention.risk_level === "critical"
              ? "text-red-500"
              : guardianIntervention.risk_level === "high"
              ? "text-orange-500"
              : "text-yellow-500"
          }`}
        />
        <h4 className="font-bold text-white">
          {guardianIntervention.intervention_type === "block"
            ? "Wait!"
            : "Think Again"}
        </h4>
      </div>

      <p className="text-sm font-medium text-white mb-2">
        {guardianIntervention.message}
      </p>
      <p className="text-xs text-muted-foreground mb-3">
        {guardianIntervention.explanation}
      </p>

      {guardianIntervention.alternative_moves?.length > 0 && (
        <div className="p-2 rounded bg-muted/50 mb-3">
          <p className="text-xs font-medium text-foreground mb-1.5 flex items-center gap-1">
            <Lightbulb className="w-3 h-3 text-primary" />
            Better alternatives:
          </p>
          <div className="flex flex-wrap gap-1.5">
            {guardianIntervention.alternative_moves.map((move, i) => (
              <Badge
                key={i}
                variant="outline"
                className="font-mono cursor-pointer hover:bg-primary/20 text-xs"
              >
                {move}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-muted-foreground mb-3">
        Your move:{" "}
        <span className="font-mono font-medium text-white">
          {pendingMove.moveSan}
        </span>
      </p>

      {/* Engine analysis — why this move is bad */}
      {guardianIntervention.analysis && (
        <div className="space-y-2 mb-3">
          {/* Punishment line: what happens after your bad move */}
          {guardianIntervention.analysis.punishment_line?.length > 0 && (
            <div className="p-2 rounded bg-red-500/10 border border-red-500/20">
              <p className="text-[10px] uppercase tracking-widest text-red-400 font-bold mb-1">
                What happens next
              </p>
              <p className="text-xs text-foreground font-mono">
                {pendingMove.moveSan}{" "}
                {guardianIntervention.analysis.punishment_line.join(" ")}
              </p>
            </div>
          )}

          {/* Best line: what you should play instead */}
          {guardianIntervention.analysis.best_line?.length > 0 && (
            <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/20">
              <p className="text-[10px] uppercase tracking-widest text-emerald-400 font-bold mb-1">
                Better plan
              </p>
              <p className="text-xs text-foreground font-mono">
                {guardianIntervention.analysis.best_line.join(" ")}
              </p>
            </div>
          )}

          {/* Mistake category badge */}
          {guardianIntervention.analysis.mistake_category && (
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[10px]">
                {guardianIntervention.analysis.mistake_category === "one_move_blunder" ? "One-move blunder"
                  : guardianIntervention.analysis.mistake_category === "tactical_miss" ? "Missed tactic"
                  : guardianIntervention.analysis.mistake_category === "threat_blindness" ? "Missed threat"
                  : guardianIntervention.analysis.mistake_category === "calculation_error" ? "Calculation error"
                  : "Positional mistake"}
              </Badge>
              {guardianIntervention.analysis.cp_loss > 0 && (
                <span className="text-[10px] text-muted-foreground">
                  -{(guardianIntervention.analysis.cp_loss / 100).toFixed(1)} pawns
                </span>
              )}
            </div>
          )}
        </div>
      )}

      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          className="flex-1"
          onClick={cancelRiskyMove}
          data-testid="guardian-cancel-btn"
        >
          <RotateCcw className="w-3 h-3 mr-1" />
          Different Move
        </Button>
        <Button
          size="sm"
          variant={
            guardianIntervention.risk_level === "critical"
              ? "destructive"
              : "default"
          }
          className="flex-1"
          onClick={confirmRiskyMove}
          data-testid="guardian-confirm-btn"
        >
          Play Anyway
        </Button>
      </div>
    </div>
  );
};

/* ── Feedback Modal ── */
const InlineFeedbackModal = ({
  feedbackMessage,
  setFeedbackMessage,
  feedbackType,
  setFeedbackType,
  feedbackComment,
  setFeedbackComment,
  feedbackCorrectPattern,
  setFeedbackCorrectPattern,
  submitFeedback,
}) => {
  if (!feedbackMessage) return null;

  return (
    <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">What was wrong?</CardTitle>
            <button
              onClick={() => setFeedbackMessage(null)}
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-2 bg-muted/50 rounded text-xs text-muted-foreground line-clamp-2">
            "{feedbackMessage.message}"
          </div>

          <div className="space-y-2">
            {[
              { value: "confusing", label: "Confusing / Hard to understand" },
              { value: "wrong", label: "Wrong / Incorrect explanation" },
              { value: "obvious", label: "Too obvious / I knew this" },
              { value: "not_relevant", label: "Not relevant to my plan" },
            ].map((option) => (
              <label
                key={option.value}
                className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors ${
                  feedbackType === option.value
                    ? "bg-primary/10 border border-primary/30"
                    : "hover:bg-muted/50"
                }`}
              >
                <input
                  type="radio"
                  name="feedback"
                  value={option.value}
                  checked={feedbackType === option.value}
                  onChange={(e) => setFeedbackType(e.target.value)}
                  className="sr-only"
                />
                <div
                  className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                    feedbackType === option.value
                      ? "border-primary bg-primary"
                      : "border-muted-foreground"
                  }`}
                >
                  {feedbackType === option.value && (
                    <div className="w-2 h-2 rounded-full bg-background" />
                  )}
                </div>
                <span className="text-sm">{option.label}</span>
              </label>
            ))}
          </div>

          {feedbackType === "wrong" && (
            <div className="space-y-3 p-3 bg-amber-50 border border-amber-500/20 rounded-lg">
              <p className="text-xs font-medium text-amber-600 dark:text-amber-700">
                Help us learn! What was it actually?
              </p>
              <select
                value={feedbackCorrectPattern}
                onChange={(e) => setFeedbackCorrectPattern(e.target.value)}
                className="w-full p-2 text-sm rounded border bg-background"
                data-testid="pattern-correction-select"
              >
                <option value="">Select the correct pattern...</option>
                <option value="WALKED_INTO_FORK">
                  I walked into a fork
                </option>
                <option value="WALKED_INTO_PIN">
                  I walked into a pin
                </option>
                <option value="WALKED_INTO_SKEWER">
                  I walked into a skewer
                </option>
                <option value="HANGING_PIECE">
                  I left a piece hanging
                </option>
                <option value="MISSED_FORK">
                  I missed a fork opportunity
                </option>
                <option value="MISSED_PIN">
                  I missed a pin opportunity
                </option>
                <option value="MISSED_WINNING_TACTIC">
                  I missed a winning tactic
                </option>
                <option value="BLUNDER_WHEN_AHEAD">
                  I blundered when ahead
                </option>
                <option value="IGNORED_THREAT">
                  I ignored opponent's threat
                </option>
                <option value="POSITIONAL_DRIFT">
                  Small positional mistake
                </option>
                <option value="OTHER">Something else</option>
              </select>
            </div>
          )}

          <Textarea
            placeholder={
              feedbackType === "wrong"
                ? "Explain what the mistake actually was..."
                : "Tell us more (optional)..."
            }
            value={feedbackComment}
            onChange={(e) => setFeedbackComment(e.target.value)}
            className="h-20 text-sm"
          />

          <Button
            onClick={submitFeedback}
            disabled={
              !feedbackType ||
              (feedbackType === "wrong" && !feedbackCorrectPattern)
            }
            className="w-full"
          >
            {feedbackType === "wrong"
              ? "Submit & Help Coach Learn"
              : "Submit Feedback"}
          </Button>

          {feedbackType === "wrong" && (
            <p className="text-xs text-center text-muted-foreground">
              Your correction helps the coach improve for everyone!
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

/* ── Game Over Summary Card ── */
const GameOverCard = ({ gameResult, summary }) => (
  <div className="p-4 border-t border-border">
    <Card
      className={`${
        gameResult === "win"
          ? "border-emerald-200 bg-green-500/5"
          : gameResult === "loss"
          ? "border-red-200 bg-red-500/5"
          : "border-yellow-200 bg-yellow-500/5"
      }`}
    >
      <CardContent className="p-3">
        <div className="flex items-center gap-2">
          {gameResult === "win" ? (
            <Trophy className="w-5 h-5 text-green-500" />
          ) : gameResult === "loss" ? (
            <XCircle className="w-5 h-5 text-red-500" />
          ) : (
            <CheckCircle2 className="w-5 h-5 text-yellow-500" />
          )}
          <span className="font-medium capitalize">{gameResult || "Draw"}</span>
        </div>
        {summary && (
          <p className="text-xs text-muted-foreground mt-1">
            {summary.total_moves} moves •{" "}
            {Math.floor(summary.duration_seconds / 60)}m
          </p>
        )}
      </CardContent>
    </Card>
  </div>
);

/* ── Legacy Chat Messages ── */
const LegacyChatMessages = ({
  chatMessages,
  isSendingChat,
  chatEndRef,
  sendChatMessage,
  setFeedbackMessage,
  setInlineOpening,
  moveFeedback,
  setMoveFeedback,
  loadingFeedback,
  gameOver,
}) => (
  <div
    className="flex-1 overflow-y-auto p-4 space-y-3"
    data-testid="chat-messages"
  >
    {moveFeedback && !gameOver && (
      <MoveFeedbackPanel
        feedback={moveFeedback}
        onDismiss={() => setMoveFeedback(null)}
      />
    )}

    {loadingFeedback && (
      <div className="p-3 rounded-lg bg-primary/5 border border-primary/10 animate-pulse">
        <div className="flex items-center gap-2 text-sm text-primary">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Analyzing your move...</span>
        </div>
      </div>
    )}

    {chatMessages.length === 0 && !moveFeedback && !gameOver && (
      <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
        <div className="flex items-start gap-2">
          <Brain className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
          <div className="text-sm">
            <p className="font-medium text-primary">Let's play!</p>
            <p className="text-muted-foreground mt-1">
              I'll give you feedback on interesting moves. Feel free to ask me
              anything!
            </p>
          </div>
        </div>
      </div>
    )}

    {chatMessages.map((msg, i) => (
      <div
        key={i}
        className={`p-3 rounded-lg ${
          msg.type === "coach"
            ? msg.trigger === "warning"
              ? "bg-red-500/10 border border-red-500/20"
              : msg.trigger === "teaching"
              ? "bg-amber-50 border border-amber-500/20"
              : msg.trigger === "encouragement"
              ? "bg-emerald-50 border border-emerald-200"
              : "bg-primary/10 border border-primary/20"
            : msg.type === "thinking"
            ? "bg-primary/5 border border-primary/10 animate-pulse"
            : "bg-muted/50 ml-6"
        }`}
      >
        <div className="flex items-start gap-2">
          {msg.type === "coach" ? (
            <Brain
              className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                msg.trigger === "warning"
                  ? "text-red-600"
                  : msg.trigger === "teaching"
                  ? "text-amber-700"
                  : msg.trigger === "encouragement"
                  ? "text-emerald-700"
                  : "text-primary"
              }`}
            />
          ) : msg.type === "thinking" ? (
            <Loader2 className="w-4 h-4 text-primary mt-0.5 flex-shrink-0 animate-spin" />
          ) : (
            <MessageCircle className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
          )}
          <div className="text-sm flex-1">
            {msg.type === "coach" && msg.trigger && (
              <Badge
                variant="outline"
                className={`text-xs mb-1 capitalize ${
                  msg.trigger === "warning"
                    ? "border-red-200 text-red-600"
                    : msg.trigger === "teaching"
                    ? "border-amber-200 text-amber-700"
                    : msg.trigger === "encouragement"
                    ? "border-emerald-200 text-emerald-700"
                    : ""
                }`}
              >
                {msg.trigger === "encouragement"
                  ? "👏"
                  : msg.trigger === "warning"
                  ? "⚠️"
                  : msg.trigger === "teaching"
                  ? "💡"
                  : "💬"}{" "}
                {msg.trigger}
              </Badge>
            )}
            {msg.type === "coach" && msg.move && (
              <span className="text-xs text-muted-foreground block">
                After {msg.move}:
              </span>
            )}
            <p
              className={
                msg.type === "coach"
                  ? ""
                  : msg.type === "thinking"
                  ? "text-primary italic"
                  : "text-muted-foreground"
              }
            >
              {msg.message}
            </p>

            {/* Quick Action Buttons */}
            {msg.type === "coach" &&
              msg.trigger === "teaching" &&
              !msg.question && (
                <div className="mt-2 flex items-center gap-2">
                  {msg.isCoachMove ||
                  msg.message?.toLowerCase().includes("i played") ||
                  msg.message?.toLowerCase().includes("i moved") ? (
                    <>
                      <button
                        onClick={() =>
                          sendChatMessage(
                            `Why did you play ${msg.move || "that move"}?`
                          )
                        }
                        className="text-xs px-2 py-1 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                        data-testid={`why-coach-btn-${i}`}
                      >
                        Why that move?
                      </button>
                      <button
                        onClick={() =>
                          sendChatMessage(
                            `What's the idea behind ${
                              msg.move || "your move"
                            }?`
                          )
                        }
                        className="text-xs px-2 py-1 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                        data-testid={`idea-btn-${i}`}
                      >
                        What's the idea?
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() =>
                          sendChatMessage(
                            `Why was ${msg.move || "my move"} bad?`
                          )
                        }
                        className="text-xs px-2 py-1 rounded bg-amber-50 text-amber-700 hover:bg-amber-500/20 transition-colors"
                        data-testid={`why-btn-${i}`}
                      >
                        Why?
                      </button>
                      <button
                        onClick={() =>
                          sendChatMessage(
                            `What should I have played instead of ${
                              msg.move || "that"
                            }?`
                          )
                        }
                        className="text-xs px-2 py-1 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                        data-testid={`what-btn-${i}`}
                      >
                        What instead?
                      </button>
                    </>
                  )}
                </div>
              )}

            {/* Question options */}
            {msg.type === "coach" &&
              msg.question &&
              msg.question.options && (
                <div className="mt-3 space-y-2">
                  {msg.question.options.map((option, optIdx) => (
                    <button
                      key={optIdx}
                      onClick={() => sendChatMessage(option)}
                      className="w-full text-left p-2 rounded-lg bg-muted/30 hover:bg-muted/50 text-sm transition-colors border border-transparent hover:border-primary/30 flex items-center gap-2"
                      data-testid={`question-option-${i}-${optIdx}`}
                    >
                      <span className="w-5 h-5 rounded-full bg-primary/10 text-primary text-xs flex items-center justify-center flex-shrink-0">
                        {String.fromCharCode(65 + optIdx)}
                      </span>
                      {option}
                    </button>
                  ))}
                </div>
              )}

            {/* Feedback button */}
            {msg.type === "coach" && msg.id && (
              <div className="mt-2 flex items-center gap-2">
                <button
                  onClick={() => setFeedbackMessage(msg)}
                  className="text-xs text-muted-foreground hover:text-primary flex items-center gap-1 transition-colors"
                  data-testid={`feedback-btn-${i}`}
                >
                  <ThumbsDown className="w-3 h-3" />
                  Not helpful
                </button>
              </div>
            )}

            {/* Learn Opening button */}
            {msg.type === "coach" && msg.opening_key && (
              <div className="mt-2">
                <button
                  onClick={() => {
                    setInlineOpening({
                      name: msg.opening_name || "Opening",
                      key: msg.opening_key,
                      main_idea: `Let's learn the ${msg.opening_name}!`,
                      simple_explanation: msg.message,
                      key_moves: [],
                      key_squares: [],
                    });
                  }}
                  className="text-xs px-3 py-1.5 rounded-full bg-primary/10 text-primary hover:bg-primary/20 transition-colors flex items-center gap-1"
                  data-testid={`learn-opening-btn-${i}`}
                >
                  <BookOpen className="w-3 h-3" />
                  Learn {msg.opening_name || "this opening"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    ))}

    {isSendingChat && (
      <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
        <div className="flex items-center gap-2">
          <Loader2 className="w-4 h-4 text-primary animate-spin" />
          <span className="text-sm text-muted-foreground">
            Coach is thinking...
          </span>
        </div>
      </div>
    )}

    <div ref={chatEndRef} />
  </div>
);

/* ── Main Sidebar Component ── */
const CoachPlaySidebar = ({
  /* game state */
  session,
  currentFen,
  isPlayerTurn,
  gameOver,
  gameResult,
  summary,
  selectedColor,
  /* coaching */
  cleanUIMode,
  openingGuidance,
  coachIntroMessage,
  curriculumFeedback,
  lastCoachMoveSan,
  v5Coaching,
  preMoveTrap,
  interactiveCoaching,
  behavioralCoaching,
  consequenceFeedback,
  setConsequenceFeedback,
  isCoachThinking,
  loadingFeedback,
  acknowledgedConcepts,
  activeTrapAlert,
  setActiveTrapAlert,
  moveFeedback,
  setMoveFeedback,
  /* guardian */
  guardianIntervention,
  pendingMove,
  cancelRiskyMove,
  confirmRiskyMove,
  remainingInterventions,
  /* teaching */
  isInTeachingMode,
  activeLesson,
  lessonInstruction,
  lessonComplete,
  teachingOffer,
  inlineOpening,
  inlineTrap,
  setInlineOpening,
  handleStartLesson,
  handleSkipTeachingOffer,
  handleExitLesson,
  setOpeningGuidance,
  /* chat */
  chatMessages,
  isSendingChat,
  sendChatMessage,
  chatEndRef,
  setFeedbackMessage,
  feedbackMessage,
  feedbackType,
  setFeedbackType,
  feedbackComment,
  setFeedbackComment,
  feedbackCorrectPattern,
  setFeedbackCorrectPattern,
  submitFeedback,
  /* V5 / interactive */
  showAlternativeMove,
  handleAcknowledgeConcept,
  /* emotional */
  blundersThisGame,
  recentResults,
  /* escape squares quiz */
  escapeSquaresQuiz,
  onEscapeQuizComplete,
  /* actions */
  newGame,
  coachTimeline = [],
  coachFlowState,
  activeStripCoaching,
  activeCoachingMoment,
  liveChecklist,
  playerWeaknessList,
  playerProfile,
  rootProblem,
  isInHold,
  clockState,
  onClockTap,
}) => {
  const [showLessonPicker, setShowLessonPicker] = useState(false);

  // When the new coaching flow is wired up, suppress ALL old coaching sections.
  // The ActiveCoachingCard (board-adjacent) handles live coaching.
  // Sidebar only shows timeline + teaching mode.
  const suppressOldCoaching = coachFlowState !== undefined;

  // When lesson picker starts a lesson, pass through to parent handler
  const handleLessonFromPicker = (lessonData) => {
    setShowLessonPicker(false);
    handleStartLesson(lessonData);
  };

  // Show lesson picker overlay
  if (showLessonPicker && session && !gameOver && !isInTeachingMode) {
    return (
      <div
        className="w-[380px] border-l border-border flex flex-col h-full"
        data-testid="coach-chat-panel"
      >
        <LessonPicker
          sessionId={session.session_id}
          userColor={selectedColor || session?.user_color || "white"}
          onStartLesson={handleLessonFromPicker}
          onClose={() => setShowLessonPicker(false)}
        />
      </div>
    );
  }

  return (
    <div
      className="w-[380px] border-l border-border flex flex-col h-full"
      data-testid="coach-chat-panel"
    >
      {/* ═══ Clean UI Mode ═══ */}
      {cleanUIMode && session && !gameOver ? (
        <>
          {/* Header */}
          <div className="p-4 border-b border-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg">🎯</span>
                <span className="text-sm font-medium">Your Coach</span>
              </div>
              <div className="flex items-center gap-2">
                {!isInTeachingMode && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => setShowLessonPicker(true)}
                    data-testid="open-lessons-btn"
                  >
                    <BookOpen className="w-3 h-3 mr-1" />
                    Lessons
                  </Button>
                )}
                {openingGuidance?.opening_key && (
                  <span className="text-xs text-muted-foreground">
                    {openingGuidance.opening_key.replace(/_/g, " ")}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Main Content - Scrollable */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* ═══ NEW COACHING SYSTEM (in sidebar) ═══ */}

            {/* Critical Hold Card — mistake/blunder with clock commit */}
            {suppressOldCoaching && isInHold && activeCoachingMoment && (
              <ActiveCoachingCard
                moment={activeCoachingMoment}
                clockState={clockState}
                onClockTap={onClockTap}
              />
            )}

            {/* Ambient/Advisory Strip — live coaching in sidebar */}
            {suppressOldCoaching && !isInHold && activeStripCoaching && (
              <ActiveCoachStrip coaching={activeStripCoaching} />
            )}

            {/* Live Checklist — fundamentals + weaknesses */}
            {suppressOldCoaching && !gameOver && (
              <LiveChecklist
                checklist={liveChecklist}
                weaknesses={playerWeaknessList}
                playerProfile={playerProfile}
                rootProblem={rootProblem}
                gamePhase={activeStripCoaching?.gamePhase || (activeCoachingMoment ? "critical" : null)}
                coachNote={activeStripCoaching?.text || (isInHold ? activeCoachingMoment?.text : null)}
              />
            )}

            {/* Coach Timeline — historical moments */}
            {suppressOldCoaching && coachTimeline && coachTimeline.length > 0 && !gameOver && (
              <CoachTimelinePanel timeline={coachTimeline} />
            )}

            {/* ═══ LEGACY COACHING (old mode) ═══ */}

            {/* Pre-Move Fundamentals Reminder — only in old mode */}
            {!suppressOldCoaching && !gameOver && isPlayerTurn && !v5Coaching && !isCoachThinking && !guardianIntervention && !isInTeachingMode && (
              <PreMoveFundamentals />
            )}

            {/* Coach Panel — only in old mode */}
            {!suppressOldCoaching && !gameOver && !v5Coaching && !isCoachThinking && (
              <CoachPanel
                sessionId={session?.session_id}
                fen={currentFen}
                isPlayerTurn={isPlayerTurn}
                openingKey={
                  session?.teaching_opening || openingGuidance?.opening_key
                }
                introMessage={coachIntroMessage}
                curriculumFeedback={curriculumFeedback}
                lastCoachMove={lastCoachMoveSan}
              />
            )}

            {/* Guardian Intervention */}
            <GuardianPanel
              guardianIntervention={guardianIntervention}
              pendingMove={pendingMove}
              cancelRiskyMove={cancelRiskyMove}
              confirmRiskyMove={confirmRiskyMove}
            />

            {/* Trap Alert — only in old mode */}
            {!suppressOldCoaching && activeTrapAlert && (
              <TrapAlert
                trap={activeTrapAlert}
                onShowLine={() => {}}
                onDismiss={() => setActiveTrapAlert(null)}
              />
            )}

            {/* Escape Squares Quiz — only in old mode */}
            {!suppressOldCoaching && escapeSquaresQuiz && !isInTeachingMode && !gameOver && !v5Coaching && (
              <EscapeSquaresQuiz
                quiz={escapeSquaresQuiz}
                sessionId={session?.session_id}
                onComplete={onEscapeQuizComplete}
              />
            )}

            {/* Coach's Move Explanation — only in old mode */}
            {(() => {
              if (interactiveCoaching?.coachMoveCoaching) {
                console.log("[V2-RENDER] Coach explanation:", JSON.stringify({
                  move: interactiveCoaching.coachMoveCoaching.move_san,
                  explanation: interactiveCoaching.coachMoveCoaching.explanation?.substring(0, 60),
                  v2_intent: interactiveCoaching.coachMoveCoaching.v2_intent,
                  v2_label: interactiveCoaching.coachMoveCoaching.v2_label,
                  plan: interactiveCoaching.coachMoveCoaching.plan?.substring(0, 60),
                  hint: interactiveCoaching.coachMoveCoaching.hint_for_user?.substring(0, 60),
                  suppressOldCoaching,
                  willRender: true,
                }));
              }
              return null;
            })()}
            {/* Coach move explanation now renders in CommentaryPanel (next to board).
                Only show here if CommentaryPanel is not available (fallback). */}
            {interactiveCoaching.coachMoveCoaching && !interactiveCoaching.coachMoveCoaching.v2_intent && (
              <div
                data-testid="coach-move-explanation"
                className="p-4 rounded-lg bg-blue-50 border border-blue-200 space-y-2"
              >
                <div className="flex items-center gap-2">
                  <span className="text-blue-700 font-bold text-sm tracking-wide uppercase">
                    Coach played
                  </span>
                  <span className="font-mono text-blue-700 bg-blue-100 px-2 py-0.5 rounded text-sm">
                    {interactiveCoaching.coachMoveCoaching.move_san}
                  </span>
                  <FlagMoveButton
                    source="coach"
                    sessionId={session?.session_id}
                    fen={currentFen || ""}
                    moveSan={
                      interactiveCoaching.coachMoveCoaching.move_san
                    }
                    coachingText={
                      interactiveCoaching.coachMoveCoaching.explanation
                    }
                    className="ml-auto"
                  />
                </div>
                {interactiveCoaching.coachMoveCoaching.v2_label && (
                  <span className={`inline-block text-xs font-bold px-2 py-0.5 rounded-full ${
                    interactiveCoaching.coachMoveCoaching.v2_intent === 'fork_opportunity'
                      ? 'bg-red-100 text-red-700'
                      : interactiveCoaching.coachMoveCoaching.v2_intent === 'hanging_piece_punishment'
                        ? 'bg-amber-100 text-amber-700'
                        : 'bg-purple-100 text-purple-700'
                  }`}>
                    {interactiveCoaching.coachMoveCoaching.v2_label}
                  </span>
                )}
                {interactiveCoaching.coachMoveCoaching.v2_explanation ? (
                  <p className="text-blue-800 text-sm font-medium">
                    {interactiveCoaching.coachMoveCoaching.v2_explanation}
                  </p>
                ) : interactiveCoaching.coachMoveCoaching.explanation && (
                  <p className="text-blue-800 text-sm">
                    {interactiveCoaching.coachMoveCoaching.explanation}
                  </p>
                )}
                {interactiveCoaching.coachMoveCoaching.plan && (
                  <div className="flex items-start gap-2 mt-1">
                    <span className="text-blue-700 text-xs font-semibold shrink-0">
                      PLAN:
                    </span>
                    <p className="text-blue-800 text-sm">
                      {interactiveCoaching.coachMoveCoaching.plan}
                    </p>
                  </div>
                )}
                {interactiveCoaching.coachMoveCoaching.threats?.length >
                  0 && (
                  <div className="flex items-start gap-2 mt-1">
                    <span className="text-red-600 text-xs font-semibold shrink-0">
                      THREATS:
                    </span>
                    <p className="text-red-600 text-sm">
                      {interactiveCoaching.coachMoveCoaching.threats.join(
                        ", "
                      )}
                    </p>
                  </div>
                )}
                {interactiveCoaching.coachMoveCoaching.hint_for_user && (
                  <div className="mt-2 pt-2 border-t border-blue-500/20">
                    <p className="text-amber-700 text-sm font-medium">
                      🤔 {interactiveCoaching.coachMoveCoaching.hint_for_user}
                    </p>
                  </div>
                )}
                {interactiveCoaching.coachMoveCoaching.teaching_point && (
                  <div className={`${interactiveCoaching.coachMoveCoaching.hint_for_user ? 'mt-1' : 'mt-2 pt-2 border-t border-blue-500/20'}`}>
                    <p className="text-blue-600 text-xs italic">
                      {interactiveCoaching.coachMoveCoaching.teaching_point}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Opponent Opportunity — teach student to read the board */}
            {interactiveCoaching?.coachMoveCoaching?.opponent_opportunity && (
              <div className="p-3 rounded-lg border border-emerald-200 bg-emerald-50 space-y-1">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-700">
                  Can you see it?
                </span>
                <p className="text-sm text-emerald-800 font-medium">
                  {interactiveCoaching.coachMoveCoaching.opponent_opportunity.message}
                </p>
              </div>
            )}

            {/* Consequence Feedback (Pedagogical Opponent) */}
            {consequenceFeedback && (
              <ConsequenceFeedback
                consequence={consequenceFeedback}
                onDismiss={() => setConsequenceFeedback(null)}
              />
            )}

            {/* Pre-Move Trap Prompt — shown BEFORE user moves */}
            {preMoveTrap && !v5Coaching && !isCoachThinking && (
              <div className="p-3 rounded-lg border-2 border-amber-500/30 bg-amber-500/5 animate-in slide-in-from-top-2" data-testid="pre-move-trap">
                <div className="flex items-center gap-2 mb-2">
                  <Target className="w-4 h-4 text-amber-500" strokeWidth={2} />
                  <span className="text-xs font-bold uppercase tracking-wider text-amber-500">
                    Before You Move
                  </span>
                </div>
                <p className="text-sm text-foreground leading-relaxed">
                  {preMoveTrap.message}
                </p>
                {preMoveTrap.escape_squares?.length > 0 && (
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-[10px] text-muted-foreground uppercase">Escapes:</span>
                    {preMoveTrap.escape_squares.map((sq) => (
                      <span key={sq} className="text-xs font-mono bg-amber-500/10 text-amber-500 px-1.5 py-0.5 rounded border border-amber-500/20">
                        {sq}
                      </span>
                    ))}
                  </div>
                )}
                {preMoveTrap.is_trappable_in_2 && preMoveTrap.trap_sequence?.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-amber-500/10 text-xs">
                    <span className="text-amber-500 font-semibold">
                      You can trap it in {preMoveTrap.trap_sequence.length} moves!
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Coach Thinking Indicator — only in old mode */}
            {!suppressOldCoaching && isCoachThinking &&
              !v5Coaching &&
              !guardianIntervention &&
              !session?.curriculum_active && (
                <div
                  data-testid="coach-thinking-indicator"
                  className="p-4 rounded-lg bg-primary/5 border border-primary/10 animate-pulse"
                >
                  <div className="flex items-center gap-3">
                    <Loader2 className="w-5 h-5 text-primary animate-spin" />
                    <div>
                      <p className="text-sm font-medium text-primary">
                        Analyzing your move...
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Coach is evaluating the position
                      </p>
                    </div>
                  </div>
                </div>
              )}

            {/* User's Move Feedback — only in old mode */}
            {(() => {
              if (v5Coaching) {
                console.log("[V2-RENDER] v5Coaching present:", JSON.stringify({
                  severity: v5Coaching.severity,
                  fundamental: v5Coaching.fundamental_violated,
                  socratic: v5Coaching.socratic_question?.substring(0, 40),
                  suppressOldCoaching,
                  curriculum: session?.curriculum_active,
                  willRender: !session?.curriculum_active,
                }));
              }
              return null;
            })()}
            {v5Coaching && !session?.curriculum_active && (
              <V5CoachingCard
                coaching={v5Coaching}
                moveSan={v5Coaching.move_san}
                onShowAlternativeMove={showAlternativeMove}
                onAcknowledge={handleAcknowledgeConcept}
                isAcknowledged={acknowledgedConcepts.has(
                  v5Coaching.concept_id
                )}
                showAcknowledgeButton={true}
                sessionId={session?.session_id}
                source="coach"
              />
            )}

            {/* Fundamentals Checklist — only in old mode */}
            {v5Coaching?.checklist_snapshot && (
              <FundamentalsChecklist snapshot={v5Coaching.checklist_snapshot} />
            )}

            {/* Trap Opportunity — only in old mode */}
            {v5Coaching?.trap_opportunity && (
              <div className="p-3 rounded-lg border border-amber-500/20 bg-amber-500/5" data-testid="trap-opportunity">
                <div className="flex items-center gap-2 mb-2">
                  <Target className="w-4 h-4 text-amber-500" strokeWidth={2} />
                  <span className="text-xs font-bold uppercase tracking-wider text-amber-500">
                    Escape Square Control
                  </span>
                </div>
                <p className="text-sm text-foreground leading-relaxed">
                  {v5Coaching.trap_opportunity.message}
                </p>
                {v5Coaching.trap_opportunity.escape_squares?.length > 0 && (
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Escapes:</span>
                    {v5Coaching.trap_opportunity.escape_squares.map((sq) => (
                      <span key={sq} className="text-xs font-mono bg-amber-500/10 text-amber-500 px-1.5 py-0.5 rounded border border-amber-500/20">
                        {sq}
                      </span>
                    ))}
                    <span className="text-[10px] font-mono text-muted-foreground ml-auto">
                      {v5Coaching.trap_opportunity.escape_count}/6
                    </span>
                  </div>
                )}
                {v5Coaching.trap_opportunity.reduction_moves?.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-amber-500/10">
                    <span className="text-[10px] text-muted-foreground">Try: </span>
                    <span className="text-xs font-mono font-semibold text-amber-500">
                      {v5Coaching.trap_opportunity.reduction_moves[0].move_san}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {" "}blocks {v5Coaching.trap_opportunity.reduction_moves[0].blocks?.join(", ")}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Position Evaluation — hide when v2 coach explanation is showing */}
            {v5Coaching?.eval_label && !interactiveCoaching?.coachMoveCoaching?.v2_intent && (
              <EvalBadge evalLabel={v5Coaching.eval_label} size="md" showDescription />
            )}

            {/* Position Intelligence — hide when v2 coach explanation is showing */}
            {v5Coaching?.position_read && !interactiveCoaching?.coachMoveCoaching?.v2_intent && (
              <div className="p-3 rounded-lg border border-blue-500/15 bg-blue-500/5" data-testid="position-read">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-blue-500">
                    Board Reading
                  </span>
                  {v5Coaching.position_read.phase && (
                    <span className="text-[10px] font-mono text-muted-foreground/50 uppercase">
                      {v5Coaching.position_read.phase}
                    </span>
                  )}
                </div>
                {v5Coaching.position_read.material && (
                  <p className="text-[11px] text-muted-foreground font-medium mb-1">
                    {v5Coaching.position_read.material}
                  </p>
                )}
                <p className="text-sm text-foreground leading-relaxed mb-2">
                  {v5Coaching.position_read.plan}
                </p>
                {v5Coaching.position_read.observations?.length > 0 && (
                  <div className="space-y-1 pt-2 border-t border-blue-500/10">
                    {v5Coaching.position_read.observations.map((obs, i) => (
                      <p key={i} className="text-xs text-muted-foreground">
                        <span className="text-blue-500 mr-1">•</span>
                        {obs.description || obs.title}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Behavioral Coaching — only in old mode */}
            {!suppressOldCoaching && behavioralCoaching && !session?.curriculum_active && (
              <div
                data-testid="behavioral-coaching"
                className={`p-3 rounded-lg border ${
                  behavioralCoaching.severity === "high"
                    ? "bg-red-50 border-red-200"
                    : behavioralCoaching.type === "positive"
                    ? "bg-emerald-50 border-emerald-200"
                    : "bg-orange-500/10 border-orange-500/30"
                }`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-lg shrink-0">
                    {behavioralCoaching.type === "positive"
                      ? "⭐"
                      : behavioralCoaching.type === "emotional"
                      ? "🧠"
                      : behavioralCoaching.type === "calculation"
                      ? "🧮"
                      : behavioralCoaching.type === "pattern"
                      ? "🔄"
                      : "⏱️"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p
                      className={`text-sm font-medium mb-1 ${
                        behavioralCoaching.type === "positive"
                          ? "text-emerald-700"
                          : behavioralCoaching.severity === "high"
                          ? "text-red-600"
                          : "text-orange-300"
                      }`}
                    >
                      {behavioralCoaching.type === "time_management"
                        ? "Time Check"
                        : behavioralCoaching.type === "emotional"
                        ? "Mental Check"
                        : behavioralCoaching.type === "calculation"
                        ? "Calculation"
                        : behavioralCoaching.type === "pattern"
                        ? "Pattern Alert"
                        : behavioralCoaching.type === "positive"
                        ? "Nice!"
                        : "Habit"}
                    </p>
                    <p className="text-sm text-white/90">
                      {behavioralCoaching.message}
                    </p>
                    {behavioralCoaching.actionable_tip && (
                      <p className="text-xs text-muted-foreground mt-2 italic">
                        Tip: {behavioralCoaching.actionable_tip}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* (Coach Timeline moved to top of sidebar under new coaching system) */}

            {/* Teaching Mode Instruction */}
            {isInTeachingMode &&
              activeLesson &&
              lessonInstruction &&
              !lessonComplete && (
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
                  <div className="flex items-center gap-2 mb-1">
                    <BookOpen className="w-4 h-4 text-amber-500" />
                    <span className="text-sm font-medium text-amber-500">
                      {activeLesson.lesson_name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      ({lessonInstruction.remaining} left)
                    </span>
                  </div>
                  <p className="text-sm">
                    {lessonInstruction.is_user_move
                      ? `Your turn → play ${lessonInstruction.move}`
                      : `Coach plays ${lessonInstruction.move}...`}
                  </p>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="mt-2 h-6 text-xs"
                    onClick={() => handleExitLesson("continue_game", {})}
                  >
                    Exit lesson
                  </Button>
                </div>
              )}
          </div>

          {/* Footer - Move History */}
          <div className="p-4 border-t border-border">
            <MoveHistorySection
              moves={session?.move_history?.map((m) => m.move) || []}
              currentMoveIndex={(session?.move_history?.length || 0) - 1}
              onMoveClick={() => {}}
              defaultExpanded={false}
            />
          </div>
        </>
      ) : (
        <>
          {/* Legacy Header */}
          <div className="p-4 border-b border-border">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Brain className="w-5 h-5 text-primary" />
              Coach Chat
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Ask questions anytime. Coach speaks on teachable moments.
            </p>
          </div>
        </>
      )}

      {/* Feedback Modal (shared) */}
      <InlineFeedbackModal
        feedbackMessage={feedbackMessage}
        setFeedbackMessage={setFeedbackMessage}
        feedbackType={feedbackType}
        setFeedbackType={setFeedbackType}
        feedbackComment={feedbackComment}
        setFeedbackComment={setFeedbackComment}
        feedbackCorrectPattern={feedbackCorrectPattern}
        setFeedbackCorrectPattern={setFeedbackCorrectPattern}
        submitFeedback={submitFeedback}
      />

      {/* Legacy panels */}
      {!cleanUIMode && (
        <>
          {session && !gameOver && (
            <div className="p-4 border-b border-border">
              <DeepMemoryPanel compact={true} />
            </div>
          )}

          {session &&
            !gameOver &&
            openingGuidance?.teaching_active &&
            openingGuidance.guidance && (
              <div className="px-4 pb-4 border-b border-border">
                <OpeningGuidePanel
                  openingGuidance={openingGuidance}
                  activeLesson={activeLesson}
                  sessionId={session?.session_id}
                  onStartLesson={handleStartLesson}
                  onSkipTrap={() =>
                    setOpeningGuidance((prev) => ({
                      ...prev,
                      suggested_trap: null,
                    }))
                  }
                />
              </div>
            )}
        </>
      )}

      {/* Export Session Button — for debugging */}
      {session && gameOver && (
        <div className="px-4 pt-3">
          <ExportSessionButton sessionId={session.session_id} />
        </div>
      )}

      {/* Post-Game Reflection (both modes) */}
      {session && gameOver && summary && summary.has_data && (
        <div className="p-4 border-b border-border">
          <PostGameReflection
            data={summary}
            onPlayAgain={newGame}
            onGoTrain={() => window.location.href = "/training"}
          />
        </div>
      )}

      {/* Post-Game Lesson — only if no reflection data */}
      {session && gameOver && (!summary || !summary.has_data) && (
        <div className="p-4 border-b border-border">
          <PostGameLesson
            sessionId={session.session_id}
            result={session.result || "1/2-1/2"}
            studentColor={session.user_color}
            moves={(session.move_history || []).map((m) => m.move)}
            onPlayAgain={newGame}
          />
        </div>
      )}

      {/* Legacy teaching + emotional + chat panels */}
      {!cleanUIMode && (
        <>
          {session &&
            teachingOffer &&
            !inlineOpening &&
            !inlineTrap &&
            !isInTeachingMode &&
            !gameOver && (
              <div className="p-4 border-b border-border">
                <OpeningTeachingOffer
                  offer={teachingOffer}
                  sessionId={session.session_id}
                  onStartLesson={handleStartLesson}
                  onSkip={handleSkipTeachingOffer}
                />
              </div>
            )}

          {session && !gameOver && blundersThisGame > 0 && (
            <EmotionalStateIndicator
              blundersThisGame={blundersThisGame}
              recentResults={recentResults}
              onTakeBreak={() => {}}
            />
          )}

          <LegacyChatMessages
            chatMessages={chatMessages}
            isSendingChat={isSendingChat}
            chatEndRef={chatEndRef}
            sendChatMessage={sendChatMessage}
            setFeedbackMessage={setFeedbackMessage}
            setInlineOpening={setInlineOpening}
            moveFeedback={moveFeedback}
            setMoveFeedback={setMoveFeedback}
            loadingFeedback={loadingFeedback}
            gameOver={gameOver}
          />

          {/* Game over summary */}
          {gameOver && (
            <GameOverCard gameResult={gameResult} summary={summary} />
          )}

          {/* Legacy Move History */}
          <details className="border-t border-border">
            <summary className="p-3 text-sm cursor-pointer hover:bg-muted/50 flex items-center gap-2">
              <Swords className="w-4 h-4" />
              Move History ({session?.move_history?.length || 0} moves)
            </summary>
            <div className="px-3 pb-3 max-h-[150px] overflow-y-auto font-mono text-xs">
              {session?.move_history?.length > 0 ? (
                <div className="space-y-1">
                  {Array.from({
                    length: Math.ceil(session.move_history.length / 2),
                  }).map((_, i) => {
                    const whiteMove = session.move_history[i * 2];
                    const blackMove = session.move_history[i * 2 + 1];
                    return (
                      <div key={i} className="flex gap-2">
                        <span className="text-muted-foreground w-5">
                          {i + 1}.
                        </span>
                        <span
                          className={
                            whiteMove?.by === "player" ? "text-primary" : ""
                          }
                        >
                          {whiteMove?.move || ""}
                        </span>
                        <span
                          className={
                            blackMove?.by === "player" ? "text-primary" : ""
                          }
                        >
                          {blackMove?.move || ""}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-2">
                  No moves yet
                </p>
              )}
            </div>
          </details>

          {/* Guardian Status */}
          <div className="p-3 border-t border-border text-xs">
            <ShieldAlert className="w-3 h-3 inline mr-1 text-primary" />
            <span className="text-muted-foreground">
              Guardian: {remainingInterventions} intervention
              {remainingInterventions !== 1 ? "s" : ""} remaining
            </span>
          </div>
        </>
      )}
    </div>
  );
};

// ─── Export Session Button ───────────────────────────────────────

const ExportSessionButton = ({ sessionId }) => {
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch(`${API}/coach/play/export-session/${sessionId}`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error("Export failed");
      const data = await res.json();

      // Download as JSON file
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `session_${sessionId.slice(0, 8)}_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Export failed:", e);
    } finally {
      setExporting(false);
    }
  };

  return (
    <button
      onClick={handleExport}
      disabled={exporting}
      className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg border border-border text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-all"
    >
      {exporting ? (
        <Loader2 className="w-3 h-3 animate-spin" />
      ) : (
        <Download className="w-3 h-3" />
      )}
      {exporting ? "Exporting..." : "Export Session (Debug)"}
    </button>
  );
};


// ─── Pre-Move Fundamentals Reminder ─────────────────────────────

const PRE_MOVE_CHECKLIST = [
  { key: "threats", label: "What is my opponent threatening?", icon: "👁" },
  { key: "hanging", label: "Are any of my pieces undefended?", icon: "🛡" },
  { key: "checks", label: "Any checks, captures, or threats?", icon: "⚡" },
  { key: "plan", label: "What is my plan with this move?", icon: "🎯" },
];

const PreMoveFundamentals = () => {
  return (
    <div className="rounded-xl border border-primary/10 bg-primary/[0.03] p-3.5">
      <p className="text-[10px] uppercase tracking-widest font-bold text-primary/60 mb-2.5">
        Before you move
      </p>
      <div className="space-y-2">
        {PRE_MOVE_CHECKLIST.map((item) => (
          <div key={item.key} className="flex items-start gap-2">
            <span className="text-sm leading-none mt-0.5">{item.icon}</span>
            <p className="text-xs text-foreground/70 leading-snug">{item.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
};


// ─── Fundamentals Checklist ─────────────────────────────────────

const FUNDAMENTAL_ICONS = {
  check_opponents_move: { label: "Threats", icon: "👁" },
  hanging_pieces: { label: "Hanging", icon: "🛡" },
  king_safety: { label: "King", icon: "♔" },
  calculate: { label: "Calculate", icon: "🧮" },
  development: { label: "Develop", icon: "♞" },
  center_control: { label: "Center", icon: "⊞" },
  have_a_plan: { label: "Plan", icon: "🎯" },
};

const FundamentalsChecklist = ({ snapshot }) => {
  if (!snapshot) return null;
  const entries = Object.entries(snapshot);
  return (
    <div className="flex flex-wrap gap-1.5 px-1 py-2">
      {entries.map(([key, passed]) => {
        const info = FUNDAMENTAL_ICONS[key] || { label: key, icon: "?" };
        return (
          <span
            key={key}
            title={info.label}
            className={`text-xs px-1.5 py-0.5 rounded ${
              passed
                ? "bg-emerald-50 text-emerald-600 border border-emerald-200"
                : "bg-red-50 text-red-600 border border-red-200 font-semibold"
            }`}
          >
            {info.icon} {info.label}
          </span>
        );
      })}
    </div>
  );
};

export default CoachPlaySidebar;
