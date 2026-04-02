/**
 * HabitChallenge - Break the Habit Training Mode
 * 
 * Presents positions from user's past mistakes and asks them
 * to find the correct move. Ultimate personalized training!
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { Chess } from "chess.js";
import { Chessground } from "chessground";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Brain,
  Target,
  CheckCircle2,
  XCircle,
  ChevronRight,
  RotateCcw,
  Loader2,
  Zap,
  Trophy,
  Lightbulb
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";
import { API } from "@/App";

const HabitChallenge = ({ onClose }) => {
  const boardRef = useRef(null);
  const groundRef = useRef(null);
  const chessRef = useRef(new Chess());
  
  const [loading, setLoading] = useState(true);
  const [challenges, setChallenges] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [coachMessage, setCoachMessage] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [score, setScore] = useState({ correct: 0, total: 0 });
  const [showHint, setShowHint] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [boardReady, setBoardReady] = useState(false);
  
  const currentChallenge = challenges[currentIndex];
  
  // Fetch challenges
  useEffect(() => {
    fetchChallenges();
  }, []);
  
  const fetchChallenges = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/coach/habit-challenge`, {
        credentials: "include"
      });
      
      if (res.ok) {
        const data = await res.json();
        setChallenges(data.challenges || []);
        setCoachMessage(data.coach_message);
      }
    } catch (err) {
      console.error("Error fetching habit challenges:", err);
      toast.error("Could not load challenges");
    } finally {
      setLoading(false);
    }
  };
  
  // Initialize board - only once when the DOM element is ready
  useEffect(() => {
    const initBoard = () => {
      if (boardRef.current && !groundRef.current) {
        groundRef.current = Chessground(boardRef.current, {
          fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
          orientation: "white",
          coordinates: true,
          movable: {
            free: false,
            color: undefined
          },
          animation: { duration: 300 }
        });
        setBoardReady(true);
      }
    };
    
    // Small timeout to ensure DOM is ready
    const timer = setTimeout(initBoard, 50);
    
    return () => {
      clearTimeout(timer);
      if (groundRef.current) {
        groundRef.current.destroy();
        groundRef.current = null;
        setBoardReady(false);
      }
    };
  }, []);
  
  // Handle move
  const handleMove = useCallback(async (orig, dest) => {
    const challenge = challenges[currentIndex];
    if (!challenge) return;
    
    const moveObj = chessRef.current.move({ from: orig, to: dest });
    const moveSan = moveObj?.san || (orig + dest);
    
    try {
      const res = await fetch(`${API}/coach/habit-challenge/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          challenge_id: challenge.challenge_id,
          user_move: moveSan,
          fen: challenge.fen,
          correct_move: challenge.correct_move
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        
        setFeedback({
          correct: data.correct,
          message: data.message
        });
        
        setScore(prev => ({
          correct: prev.correct + (data.correct ? 1 : 0),
          total: prev.total + 1
        }));
        
        // Disable further moves
        if (groundRef.current) {
          groundRef.current.set({
            movable: { free: false, color: undefined }
          });
        }
      }
    } catch (err) {
      console.error("Error checking move:", err);
      toast.error("Could not check your move");
    }
  }, [challenges, currentIndex]);
  
  // Set up board when challenges are loaded or index changes
  useEffect(() => {
    if (!boardReady || challenges.length === 0 || loading) return;
    
    const challenge = challenges[currentIndex];
    if (!challenge || !groundRef.current) return;
    
    const fen = challenge.fen;
    const orientation = challenge.user_color || "white";
    
    chessRef.current.load(fen);
    
    // Determine which color to move
    const toMove = fen.split(" ")[1] === "w" ? "white" : "black";
    
    // Get legal moves for highlighting
    const legalMoves = new Map();
    const moves = chessRef.current.moves({ verbose: true });
    moves.forEach(move => {
      const from = move.from;
      const to = move.to;
      if (!legalMoves.has(from)) {
        legalMoves.set(from, []);
      }
      legalMoves.get(from).push(to);
    });
    
    groundRef.current.set({
      fen: fen,
      orientation: orientation,
      turnColor: toMove,
      movable: {
        free: false,
        color: toMove,
        dests: legalMoves,
        events: {
          after: handleMove
        }
      },
      lastMove: undefined
    });
    
    setFeedback(null);
    setShowHint(false);
  }, [boardReady, challenges, currentIndex, handleMove, loading]);
  
  const nextChallenge = () => {
    if (currentIndex < challenges.length - 1) {
      setCurrentIndex(prev => prev + 1);
    } else {
      setCompleted(true);
    }
  };
  
  const resetChallenges = () => {
    setCurrentIndex(0);
    setScore({ correct: 0, total: 0 });
    setCompleted(false);
    setFeedback(null);
  };
  
  // Show overlay for loading/empty/completed states
  const showBoard = !loading && challenges.length > 0 && !completed;
  
  return (
    <div className="relative min-h-[450px]">
      {/* Overlay states */}
      <AnimatePresence>
        {loading && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 flex items-center justify-center bg-background z-20"
          >
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-muted-foreground">Finding your habits to break...</span>
          </motion.div>
        )}
        
        {!loading && challenges.length === 0 && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 flex flex-col items-center justify-center bg-background z-20"
          >
            <Trophy className="w-12 h-12 mb-4 text-green-400" />
            <h3 className="font-semibold text-lg mb-2">No Habits to Break!</h3>
            <p className="text-muted-foreground mb-4 text-center px-4">
              {coachMessage || "Play more games and I'll find positions to practice."}
            </p>
            <Button onClick={onClose} variant="outline">
              Back to Dashboard
            </Button>
          </motion.div>
        )}
        
        {completed && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 flex flex-col items-center justify-center bg-background z-20"
          >
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 200 }}
            >
              {score.total > 0 && Math.round((score.correct / score.total) * 100) >= 80 ? (
                <Trophy className="w-16 h-16 mb-4 text-yellow-400" />
              ) : score.total > 0 && Math.round((score.correct / score.total) * 100) >= 50 ? (
                <Target className="w-16 h-16 mb-4 text-blue-400" />
              ) : (
                <Brain className="w-16 h-16 mb-4 text-purple-400" />
              )}
            </motion.div>
            
            <h3 className="font-semibold text-2xl mb-2">Challenge Complete!</h3>
            <p className="text-4xl font-bold mb-2">
              {score.correct}/{score.total}
            </p>
            <p className="text-muted-foreground mb-6">
              {score.total > 0 && Math.round((score.correct / score.total) * 100) >= 80 
                ? "Shabash! You're breaking those habits!"
                : score.total > 0 && Math.round((score.correct / score.total) * 100) >= 50
                ? "Good effort! Keep practicing these positions."
                : "Koi baat nahi! Practice makes perfect. Try again!"}
            </p>
            
            <div className="flex gap-3 justify-center">
              <Button onClick={resetChallenges} variant="outline">
                <RotateCcw className="w-4 h-4 mr-2" />
                Try Again
              </Button>
              <Button onClick={() => { setCompleted(false); fetchChallenges(); }}>
                <Zap className="w-4 h-4 mr-2" />
                New Challenges
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Main content - always rendered so board ref is available */}
      <div className={showBoard ? "opacity-100" : "opacity-0 pointer-events-none"}>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-red-500/20">
              <Target className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <h3 className="font-semibold">Break the Habit</h3>
              <p className="text-xs text-muted-foreground">
                Position {currentIndex + 1} of {challenges.length || 1}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-green-400 border-green-500/30">
              {score.correct} correct
            </Badge>
            <Badge variant="outline">
              {score.total} attempted
            </Badge>
          </div>
        </div>
        
        {/* Coach Message */}
        {currentChallenge && (
          <div className="mb-4 p-3 rounded-lg bg-primary/10 border border-primary/30">
            <div className="flex items-start gap-2">
              <Brain className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
              <p className="text-sm">{currentChallenge.message}</p>
            </div>
          </div>
        )}
        
        {/* Board and Info */}
        <div className="flex gap-4">
          <div style={{ width: "350px", height: "350px", flexShrink: 0 }}>
            <div 
              ref={boardRef} 
              className="w-full h-full rounded-lg overflow-hidden"
              style={{ width: "350px", height: "350px" }}
              data-testid="habit-challenge-board"
            />
          </div>
          
          {/* Info Panel */}
          <div className="flex-1 space-y-3">
            {/* What you played */}
            {currentChallenge && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                <p className="text-xs text-red-400 uppercase font-semibold mb-1">
                  What you played
                </p>
                <p className="font-mono text-lg">{currentChallenge.your_move}</p>
                <p className="text-xs text-muted-foreground">
                  Lost {currentChallenge.cp_loss} centipawns
                </p>
              </div>
            )}
            
            {/* Hint */}
            {showHint && currentChallenge && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30"
              >
                <div className="flex items-start gap-2">
                  <Lightbulb className="w-4 h-4 text-amber-400 mt-0.5" />
                  <p className="text-sm">{currentChallenge.hint}</p>
                </div>
              </motion.div>
            )}
            
            {/* Feedback */}
            <AnimatePresence>
              {feedback && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className={`p-3 rounded-lg border ${
                    feedback.correct 
                      ? "bg-green-500/10 border-green-500/30" 
                      : "bg-red-500/10 border-red-500/30"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {feedback.correct ? (
                      <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                    )}
                    <div>
                      <p className="text-sm font-medium">{feedback.message}</p>
                      {!feedback.correct && currentChallenge && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Best move: <span className="font-mono">{currentChallenge.correct_move}</span>
                        </p>
                      )}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            
            {/* Actions */}
            <div className="flex gap-2">
              {!feedback && !showHint && (
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => setShowHint(true)}
                >
                  <Lightbulb className="w-4 h-4 mr-1" />
                  Hint
                </Button>
              )}
              
              {feedback && (
                <Button onClick={nextChallenge} className="flex-1">
                  {currentIndex < challenges.length - 1 ? (
                    <>
                      Next Position
                      <ChevronRight className="w-4 h-4 ml-1" />
                    </>
                  ) : (
                    <>
                      See Results
                      <Trophy className="w-4 h-4 ml-1" />
                    </>
                  )}
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HabitChallenge;
