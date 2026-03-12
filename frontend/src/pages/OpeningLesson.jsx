import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import { Chessground } from "chessground";
import { 
  BookOpen, 
  ChevronLeft,
  ChevronRight,
  Play,
  RotateCcw,
  Target,
  Lightbulb,
  AlertTriangle,
  CheckCircle2,
  Trophy,
  Loader2,
  ArrowRight,
  Brain,
  Sparkles,
  ExternalLink,
  MessageCircle
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";

import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";

import InteractivePractice from "@/components/openings/InteractivePractice";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const OpeningLesson = () => {
  const { openingKey } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const boardRef = useRef(null);
  const groundRef = useRef(null);
  const chessRef = useRef(new Chess());
  
  // Get current game mistake passed from Lab page
  const currentGameMistake = location.state?.currentGameMistake;
  
  const [lesson, setLesson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("learn");
  
  // Learning state
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [isPracticing, setIsPracticing] = useState(false);
  const [practiceIndex, setPracticeIndex] = useState(0);
  const [feedback, setFeedback] = useState(null);
  const [showHint, setShowHint] = useState(false);
  
  // Trap practice state
  const [selectedTrap, setSelectedTrap] = useState(null);
  const [trapIndex, setTrapIndex] = useState(-1);
  
  // Fetch lesson data
  useEffect(() => {
    const fetchLesson = async () => {
      try {
        const res = await fetch(`${API}/openings/${openingKey}`, {
          credentials: "include"
        });
        if (res.ok) {
          const data = await res.json();
          setLesson(data);
        } else {
          toast.error("Opening not found");
          navigate("/openings");
        }
      } catch (err) {
        console.error("Error fetching lesson:", err);
        toast.error("Failed to load lesson");
      } finally {
        setLoading(false);
      }
    };
    fetchLesson();
  }, [openingKey, navigate]);
  
  // Initialize board
  useEffect(() => {
    if (boardRef.current && !groundRef.current) {
      groundRef.current = Chessground(boardRef.current, {
        fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        orientation: lesson?.opening?.color || "white",
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
  }, [lesson]);
  
  // Update board orientation when lesson loads
  useEffect(() => {
    if (groundRef.current && lesson?.opening?.color) {
      groundRef.current.set({
        orientation: lesson.opening.color
      });
    }
  }, [lesson?.opening?.color]);
  
  // Update board position
  const updateBoard = useCallback((fen, lastMove = null) => {
    if (groundRef.current) {
      groundRef.current.set({
        fen,
        lastMove: lastMove ? [lastMove.slice(0, 2), lastMove.slice(2, 4)] : undefined
      });
    }
  }, []);
  
  // Go to specific move in main line
  const goToMove = useCallback((index) => {
    if (!lesson?.opening?.main_line) return;
    
    chessRef.current.reset();
    let lastMove = null;
    
    for (let i = 0; i <= index && i < lesson.opening.main_line.length; i++) {
      const moveData = lesson.opening.main_line[i];
      const move = chessRef.current.move(moveData.move);
      if (move) {
        lastMove = move.from + move.to;
      }
    }
    
    setCurrentMoveIndex(index);
    updateBoard(chessRef.current.fen(), lastMove);
  }, [lesson, updateBoard]);
  
  // Practice mode handlers
  const startPractice = useCallback(() => {
    setIsPracticing(true);
    setPracticeIndex(0);
    setFeedback(null);
    setShowHint(false);
    chessRef.current.reset();
    updateBoard(chessRef.current.fen());
    
    // Set up for user's first move
    if (lesson?.opening?.color === "white") {
      // User plays white, their turn first
      setupPracticeMove(0);
    } else {
      // User plays black, play white's first move
      const firstMove = lesson?.opening?.main_line[0];
      if (firstMove) {
        setTimeout(() => {
          chessRef.current.move(firstMove.move);
          updateBoard(chessRef.current.fen());
          setupPracticeMove(1);
        }, 500);
      }
    }
  }, [lesson, updateBoard]);
  
  const setupPracticeMove = useCallback((index) => {
    setPracticeIndex(index);
    setFeedback(null);
    setShowHint(false);
    
    if (groundRef.current) {
      const chess = chessRef.current;
      const dests = new Map();
      
      for (const move of chess.moves({ verbose: true })) {
        if (!dests.has(move.from)) {
          dests.set(move.from, []);
        }
        dests.get(move.from).push(move.to);
      }
      
      groundRef.current.set({
        movable: {
          free: false,
          color: chess.turn() === 'w' ? 'white' : 'black',
          dests
        },
        events: {
          move: (orig, dest) => handlePracticeMove(orig, dest, index)
        }
      });
    }
  }, []);
  
  const handlePracticeMove = useCallback((orig, dest, expectedIndex) => {
    if (!lesson?.opening?.main_line) return;
    
    const expectedMove = lesson.opening.main_line[expectedIndex];
    const chess = chessRef.current;
    
    // Try to make the move
    const move = chess.move({ from: orig, to: dest, promotion: 'q' });
    
    if (!move) {
      // Invalid move
      updateBoard(chess.fen());
      return;
    }
    
    // Check if correct
    const isCorrect = move.san === expectedMove.move || 
                      (move.from + move.to) === expectedMove.move.toLowerCase().replace(/[+#x]/g, '');
    
    if (isCorrect) {
      setFeedback({
        type: "correct",
        message: expectedMove.explanation
      });
      
      updateBoard(chess.fen(), orig + dest);
      
      // Play opponent's response after delay
      const nextIndex = expectedIndex + 1;
      if (nextIndex < lesson.opening.main_line.length) {
        setTimeout(() => {
          const nextMove = lesson.opening.main_line[nextIndex];
          const opponentMove = chess.move(nextMove.move);
          if (opponentMove) {
            updateBoard(chess.fen(), opponentMove.from + opponentMove.to);
            
            // User's next turn
            const userNextIndex = nextIndex + 1;
            if (userNextIndex < lesson.opening.main_line.length) {
              setTimeout(() => {
                setupPracticeMove(userNextIndex);
              }, 500);
            } else {
              // Practice complete!
              setFeedback({
                type: "complete",
                message: "Excellent! You've completed the main line!"
              });
              setIsPracticing(false);
              
              // Update progress
              updateProgress(lesson.opening.main_line.length);
            }
          }
        }, 1000);
      }
    } else {
      // Wrong move - undo and show feedback
      chess.undo();
      updateBoard(chess.fen());
      
      setFeedback({
        type: "incorrect",
        message: `Try again! The main line move is ${expectedMove.move}`,
        hint: expectedMove.explanation
      });
    }
  }, [lesson, updateBoard, setupPracticeMove]);
  
  const updateProgress = async (movesLearned) => {
    try {
      await fetch(`${API}/openings/${openingKey}/progress`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          main_line_progress: movesLearned,
          practiced: true
        })
      });
    } catch (err) {
      console.error("Error updating progress:", err);
    }
  };
  
  // Trap practice
  const startTrapPractice = useCallback((trap) => {
    setSelectedTrap(trap);
    setTrapIndex(-1);
    setActiveTab("traps");
    
    // Reset board and play setup moves
    chessRef.current.reset();
    
    // Play setup moves
    for (const move of trap.setup_moves) {
      chessRef.current.move(move);
    }
    
    updateBoard(chessRef.current.fen());
    
    // Play first trap move automatically after a delay
    setTimeout(() => {
      if (trap.trap_line.length > 0) {
        const firstMove = trap.trap_line[0];
        const move = chessRef.current.move(firstMove.move);
        if (move) {
          updateBoard(chessRef.current.fen(), move.from + move.to);
        }
        setTrapIndex(0);
      }
    }, 500);
  }, [updateBoard]);
  
  const playNextTrapMove = useCallback(() => {
    if (!selectedTrap) return;
    
    const nextIndex = trapIndex + 1;
    if (nextIndex < selectedTrap.trap_line.length) {
      const moveData = selectedTrap.trap_line[nextIndex];
      const move = chessRef.current.move(moveData.move);
      if (move) {
        updateBoard(chessRef.current.fen(), move.from + move.to);
        setTrapIndex(nextIndex);
      } else {
        console.error("Invalid move in trap line:", moveData.move);
      }
    }
  }, [selectedTrap, trapIndex, updateBoard]);
  
  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }
  
  if (!lesson) return null;
  
  const { opening, user_stats, user_mistakes, learning_progress } = lesson;
  
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border/50 bg-card/50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => navigate("/openings")}
            className="mb-2"
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            Back to Repertoire
          </Button>
          
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/20">
              <BookOpen className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">{opening.name}</h1>
              <p className="text-sm text-muted-foreground">
                {opening.eco} • {opening.color === "white" ? "White Opening" : "Black Defense"}
              </p>
            </div>
            
            {user_stats && (
              <div className="ml-auto flex items-center gap-4">
                <Badge variant={user_stats.win_rate >= 50 ? "default" : "destructive"}>
                  {user_stats.win_rate?.toFixed(0)}% win rate
                </Badge>
                <span className="text-sm text-muted-foreground">
                  {user_stats.games_played} games
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Board */}
          <div>
            <Card>
              <CardContent className="p-4">
                <div 
                  ref={boardRef} 
                  className="w-full aspect-square rounded-lg overflow-hidden"
                  style={{ maxWidth: "500px", margin: "0 auto" }}
                />
                
                {/* Navigation */}
                {!isPracticing && (
                  <div className="flex items-center justify-center gap-2 mt-4">
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => goToMove(-1)}
                      disabled={currentMoveIndex < 0}
                    >
                      <RotateCcw className="w-4 h-4" />
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => goToMove(Math.max(-1, currentMoveIndex - 1))}
                      disabled={currentMoveIndex < 0}
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </Button>
                    <span className="text-sm px-3 min-w-[80px] text-center">
                      {currentMoveIndex < 0 ? "Start" : `Move ${currentMoveIndex + 1}`}
                    </span>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => goToMove(currentMoveIndex + 1)}
                      disabled={currentMoveIndex >= opening.main_line.length - 1}
                    >
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                )}
                
                {/* Practice Feedback */}
                <AnimatePresence>
                  {feedback && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      className={`mt-4 p-3 rounded-lg ${
                        feedback.type === "correct" ? "bg-green-500/10 border border-green-500/30" :
                        feedback.type === "complete" ? "bg-primary/10 border border-primary/30" :
                        "bg-red-500/10 border border-red-500/30"
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        {feedback.type === "correct" && <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />}
                        {feedback.type === "complete" && <Trophy className="w-5 h-5 text-primary flex-shrink-0" />}
                        {feedback.type === "incorrect" && <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0" />}
                        <div>
                          <p className="text-sm">{feedback.message}</p>
                          {feedback.hint && (
                            <p className="text-xs text-muted-foreground mt-1">{feedback.hint}</p>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
                
                {/* Practice Controls */}
                {isPracticing && (
                  <div className="mt-4 flex gap-2">
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => setShowHint(!showHint)}
                    >
                      <Lightbulb className="w-4 h-4 mr-1" />
                      Hint
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => {
                        setIsPracticing(false);
                        setFeedback(null);
                        goToMove(-1);
                      }}
                    >
                      Exit Practice
                    </Button>
                  </div>
                )}
                
                {showHint && isPracticing && (
                  <div className="mt-2 p-2 rounded bg-amber-500/10 border border-amber-500/20 text-sm">
                    <Lightbulb className="w-4 h-4 inline mr-1 text-amber-400" />
                    {opening.main_line[practiceIndex]?.explanation}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
          
          {/* Lesson Content */}
          <div>
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="mb-4">
                <TabsTrigger value="learn">Learn</TabsTrigger>
                <TabsTrigger value="practice">
                  <MessageCircle className="w-3 h-3 mr-1" />
                  Practice
                </TabsTrigger>
                <TabsTrigger value="traps">
                  Traps
                  {opening.traps?.length > 0 && (
                    <Badge variant="secondary" className="ml-1 h-5">
                      {opening.traps.length}
                    </Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="mistakes">Your Mistakes</TabsTrigger>
              </TabsList>
              
              <TabsContent value="learn" className="space-y-4">
                {/* Description */}
                <Card>
                  <CardContent className="p-4">
                    <p className="text-sm text-muted-foreground">
                      {opening.description}
                    </p>
                    
                    <div className="mt-4 flex gap-2">
                      <Button onClick={startPractice} className="flex-1">
                        <Play className="w-4 h-4 mr-2" />
                        Practice Moves
                      </Button>
                    </div>
                    
                    {learning_progress && learning_progress.main_line_progress > 0 && (
                      <div className="mt-4">
                        <div className="flex justify-between text-xs mb-1">
                          <span>Progress</span>
                          <span>{learning_progress.main_line_progress}/{opening.main_line.length} moves</span>
                        </div>
                        <Progress 
                          value={(learning_progress.main_line_progress / opening.main_line.length) * 100} 
                        />
                      </div>
                    )}
                  </CardContent>
                </Card>
                
                {/* Key Ideas */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Brain className="w-4 h-4 text-primary" />
                      Key Ideas
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 pt-0">
                    <ul className="space-y-2">
                      {opening.key_ideas?.map((idea, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0 mt-0.5" />
                          {idea}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
                
                {/* Main Line */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Main Line</CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 pt-0">
                    <div className="space-y-1 max-h-[300px] overflow-y-auto">
                      {opening.main_line?.map((moveData, i) => (
                        <div 
                          key={i}
                          className={`p-2 rounded cursor-pointer transition-colors ${
                            currentMoveIndex === i 
                              ? "bg-primary/20 border border-primary/30" 
                              : "hover:bg-muted/50"
                          }`}
                          onClick={() => goToMove(i)}
                        >
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground w-6">
                              {Math.floor(i / 2) + 1}.{i % 2 === 0 ? "" : ".."}
                            </span>
                            <span className="font-mono font-semibold text-sm">
                              {moveData.move}
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground ml-8 mt-1">
                            {moveData.explanation}
                          </p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
              
              <TabsContent value="practice" className="space-y-4">
                <InteractivePractice
                  openingKey={openingKey}
                  openingName={opening.name}
                  userColor={opening.color}
                />
              </TabsContent>
              
              <TabsContent value="traps" className="space-y-4">
                {opening.traps?.length > 0 ? (
                  <>
                    {/* Trap List */}
                    {!selectedTrap && opening.traps.map((trap, i) => (
                      <Card 
                        key={i} 
                        className="cursor-pointer hover:border-primary/50 transition-colors"
                        onClick={() => startTrapPractice(trap)}
                      >
                        <CardContent className="p-4">
                          <div className="flex items-start gap-3">
                            <div className="p-2 rounded-lg bg-amber-500/20">
                              <Target className="w-4 h-4 text-amber-400" />
                            </div>
                            <div className="flex-1">
                              <h3 className="font-semibold text-sm">{trap.name}</h3>
                              <p className="text-xs text-muted-foreground mt-1">
                                {trap.description}
                              </p>
                            </div>
                            <ChevronRight className="w-4 h-4 text-muted-foreground" />
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                    
                    {/* Active Trap */}
                    {selectedTrap && (
                      <Card className="border-amber-500/30 bg-amber-500/5">
                        <CardHeader className="pb-2">
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-sm flex items-center gap-2">
                              <Target className="w-4 h-4 text-amber-400" />
                              {selectedTrap.name}
                            </CardTitle>
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={() => setSelectedTrap(null)}
                            >
                              Back to list
                            </Button>
                          </div>
                        </CardHeader>
                        <CardContent className="p-4 pt-0">
                          <p className="text-sm text-muted-foreground mb-4">
                            {selectedTrap.description}
                          </p>
                          
                          <div className="space-y-2">
                            {selectedTrap.trap_line.map((moveData, i) => (
                              <div 
                                key={i}
                                className={`p-2 rounded ${
                                  trapIndex === i 
                                    ? "bg-amber-500/20 border border-amber-500/30" 
                                    : trapIndex > i 
                                    ? "bg-muted/30" 
                                    : "opacity-50"
                                }`}
                              >
                                <div className="flex items-center gap-2">
                                  <span className="font-mono font-semibold text-sm">
                                    {moveData.move}
                                  </span>
                                  {trapIndex >= i && (
                                    <CheckCircle2 className="w-4 h-4 text-green-400" />
                                  )}
                                </div>
                                {trapIndex >= i && (
                                  <p className="text-xs text-muted-foreground mt-1">
                                    {moveData.explanation}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                          
                          {trapIndex < selectedTrap.trap_line.length - 1 && (
                            <Button 
                              className="w-full mt-4"
                              onClick={playNextTrapMove}
                            >
                              Next Move
                              <ArrowRight className="w-4 h-4 ml-2" />
                            </Button>
                          )}
                          
                          {trapIndex === selectedTrap.trap_line.length - 1 && (
                            <div className="mt-4 p-3 rounded-lg bg-green-500/10 border border-green-500/30">
                              <div className="flex items-center gap-2">
                                <Trophy className="w-5 h-5 text-green-400" />
                                <p className="text-sm font-medium">
                                  {selectedTrap.success_message}
                                </p>
                              </div>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    )}
                  </>
                ) : (
                  <Card className="border-dashed">
                    <CardContent className="p-8 text-center">
                      <p className="text-muted-foreground">
                        No traps available for this opening yet.
                      </p>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>
              
              <TabsContent value="mistakes" className="space-y-4">
                {/* Current game mistake from Lab page */}
                {currentGameMistake && (
                  <Card className="border-amber-500/30 bg-amber-500/5">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                        From Your Recent Game
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-4 pt-0">
                      <div className="flex items-start gap-3">
                        <div>
                          <p className="text-sm">
                            <span className="font-semibold">Move {currentGameMistake.mistake.move_number}:</span>{" "}
                            You played <span className="text-red-400">{currentGameMistake.mistake.your_move}</span>
                          </p>
                          {currentGameMistake.mistake.best_move && (
                            <p className="text-sm mt-1">
                              Better was <span className="text-green-400">{currentGameMistake.mistake.best_move}</span>
                            </p>
                          )}
                          {currentGameMistake.gameId && (
                            <Button
                              variant="link"
                              size="sm"
                              className="px-0 mt-2 text-xs"
                              onClick={() => navigate(`/game/${currentGameMistake.gameId}`)}
                            >
                              <ExternalLink className="w-3 h-3 mr-1" />
                              View in game
                            </Button>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}
                
                {/* Historical mistakes from analyzed games */}
                {user_mistakes?.length > 0 ? (
                  user_mistakes.map((mistake, i) => (
                    <Card key={i} className="border-red-500/30 bg-red-500/5">
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0" />
                          <div>
                            <p className="text-sm">
                              <span className="font-semibold">Move {mistake.move_number}:</span>{" "}
                              You played <span className="text-red-400">{mistake.your_move}</span>
                            </p>
                            {mistake.best_move && (
                              <p className="text-sm mt-1">
                                Better was <span className="text-green-400">{mistake.best_move}</span>
                              </p>
                            )}
                            <p className="text-xs text-muted-foreground mt-2">
                              Loss: {Math.abs(mistake.cp_loss)} centipawns
                            </p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))
                ) : !currentGameMistake ? (
                  <Card className="border-dashed">
                    <CardContent className="p-8 text-center">
                      <Sparkles className="w-8 h-8 text-primary mx-auto mb-2" />
                      <p className="text-muted-foreground">
                        No recorded mistakes in this opening yet!
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Play more games with this opening to see your patterns.
                      </p>
                    </CardContent>
                  </Card>
                ) : null}
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OpeningLesson;
