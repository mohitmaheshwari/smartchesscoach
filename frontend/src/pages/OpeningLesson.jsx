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
import TrapPractice from "@/components/openings/TrapPractice";
import GuidedOpeningLesson from "@/components/openings/GuidedOpeningLesson";
import { OpeningCorrectionDialog } from "@/components/openings/OpeningCorrectionDialog";
import { API } from "@/App";

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
  const [trapPracticeMode, setTrapPracticeMode] = useState(false);
  const [selectedVariation, setSelectedVariation] = useState(null);
  
  // Fetch lesson data
  useEffect(() => {
    const fetchLesson = async () => {
      try {
        const variationParam = selectedVariation ? `?variation=${selectedVariation}` : "";
        const res = await fetch(`${API}/openings/${openingKey}${variationParam}`, {
          credentials: "include"
        });
        if (res.ok) {
          const data = await res.json();
          setLesson(data);
          // Reset board state when variation changes
          setCurrentMoveIndex(-1);
          chessRef.current.reset();
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
  }, [openingKey, navigate, selectedVariation]);

  // Ping Engine 2 once per page visit to register "seen" on the matching
  // opening skill (if the tree has one). Fire-and-forget — don't block UI.
  // Also ticks the trap_set skill for this opening (same content_ref slug).
  useEffect(() => {
    if (!openingKey) return;
    const engine2Candidates = [
      `opening_${openingKey}_white`,
      `opening_${openingKey}_black`,
      `opening_${openingKey}`,
      `trap_set_${openingKey}`,
    ];
    (async () => {
      for (const skillId of engine2Candidates) {
        try {
          await fetch(`${API}/engine2/skill-seen`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ skill_id: skillId }),
          });
        } catch {
          // non-fatal — skill might not be in the tree, that's OK
        }
      }
    })();
  }, [openingKey]);
  
  // Resolve board orientation from whichever path has data. Before the
  // backend fix, `lesson.opening.color` was undefined for every lesson, so
  // every board rendered white-on-bottom. Now the API returns `color` both
  // at the top level (`lesson.color`) and nested (`lesson.opening.color`).
  // The URL key fallback handles explicit `_black` suffixes (`italian_game_black`).
  const resolvedOrientation =
    lesson?.color ||
    lesson?.opening?.color ||
    (openingKey?.toLowerCase().endsWith("_black") ? "black" : "white");

  // Initialize board
  useEffect(() => {
    if (boardRef.current && !groundRef.current) {
      groundRef.current = Chessground(boardRef.current, {
        fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        orientation: resolvedOrientation,
        movable: {
          free: false,
          color: undefined
        },
        animation: { duration: 300 },
        drawable: { enabled: true, visible: true }
      });
    }

    return () => {
      if (groundRef.current) {
        groundRef.current.destroy();
        groundRef.current = null;
      }
    };
  }, [lesson, resolvedOrientation]);

  // Update board orientation when lesson loads
  useEffect(() => {
    if (groundRef.current && resolvedOrientation) {
      groundRef.current.set({
        orientation: resolvedOrientation
      });
    }
  }, [resolvedOrientation]);
  
  // Update board position
  const updateBoard = useCallback((fen, lastMove = null) => {
    if (groundRef.current) {
      groundRef.current.set({
        fen,
        lastMove: lastMove ? [lastMove.slice(0, 2), lastMove.slice(2, 4)] : undefined
      });
    }
  }, []);

  // Play a mistake move on the board with an arrow. Resets to `fenBefore`
  // first, then after a short beat applies the move so chessground animates
  // the piece sliding, plus draws a colored arrow showing the move.
  // `brush`: "red" for the user's played move, "green" for the best move.
  const playMistakeMove = useCallback((fenBefore, moveUci, brush) => {
    if (!groundRef.current || !fenBefore || !moveUci || moveUci.length < 4) return;
    const from = moveUci.slice(0, 2);
    const to = moveUci.slice(2, 4);

    // Step 1: snap to the position *before* the move, clear any existing arrows.
    groundRef.current.set({
      fen: fenBefore,
      lastMove: undefined,
    });
    groundRef.current.setAutoShapes([]);

    // Step 2: after a beat, apply the move using chess.js for a clean FEN
    // and let chessground animate. Draw the arrow once the move lands.
    setTimeout(() => {
      try {
        const c = new Chess(fenBefore);
        const res = c.move({ from, to, promotion: moveUci[4] || "q" });
        if (!res) return;
        groundRef.current.set({
          fen: c.fen(),
          lastMove: [from, to],
        });
        groundRef.current.setAutoShapes([{ orig: from, dest: to, brush }]);
      } catch (e) {
        // Invalid move against this FEN — just draw the arrow on the before-position.
        groundRef.current.set({ fen: fenBefore });
        groundRef.current.setAutoShapes([{ orig: from, dest: to, brush }]);
      }
    }, 300);
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

              // Mohit 2026-05-30: clean main-line completion grades the
              // engine2 opening skill. We try multiple candidate skill
              // ids because the URL openingKey doesn't always include
              // the colour suffix (e.g. 'london_system' vs
              // 'opening_london_white'). Whichever one exists in the
              // tree gets recorded; the rest return 404 silently.
              const candidates = [
                `opening_${openingKey}_white`,
                `opening_${openingKey}_black`,
                `opening_${openingKey}`,
              ];
              for (const skillId of candidates) {
                fetch(`${API}/engine2/skill-completed`, {
                  method: "POST",
                  credentials: "include",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ skill_id: skillId, outcome: "correct" }),
                }).catch(() => {});
              }
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
  
  // Trap practice - use TrapPractice component
  const startTrapPractice = useCallback((trap) => {
    setSelectedTrap(trap);
    setTrapPracticeMode(true);
    setActiveTab("traps");
  }, []);
  
  const closeTrapPractice = useCallback(() => {
    setSelectedTrap(null);
    setTrapPracticeMode(false);
    // Reset board to opening start
    chessRef.current.reset();
    updateBoard(chessRef.current.fen());
  }, [updateBoard]);
  
  const onTrapComplete = useCallback(() => {
    // Record completion
    toast.success(`Mastered: ${selectedTrap?.name}!`);
  }, [selectedTrap]);
  
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
            <div className="ml-auto">
              <OpeningCorrectionDialog
                sourceContext="openings_page"
                openingKey={openingKey}
                openingName={opening.name}
                variationName={opening.variation || null}
                trapName={selectedTrap?.name || null}
                currentMoves={(opening.main_line || []).map((moveData) => moveData.move)}
                currentFen={chessRef.current?.fen?.() || ""}
                triggerLabel="Correct opening data"
                compact={true}
              />
            </div>
            
            {user_stats && (
              <div className="flex items-center gap-4">
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
        {/* Variation Selector */}
        {opening.variations?.length > 1 && (
          <div className="mb-4" data-testid="variation-selector">
            <p className="text-xs text-muted-foreground mb-2">Variation</p>
            <div className="flex flex-wrap gap-2">
              {opening.variations.map((v) => (
                <button
                  key={v.key}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    (selectedVariation || opening.active_variation) === v.key
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
                  }`}
                  onClick={() => setSelectedVariation(v.key)}
                  data-testid={`variation-btn-${v.key}`}
                >
                  {v.name}
                  <span className="text-zinc-600 ml-1">({v.total_moves})</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Tab Navigation - Full Width */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
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
          
          {/* Learn Tab - Full width guided experience */}
          <TabsContent value="learn" className="space-y-4">
            <div className="max-w-2xl mx-auto">
              {/* Guided Interactive Lesson - This is the main experience */}
              <GuidedOpeningLesson
                openingKey={openingKey}
                opening={opening}
                onComplete={() => {
                  console.log("Lesson completed");
                }}
                onStartPractice={() => setActiveTab("practice")}
              />
              
              {/* Key Ideas - Collapsed reference */}
              <Card className="bg-zinc-900/30 border-zinc-800 mt-4">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2 text-zinc-400">
                    <Brain className="w-4 h-4 text-amber-500" />
                    Key Ideas Reference
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-0">
                  <ul className="space-y-2">
                    {opening.key_ideas?.map((idea, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-zinc-400">
                        <CheckCircle2 className="w-4 h-4 text-green-500/60 flex-shrink-0 mt-0.5" />
                        {idea}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
          
          {/* Other Tabs - 2 column layout with board */}
          <div className={activeTab === "learn" ? "hidden" : "grid grid-cols-1 lg:grid-cols-2 gap-6"}>
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
                  {!isPracticing && activeTab !== "practice" && (
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
            
            {/* Lesson Content for other tabs */}
            <div>
              
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
                    {/* Active Trap Practice Mode */}
                    {selectedTrap && trapPracticeMode ? (
                      <TrapPractice
                        trap={selectedTrap}
                        onClose={closeTrapPractice}
                        onComplete={onTrapComplete}
                      />
                    ) : (
                      /* Trap List */
                      <>
                        <div className="text-sm text-muted-foreground mb-2">
                          Click a trap to practice executing it against the coach.
                        </div>
                        {opening.traps.map((trap, i) => (
                          <Card 
                            key={i} 
                            className="cursor-pointer hover:border-amber-500/50 transition-colors"
                            onClick={() => startTrapPractice(trap)}
                            data-testid={`trap-card-${i}`}
                          >
                            <CardContent className="p-4">
                              <div className="flex items-start gap-3">
                                <div className="p-2 rounded-lg bg-amber-500/20">
                                  <Target className="w-4 h-4 text-amber-400" />
                                </div>
                                <div className="flex-1">
                                  <div className="flex items-center gap-2">
                                    <h3 className="font-semibold text-sm">{trap.name}</h3>
                                    <Badge 
                                      variant="outline" 
                                      className={`text-xs ${
                                        trap.difficulty === "beginner" 
                                          ? "border-green-500/30 text-green-400" 
                                          : trap.difficulty === "advanced"
                                          ? "border-red-500/30 text-red-400"
                                          : "border-amber-500/30 text-amber-400"
                                      }`}
                                    >
                                      {trap.difficulty}
                                    </Badge>
                                  </div>
                                  <p className="text-xs text-muted-foreground mt-1">
                                    {trap.description}
                                  </p>
                                  <div className="flex items-center gap-2 mt-2">
                                    <Badge variant="secondary" className="text-xs">
                                      {trap.result_type?.replace(/_/g, " ")}
                                    </Badge>
                                    <span className="text-xs text-muted-foreground">
                                      {trap.trap_line?.length || 0} moves
                                    </span>
                                  </div>
                                </div>
                                <Play className="w-4 h-4 text-amber-400" />
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                      </>
                    )}
                  </>
                ) : (
                  <Card className="border-dashed">
                    <CardContent className="p-8 text-center">
                      <Target className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
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
                          <div className="flex-1">
                            {/* Lead-in: the moves that produced this position,
                                so the user can recognize the Italian line. */}
                            {mistake.moves_before?.length > 0 && (
                              <p className="text-xs font-mono text-muted-foreground mb-2">
                                {(() => {
                                  const seq = mistake.moves_before;
                                  const parts = [];
                                  for (let k = 0; k < seq.length; k += 2) {
                                    const num = Math.floor(k / 2) + 1;
                                    const w = seq[k] || "";
                                    const b = seq[k + 1] || "";
                                    parts.push(`${num}.${w}${b ? " " + b : ""}`);
                                  }
                                  return parts.join(" ");
                                })()}
                              </p>
                            )}
                            <p className="text-sm">
                              <span className="font-semibold">Move {mistake.move_number}:</span>{" "}
                              You played <span className="text-red-400">{mistake.your_move}</span>
                              {mistake.book_move && (
                                <>
                                  {" "}— book was{" "}
                                  <span className="text-green-400">{mistake.book_move}</span>
                                </>
                              )}
                            </p>
                            {mistake.coach?.book_line && (
                              <p className="text-sm text-foreground/90 mt-2 leading-relaxed">
                                {mistake.coach.book_line}
                              </p>
                            )}
                            {mistake.coach?.principle && (
                              <p className="text-xs text-amber-300/90 mt-1 italic">
                                Principle: {mistake.coach.principle}
                              </p>
                            )}
                            <p className="text-xs text-muted-foreground mt-2">
                              Loss: {Math.abs(mistake.cp_loss)} cp
                              {mistake.cognitive_gap && (
                                <span className="ml-2 px-1.5 py-0.5 rounded bg-muted text-foreground/70 uppercase tracking-wide text-[10px]">
                                  {String(mistake.cognitive_gap).replace(/_/g, " ")}
                                </span>
                              )}
                            </p>
                            {mistake.fen_before && (
                              <div className="flex gap-2 mt-3">
                                {mistake.your_move_uci && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 text-xs border-red-500/40 text-red-300 hover:bg-red-500/10"
                                    onClick={() =>
                                      playMistakeMove(mistake.fen_before, mistake.your_move_uci, "red")
                                    }
                                  >
                                    Play your move
                                  </Button>
                                )}
                                {mistake.best_move_uci && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 text-xs border-green-500/40 text-green-300 hover:bg-green-500/10"
                                    onClick={() =>
                                      playMistakeMove(mistake.fen_before, mistake.best_move_uci, "green")
                                    }
                                  >
                                    Play best move
                                  </Button>
                                )}
                              </div>
                            )}
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
            </div>
          </div>
        </Tabs>
      </div>
    </div>
  );
};

export default OpeningLesson;
