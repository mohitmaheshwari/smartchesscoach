/**
 * MoveFeedbackPanel - Comprehensive move feedback display with Socratic Mode
 * 
 * Features:
 * - Socratic questioning: Asks "What were you thinking?" before revealing answer
 * - Indian-English conversational style
 * - Pattern recognition: "This is the 3rd time this week..."
 * - Memory references: "Remember your game last Tuesday?"
 */

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Brain,
  CheckCircle2,
  Lightbulb,
  Target,
  Sparkles,
  ArrowRight,
  MessageCircle,
  HelpCircle,
  Send,
  Eye,
  BookOpen,
  AlertCircle,
  Star
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { InlineFlag } from "@/components/shared/FlagMoveDialog";

const MoveFeedbackPanel = ({ feedback, onDismiss, onSocraticResponse, sessionId, gameId }) => {
  const [showingAnswer, setShowingAnswer] = useState(false);
  const [userResponse, setUserResponse] = useState("");
  const [hasResponded, setHasResponded] = useState(false);

  if (!feedback) return null;

  const {
    user_move,
    user_move_quality,
    best_move,
    best_move_explanation,
    coach_move,
    coach_move_explanation,
    coaching_message,
    relates_to_weakness,
    encouragement,
    trap_suggestion,
    // NEW: Socratic mode fields
    socratic_question,
    expects_response,
    pattern_reference,
    memory_reference,
    // NEW: Opening theory note — pairs with the move-level rule to give
    // opening-specific context. See services/opening_theory_note.py.
    opening_theory_note,
    // V5 fields produced by the realtime path — backend was generating
    // these for months but the panel never rendered them. Pass 5 fix.
    golden_rule,
    consequence,
    // Brilliant/sacrifice flags for celebratory visual emphasis.
    is_brilliant,
    is_sacrifice,
    // Position context fields used to enrich tester flags
    fen_before,
  } = feedback;

  // Shared flag context for every InlineFlag in this panel — tester
  // gets full position + classification + best-move data on every flag.
  const flagCtx = {
    source: "play_with_coach",
    sessionId: sessionId || feedback.session_id || null,
    gameId: gameId || feedback.game_id || feedback.session_id || null,
    fen: fen_before || feedback.fen || "",
    moveSan: user_move || null,
    severity: user_move_quality || null,
    bestMove: best_move || null,
    component: "MoveFeedbackPanel",
  };
  
  // Quality colors. "brilliant" gets gold treatment for celebration —
  // backend's sacrifice/brilliant detection earned it; UI was previously
  // dropping is_brilliant on the floor.
  const qualityColors = {
    brilliant: "text-yellow-300 bg-yellow-400/10 border-yellow-400/40",
    excellent: "text-green-400 bg-green-500/10 border-green-500/30",
    good: "text-blue-400 bg-blue-500/10 border-blue-500/30",
    book: "text-blue-400 bg-blue-500/10 border-blue-500/30",
    inaccuracy: "text-amber-400 bg-amber-500/10 border-amber-500/30",
    mistake: "text-orange-400 bg-orange-500/10 border-orange-500/30",
    blunder: "text-red-400 bg-red-500/10 border-red-500/30"
  };

  const qualityEmoji = {
    brilliant: "⭐",
    excellent: "🎯",
    good: "👍",
    book: "📖",
    inaccuracy: "🤔",
    mistake: "⚠️",
    blunder: "❌"
  };

  const isGoodMove = ["excellent", "good", "book", "brilliant"].includes(user_move_quality);
  // Pass 5 fix: don't gate the coaching_message behind the Socratic
  // prompt. Backend was generating real teaching for every mistake/
  // blunder, but the panel hid it until the user clicked "Show answer."
  // Now we always render the coaching, and surface the Socratic
  // question as an optional engagement prompt above it.
  const showSocraticPrompt = socratic_question && expects_response && !isGoodMove && !hasResponded;
  
  const handleSubmitResponse = () => {
    setHasResponded(true);
    if (onSocraticResponse) {
      onSocraticResponse(userResponse);
    }
    // Show the answer after a brief pause
    setTimeout(() => {
      setShowingAnswer(true);
    }, 500);
  };
  
  const handleShowAnswer = () => {
    setShowingAnswer(true);
  };
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-4 rounded-lg border ${qualityColors[user_move_quality] || qualityColors.inaccuracy}`}
      data-testid="move-feedback-panel"
    >
      {/* Header with move quality */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{qualityEmoji[user_move_quality]}</span>
          <span className="font-semibold capitalize">{user_move_quality}</span>
          <Badge variant="outline" className="text-xs">
            {user_move}
          </Badge>
        </div>
        <button 
          onClick={onDismiss}
          className="text-muted-foreground hover:text-foreground text-xs"
        >
          Dismiss
        </button>
      </div>
      
      {/* Coaching content — ALWAYS visible. Pass 5 fix: was previously
          gated behind the Socratic prompt for mistakes/blunders, hiding
          the rich teaching the backend generated. Now the Socratic
          question is an optional engagement prompt that appears
          ALONGSIDE the coaching, not instead of it. */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="space-y-3"
      >
        {/* Optional Socratic prompt — appears for mistakes/blunders to
            encourage thinking-before-reading, but doesn't gate the body. */}
        {showSocraticPrompt && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-primary/10 border border-primary/30">
            <HelpCircle className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-[10px] uppercase tracking-wide text-primary font-medium mb-1">
                Coach asks
              </p>
              <p className="group text-sm font-medium">
                {socratic_question}
                <InlineFlag section="socratic_question" flaggedText={socratic_question} context={flagCtx} />
              </p>
              {/* Inline textarea — collapsed by default. The user can
                  type if they want to engage; otherwise the answer below
                  is already visible. */}
              <details className="mt-2">
                <summary className="text-xs text-primary/80 cursor-pointer hover:text-primary">
                  Share your thinking
                </summary>
                <div className="mt-2 space-y-2">
                  <Textarea
                    placeholder="Type your thinking here... What was your plan?"
                    value={userResponse}
                    onChange={(e) => setUserResponse(e.target.value)}
                    className="text-sm min-h-[60px] bg-background/50"
                    disabled={hasResponded}
                  />
                  <Button
                    size="sm"
                    onClick={handleSubmitResponse}
                    disabled={hasResponded || !userResponse.trim()}
                  >
                    <Send className="w-3 h-3 mr-2" />
                    {hasResponded ? "Shared" : "Share my thinking"}
                  </Button>
                </div>
              </details>
            </div>
          </div>
        )}

        {/* Brilliant/sacrifice celebration — UI emphasis to match the
            backend's brilliant-detection work. Was previously dropped. */}
        {(is_brilliant || is_sacrifice) && (
          <div className="flex items-center gap-2 p-2 rounded bg-yellow-400/5 border border-yellow-400/30">
            <Star className="w-4 h-4 text-yellow-300 flex-shrink-0" />
            <p className="text-xs text-yellow-200 font-medium">
              {is_brilliant
                ? "Brilliant move — the kind that wins games."
                : "A sacrifice. Confidence in your calculation."}
            </p>
          </div>
        )}

        {/* Main coaching message */}
            <p className="group text-sm">
              {coaching_message}
              <InlineFlag section="coaching_message" flaggedText={coaching_message} context={flagCtx} />
            </p>

            {/* Consequence — backend's "what happens next" warning.
                Pass 5 fix: was being generated and dropped on the floor. */}
            {consequence && (
              <div className="flex items-start gap-2 p-2 rounded bg-red-500/5 border border-red-500/20">
                <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] uppercase tracking-wide text-red-400 font-medium mb-1">
                    Watch out
                  </p>
                  <p className="group text-xs text-zinc-200">
                    {consequence}
                    <InlineFlag section="consequence" flaggedText={consequence} context={flagCtx} />
                  </p>
                </div>
              </div>
            )}

            {/* Golden rule — transferable principle the player should
                carry to future games. Pass 5 fix: backend produces this
                regularly; frontend was dropping it. */}
            {golden_rule && (
              <div className="flex items-start gap-2 p-2 rounded bg-amber-500/5 border border-amber-500/20">
                <Lightbulb className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] uppercase tracking-wide text-amber-400 font-medium mb-1">
                    Rule
                  </p>
                  <p className="group text-xs text-zinc-200 italic">
                    {golden_rule}
                    <InlineFlag section="golden_rule" flaggedText={golden_rule} context={flagCtx} />
                  </p>
                </div>
              </div>
            )}

            {/* Opening-theory note — pairs the move-level rule with opening-
                specific theory. Renders in the opening phase only (gated
                server-side to move <= 12). */}
            {opening_theory_note && (
              <div className="p-2 rounded bg-sky-500/5 border border-sky-500/20">
                <div className="flex items-start gap-2">
                  <BookOpen className="w-4 h-4 text-sky-400 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs uppercase tracking-wide text-sky-400 font-medium mb-1">
                      {opening_theory_note.opening_name || "Opening"}
                    </div>
                    {opening_theory_note.summary && (
                      <p className="text-xs text-zinc-200 leading-relaxed">
                        {opening_theory_note.summary}
                      </p>
                    )}
                    {opening_theory_note.key_rule && (
                      <p className="text-xs text-sky-300 mt-1 italic">
                        {opening_theory_note.key_rule}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Pattern reference - "This is the 3rd time this week..." */}
            {pattern_reference && (
              <div className="p-2 rounded bg-amber-500/10 border border-amber-500/30">
                <p className="group text-xs text-amber-400">
                  <Lightbulb className="w-3 h-3 inline mr-1" />
                  {pattern_reference}
                  <InlineFlag section="pattern_reference" flaggedText={pattern_reference} context={flagCtx} />
                </p>
              </div>
            )}

            {/* Memory reference - "Remember your game last Tuesday?" */}
            {memory_reference && (
              <div className="p-2 rounded bg-blue-500/10 border border-blue-500/30">
                <p className="group text-xs text-blue-400">
                  <Brain className="w-3 h-3 inline mr-1" />
                  {memory_reference}
                  <InlineFlag section="memory_reference" flaggedText={memory_reference} context={flagCtx} />
                </p>
              </div>
            )}

            {/* Trap Suggestion */}
            {trap_suggestion && trap_suggestion.moves_until_trap <= 3 && (
              <div className="p-2 rounded bg-purple-500/10 border border-purple-500/30">
                <div className="flex items-center gap-2 text-xs mb-1">
                  <Sparkles className="w-3 h-3 text-purple-400" />
                  <span className="font-medium text-purple-400">
                    Trap Alert: {trap_suggestion.name}
                  </span>
                </div>
                <p className="group text-xs text-muted-foreground pl-5 mb-2">
                  {trap_suggestion.description}
                  <InlineFlag section="trap_suggestion" flaggedText={trap_suggestion.description} context={flagCtx} />
                </p>
                {trap_suggestion.setup_remaining?.length > 0 && (
                  <div className="pl-5 flex items-center gap-1 text-xs">
                    <span className="text-purple-300">Play:</span>
                    {trap_suggestion.setup_remaining.map((move, i) => (
                      <span key={i} className="font-mono text-purple-400">
                        {move}{i < trap_suggestion.setup_remaining.length - 1 ? "," : ""}
                      </span>
                    ))}
                    <ArrowRight className="w-3 h-3 text-purple-400 mx-1" />
                    <span className="text-purple-300">then spring the trap!</span>
                  </div>
                )}
              </div>
            )}
            
            {/* Best move explanation - only if move wasn't excellent */}
            {!isGoodMove && best_move && best_move !== user_move && (
              <div className="p-2 rounded bg-background/50">
                <div className="flex items-center gap-2 text-xs mb-1">
                  <Target className="w-3 h-3 text-primary" />
                  <span className="font-medium text-primary">Best was {best_move}</span>
                </div>
                {best_move_explanation && (
                  <p className="group text-xs text-muted-foreground pl-5">
                    {best_move_explanation}
                    <InlineFlag section="best_move_explanation" flaggedText={best_move_explanation} context={flagCtx} />
                  </p>
                )}
              </div>
            )}

            {/* Coach's response */}
            {coach_move && (
              <div className="p-2 rounded bg-background/50">
                <div className="flex items-center gap-2 text-xs">
                  <MessageCircle className="w-3 h-3 text-primary" />
                  <span className="font-medium">
                    Coach played {coach_move}
                  </span>
                </div>
                {coach_move_explanation && (
                  <p className="group text-xs text-muted-foreground pl-5 mt-1">
                    {coach_move_explanation}
                    <InlineFlag section="coach_move_explanation" flaggedText={coach_move_explanation} context={flagCtx} />
                  </p>
                )}
              </div>
            )}

            {/* Personal feedback */}
            {relates_to_weakness && (
              <div className="group text-xs text-amber-400 border-t border-border/50 pt-2">
                <Lightbulb className="w-3 h-3 inline mr-1" />
                {relates_to_weakness}
                <InlineFlag section="relates_to_weakness" flaggedText={relates_to_weakness} context={flagCtx} />
              </div>
            )}

            {/* Encouragement */}
            {encouragement && (
              <div className={`group text-xs border-t border-border/50 pt-2 ${isGoodMove ? 'text-green-400' : 'text-muted-foreground'}`}>
                <CheckCircle2 className="w-3 h-3 inline mr-1" />
                {encouragement}
                <InlineFlag section="encouragement" flaggedText={encouragement} context={flagCtx} />
              </div>
            )}
      </motion.div>
    </motion.div>
  );
};

export default MoveFeedbackPanel;
