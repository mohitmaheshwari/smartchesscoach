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
  Eye
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const MoveFeedbackPanel = ({ feedback, onDismiss, onSocraticResponse }) => {
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
    memory_reference
  } = feedback;
  
  // Quality colors
  const qualityColors = {
    excellent: "text-green-400 bg-green-500/10 border-green-500/30",
    good: "text-blue-400 bg-blue-500/10 border-blue-500/30",
    inaccuracy: "text-amber-400 bg-amber-500/10 border-amber-500/30",
    mistake: "text-orange-400 bg-orange-500/10 border-orange-500/30",
    blunder: "text-red-400 bg-red-500/10 border-red-500/30"
  };
  
  const qualityEmoji = {
    excellent: "🎯",
    good: "👍",
    inaccuracy: "🤔",
    mistake: "⚠️",
    blunder: "❌"
  };
  
  const isGoodMove = ["excellent", "good"].includes(user_move_quality);
  const shouldShowSocratic = socratic_question && expects_response && !showingAnswer && !isGoodMove;
  
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
      
      {/* SOCRATIC MODE - Ask before telling */}
      <AnimatePresence mode="wait">
        {shouldShowSocratic ? (
          <motion.div
            key="socratic"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="space-y-3"
          >
            {/* Coach's question */}
            <div className="flex items-start gap-2 p-3 rounded-lg bg-primary/10 border border-primary/30">
              <HelpCircle className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium">{socratic_question}</p>
                {pattern_reference && (
                  <p className="text-xs text-amber-400 mt-2">
                    <Lightbulb className="w-3 h-3 inline mr-1" />
                    {pattern_reference}
                  </p>
                )}
              </div>
            </div>
            
            {/* User's response input */}
            <div className="space-y-2">
              <Textarea
                placeholder="Type your thinking here... What was your plan?"
                value={userResponse}
                onChange={(e) => setUserResponse(e.target.value)}
                className="text-sm min-h-[60px] bg-background/50"
                disabled={hasResponded}
              />
              
              <div className="flex gap-2">
                <Button 
                  size="sm" 
                  onClick={handleSubmitResponse}
                  disabled={hasResponded}
                  className="flex-1"
                >
                  <Send className="w-3 h-3 mr-2" />
                  Share my thinking
                </Button>
                <Button 
                  size="sm" 
                  variant="outline"
                  onClick={handleShowAnswer}
                >
                  <Eye className="w-3 h-3 mr-2" />
                  Show answer
                </Button>
              </div>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="feedback"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-3"
          >
            {/* Main coaching message */}
            <p className="text-sm">
              {coaching_message}
            </p>
            
            {/* Pattern reference - "This is the 3rd time this week..." */}
            {pattern_reference && (
              <div className="p-2 rounded bg-amber-500/10 border border-amber-500/30">
                <p className="text-xs text-amber-400">
                  <Lightbulb className="w-3 h-3 inline mr-1" />
                  {pattern_reference}
                </p>
              </div>
            )}
            
            {/* Memory reference - "Remember your game last Tuesday?" */}
            {memory_reference && (
              <div className="p-2 rounded bg-blue-500/10 border border-blue-500/30">
                <p className="text-xs text-blue-400">
                  <Brain className="w-3 h-3 inline mr-1" />
                  {memory_reference}
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
                <p className="text-xs text-muted-foreground pl-5 mb-2">
                  {trap_suggestion.description}
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
                  <p className="text-xs text-muted-foreground pl-5">
                    {best_move_explanation}
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
                  <p className="text-xs text-muted-foreground pl-5 mt-1">
                    {coach_move_explanation}
                  </p>
                )}
              </div>
            )}
            
            {/* Personal feedback */}
            {relates_to_weakness && (
              <div className="text-xs text-amber-400 border-t border-border/50 pt-2">
                <Lightbulb className="w-3 h-3 inline mr-1" />
                {relates_to_weakness}
              </div>
            )}
            
            {/* Encouragement */}
            {encouragement && (
              <div className={`text-xs border-t border-border/50 pt-2 ${isGoodMove ? 'text-green-400' : 'text-muted-foreground'}`}>
                <CheckCircle2 className="w-3 h-3 inline mr-1" />
                {encouragement}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default MoveFeedbackPanel;
