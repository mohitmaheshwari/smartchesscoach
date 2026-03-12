/**
 * InteractivePractice - Practice Opening with AI Coach
 * 
 * The coach plays the opponent's moves and provides Socratic
 * feedback when the user makes mistakes.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { Chess } from "chess.js";
import { Chessground } from "chessground";
import { motion, AnimatePresence } from "framer-motion";
import {
  Play,
  RotateCcw,
  Lightbulb,
  CheckCircle2,
  AlertTriangle,
  Trophy,
  MessageCircle,
  Loader2,
  X
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const InteractivePractice = ({ openingKey, openingName, userColor, onClose }) => {
  const boardRef = useRef(null);
  const groundRef = useRef(null);
  const chessRef = useRef(new Chess());
  
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fen, setFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [isUserTurn, setIsUserTurn] = useState(true);
  const [moveNumber, setMoveNumber] = useState(1);
  const [feedback, setFeedback] = useState(null);
  const [coachMessage, setCoachMessage] = useState(null);
  const [completed, setCompleted] = useState(false);
  const [hintCount, setHintCount] = useState(0);
  const [hint, setHint] = useState(null);
  
  // Initialize board
  useEffect(() => {
    if (boardRef.current && !groundRef.current) {
      groundRef.current = Chessground(boardRef.current, {
        fen: fen,
        orientation: userColor || "white",
        movable: {
          free: false,
          color: undefined
        },
        animation: { duration: 300 }
      });
    }
    
    return () => {
      if (groundRef.current) {
        groundRef.current.destroy();
        groundRef.current = null;
      }
    };
  }, []);
  
  // Update board when FEN changes
  useEffect(() => {
    if (groundRef.current) {
      chessRef.current.load(fen);
      groundRef.current.set({ fen });
    }
  }, [fen]);
  
  // Start practice session
  const startSession = useCallback(async () => {
    setLoading(true);
    setFeedback(null);
    setCoachMessage(null);
    setCompleted(false);
    setHint(null);
    setHintCount(0);
    
    try {
      const res = await fetch(`${API}/openings/${openingKey}/practice/start`, {
        method: "POST",
        credentials: "include"
      });
      
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.session_id);
        setFen(data.fen);
        setMoveNumber(data.move_number);
        setIsUserTurn(data.is_user_turn);
        
        if (data.coach_move) {
          setCoachMessage({
            move: data.coach_move,
            explanation: data.coach_explanation
          });
        }
        
        // Set up board for user's move
        setupUserMove(data.fen);
      } else {
        toast.error("Failed to start practice session");
      }
    } catch (err) {
      console.error("Error starting session:", err);
      toast.error("Failed to start practice session");
    } finally {
      setLoading(false);
    }
  }, [openingKey]);
  
  // Set up board for user to make a move
  const setupUserMove = useCallback((currentFen) => {
    if (!groundRef.current) return;
    
    const chess = new Chess(currentFen);
    const dests = new Map();
    
    for (const move of chess.moves({ verbose: true })) {
      if (!dests.has(move.from)) {
        dests.set(move.from, []);
      }
      dests.get(move.from).push(move.to);
    }
    
    const turnColor = chess.turn() === 'w' ? 'white' : 'black';
    
    groundRef.current.set({
      fen: currentFen,
      turnColor,
      movable: {
        free: false,
        color: turnColor,
        dests
      },
      events: {
        move: handleUserMove
      }
    });
  }, []);
  
  // Handle user's move
  const handleUserMove = useCallback(async (orig, dest) => {
    if (!sessionId) return;
    
    setFeedback(null);
    setHint(null);
    
    const moveUci = orig + dest;
    
    try {
      const res = await fetch(`${API}/openings/practice/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          move: moveUci
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        
        if (data.complete) {
          // Practice completed!
          setCompleted(true);
          setFen(data.fen);
          groundRef.current.set({
            fen: data.fen,
            movable: { free: false, color: undefined }
          });
          setFeedback({
            type: "success",
            message: data.message || "Congratulations! You've mastered this opening line!"
          });
        } else if (data.correct) {
          // Correct move
          setFen(data.fen);
          setMoveNumber(data.move_number);
          setHintCount(0);
          
          // Show coach's response
          if (data.coach_move) {
            setCoachMessage({
              move: data.coach_move,
              explanation: data.coach_explanation
            });
          }
          
          setFeedback({
            type: "correct",
            message: data.your_move_explanation
          });
          
          // Set up for next move after a short delay
          setTimeout(() => {
            setupUserMove(data.fen);
          }, 1000);
        } else if (data.try_again) {
          // Incorrect move - show Socratic feedback
          setFeedback({
            type: "incorrect",
            message: data.feedback?.message || "Not quite. Try again!",
            socratic: true
          });
          
          // Reset board to original position
          setupUserMove(data.fen);
        }
      }
    } catch (err) {
      console.error("Error making move:", err);
      toast.error("Failed to make move");
    }
  }, [sessionId, setupUserMove]);
  
  // Get hint
  const getHint = useCallback(async () => {
    if (!sessionId) return;
    
    try {
      const res = await fetch(`${API}/openings/practice/${sessionId}/hint`, {
        credentials: "include"
      });
      
      if (res.ok) {
        const data = await res.json();
        setHint(data.hint);
        setHintCount(data.hint_level || hintCount + 1);
      }
    } catch (err) {
      console.error("Error getting hint:", err);
    }
  }, [sessionId, hintCount]);
  
  // Reset session
  const resetSession = useCallback(async () => {
    if (sessionId) {
      try {
        await fetch(`${API}/openings/practice/${sessionId}/resign`, {
          method: "POST",
          credentials: "include"
        });
      } catch (err) {
        console.error("Error resigning session:", err);
      }
    }
    
    setSessionId(null);
    setFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    setFeedback(null);
    setCoachMessage(null);
    setCompleted(false);
    setHint(null);
    setHintCount(0);
    
    if (groundRef.current) {
      groundRef.current.set({
        fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        movable: { free: false, color: undefined }
      });
    }
  }, [sessionId]);
  
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageCircle className="w-5 h-5 text-primary" />
          <h3 className="font-semibold">Practice with Coach</h3>
          {moveNumber > 0 && !completed && (
            <Badge variant="outline" className="ml-2">
              Move {moveNumber}
            </Badge>
          )}
        </div>
        {onClose && (
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>
      
      {/* Board */}
      <Card>
        <CardContent className="p-4">
          <div 
            ref={boardRef} 
            className="w-full aspect-square rounded-lg overflow-hidden"
            style={{ maxWidth: "400px", margin: "0 auto" }}
          />
          
          {/* Coach Message */}
          <AnimatePresence>
            {coachMessage && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mt-4 p-3 rounded-lg bg-primary/10 border border-primary/30"
              >
                <div className="flex items-start gap-2">
                  <div className="p-1 rounded-full bg-primary/20">
                    <MessageCircle className="w-4 h-4 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">
                      Coach played: <span className="font-mono">{coachMessage.move}</span>
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {coachMessage.explanation}
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          
          {/* Feedback */}
          <AnimatePresence>
            {feedback && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className={`mt-4 p-3 rounded-lg ${
                  feedback.type === "correct" ? "bg-green-500/10 border border-green-500/30" :
                  feedback.type === "success" ? "bg-primary/10 border border-primary/30" :
                  "bg-amber-500/10 border border-amber-500/30"
                }`}
              >
                <div className="flex items-start gap-2">
                  {feedback.type === "correct" && <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />}
                  {feedback.type === "success" && <Trophy className="w-5 h-5 text-primary flex-shrink-0" />}
                  {feedback.type === "incorrect" && <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />}
                  <div>
                    <p className="text-sm">{feedback.message}</p>
                    {feedback.socratic && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Think about it and try again!
                      </p>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          
          {/* Hint */}
          <AnimatePresence>
            {hint && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mt-3 p-3 rounded-lg bg-blue-500/10 border border-blue-500/30"
              >
                <div className="flex items-start gap-2">
                  <Lightbulb className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-medium text-blue-400 uppercase">
                      Hint {hintCount > 1 ? `(Level ${hintCount})` : ""}
                    </p>
                    <p className="text-sm mt-1">{hint}</p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </CardContent>
      </Card>
      
      {/* Controls */}
      <div className="flex gap-2">
        {!sessionId ? (
          <Button 
            onClick={startSession} 
            className="flex-1"
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Play className="w-4 h-4 mr-2" />
            )}
            Start Practice
          </Button>
        ) : completed ? (
          <Button 
            onClick={startSession} 
            className="flex-1"
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            Practice Again
          </Button>
        ) : (
          <>
            <Button 
              variant="outline"
              onClick={getHint}
              className="flex-1"
            >
              <Lightbulb className="w-4 h-4 mr-2" />
              Hint
            </Button>
            <Button 
              variant="outline"
              onClick={resetSession}
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Reset
            </Button>
          </>
        )}
      </div>
      
      {/* Instructions */}
      {!sessionId && (
        <p className="text-xs text-muted-foreground text-center">
          Practice the {openingName} with your AI coach. The coach will play the opponent's 
          moves and give you feedback when you make mistakes.
        </p>
      )}
    </div>
  );
};

export default InteractivePractice;
