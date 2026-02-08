import { useState, useEffect, useCallback, useRef } from "react";
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
  ChevronLeft,
  Trophy,
  Flame,
  Clock,
  Loader2,
  ArrowRight,
  RotateCcw,
  Sparkles,
  Play,
  Pause,
  RotateCw,
  SkipBack,
  SkipForward
} from "lucide-react";

const MistakeMastery = ({ token, onComplete }) => {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [phase, setPhase] = useState("question");
  const [selectedMove, setSelectedMove] = useState(null);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [sessionStats, setSessionStats] = useState({ correct: 0, incorrect: 0 });
  
  const [boardPosition, setBoardPosition] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackIndex, setPlaybackIndex] = useState(0);
  const [playbackMoves, setPlaybackMoves] = useState([]);
  const [playbackType, setPlaybackType] = useState(null);
  const [playbackPositions, setPlaybackPositions] = useState([]);
  
  const [selectedWhy, setSelectedWhy] = useState(null);
  const [whyRevealed, setWhyRevealed] = useState(false);
  const [whyData, setWhyData] = useState(null);
  const [loadingWhy, setLoadingWhy] = useState(false);
  
  // For preview mode - clicking options before submitting
  const [previewMove, setPreviewMove] = useState(null);
  const playbackRef = useRef(null);

  const fetchSession = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/training/session`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error("Failed to fetch training session");
      const data = await res.json();
      setSession(data);
      resetCardState();
    } catch (err) {
      console.error("Training session error:", err);
      toast.error("Couldn't load training session");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchSession(); }, [fetchSession]);

  const resetCardState = () => {
    setCurrentCardIndex(0);
    setPhase("question");
    setSelectedMove(null);
    setResult(null);
    setBoardPosition(null);
    setIsPlaying(false);
    setPlaybackIndex(0);
    setPlaybackMoves([]);
    setPlaybackType(null);
    setSelectedWhy(null);
    setWhyRevealed(false);
    setWhyData(null);
  };

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

  useEffect(() => {
    if (currentCard?.fen) setBoardPosition(currentCard.fen);
  }, [currentCard]);

  const handleMoveSelect = (move) => {
    if (phase !== "question") return;
    setSelectedMove(move);
  };

  const submitAnswer = async () => {
    if (!selectedMove || !currentCard || submitting) return;
    setSubmitting(true);
    const isCorrect = selectedMove === currentCard.correct_move;
    
    try {
      const res = await fetch(`${API}/training/attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ card_id: currentCard.card_id, correct: isCorrect })
      });
      if (!res.ok) throw new Error("Failed to record attempt");
      const attemptResult = await res.json();
      
      setResult(isCorrect ? "correct" : "incorrect");
      setPhase("feedback");
      setSessionStats(prev => ({
        correct: prev.correct + (isCorrect ? 1 : 0),
        incorrect: prev.incorrect + (isCorrect ? 0 : 1)
      }));
      if (attemptResult.is_mastered) toast.success("Position mastered!");
    } catch (err) {
      toast.error("Couldn't save your answer");
    } finally {
      setSubmitting(false);
    }
  };

  const playMovesOnBoard = (moves, type, startMove = null) => {
    if (!currentCard?.fen) return;
    
    // Build all positions upfront for step-through navigation
    const positions = [currentCard.fen];
    const chess = new Chess(currentCard.fen);
    
    // If there's a starting move (like user_move or correct_move), play it first
    if (startMove) {
      try {
        chess.move(startMove);
        positions.push(chess.fen());
      } catch (e) {
        console.error("Failed to play start move:", startMove);
        return; // Can't continue if start move fails
      }
    }
    
    // Then play the continuation (if any)
    if (moves && moves.length > 0) {
      for (const move of moves) {
        try {
          chess.move(move);
          positions.push(chess.fen());
        } catch (e) {
          break;
        }
      }
    }
    
    // Only proceed if we have at least 2 positions (original + at least one move)
    if (positions.length < 2) return;
    
    setPlaybackType(type);
    setPlaybackMoves(startMove ? [startMove, ...(moves || [])] : (moves || []));
    setPlaybackPositions(positions);
    setPlaybackIndex(0);
    setBoardPosition(positions[0]);
    
    // Auto-advance to show the move
    setTimeout(() => {
      setPlaybackIndex(1);
      setBoardPosition(positions[1]);
    }, 300);
  };

  // Auto-play effect
  useEffect(() => {
    if (!isPlaying || playbackPositions.length === 0) return;
    
    if (playbackRef.current) clearTimeout(playbackRef.current);
    
    playbackRef.current = setTimeout(() => {
      if (playbackIndex < playbackPositions.length - 1) {
        const nextIdx = playbackIndex + 1;
        setPlaybackIndex(nextIdx);
        setBoardPosition(playbackPositions[nextIdx]);
      } else {
        setIsPlaying(false);
      }
    }, 800);
    
    return () => {
      if (playbackRef.current) clearTimeout(playbackRef.current);
    };
  }, [isPlaying, playbackIndex, playbackPositions]);

  // Step controls
  const stepForward = () => {
    if (playbackIndex < playbackPositions.length - 1) {
      setIsPlaying(false);
      const nextIdx = playbackIndex + 1;
      setPlaybackIndex(nextIdx);
      setBoardPosition(playbackPositions[nextIdx]);
    }
  };
  
  const stepBackward = () => {
    if (playbackIndex > 0) {
      setIsPlaying(false);
      const prevIdx = playbackIndex - 1;
      setPlaybackIndex(prevIdx);
      setBoardPosition(playbackPositions[prevIdx]);
    }
  };
  
  const goToStart = () => {
    setIsPlaying(false);
    setPlaybackIndex(0);
    if (playbackPositions.length > 0) {
      setBoardPosition(playbackPositions[0]);
    } else if (currentCard?.fen) {
      setBoardPosition(currentCard.fen);
    }
  };
  
  const goToEnd = () => {
    setIsPlaying(false);
    if (playbackPositions.length > 0) {
      const lastIdx = playbackPositions.length - 1;
      setPlaybackIndex(lastIdx);
      setBoardPosition(playbackPositions[lastIdx]);
    }
  };

  const resetBoard = () => {
    if (currentCard?.fen) {
      setBoardPosition(currentCard.fen);
      setPlaybackIndex(0);
      setPlaybackPositions([]);
      setPlaybackMoves([]);
      setIsPlaying(false);
      setPlaybackType(null);
      setPreviewMove(null);
    }
  };
  
  // Preview a move option (show ONLY that single move, not the full line)
  const previewMoveOption = (move, isCorrect) => {
    if (!currentCard?.fen) return;
    setPreviewMove(move);
    
    // Only play the single move - not the continuation
    // Full line is revealed only after submitting the answer
    playMovesOnBoard([], isCorrect ? 'better' : 'threat', move);
  };

  const goToWhyPhase = async () => {
    if (!currentCard?.card_id) {
      setPhase("why");
      return;
    }
    
    setLoadingWhy(true);
    try {
      const res = await fetch(`${API}/training/card/${currentCard.card_id}/why`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setWhyData(data);
      }
    } catch (err) {
      console.error("Failed to fetch why question:", err);
    } finally {
      setLoadingWhy(false);
      setPhase("why");
    }
  };

  const getWhyOptions = () => {
    // Use backend-generated options if available
    if (whyData?.options) {
      return whyData.options;
    }
    // Fallback options
    return [
      { id: "a", text: "It creates a direct threat that's hard to defend", is_correct: true },
      { id: "b", text: "It improves piece activity and coordination", is_correct: false },
      { id: "c", text: "It exploits a weakness in the opponent's position", is_correct: false }
    ];
  };

  const handleWhyAnswer = (optionId) => {
    setSelectedWhy(optionId);
    setWhyRevealed(true);
    
    // Play the better line on the board if the answer was correct
    const selectedOption = getWhyOptions().find(o => o.id === optionId);
    if (selectedOption?.is_correct && (whyData?.better_line?.length > 0 || currentCard?.better_line?.length > 0)) {
      const lineToPlay = whyData?.better_line || currentCard?.better_line;
      setTimeout(() => playMovesOnBoard(lineToPlay, 'better'), 500);
    }
  };

  const nextCard = () => {
    if (currentCardIndex < totalCards - 1) {
      setCurrentCardIndex(prev => prev + 1);
      setPhase("question");
      setSelectedMove(null);
      setResult(null);
      setBoardPosition(null);
      setIsPlaying(false);
      setPlaybackIndex(0);
      setPlaybackMoves([]);
      setPlaybackPositions([]);
      setPlaybackType(null);
      setPreviewMove(null);
      setSelectedWhy(null);
      setWhyRevealed(false);
      setWhyData(null);
    } else {
      setPhase("complete");
    }
  };

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
            <ArrowRight className="w-4 h-4" /> Go Play
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (phase === "complete") {
    const accuracy = sessionStats.correct + sessionStats.incorrect > 0
      ? Math.round((sessionStats.correct / (sessionStats.correct + sessionStats.incorrect)) * 100) : 0;
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
              <RotateCcw className="w-4 h-4" /> More Training
            </Button>
            <Button onClick={onComplete} className="gap-2">
              <ArrowRight className="w-4 h-4" /> Continue
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

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

  // Use user_color to orient the board from player's perspective
  const getBoardOrientation = () => currentCard?.user_color || "white";

  return (
    <Card className="border-primary/20 overflow-hidden">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {session.mode === "post_game_debrief" ? (
              <><Flame className="w-5 h-5 text-orange-500" /><CardTitle className="text-lg">Post-Game Debrief</CardTitle></>
            ) : (
              <><Target className="w-5 h-5 text-primary" /><CardTitle className="text-lg">{session.active_habit_display || "Daily Training"}</CardTitle></>
            )}
          </div>
          {session.mode === "daily_training" && totalCards > 1 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">{currentCardIndex + 1}/{totalCards}</span>
              <Progress value={((currentCardIndex + 1) / totalCards) * 100} className="w-20 h-2" />
            </div>
          )}
        </div>
        {session.habit_progress && (
          <div className="mt-2 p-3 rounded bg-muted/50">
            <div className="flex items-center justify-between text-sm gap-4">
              <span className="text-muted-foreground whitespace-nowrap">Correction Progress</span>
              <div className="flex items-center gap-2">
                <span className="font-medium whitespace-nowrap">
                  {session.habit_progress.mastered_cards} / {session.habit_progress.total_cards}
                </span>
                <span className="text-xs text-muted-foreground">fixed</span>
              </div>
            </div>
            <Progress value={session.habit_progress.progress_pct} className="h-1.5 mt-2" />
          </div>
        )}
      </CardHeader>

      <CardContent className="pt-4">
        <div className="flex flex-col lg:flex-row gap-6">
          <div className="flex-1 max-w-md mx-auto lg:mx-0">
            <div className="aspect-square">
              <Chessboard 
                position={boardPosition || currentCard.fen}
                boardOrientation={getBoardOrientation()}
                arePiecesDraggable={false}
                customBoardStyle={{ borderRadius: "8px", boxShadow: "0 4px 20px rgba(0,0,0,0.3)" }}
              />
            </div>
            <div className="mt-3 space-y-2">
              {/* Personalized game context */}
              <div className="text-center space-y-1">
                <div className="flex items-center justify-center gap-2 text-sm">
                  {currentCard.opponent ? (
                    <span className="text-muted-foreground">vs <span className="font-medium text-foreground">{currentCard.opponent}</span></span>
                  ) : null}
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    currentCard.user_color === 'black' ? 'bg-zinc-800 text-white' : 'bg-white text-black border'
                  }`}>
                    {currentCard.user_color === 'black' ? 'Black' : 'White'}
                  </span>
                </div>
                <span className="text-sm text-muted-foreground">
                  Move {currentCard.move_number} • 
                  {currentCard.evaluation === "blunder" && " Discipline broke here"}
                  {currentCard.evaluation === "mistake" && " Discipline slipped"}
                  {currentCard.evaluation === "inaccuracy" && " Could be sharper"}
                  {currentCard.cp_loss ? ` (-${(currentCard.cp_loss / 100).toFixed(1)})` : ""}
                </span>
              </div>
              {phase === "feedback" && playbackPositions.length > 0 && (
                <div className="flex items-center justify-center gap-1 flex-wrap">
                  <Button variant="outline" size="sm" onClick={goToStart} disabled={playbackIndex === 0} className="h-8 w-8 p-0">
                    <SkipBack className="w-3 h-3" />
                  </Button>
                  <Button variant="outline" size="sm" onClick={stepBackward} disabled={playbackIndex === 0} className="h-8 w-8 p-0">
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  {isPlaying ? (
                    <Button variant="outline" size="sm" onClick={() => setIsPlaying(false)} className="gap-1 h-8">
                      <Pause className="w-3 h-3" /> Pause
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" onClick={() => setIsPlaying(true)} 
                      disabled={playbackIndex >= playbackPositions.length - 1} className="gap-1 h-8">
                      <Play className="w-3 h-3" /> Play
                    </Button>
                  )}
                  <Button variant="outline" size="sm" onClick={stepForward} 
                    disabled={playbackIndex >= playbackPositions.length - 1} className="h-8 w-8 p-0">
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                  <Button variant="outline" size="sm" onClick={goToEnd} 
                    disabled={playbackIndex >= playbackPositions.length - 1} className="h-8 w-8 p-0">
                    <SkipForward className="w-3 h-3" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={resetBoard} className="gap-1 h-8 ml-2">
                    <RotateCw className="w-3 h-3" /> Reset
                  </Button>
                </div>
              )}
              {phase === "feedback" && playbackPositions.length > 0 && (
                <div className="text-center">
                  <span className={`text-xs px-2 py-1 rounded ${
                    playbackType === 'threat' ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'
                  }`}>
                    {playbackType === 'threat' ? 'After your move' : 'Better line'}: Move {playbackIndex}/{playbackPositions.length - 1}
                  </span>
                </div>
              )}
              {phase === "feedback" && playbackPositions.length === 0 && (
                <div className="flex items-center justify-center gap-2">
                  <Button variant="outline" size="sm" onClick={resetBoard} className="gap-1">
                    <RotateCw className="w-3 h-3" /> Reset
                  </Button>
                  {currentCard.threat_line?.length > 0 && (
                    <Button variant="outline" size="sm" 
                      onClick={() => playMovesOnBoard(currentCard.threat_line, 'threat', currentCard.user_move)}
                      className="gap-1 text-red-500 border-red-500/30 hover:bg-red-500/10">
                      <Play className="w-3 h-3" /> Your Move
                    </Button>
                  )}
                  {currentCard.better_line?.length > 0 && (
                    <Button variant="outline" size="sm" 
                      onClick={() => playMovesOnBoard(currentCard.better_line, 'better', currentCard.correct_move)}
                      className="gap-1 text-emerald-500 border-emerald-500/30 hover:bg-emerald-500/10">
                      <Play className="w-3 h-3" /> Best Move
                    </Button>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="flex-1 flex flex-col justify-center">
            <AnimatePresence mode="wait">
              {phase === "question" && (
                <motion.div key="question" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-4">
                  <div>
                    <h4 className="text-lg font-medium">What should you play here?</h4>
                    <p className="text-sm text-muted-foreground">Click "Preview" to see the move on the board, then select your answer.</p>
                  </div>
                  
                  <div className="space-y-3">
                    {/* Move Option Cards - Both clickable to preview */}
                    {[
                      { move: currentCard.correct_move, isCorrect: true },
                      { move: currentCard.user_move, isCorrect: false }
                    ].sort(() => Math.random() - 0.5).map((opt, idx) => (
                      <div key={idx} 
                        className={`p-4 rounded-lg border-2 transition-all ${
                          selectedMove === opt.move ? "border-primary bg-primary/10" : 
                          previewMove === opt.move ? "border-blue-500/50 bg-blue-500/5" : 
                          "border-border hover:border-primary/30"
                        }`}>
                        <div className="flex items-center justify-between">
                          <button 
                            onClick={() => handleMoveSelect(opt.move)}
                            className="flex items-center gap-3 flex-1 text-left"
                          >
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                              selectedMove === opt.move ? "bg-primary text-primary-foreground" : "bg-muted"
                            }`}>
                              {idx + 1}
                            </div>
                            <span className="font-mono text-xl">{opt.move}</span>
                            {selectedMove === opt.move && <CheckCircle2 className="w-5 h-5 text-primary ml-2" />}
                          </button>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => previewMoveOption(opt.move, opt.isCorrect)}
                            className={`gap-1 ${previewMove === opt.move ? "text-blue-500" : "text-muted-foreground"}`}
                          >
                            <Play className="w-4 h-4" /> Preview
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  {/* Reset button for question phase preview */}
                  {previewMove && (
                    <Button variant="outline" size="sm" onClick={resetBoard} className="gap-1">
                      <RotateCw className="w-3 h-3" /> Reset Board
                    </Button>
                  )}
                  
                  <Button onClick={submitAnswer} disabled={!selectedMove || submitting} className="w-full gap-2">
                    {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ChevronRight className="w-4 h-4" />}
                    Submit Answer
                  </Button>
                </motion.div>
              )}

              {phase === "feedback" && (
                <motion.div key="feedback" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-4">
                  <div className={`p-4 rounded-lg ${result === "correct" ? "bg-emerald-500/10 border border-emerald-500/30" : "bg-red-500/10 border border-red-500/30"}`}>
                    <div className="flex items-center gap-3">
                      {result === "correct" ? <CheckCircle2 className="w-8 h-8 text-emerald-500" /> : <XCircle className="w-8 h-8 text-red-500" />}
                      <div>
                        <h4 className={`font-semibold ${result === "correct" ? "text-emerald-500" : "text-red-500"}`}>
                          {result === "correct" ? "Correct!" : "Not quite..."}
                        </h4>
                        <p className="text-sm text-muted-foreground">
                          The disciplined move: <span className="font-mono font-medium text-emerald-500">{currentCard.correct_move}</span>
                          {result !== "correct" && <span className="text-red-400 ml-2">(you played {currentCard.user_move})</span>}
                        </p>
                      </div>
                    </div>
                  </div>
                  {currentCard.explanation && <div className="p-3 rounded bg-muted/50"><p className="text-sm">{currentCard.explanation}</p></div>}
                  <div className="space-y-2">
                    {currentCard.threat_line?.length > 0 && (
                      <button 
                        onClick={() => playMovesOnBoard(currentCard.threat_line, 'threat', currentCard.user_move)}
                        className="w-full p-3 rounded bg-red-500/5 border border-red-500/20 text-left hover:bg-red-500/10 transition-colors group"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <p className="text-xs text-red-400 font-medium">After {currentCard.user_move}</p>
                          <span className="text-xs text-red-400 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                            <Play className="w-3 h-3" /> Click to play
                          </span>
                        </div>
                        <p className="font-mono text-sm text-red-400">{currentCard.user_move} {currentCard.threat_line.slice(0, 4).join(" ")}</p>
                      </button>
                    )}
                    {currentCard.better_line?.length > 0 && (
                      <button 
                        onClick={() => playMovesOnBoard(currentCard.better_line, 'better', currentCard.correct_move)}
                        className="w-full p-3 rounded bg-emerald-500/5 border border-emerald-500/20 text-left hover:bg-emerald-500/10 transition-colors group"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <p className="text-xs text-emerald-400 font-medium">Best continuation</p>
                          <span className="text-xs text-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                            <Play className="w-3 h-3" /> Click to play
                          </span>
                        </div>
                        <p className="font-mono text-sm text-emerald-400">{currentCard.correct_move} {currentCard.better_line.slice(0, 4).join(" ")}</p>
                      </button>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">This habit is costing rating:</span>
                    <span className="text-xs px-2 py-1 rounded bg-amber-500/10 text-amber-500 font-medium">
                      {currentCard.habit_tag?.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {result === "correct" && (
                      <Button variant="outline" onClick={goToWhyPhase} disabled={loadingWhy} className="flex-1 gap-2">
                        {loadingWhy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />} 
                        Why is this better?
                      </Button>
                    )}
                    <Button onClick={nextCard} className={`gap-2 ${result === "correct" ? "flex-1" : "w-full"}`}>
                      {currentCardIndex < totalCards - 1 ? "Next Position" : "Finish"} <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                </motion.div>
              )}

              {phase === "why" && (
                <motion.div key="why" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-4">
                  <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/30">
                    <div className="flex items-center gap-2 mb-2">
                      <Brain className="w-5 h-5 text-blue-500" />
                      <h4 className="font-semibold text-blue-500">
                        {whyData?.question || `Why is ${currentCard.correct_move} better?`}
                      </h4>
                    </div>
                    <p className="text-sm text-muted-foreground">Understanding WHY helps you recognize similar patterns.</p>
                    {whyData?.hint && (
                      <p className="text-xs text-muted-foreground mt-1 italic">{whyData.hint}</p>
                    )}
                  </div>
                  {loadingWhy ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {getWhyOptions().map((option) => (
                        <button key={option.id} onClick={() => handleWhyAnswer(option.id)} disabled={whyRevealed}
                          className={`w-full p-3 rounded-lg border-2 transition-all text-left ${
                            whyRevealed && option.is_correct ? "border-emerald-500 bg-emerald-500/10" :
                            whyRevealed && selectedWhy === option.id && !option.is_correct ? "border-red-500 bg-red-500/10" :
                            selectedWhy === option.id ? "border-primary bg-primary/10" : "border-border hover:border-primary/50"
                          } ${whyRevealed ? "cursor-default" : "cursor-pointer"}`}>
                          <span className="text-sm">{option.text}</span>
                          {whyRevealed && option.is_correct && (
                            <CheckCircle2 className="w-4 h-4 text-emerald-500 inline ml-2" />
                          )}
                          {whyRevealed && selectedWhy === option.id && !option.is_correct && (
                            <XCircle className="w-4 h-4 text-red-500 inline ml-2" />
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                  {whyRevealed && (
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="p-3 rounded bg-muted/50">
                      <p className="text-sm text-muted-foreground">
                        <span className="font-medium text-foreground">Key insight:</span>{" "}
                        {whyData?.correct_explanation || "The best move addresses the tactical issue. Use the play buttons to visualize!"}
                      </p>
                    </motion.div>
                  )}
                  <Button onClick={nextCard} className="w-full gap-2" disabled={!whyRevealed}>
                    {currentCardIndex < totalCards - 1 ? "Next Position" : "Finish"} <ChevronRight className="w-4 h-4" />
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
