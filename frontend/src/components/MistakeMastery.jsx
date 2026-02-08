import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";
import { 
  Target,
  Brain,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Trophy,
  Flame,
  Clock,
  Loader2,
  ArrowRight,
  RotateCcw,
  Sparkles
} from "lucide-react";

/**
 * MistakeMastery Component
 * 
 * The Mistake Mastery System - spaced repetition for your own chess mistakes.
 * 
 * Modes:
 * - post_game_debrief: Shows THE critical moment from a game you just played
 * - daily_training: Shows due cards from your active habit
 * - all_caught_up: No cards due, encourages playing
 */
const MistakeMastery = ({ token, onComplete }) => {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [phase, setPhase] = useState("question"); // question, feedback, complete
  const [selectedMove, setSelectedMove] = useState(null);
  const [result, setResult] = useState(null); // correct, incorrect
  const [submitting, setSubmitting] = useState(false);
  const [sessionStats, setSessionStats] = useState({ correct: 0, incorrect: 0 });

  // Fetch training session
  const fetchSession = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/training/session`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error("Failed to fetch training session");
      const data = await res.json();
      setSession(data);
      setCurrentCardIndex(0);
      setPhase("question");
      setSelectedMove(null);
      setResult(null);
    } catch (err) {
      console.error("Training session error:", err);
      toast.error("Couldn't load training session");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchSession();
  }, [fetchSession]);

  // Get current card
  const getCurrentCard = () => {
    if (!session) return null;
    if (session.mode === "post_game_debrief") return session.card;
    if (session.mode === "daily_training" && session.cards?.length > 0) {
      return session.cards[currentCardIndex];
    }
    return null;
  };

  const currentCard = getCurrentCard();
  const totalCards = session?.mode === "daily_training" ? (session.cards?.length || 0) : 1;

  // Handle move selection
  const handleMoveSelect = (move) => {
    if (phase !== "question") return;
    setSelectedMove(move);
  };

  // Submit answer
  const submitAnswer = async () => {
    if (!selectedMove || !currentCard || submitting) return;
    
    setSubmitting(true);
    const isCorrect = selectedMove === currentCard.correct_move;
    
    try {
      // Record the attempt
      const res = await fetch(`${API}/training/attempt`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          card_id: currentCard.card_id,
          correct: isCorrect
        })
      });
      
      if (!res.ok) throw new Error("Failed to record attempt");
      
      const attemptResult = await res.json();
      
      setResult(isCorrect ? "correct" : "incorrect");
      setPhase("feedback");
      setSessionStats(prev => ({
        correct: prev.correct + (isCorrect ? 1 : 0),
        incorrect: prev.incorrect + (isCorrect ? 0 : 1)
      }));
      
      // Check if card was mastered
      if (attemptResult.is_mastered) {
        toast.success("Position mastered! 🎉");
      }
    } catch (err) {
      console.error("Submit error:", err);
      toast.error("Couldn't save your answer");
    } finally {
      setSubmitting(false);
    }
  };

  // Go to next card
  const nextCard = () => {
    if (currentCardIndex < totalCards - 1) {
      setCurrentCardIndex(prev => prev + 1);
      setPhase("question");
      setSelectedMove(null);
      setResult(null);
    } else {
      setPhase("complete");
    }
  };

  // Render loading state
  if (loading) {
    return (
      <Card className="border-primary/20">
        <CardContent className="py-16 flex flex-col items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
          <p className="text-muted-foreground">Loading training...</p>
        </CardContent>
      </Card>
    );
  }

  // Render "all caught up" state
  if (session?.mode === "all_caught_up") {
    return (
      <Card className="border-emerald-500/30 bg-gradient-to-br from-emerald-500/5 to-transparent">
        <CardContent className="py-12 text-center">
          <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-4">
            <Trophy className="w-8 h-8 text-emerald-500" />
          </div>
          <h3 className="text-xl font-semibold mb-2">All Caught Up!</h3>
          <p className="text-muted-foreground mb-6">{session.message}</p>
          
          {session.next_review && (
            <p className="text-sm text-muted-foreground mb-4">
              <Clock className="w-4 h-4 inline mr-1" />
              Next review: {new Date(session.next_review).toLocaleDateString()}
            </p>
          )}
          
          <Button onClick={onComplete} className="gap-2">
            <ArrowRight className="w-4 h-4" />
            Go Play
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Render complete state (finished all cards)
  if (phase === "complete") {
    const accuracy = sessionStats.correct + sessionStats.incorrect > 0
      ? Math.round((sessionStats.correct / (sessionStats.correct + sessionStats.incorrect)) * 100)
      : 0;
    
    return (
      <Card className="border-primary/30">
        <CardContent className="py-12 text-center">
          <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-8 h-8 text-primary" />
          </div>
          <h3 className="text-xl font-semibold mb-2">Training Complete!</h3>
          
          <div className="flex justify-center gap-8 my-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-emerald-500">{sessionStats.correct}</div>
              <div className="text-xs text-muted-foreground">Correct</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-red-500">{sessionStats.incorrect}</div>
              <div className="text-xs text-muted-foreground">Incorrect</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-primary">{accuracy}%</div>
              <div className="text-xs text-muted-foreground">Accuracy</div>
            </div>
          </div>
          
          <div className="flex justify-center gap-3">
            <Button variant="outline" onClick={fetchSession} className="gap-2">
              <RotateCcw className="w-4 h-4" />
              More Training
            </Button>
            <Button onClick={onComplete} className="gap-2">
              <ArrowRight className="w-4 h-4" />
              Continue
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // No card available
  if (!currentCard) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Brain className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">No training cards available yet.</p>
          <p className="text-sm text-muted-foreground mt-2">Play and analyze some games to get started!</p>
        </CardContent>
      </Card>
    );
  }

  // Render training card
  return (
    <Card className="border-primary/20 overflow-hidden">
      {/* Header */}
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {session.mode === "post_game_debrief" ? (
              <>
                <Flame className="w-5 h-5 text-orange-500" />
                <CardTitle className="text-lg">Post-Game Debrief</CardTitle>
              </>
            ) : (
              <>
                <Target className="w-5 h-5 text-primary" />
                <CardTitle className="text-lg">
                  {session.active_habit_display || "Daily Training"}
                </CardTitle>
              </>
            )}
          </div>
          
          {/* Progress indicator */}
          {session.mode === "daily_training" && totalCards > 1 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {currentCardIndex + 1}/{totalCards}
              </span>
              <Progress 
                value={((currentCardIndex + 1) / totalCards) * 100} 
                className="w-20 h-2"
              />
            </div>
          )}
        </div>
        
        {/* Game info for post-game */}
        {session.mode === "post_game_debrief" && session.game_info && (
          <p className="text-sm text-muted-foreground mt-1">
            vs {session.game_info.white_player === session.game_info.black_player 
              ? "opponent" 
              : session.game_info.user_color === "white" 
                ? session.game_info.black_player 
                : session.game_info.white_player}
            {" • "}
            {session.game_info.result === "1-0" 
              ? (session.game_info.user_color === "white" ? "Won" : "Lost")
              : session.game_info.result === "0-1"
                ? (session.game_info.user_color === "black" ? "Won" : "Lost")
                : "Draw"}
          </p>
        )}
        
        {/* Habit progress */}
        {session.habit_progress && (
          <div className="mt-2 p-2 rounded bg-muted/50">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Habit Progress</span>
              <span className="font-medium">
                {session.habit_progress.mastered_cards}/{session.habit_progress.total_cards} mastered
              </span>
            </div>
            <Progress 
              value={session.habit_progress.progress_pct} 
              className="h-1.5 mt-1"
            />
          </div>
        )}
      </CardHeader>

      <CardContent className="pt-4">
        {/* Chess Board */}
        <div className="flex flex-col lg:flex-row gap-6">
          <div className="flex-1 max-w-md mx-auto lg:mx-0">
            <div className="aspect-square">
              <Chessboard 
                position={currentCard.fen}
                boardOrientation={currentCard.phase === "endgame" ? "white" : 
                  (currentCard.fen.includes(" w ") ? "white" : "black")}
                arePiecesDraggable={false}
                customBoardStyle={{
                  borderRadius: "8px",
                  boxShadow: "0 4px 20px rgba(0,0,0,0.3)"
                }}
              />
            </div>
            
            {/* Move info */}
            <div className="mt-3 text-center">
              <span className="text-sm text-muted-foreground">
                Move {currentCard.move_number} • 
                {currentCard.evaluation === "blunder" && " Blunder"}
                {currentCard.evaluation === "mistake" && " Mistake"}
                {currentCard.evaluation === "inaccuracy" && " Inaccuracy"}
                {" (-"}{(currentCard.cp_loss / 100).toFixed(1)}{")"}
              </span>
            </div>
          </div>

          {/* Question/Feedback Panel */}
          <div className="flex-1 flex flex-col justify-center">
            <AnimatePresence mode="wait">
              {phase === "question" && (
                <motion.div
                  key="question"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="space-y-4"
                >
                  <h4 className="text-lg font-medium">What should you play here?</h4>
                  
                  {/* Move options */}
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={() => handleMoveSelect(currentCard.correct_move)}
                      className={`p-4 rounded-lg border-2 transition-all text-left ${
                        selectedMove === currentCard.correct_move
                          ? "border-primary bg-primary/10"
                          : "border-border hover:border-primary/50"
                      }`}
                      data-testid="move-option-correct"
                    >
                      <span className="font-mono text-lg">{currentCard.correct_move}</span>
                    </button>
                    
                    <button
                      onClick={() => handleMoveSelect(currentCard.user_move)}
                      className={`p-4 rounded-lg border-2 transition-all text-left ${
                        selectedMove === currentCard.user_move
                          ? "border-primary bg-primary/10"
                          : "border-border hover:border-primary/50"
                      }`}
                      data-testid="move-option-user"
                    >
                      <span className="font-mono text-lg">{currentCard.user_move}</span>
                    </button>
                  </div>
                  
                  {/* Submit button */}
                  <Button
                    onClick={submitAnswer}
                    disabled={!selectedMove || submitting}
                    className="w-full gap-2"
                    data-testid="submit-answer-btn"
                  >
                    {submitting ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                    Submit Answer
                  </Button>
                </motion.div>
              )}

              {phase === "feedback" && (
                <motion.div
                  key="feedback"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="space-y-4"
                >
                  {/* Result indicator */}
                  <div className={`p-4 rounded-lg ${
                    result === "correct" 
                      ? "bg-emerald-500/10 border border-emerald-500/30"
                      : "bg-red-500/10 border border-red-500/30"
                  }`}>
                    <div className="flex items-center gap-3">
                      {result === "correct" ? (
                        <CheckCircle2 className="w-8 h-8 text-emerald-500" />
                      ) : (
                        <XCircle className="w-8 h-8 text-red-500" />
                      )}
                      <div>
                        <h4 className={`font-semibold ${
                          result === "correct" ? "text-emerald-500" : "text-red-500"
                        }`}>
                          {result === "correct" ? "Correct!" : "Not quite..."}
                        </h4>
                        <p className="text-sm text-muted-foreground">
                          Best move: <span className="font-mono font-medium">{currentCard.correct_move}</span>
                        </p>
                      </div>
                    </div>
                  </div>
                  
                  {/* Explanation */}
                  {currentCard.explanation && (
                    <div className="p-3 rounded bg-muted/50">
                      <p className="text-sm">{currentCard.explanation}</p>
                    </div>
                  )}
                  
                  {/* Lines if available */}
                  {result === "incorrect" && currentCard.threat_line?.length > 0 && (
                    <div className="p-3 rounded bg-red-500/5 border border-red-500/20">
                      <p className="text-xs text-muted-foreground mb-1">After your move:</p>
                      <p className="font-mono text-sm text-red-400">
                        {currentCard.threat_line.slice(0, 4).join(" ")}
                      </p>
                    </div>
                  )}
                  
                  {currentCard.better_line?.length > 0 && (
                    <div className="p-3 rounded bg-emerald-500/5 border border-emerald-500/20">
                      <p className="text-xs text-muted-foreground mb-1">Better line:</p>
                      <p className="font-mono text-sm text-emerald-400">
                        {currentCard.better_line.slice(0, 4).join(" ")}
                      </p>
                    </div>
                  )}
                  
                  {/* Habit tag */}
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Habit:</span>
                    <span className="text-xs px-2 py-1 rounded bg-primary/10 text-primary">
                      {currentCard.habit_tag?.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                  </div>
                  
                  {/* Next button */}
                  <Button onClick={nextCard} className="w-full gap-2" data-testid="next-card-btn">
                    {currentCardIndex < totalCards - 1 ? "Next Position" : "Finish"}
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default MistakeMastery;
