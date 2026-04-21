/**
 * PrescribedTraining - Puzzles prescribed based on user's weaknesses
 * 
 * This is the IMPROVEMENT engine:
 * - Shows puzzles targeted at user's specific weaknesses
 * - Includes puzzles from user's OWN games
 * - Provides coaching context for each puzzle
 * - Tracks progress over time
 */

import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import LichessBoard from "@/components/LichessBoard";
import { Chess } from "chess.js";
import {
  ArrowLeft,
  Brain,
  Target,
  CheckCircle2,
  XCircle,
  Lightbulb,
  ChevronRight,
  Loader2,
  Trophy,
  AlertCircle,
  Play,
  RotateCcw,
  Eye
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { API } from "@/App";

// Encouraging messages for puzzle completion
const PUZZLE_ENCOURAGEMENTS = {
  correct: [
    "Nice! You're building the habit.",
    "That's the pattern! Keep going.",
    "Excellent! Your eyes are getting sharper.",
    "Great recognition! This is how you improve.",
    "Perfect! You won't miss this in a real game.",
  ],
  incorrect: [
    "Almost! The pattern is tricky, but you'll get it.",
    "Not quite, but keep trying. This is exactly the training you need.",
    "Take another look. The solution involves the same weakness you're working on.",
  ],
  streak: [
    "You're on fire! 🔥",
    "Three in a row - your pattern recognition is improving!",
    "Streak! This weakness is becoming your strength.",
  ],
  complete: [
    "Training session complete! Every puzzle makes you stronger.",
    "Great work! You've done your training for today.",
    "Session done! Come back tomorrow to keep the momentum.",
  ]
};

const getEncouragement = (type, streak = 0) => {
  if (streak >= 3 && type === "correct") {
    return PUZZLE_ENCOURAGEMENTS.streak[Math.floor(Math.random() * PUZZLE_ENCOURAGEMENTS.streak.length)];
  }
  const messages = PUZZLE_ENCOURAGEMENTS[type] || PUZZLE_ENCOURAGEMENTS.correct;
  return messages[Math.floor(Math.random() * messages.length)];
};

export default function PrescribedTraining() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Weakness can come from either:
  //   1. ?weakness=X query param (canonical: /training?weakness=X)
  //   2. :pattern URL segment (legacy: /training/pattern/:pattern)
  //   3. default to "current" — backend resolves to user's active focus
  const { pattern: patternFromUrl } = useParams();
  const weakness = searchParams.get("weakness") || patternFromUrl || "current";
  
  // Data state
  const [trainingData, setTrainingData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Puzzle state
  const [currentPuzzleIndex, setCurrentPuzzleIndex] = useState(0);
  const [puzzleState, setPuzzleState] = useState("thinking"); // thinking, correct, incorrect, revealed
  const [userMove, setUserMove] = useState(null);
  const [showSolution, setShowSolution] = useState(false);
  const [solvedCount, setSolvedCount] = useState(0);
  const [streak, setStreak] = useState(0);
  const [encouragement, setEncouragement] = useState("");
  
  // Board state
  const [game, setGame] = useState(new Chess());
  const [boardOrientation, setBoardOrientation] = useState("white");
  const boardRef = useRef(null);
  
  // Fetch prescribed training
  useEffect(() => {
    const fetchTraining = async () => {
      setLoading(true);
      try {
        const response = await fetch(
          `${API}/training/prescribed/${weakness}?num_puzzles=5`,
          { credentials: "include" }
        );
        if (response.ok) {
          const data = await response.json();
          setTrainingData(data);
          
          // Set up first puzzle
          if (data.puzzles && data.puzzles.length > 0) {
            const firstPuzzle = data.puzzles[0];
            if (firstPuzzle.fen) {
              const newGame = new Chess(firstPuzzle.fen);
              setGame(newGame);
              // Set orientation based on whose turn it is
              const turn = firstPuzzle.fen.split(" ")[1];
              setBoardOrientation(turn === "w" ? "white" : "black");
            }
          }
        } else {
          setError("Failed to load training");
        }
      } catch (err) {
        console.error("Error fetching training:", err);
        setError("Failed to load training");
      } finally {
        setLoading(false);
      }
    };
    
    fetchTraining();
  }, [weakness]);
  
  // Current puzzle
  const currentPuzzle = trainingData?.puzzles?.[currentPuzzleIndex];
  
  // Handle move attempt
  const onDrop = (sourceSquare, targetSquare) => {
    if (puzzleState !== "thinking") return false;
    if (!currentPuzzle) return false;
    
    try {
      const move = game.move({
        from: sourceSquare,
        to: targetSquare,
        promotion: "q"
      });
      
      if (move === null) return false;
      
      setUserMove(move.san);
      
      // Check if correct
      const solution = currentPuzzle.solution || [];
      const correctMove = solution[0];
      const userMoveUci = `${sourceSquare}${targetSquare}`;
      
      // Compare moves (handle SAN or UCI notation)
      const isCorrect = move.san === correctMove || 
                       move.san === currentPuzzle.solution_san ||
                       userMoveUci === correctMove ||
                       move.lan?.toLowerCase() === correctMove?.toLowerCase();
      
      if (isCorrect) {
        setPuzzleState("correct");
        setSolvedCount(prev => prev + 1);
        setStreak(prev => prev + 1);
        setEncouragement(getEncouragement("correct", streak + 1));
        
        // Record attempt
        recordAttempt(currentPuzzle, true);
      } else {
        setPuzzleState("incorrect");
        setStreak(0);
        setEncouragement(getEncouragement("incorrect"));
        // Undo the wrong move
        game.undo();
        setGame(new Chess(game.fen()));
        
        // Record attempt
        recordAttempt(currentPuzzle, false);
      }
      
      return true;
    } catch (e) {
      return false;
    }
  };
  
  // Record puzzle attempt
  const recordAttempt = async (puzzle, solved) => {
    try {
      await fetch(`${API}/training/puzzle-attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          puzzle_id: puzzle.puzzle_id || puzzle.game_id,
          solved,
          time_taken: 0, // TODO: track time
          weakness_pattern: weakness
        })
      });
    } catch (e) {
      console.error("Error recording attempt:", e);
    }
  };
  
  // Next puzzle
  const nextPuzzle = () => {
    const nextIdx = currentPuzzleIndex + 1;
    if (nextIdx < trainingData.puzzles.length) {
      setCurrentPuzzleIndex(nextIdx);
      setPuzzleState("thinking");
      setUserMove(null);
      setShowSolution(false);
      
      const nextPuzzle = trainingData.puzzles[nextIdx];
      if (nextPuzzle.fen) {
        const newGame = new Chess(nextPuzzle.fen);
        setGame(newGame);
        const turn = nextPuzzle.fen.split(" ")[1];
        setBoardOrientation(turn === "w" ? "white" : "black");
      }
    }
  };
  
  // Retry puzzle
  const retryPuzzle = () => {
    if (currentPuzzle?.fen) {
      const newGame = new Chess(currentPuzzle.fen);
      setGame(newGame);
      setPuzzleState("thinking");
      setUserMove(null);
      setShowSolution(false);
    }
  };
  
  // Show solution
  const revealSolution = () => {
    setShowSolution(true);
    setPuzzleState("revealed");
  };
  
  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading your training...</p>
        </div>
      </div>
    );
  }
  
  if (error || !trainingData) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-4" />
          <p className="text-red-500">{error || "No training data available"}</p>
          <Button onClick={() => navigate("/home")} className="mt-4">
            Go Home
          </Button>
        </div>
      </div>
    );
  }
  
  const progress = ((currentPuzzleIndex + (puzzleState === "correct" ? 1 : 0)) / trainingData.puzzles.length) * 100;
  const isComplete = currentPuzzleIndex >= trainingData.puzzles.length - 1 && puzzleState === "correct";
  
  return (
    <div className="min-h-screen bg-background" data-testid="prescribed-training">
      {/* Header */}
      <div className="border-b bg-card/50">
        <div className="max-w-6xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
                <ArrowLeft className="w-4 h-4" />
              </Button>
              <div>
                <h1 className="font-semibold flex items-center gap-2">
                  <Target className="w-5 h-5 text-primary" />
                  {trainingData.coaching_intro?.lesson || "Training"}
                </h1>
                <p className="text-xs text-muted-foreground">
                  Weakness: {weakness.replace(/_/g, " ")}
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-sm font-medium">{solvedCount}/{trainingData.total}</p>
                <p className="text-xs text-muted-foreground">Solved</p>
              </div>
              <Progress value={progress} className="w-24 h-2" />
            </div>
          </div>
        </div>
      </div>
      
      {/* Main content */}
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Board */}
          <div>
            {currentPuzzle?.fen ? (
              <div className="rounded-lg overflow-hidden border border-border">
                <LichessBoard
                  ref={boardRef}
                  fen={game.fen()}
                  orientation={boardOrientation}
                  onMove={(moveData) => {
                    if (puzzleState === "thinking" && moveData) {
                      onDrop(moveData.from, moveData.to);
                    }
                  }}
                  interactive={puzzleState === "thinking"}
                  viewOnly={puzzleState !== "thinking"}
                  arrows={
                    // Show arrows when solution is revealed or incorrect
                    (showSolution || puzzleState === "incorrect")
                      ? (() => {
                          const arrows = [];
                          
                          // Green arrow for best move
                          if (currentPuzzle.solution?.[0]) {
                            arrows.push([
                              currentPuzzle.solution[0].slice(0, 2),
                              currentPuzzle.solution[0].slice(2, 4),
                              "green"
                            ]);
                          }
                          
                          // Orange arrow for the threat (what you missed)
                          if (currentPuzzle.threat) {
                            // Try to parse the threat as a UCI move (e.g., "e2e4" or "fxe5")
                            const threat = currentPuzzle.threat;
                            
                            // If threat is 4 chars, it's a UCI move
                            if (threat.length === 4 && /^[a-h][1-8][a-h][1-8]$/.test(threat)) {
                              arrows.push([threat.slice(0, 2), threat.slice(2, 4), "orange"]);
                            }
                            // If threat is like "fxe5" or "Nxe5", try to parse it
                            else if (threat.includes('x')) {
                              // Extract the target square from capture notation
                              const match = threat.match(/x([a-h][1-8])/);
                              if (match) {
                                // We can show a highlight on the target square
                                // For arrow, we'd need the from square - skip for now
                              }
                            }
                            // If threat is just a square like "b5", highlight it
                            // (This will be handled by highlights, not arrows)
                          }
                          
                          return arrows;
                        })()
                      : []
                  }
                  highlights={
                    // Highlight squares when solution is revealed or incorrect
                    (showSolution || puzzleState === "incorrect")
                      ? (() => {
                          const highlights = [];
                          
                          // Highlight the move that was played (mistake) when from own game
                          if (currentPuzzle.your_move_uci) {
                            highlights.push(currentPuzzle.your_move_uci.slice(0, 2));
                            highlights.push(currentPuzzle.your_move_uci.slice(2, 4));
                          }
                          
                          // Highlight the threat square if it's a simple notation
                          if (currentPuzzle.threat) {
                            const threat = currentPuzzle.threat;
                            // If threat is a square like "b5" or "e4"
                            if (/^[a-h][1-8]$/.test(threat)) {
                              highlights.push(threat);
                            }
                            // If threat is capture notation like "fxe5", highlight target
                            else if (threat.includes('x')) {
                              const match = threat.match(/x([a-h][1-8])/);
                              if (match) {
                                highlights.push(match[1]);
                              }
                            }
                          }
                          
                          return highlights;
                        })()
                      : []
                  }
                />
              </div>
            ) : currentPuzzle?.game_url ? (
              <div className="aspect-square bg-slate-800/50 rounded-lg flex items-center justify-center">
                <div className="text-center p-6">
                  <p className="text-muted-foreground mb-4">
                    This puzzle is from Lichess
                  </p>
                  <Button
                    onClick={() => window.open(currentPuzzle.game_url, "_blank")}
                  >
                    Solve on Lichess
                  </Button>
                </div>
              </div>
            ) : (
              <div className="aspect-square bg-slate-800/50 rounded-lg flex items-center justify-center">
                <p className="text-muted-foreground">No puzzle available</p>
              </div>
            )}
            
            {/* Puzzle status */}
            {puzzleState === "correct" && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 p-4 rounded-lg bg-green-500/10 border border-green-500/30"
              >
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle2 className="w-5 h-5 text-green-500" />
                  <span className="font-medium text-green-500">Correct!</span>
                  {streak >= 3 && (
                    <Badge variant="outline" className="ml-2 border-amber-500/50 text-amber-400">
                      {streak} streak 🔥
                    </Badge>
                  )}
                </div>
                {encouragement && (
                  <p className="text-sm text-green-400/80 ml-7">{encouragement}</p>
                )}
              </motion.div>
            )}
            
            {puzzleState === "incorrect" && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 p-4 rounded-lg bg-red-500/10 border border-red-500/30"
              >
                <div className="flex items-center gap-2 mb-1">
                  <XCircle className="w-5 h-5 text-red-500" />
                  <span className="font-medium text-red-500">Not quite!</span>
                </div>
                {encouragement && (
                  <p className="text-sm text-red-400/80 ml-7">{encouragement}</p>
                )}
                {/* Show the correct answer */}
                <p className="text-sm text-muted-foreground mt-2 ml-7">
                  The best move was <span className="text-green-400 font-medium">{currentPuzzle.solution_san || currentPuzzle.solution?.[0]}</span>
                  {currentPuzzle.your_move && (
                    <> — in your game you played <span className="text-red-400">{currentPuzzle.your_move}</span></>
                  )}
                </p>
                {/* Show the threat that was missed */}
                {currentPuzzle.threat && (
                  <div className="mt-2 ml-7 p-2 bg-orange-500/10 rounded border border-orange-500/20">
                    <p className="text-xs text-orange-400">
                      <span className="font-medium">Threat you missed:</span> {currentPuzzle.threat}
                    </p>
                  </div>
                )}
                {/* Show coaching note if available */}
                {currentPuzzle.coaching?.what_you_missed && (
                  <p className="text-xs text-muted-foreground mt-2 ml-7 italic">
                    {currentPuzzle.coaching.what_you_missed}
                  </p>
                )}
              </motion.div>
            )}
            
            {/* Show solution revealed feedback */}
            {puzzleState === "revealed" && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 p-4 rounded-lg bg-blue-500/10 border border-blue-500/30"
              >
                <div className="flex items-center gap-2 mb-1">
                  <Eye className="w-5 h-5 text-blue-400" />
                  <span className="font-medium text-blue-400">Solution</span>
                </div>
                <p className="text-sm text-muted-foreground ml-7">
                  The best move was <span className="text-green-400 font-medium">{currentPuzzle.solution_san || currentPuzzle.solution?.[0]}</span>
                  {currentPuzzle.your_move && (
                    <> — in your game you played <span className="text-red-400">{currentPuzzle.your_move}</span></>
                  )}
                </p>
                {/* Show the threat that was missed */}
                {currentPuzzle.threat && (
                  <div className="mt-2 ml-7 p-2 bg-orange-500/10 rounded border border-orange-500/20">
                    <p className="text-xs text-orange-400">
                      <span className="font-medium">Threat you missed:</span> {currentPuzzle.threat}
                    </p>
                  </div>
                )}
                {/* Show coaching note if available */}
                {currentPuzzle.coaching?.what_you_missed && (
                  <p className="text-xs text-muted-foreground mt-2 ml-7 italic">
                    {currentPuzzle.coaching.what_you_missed}
                  </p>
                )}
              </motion.div>
            )}
            
            {/* Show move comparison for own games */}
            {currentPuzzle?.source === "your_game" && puzzleState === "thinking" && (
              <div className="mt-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
                <p className="text-sm text-amber-400">
                  <span className="font-medium">From your game:</span> You played <span className="text-red-400">{currentPuzzle.your_move}</span>. 
                  Can you find the better move?
                </p>
              </div>
            )}
            
            {/* Controls */}
            <div className="mt-4 flex items-center gap-2">
              {puzzleState === "thinking" && (
                <Button variant="outline" onClick={revealSolution}>
                  <Eye className="w-4 h-4 mr-2" />
                  Show Solution
                </Button>
              )}
              
              {puzzleState === "incorrect" && (
                <Button variant="outline" onClick={retryPuzzle}>
                  <RotateCcw className="w-4 h-4 mr-2" />
                  Retry
                </Button>
              )}
              
              {(puzzleState === "correct" || puzzleState === "revealed") && !isComplete && (
                <Button onClick={nextPuzzle}>
                  <ChevronRight className="w-4 h-4 mr-2" />
                  Next Puzzle
                </Button>
              )}
              
              {isComplete && (
                <Button onClick={() => navigate("/home")}>
                  <Trophy className="w-4 h-4 mr-2" />
                  Training Complete!
                </Button>
              )}
            </div>
          </div>
          
          {/* Coaching panel */}
          <div className="space-y-4">
            {/* Coaching intro */}
            <Card className="border-primary/20">
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <Brain className="w-5 h-5 text-primary" />
                  <CardTitle className="text-lg">Coach's Focus</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm">
                  {trainingData.coaching_intro?.why_this_matters}
                </p>
                <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                  <p className="text-xs text-amber-400 font-medium mb-1">
                    WHAT TO LOOK FOR
                  </p>
                  <p className="text-sm text-amber-300">
                    {trainingData.coaching_intro?.what_to_look_for}
                  </p>
                </div>
              </CardContent>
            </Card>
            
            {/* Current puzzle context */}
            {currentPuzzle && (
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm">
                      Puzzle {currentPuzzleIndex + 1} of {trainingData.total}
                    </CardTitle>
                    <Badge variant="outline">
                      {currentPuzzle.source === "your_game" ? "From Your Game" : 
                       currentPuzzle.source === "curated" ? "Training Puzzle" : "Lichess"}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Why this puzzle - explains the connection to weakness */}
                  <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                    <p className="text-xs text-blue-400 font-medium mb-1 flex items-center gap-1">
                      <Lightbulb className="w-3 h-3" />
                      WHY THIS PUZZLE?
                    </p>
                    <p className="text-sm text-blue-300">
                      {currentPuzzle.framing_text
                        ? currentPuzzle.framing_text
                        : currentPuzzle.source === "your_game"
                          ? `This is from your actual game. You made this mistake, so practicing it will help you spot it next time.`
                          : currentPuzzle.context
                            ? currentPuzzle.context
                            : `This puzzle trains your ${weakness.replace(/_/g, " ")} detection. Solving similar patterns builds pattern recognition.`
                      }
                    </p>
                  </div>

                  {/* Social proof: motivating miss-rate signal from community solves */}
                  {currentPuzzle.miss_rate_text && currentPuzzle.source !== "your_game" && (
                    <div className="px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
                      <p className="text-xs text-amber-300 flex items-center gap-1.5">
                        <AlertCircle className="w-3 h-3" />
                        {currentPuzzle.miss_rate_text}
                      </p>
                    </div>
                  )}
                  
                  {/* Personal note for user's own games */}
                  {currentPuzzle.source === "your_game" && (
                    <div className="p-3 rounded-lg bg-violet-500/10 border border-violet-500/20">
                      <p className="text-xs text-violet-400 font-medium mb-1">
                        FROM YOUR GAME
                      </p>
                      <p className="text-sm text-violet-300">
                        You played <span className="font-mono">{currentPuzzle.your_move}</span> but 
                        the best move was <span className="font-mono">{currentPuzzle.solution_san || currentPuzzle.solution?.[0]}</span>
                      </p>
                      {currentPuzzle.threat && (
                        <p className="text-sm text-red-400 mt-2">
                          You missed: <span className="font-medium">{currentPuzzle.threat}</span>
                        </p>
                      )}
                    </div>
                  )}
                  
                  {/* Solution reveal */}
                  {showSolution && currentPuzzle.solution && (
                    <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                      <p className="text-xs text-green-400 font-medium mb-1">
                        SOLUTION
                      </p>
                      <p className="text-sm text-green-300 font-mono">
                        {currentPuzzle.solution.join(" → ")}
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
            
            {/* Progress summary */}
            <Card className="bg-slate-800/30">
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{solvedCount} Correct</p>
                    <p className="text-xs text-muted-foreground">
                      {trainingData.prescription?.duration}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-primary">
                      {Math.round((solvedCount / trainingData.total) * 100)}%
                    </p>
                    <p className="text-xs text-muted-foreground">Accuracy</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
