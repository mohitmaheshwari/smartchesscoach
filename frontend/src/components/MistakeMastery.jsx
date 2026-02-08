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

  const playMovesOnBoard = (moves, type) => {
    if (!moves || moves.length === 0 || !currentCard?.fen) return;
    setPlaybackType(type);
    setPlaybackMoves(moves);
    setPlaybackIndex(0);
    setBoardPosition(currentCard.fen);
    setIsPlaying(true);
  };

  useEffect(() => {
    if (!isPlaying || playbackMoves.length === 0) return;
    const timer = setTimeout(() => {
      if (playbackIndex < playbackMoves.length) {
        try {
          const chess = new Chess(currentCard.fen);
          for (let i = 0; i <= playbackIndex; i++) {
            chess.move(playbackMoves[i]);
          }
          setBoardPosition(chess.fen());
          setPlaybackIndex(prev => prev + 1);
        } catch (e) {
          setIsPlaying(false);
        }
      } else {
        setIsPlaying(false);
      }
    }, 800);
    return () => clearTimeout(timer);
  }, [isPlaying, playbackIndex, playbackMoves, currentCard]);

  const resetBoard = () => {
    if (currentCard?.fen) {
      setBoardPosition(currentCard.fen);
      setPlaybackIndex(0);
      setIsPlaying(false);
    }
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

  const getBoardOrientation = () => currentCard.fen?.includes(" w ") ? "white" : "black";

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
              <span className="text-muted-foreground whitespace-nowrap">Habit Progress</span>
              <div className="flex items-center gap-2">
                <span className="font-medium whitespace-nowrap">
                  {session.habit_progress.mastered_cards} / {session.habit_progress.total_cards}
                </span>
                <span className="text-xs text-muted-foreground">mastered</span>
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
              <div className="text-center">
                <span className="text-sm text-muted-foreground">
                  Move {currentCard.move_number} • 
                  {currentCard.evaluation === "blunder" && " Blunder"}
                  {currentCard.evaluation === "mistake" && " Mistake"}
                  {currentCard.evaluation === "inaccuracy" && " Inaccuracy"}
                  {" (-"}{(currentCard.cp_loss / 100).toFixed(1)}{")"}
                </span>
              </div>
              {phase === "feedback" && (
                <div className="flex items-center justify-center gap-2">
                  <Button variant="outline" size="sm" onClick={resetBoard} className="gap-1">
                    <RotateCw className="w-3 h-3" /> Reset
                  </Button>
                  {!isPlaying && currentCard.threat_line?.length > 0 && (
                    <Button variant="outline" size="sm" onClick={() => playMovesOnBoard(currentCard.threat_line, 'threat')}
                      className="gap-1 text-red-500 border-red-500/30 hover:bg-red-500/10">
                      <Play className="w-3 h-3" /> Play Threat
                    </Button>
                  )}
                  {!isPlaying && currentCard.better_line?.length > 0 && (
                    <Button variant="outline" size="sm" onClick={() => playMovesOnBoard(currentCard.better_line, 'better')}
                      className="gap-1 text-emerald-500 border-emerald-500/30 hover:bg-emerald-500/10">
                      <Play className="w-3 h-3" /> Play Best
                    </Button>
                  )}
                  {isPlaying && (
                    <Button variant="outline" size="sm" onClick={() => setIsPlaying(false)} className="gap-1">
                      <Pause className="w-3 h-3" /> Pause
                    </Button>
                  )}
                </div>
              )}
              {isPlaying && (
                <div className="text-center">
                  <span className={`text-xs px-2 py-1 rounded ${playbackType === 'threat' ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
                    Playing {playbackType} line: {playbackIndex}/{playbackMoves.length}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="flex-1 flex flex-col justify-center">
            <AnimatePresence mode="wait">
              {phase === "question" && (
                <motion.div key="question" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-4">
                  <h4 className="text-lg font-medium">What should you play here?</h4>
                  <div className="grid grid-cols-2 gap-3">
                    <button onClick={() => handleMoveSelect(currentCard.correct_move)}
                      className={`p-4 rounded-lg border-2 transition-all text-left ${selectedMove === currentCard.correct_move ? "border-primary bg-primary/10" : "border-border hover:border-primary/50"}`}>
                      <span className="font-mono text-lg">{currentCard.correct_move}</span>
                    </button>
                    <button onClick={() => handleMoveSelect(currentCard.user_move)}
                      className={`p-4 rounded-lg border-2 transition-all text-left ${selectedMove === currentCard.user_move ? "border-primary bg-primary/10" : "border-border hover:border-primary/50"}`}>
                      <span className="font-mono text-lg">{currentCard.user_move}</span>
                    </button>
                  </div>
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
                          Best move: <span className="font-mono font-medium">{currentCard.correct_move}</span>
                        </p>
                      </div>
                    </div>
                  </div>
                  {currentCard.explanation && <div className="p-3 rounded bg-muted/50"><p className="text-sm">{currentCard.explanation}</p></div>}
                  <div className="space-y-2">
                    {currentCard.threat_line?.length > 0 && (
                      <div className="p-3 rounded bg-red-500/5 border border-red-500/20">
                        <p className="text-xs text-muted-foreground mb-1">After your move (click "Play Threat" to see on board):</p>
                        <p className="font-mono text-sm text-red-400">{currentCard.threat_line.slice(0, 5).join(" ")}</p>
                      </div>
                    )}
                    {currentCard.better_line?.length > 0 && (
                      <div className="p-3 rounded bg-emerald-500/5 border border-emerald-500/20">
                        <p className="text-xs text-muted-foreground mb-1">Better line (click "Play Best" to see on board):</p>
                        <p className="font-mono text-sm text-emerald-400">{currentCard.better_line.slice(0, 5).join(" ")}</p>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Habit:</span>
                    <span className="text-xs px-2 py-1 rounded bg-primary/10 text-primary">
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
