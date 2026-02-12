/**
 * LAB PAGE - Surgical Game Correction Environment
 * 
 * Purpose: Deep correction of a single game.
 * Not diagnosis. Not trend. One game → fully understood → corrected.
 * 
 * When user leaves this page, they should feel:
 * "I understand exactly where I lost control."
 */

import { useState, useEffect, useRef, useMemo } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import Layout from "@/components/Layout";
import { toast } from "sonner";
import { 
  ArrowLeft, 
  Loader2, 
  Brain,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Target,
  Zap,
  Play,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  RotateCcw,
  Eye,
  EyeOff,
  BookOpen,
  Lightbulb,
  TrendingUp,
  TrendingDown,
  Pause
} from "lucide-react";
import { formatEvalWithContext, formatCpLoss } from "@/utils/evalFormatter";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

// Convert FEN to position object for react-chessboard
const fenToPositionObject = (fen) => {
  const position = {};
  const parts = fen.split(' ');
  const rows = parts[0].split('/');
  
  for (let row = 0; row < 8; row++) {
    let col = 0;
    for (const char of rows[row]) {
      if (char >= '1' && char <= '8') {
        col += parseInt(char);
      } else {
        const file = String.fromCharCode(97 + col);
        const rank = 8 - row;
        const square = file + rank;
        const color = char === char.toUpperCase() ? 'w' : 'b';
        const piece = char.toUpperCase();
        position[square] = color + piece;
        col++;
      }
    }
  }
  return position;
};

const Lab = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialMove = searchParams.get('move');
  
  // Data states
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [labData, setLabData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  
  // Board states
  const [moves, setMoves] = useState([]);
  const [allFens, setAllFens] = useState([START_FEN]);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [positionObject, setPositionObject] = useState(() => fenToPositionObject(START_FEN));
  const [boardOrientation, setBoardOrientation] = useState("white");
  const [lastMoveSquares, setLastMoveSquares] = useState({});
  const [isPlaying, setIsPlaying] = useState(false);
  
  // UI states
  const [showOnlyCritical, setShowOnlyCritical] = useState(false);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState("mistakes");
  
  // Practice mode
  const [practiceMode, setPracticeMode] = useState(false);
  const [practicePositions, setPracticePositions] = useState([]);
  const [practiceIndex, setPracticeIndex] = useState(0);
  
  // Fetch game and analysis data
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch game data
        const gameResponse = await fetch(`${API}/games/${gameId}`, { credentials: "include" });
        if (!gameResponse.ok) throw new Error("Game not found");
        const gameData = await gameResponse.json();
        setGame(gameData);
        setBoardOrientation(gameData.user_color === "black" ? "black" : "white");
        
        // Fetch analysis
        const analysisResponse = await fetch(`${API}/analysis/${gameId}`, { credentials: "include" });
        if (analysisResponse.ok) {
          const analysisData = await analysisResponse.json();
          setAnalysis(analysisData);
        }
        
        // Fetch lab-specific data
        const labResponse = await fetch(`${API}/lab/${gameId}`, { credentials: "include" });
        if (labResponse.ok) {
          const labDataResponse = await labResponse.json();
          setLabData(labDataResponse);
        }
      } catch (error) {
        toast.error("Failed to load game");
        navigate("/import");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [gameId, navigate]);

  // Parse PGN and setup board
  useEffect(() => {
    if (!game?.pgn) return;
    
    const tempGame = new Chess();
    try {
      tempGame.loadPgn(game.pgn);
    } catch {
      // Try parsing moves only
      const lines = game.pgn.split('\n');
      let movesText = '';
      for (const line of lines) {
        if (!line.startsWith('[') && line.trim()) {
          movesText += ' ' + line;
        }
      }
      movesText = movesText.replace(/\{[^}]*\}/g, '').replace(/\([^)]*\)/g, '').trim();
      try {
        tempGame.loadPgn(movesText);
      } catch {
        return;
      }
    }
    
    const history = tempGame.history({ verbose: true });
    const fens = [START_FEN];
    const calcGame = new Chess();
    
    for (const m of history) {
      calcGame.move({ from: m.from, to: m.to, promotion: m.promotion });
      fens.push(calcGame.fen());
    }
    
    setAllFens(fens);
    setMoves(history);
    setPositionObject(fenToPositionObject(START_FEN));
    setCurrentMoveIndex(-1);
  }, [game?.pgn]);

  // Handle initial move from URL
  useEffect(() => {
    if (initialMove && moves.length > 0) {
      const moveNum = parseInt(initialMove, 10);
      if (!isNaN(moveNum) && moveNum > 0) {
        // Convert move number to index (move 1 = index 0 or 1 depending on color)
        const targetIndex = (moveNum - 1) * 2 + (game?.user_color === "black" ? 1 : 0);
        goToMove(Math.min(targetIndex, moves.length - 1));
      }
    }
  }, [initialMove, moves.length, game?.user_color]);

  // Navigate to a specific move
  const goToMove = (targetIndex) => {
    const clampedIndex = Math.max(-1, Math.min(targetIndex, moves.length - 1));
    const posIndex = clampedIndex + 1;
    const fen = allFens[posIndex] || START_FEN;
    
    setPositionObject(fenToPositionObject(fen));
    setCurrentMoveIndex(clampedIndex);
    
    if (clampedIndex >= 0 && moves[clampedIndex]) {
      setLastMoveSquares({
        [moves[clampedIndex].from]: { backgroundColor: "rgba(255, 255, 0, 0.4)" },
        [moves[clampedIndex].to]: { backgroundColor: "rgba(255, 255, 0, 0.4)" }
      });
    } else {
      setLastMoveSquares({});
    }
  };

  // Navigation helpers
  const goToStart = () => { goToMove(-1); setIsPlaying(false); };
  const goToEnd = () => { goToMove(moves.length - 1); setIsPlaying(false); };
  const goBack = () => currentMoveIndex <= 0 ? goToStart() : goToMove(currentMoveIndex - 1);
  const goForward = () => currentMoveIndex < moves.length - 1 && goToMove(currentMoveIndex + 1);
  const flipBoard = () => setBoardOrientation(o => o === "white" ? "black" : "white");
  
  // Toggle play
  const togglePlay = () => {
    if (currentMoveIndex >= moves.length - 1) {
      goToStart();
      setTimeout(() => setIsPlaying(true), 100);
    } else {
      setIsPlaying(p => !p);
    }
  };

  // Auto-play effect
  useEffect(() => {
    if (!isPlaying || currentMoveIndex >= moves.length - 1) {
      if (currentMoveIndex >= moves.length - 1) setIsPlaying(false);
      return;
    }
    const timer = setTimeout(() => goToMove(currentMoveIndex + 1), 600);
    return () => clearTimeout(timer);
  }, [isPlaying, currentMoveIndex, moves.length]);

  // Trigger analysis
  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const response = await fetch(`${API}/analyze-game`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ game_id: gameId })
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Analysis failed");
      }
      const data = await response.json();
      setAnalysis(data);
      
      // Refetch lab data
      const labResponse = await fetch(`${API}/lab/${gameId}`, { credentials: "include" });
      if (labResponse.ok) {
        setLabData(await labResponse.json());
      }
      toast.success("Analysis complete!");
    } catch (error) {
      toast.error(error.message || "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  // Extract data from analysis
  const stockfishData = analysis?.stockfish_analysis || {};
  const moveEvaluations = stockfishData.move_evaluations || [];
  const accuracy = stockfishData.accuracy;
  const coreLesson = labData?.core_lesson;
  const strategicAnalysis = labData?.strategic_analysis;
  
  // Count mistakes
  const mistakeCounts = useMemo(() => {
    let blunders = 0, mistakes = 0, inaccuracies = 0;
    moveEvaluations.forEach(m => {
      if (!m.is_user_move) return;
      const cpLoss = Math.abs(m.cp_loss || 0);
      if (cpLoss >= 300) blunders++;
      else if (cpLoss >= 100) mistakes++;
      else if (cpLoss >= 50) inaccuracies++;
    });
    return { blunders, mistakes, inaccuracies };
  }, [moveEvaluations]);

  // Group mistakes by type for the Mistakes tab
  const groupedMistakes = useMemo(() => {
    const groups = {
      blunders: [],
      hanging_pieces: [],
      tactical_misses: [],
      positional_errors: [],
      other: []
    };
    
    moveEvaluations.forEach(m => {
      if (!m.is_user_move) return;
      const cpLoss = Math.abs(m.cp_loss || 0);
      if (cpLoss < 50) return; // Not a mistake
      
      const mistakeType = m.mistake_type || '';
      const entry = {
        move_number: m.move_number,
        move: m.move,
        best_move: m.best_move,
        cp_loss: cpLoss,
        eval_before: m.eval_before,
        eval_after: m.eval_after,
        fen_before: m.fen_before,
        phase: m.phase || (m.move_number <= 10 ? 'opening' : m.move_number <= 30 ? 'middlegame' : 'endgame'),
        context: getContextLabel(m),
        isBlunder: cpLoss >= 300,
        isMistake: cpLoss >= 100 && cpLoss < 300,
        isInaccuracy: cpLoss >= 50 && cpLoss < 100
      };
      
      // Group by type
      if (mistakeType.includes('hanging') || mistakeType.includes('material_blunder')) {
        groups.hanging_pieces.push(entry);
      } else if (mistakeType.includes('missed_') || mistakeType.includes('tactical')) {
        groups.tactical_misses.push(entry);
      } else if (cpLoss >= 300) {
        groups.blunders.push(entry);
      } else if (mistakeType.includes('positional') || mistakeType.includes('drift')) {
        groups.positional_errors.push(entry);
      } else {
        groups.other.push(entry);
      }
    });
    
    // Filter empty groups
    return Object.entries(groups)
      .filter(([_, items]) => items.length > 0)
      .map(([type, items]) => ({
        type,
        label: formatGroupLabel(type),
        count: items.length,
        items: items.sort((a, b) => b.cp_loss - a.cp_loss) // Sort by severity
      }));
  }, [moveEvaluations]);

  // Critical moves (eval swing > 1.5 or big cp loss)
  const criticalMoves = useMemo(() => {
    return moveEvaluations.filter(m => {
      if (!m.is_user_move) return false;
      const cpLoss = Math.abs(m.cp_loss || 0);
      return cpLoss >= 150; // 1.5 pawns
    });
  }, [moveEvaluations]);

  // Get biggest eval swing
  const biggestEvalSwing = useMemo(() => {
    let maxSwing = null;
    moveEvaluations.forEach(m => {
      if (!m.is_user_move) return;
      const cpLoss = Math.abs(m.cp_loss || 0);
      if (!maxSwing || cpLoss > maxSwing.cp_loss) {
        maxSwing = { ...m, cp_loss: cpLoss };
      }
    });
    return maxSwing;
  }, [moveEvaluations]);

  // Move list for the board panel
  const movePairs = useMemo(() => {
    const pairs = [];
    for (let i = 0; i < moves.length; i += 2) {
      const whiteMove = moves[i];
      const blackMove = moves[i + 1];
      
      // Get evaluations for these moves
      const whiteEval = moveEvaluations.find(e => 
        e.move_number === Math.floor(i / 2) + 1 && 
        (game?.user_color === 'white' ? e.is_user_move : !e.is_user_move)
      );
      const blackEval = moveEvaluations.find(e => 
        e.move_number === Math.floor(i / 2) + 1 && 
        (game?.user_color === 'black' ? e.is_user_move : !e.is_user_move)
      );
      
      pairs.push({
        num: Math.floor(i / 2) + 1,
        white: whiteMove?.san || "",
        black: blackMove?.san || "",
        wIdx: i,
        bIdx: i + 1,
        wCpLoss: game?.user_color === 'white' ? (whiteEval?.cp_loss || 0) : 0,
        bCpLoss: game?.user_color === 'black' ? (blackEval?.cp_loss || 0) : 0,
        wIsCritical: game?.user_color === 'white' && Math.abs(whiteEval?.cp_loss || 0) >= 150,
        bIsCritical: game?.user_color === 'black' && Math.abs(blackEval?.cp_loss || 0) >= 150
      });
    }
    return pairs;
  }, [moves, moveEvaluations, game?.user_color]);

  // Start practice mode
  const startPracticeMode = () => {
    const positions = criticalMoves.slice(0, 5).map(m => ({
      fen: m.fen_before,
      move_number: m.move_number,
      best_move: m.best_move,
      played_move: m.move,
      cp_loss: Math.abs(m.cp_loss || 0)
    }));
    setPracticePositions(positions);
    setPracticeIndex(0);
    setPracticeMode(true);
  };

  // Loading state
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  // Extract game info
  const whitePlayer = game?.white_player || "White";
  const blackPlayer = game?.black_player || "Black";
  const userColor = game?.user_color || "white";
  const result = game?.result || "";
  const opponent = userColor === "white" ? blackPlayer : whitePlayer;
  const opponentRating = userColor === "white" ? game?.black_rating : game?.white_rating;

  return (
    <Layout user={user}>
      <div className="h-[calc(100vh-80px)] flex flex-col" data-testid="lab-page">
        {/* STICKY HEADER */}
        <div className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b border-border/50 px-4 py-3">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
                <ArrowLeft className="w-5 h-5" />
              </Button>
              
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-bold">vs {opponent}</h1>
                  {opponentRating && (
                    <Badge variant="outline" className="text-xs">
                      {opponentRating}
                    </Badge>
                  )}
                  <Badge 
                    variant={result.includes("1-0") ? (userColor === "white" ? "default" : "destructive") : 
                            result.includes("0-1") ? (userColor === "black" ? "default" : "destructive") : 
                            "secondary"}
                    className="text-xs"
                  >
                    {result.includes("1-0") ? (userColor === "white" ? "WIN" : "LOSS") :
                     result.includes("0-1") ? (userColor === "black" ? "WIN" : "LOSS") :
                     "DRAW"}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  You played {userColor} • {accuracy ? `${accuracy}% accuracy` : ''}
                </p>
              </div>
            </div>
            
            {/* Stats */}
            {analysis && (
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-red-500 font-bold">{mistakeCounts.blunders}</span>
                  <span className="text-muted-foreground">Blunders</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-orange-500 font-bold">{mistakeCounts.mistakes}</span>
                  <span className="text-muted-foreground">Mistakes</span>
                </div>
              </div>
            )}
            
            {/* Core Lesson - One sentence */}
            {coreLesson && coreLesson.pattern !== "clean_game" && (
              <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 max-w-md">
                <Lightbulb className="w-4 h-4 text-amber-500 shrink-0" />
                <span className="text-sm truncate">{coreLesson.lesson}</span>
              </div>
            )}
            
            {/* Practice Button */}
            {criticalMoves.length > 0 && (
              <Button 
                size="sm" 
                onClick={startPracticeMode}
                className="gap-1.5 bg-primary hover:bg-primary/90"
                data-testid="practice-btn"
              >
                <Target className="w-4 h-4" />
                Practice Critical Moments
              </Button>
            )}
            
            {/* Analyze Button */}
            {!analysis && (
              <Button onClick={handleAnalyze} disabled={analyzing}>
                {analyzing ? (
                  <><Loader2 className="w-4 h-4 animate-spin mr-2" />Analyzing...</>
                ) : (
                  <><Brain className="w-4 h-4 mr-2" />Analyze</>
                )}
              </Button>
            )}
          </div>
        </div>

        {/* MAIN CONTENT - Two Panel */}
        <div className="flex-1 flex overflow-hidden">
          {/* LEFT: BOARD */}
          <div className={`flex-1 p-4 overflow-auto ${rightPanelCollapsed ? 'max-w-3xl mx-auto' : ''}`}>
            <div className="flex flex-col items-center gap-4">
              {/* Board */}
              <div className="relative w-full max-w-[500px]">
                <Chessboard
                  position={positionObject}
                  boardOrientation={boardOrientation}
                  customSquareStyles={lastMoveSquares}
                  arePiecesDraggable={false}
                  animationDuration={0}
                  customBoardStyle={{
                    borderRadius: '8px',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.2)'
                  }}
                />
              </div>
              
              {/* Navigation */}
              <div className="flex items-center gap-2">
                <Button variant="outline" size="icon" onClick={goToStart} disabled={currentMoveIndex < 0}>
                  <ChevronsLeft className="w-4 h-4" />
                </Button>
                <Button variant="outline" size="icon" onClick={goBack} disabled={currentMoveIndex < 0}>
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <Button variant="default" size="icon" onClick={togglePlay} disabled={moves.length === 0}>
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </Button>
                <Button variant="outline" size="icon" onClick={goForward} disabled={currentMoveIndex >= moves.length - 1}>
                  <ChevronRight className="w-4 h-4" />
                </Button>
                <Button variant="outline" size="icon" onClick={goToEnd} disabled={currentMoveIndex >= moves.length - 1}>
                  <ChevronsRight className="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="icon" onClick={flipBoard}>
                  <RotateCcw className="w-4 h-4" />
                </Button>
                <Button 
                  variant={showOnlyCritical ? "default" : "outline"} 
                  size="sm"
                  onClick={() => setShowOnlyCritical(!showOnlyCritical)}
                  className="ml-2 gap-1"
                >
                  {showOnlyCritical ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                  Critical Only
                </Button>
              </div>
              
              {/* Move List */}
              <div className="w-full max-w-[500px] bg-muted/30 rounded-lg p-3 max-h-48 overflow-y-auto">
                <div className="grid grid-cols-[auto_1fr_1fr] gap-x-3 gap-y-1 text-sm font-mono">
                  {movePairs.map((p) => {
                    // Filter if showing only critical
                    if (showOnlyCritical && !p.wIsCritical && !p.bIsCritical) {
                      return null;
                    }
                    return (
                      <div key={p.num} className="contents">
                        <span className="text-muted-foreground">{p.num}.</span>
                        <button
                          className={`text-left px-1.5 py-0.5 rounded transition-colors ${
                            currentMoveIndex === p.wIdx ? "bg-primary/30 font-bold" : "hover:bg-muted"
                          } ${p.wIsCritical ? "text-red-500" : ""} ${
                            Math.abs(p.wCpLoss) >= 300 ? "border-l-2 border-red-500" :
                            Math.abs(p.wCpLoss) >= 100 ? "border-l-2 border-orange-500" : ""
                          }`}
                          onClick={() => goToMove(p.wIdx)}
                        >
                          {p.white}
                        </button>
                        <button
                          className={`text-left px-1.5 py-0.5 rounded transition-colors ${
                            currentMoveIndex === p.bIdx ? "bg-primary/30 font-bold" : "hover:bg-muted"
                          } ${p.bIsCritical ? "text-red-500" : ""} ${
                            Math.abs(p.bCpLoss) >= 300 ? "border-l-2 border-red-500" :
                            Math.abs(p.bCpLoss) >= 100 ? "border-l-2 border-orange-500" : ""
                          }`}
                          onClick={() => p.black && goToMove(p.bIdx)}
                          disabled={!p.black}
                        >
                          {p.black}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT: TABS */}
          {!rightPanelCollapsed && (
            <div className="w-[400px] lg:w-[450px] border-l border-border/50 flex flex-col overflow-hidden">
              {analysis ? (
                <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
                  <TabsList className="grid w-full grid-cols-3 rounded-none border-b">
                    <TabsTrigger value="summary">Summary</TabsTrigger>
                    <TabsTrigger value="strategy">Strategy</TabsTrigger>
                    <TabsTrigger value="mistakes" className="relative">
                      Mistakes
                      {mistakeCounts.blunders > 0 && (
                        <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center">
                          {mistakeCounts.blunders}
                        </span>
                      )}
                    </TabsTrigger>
                  </TabsList>
                  
                  <ScrollArea className="flex-1">
                    {/* SUMMARY TAB */}
                    <TabsContent value="summary" className="p-4 space-y-4 m-0">
                      {/* Core Lesson */}
                      {coreLesson && coreLesson.pattern !== "clean_game" && (
                        <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/20">
                          <p className="text-xs text-amber-500 font-bold uppercase tracking-wider mb-2">Core Lesson</p>
                          <p className="font-medium">{coreLesson.lesson}</p>
                        </div>
                      )}
                      
                      {/* Clean Game */}
                      {coreLesson?.pattern === "clean_game" && (
                        <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20">
                          <div className="flex items-center gap-2 mb-2">
                            <CheckCircle2 className="w-5 h-5 text-green-500" />
                            <p className="font-bold text-green-500">Clean Game!</p>
                          </div>
                          <p className="text-sm">{coreLesson.lesson}</p>
                        </div>
                      )}
                      
                      {/* Biggest Eval Swing */}
                      {biggestEvalSwing && biggestEvalSwing.cp_loss >= 100 && (
                        <div className="p-3 rounded-lg bg-muted/50">
                          <p className="text-xs text-muted-foreground uppercase mb-1">Critical Moment</p>
                          <button 
                            className="text-left w-full"
                            onClick={() => {
                              const targetIdx = (biggestEvalSwing.move_number - 1) * 2 + (userColor === 'black' ? 1 : 0);
                              goToMove(targetIdx);
                            }}
                          >
                            <p className="font-mono">
                              Move {biggestEvalSwing.move_number}: {biggestEvalSwing.move}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {formatEvalWithContext(biggestEvalSwing.eval_before / 100).text} → Lost {(biggestEvalSwing.cp_loss / 100).toFixed(1)} pawns
                            </p>
                          </button>
                        </div>
                      )}
                      
                      {/* Game Context */}
                      {coreLesson && coreLesson.behavioral_fix && (
                        <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                          <p className="text-xs text-blue-500 uppercase mb-1">The Fix</p>
                          <p className="text-sm">{coreLesson.behavioral_fix}</p>
                        </div>
                      )}
                    </TabsContent>

                    {/* STRATEGY TAB */}
                    <TabsContent value="strategy" className="p-4 space-y-4 m-0">
                      {strategicAnalysis?.has_strategy ? (
                        <>
                          {/* OPENING STRATEGY */}
                          {strategicAnalysis.opening && (
                            <div className="p-4 rounded-lg bg-gradient-to-r from-green-500/10 to-emerald-500/10 border border-green-500/20">
                              <div className="flex items-center gap-2 mb-3">
                                <BookOpen className="w-5 h-5 text-green-500" />
                                <p className="font-semibold">Opening: {strategicAnalysis.opening.name}</p>
                                <span className="text-xs px-2 py-0.5 rounded bg-green-500/20 text-green-400">
                                  {userColor}
                                </span>
                              </div>
                              
                              {/* Main Idea */}
                              {strategicAnalysis.opening.main_idea && (
                                <p className="text-sm text-green-400 font-medium mb-3">
                                  {strategicAnalysis.opening.main_idea}
                                </p>
                              )}
                              
                              {/* The Plan */}
                              {strategicAnalysis.opening.plan && (
                                <div className="p-3 rounded bg-background/50 border border-border/50 mb-3">
                                  <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">The Plan</p>
                                  <p className="text-sm font-mono">{strategicAnalysis.opening.plan}</p>
                                </div>
                              )}
                              
                              {/* Your Execution */}
                              {strategicAnalysis.opening.execution && (
                                <div className="p-3 rounded bg-background/50 border border-red-500/20 mb-3">
                                  <p className="text-xs text-red-400 uppercase tracking-wide mb-2">Your Execution</p>
                                  <p className={`text-sm font-medium mb-2 ${
                                    strategicAnalysis.opening.execution.verdict?.includes('Excellent') ? 'text-green-400' :
                                    strategicAnalysis.opening.execution.verdict?.includes('Solid') ? 'text-yellow-400' :
                                    'text-red-400'
                                  }`}>
                                    {strategicAnalysis.opening.execution.verdict}
                                  </p>
                                  {strategicAnalysis.opening.execution.details?.map((detail, i) => (
                                    <p key={i} className="text-sm text-muted-foreground">{detail}</p>
                                  ))}
                                  
                                  {/* Critical Deviation - Clickable */}
                                  {strategicAnalysis.opening.execution.critical_deviation && (
                                    <button 
                                      className="mt-3 p-2 rounded bg-red-500/10 border border-red-500/30 w-full text-left hover:bg-red-500/20 transition-colors"
                                      onClick={() => {
                                        const moveNum = strategicAnalysis.opening.execution.critical_deviation.move_number;
                                        if (moveNum) {
                                          const targetIdx = (moveNum - 1) * 2 + (userColor === 'black' ? 1 : 0);
                                          goToMove(targetIdx);
                                        }
                                      }}
                                    >
                                      <p className="text-xs text-red-400 uppercase mb-1">Critical Deviation</p>
                                      <p className="text-sm font-medium text-red-400">
                                        {strategicAnalysis.opening.execution.critical_deviation.explanation}
                                      </p>
                                    </button>
                                  )}
                                </div>
                              )}
                              
                              {/* Key Ideas */}
                              {strategicAnalysis.opening.key_ideas?.length > 0 && (
                                <div className="space-y-1.5">
                                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Key Ideas to Remember</p>
                                  {strategicAnalysis.opening.key_ideas.map((idea, i) => (
                                    <p key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                      <span className="text-green-500 mt-0.5">•</span>
                                      <span>{idea}</span>
                                    </p>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}

                          {/* PAWN STRUCTURE */}
                          {strategicAnalysis.pawn_structure?.type && (
                            <div className="p-4 rounded-lg bg-gradient-to-r from-yellow-500/10 to-amber-500/10 border border-yellow-500/20">
                              <div className="flex items-center gap-2 mb-3">
                                <Target className="w-5 h-5 text-yellow-500" />
                                <p className="font-semibold">Pawn Structure: {strategicAnalysis.pawn_structure.type}</p>
                              </div>
                              
                              {/* The Plan */}
                              {strategicAnalysis.pawn_structure.your_plan && (
                                <div className="p-3 rounded bg-background/50 border border-border/50 mb-3">
                                  <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">The Plan</p>
                                  <p className="text-sm">{strategicAnalysis.pawn_structure.your_plan}</p>
                                </div>
                              )}
                              
                              {/* Your Execution */}
                              {strategicAnalysis.pawn_structure.execution?.details?.length > 0 && (
                                <div className="p-3 rounded bg-background/50 border border-yellow-500/20 mb-3">
                                  <p className="text-xs text-yellow-400 uppercase tracking-wide mb-2">Your Execution</p>
                                  <p className={`text-sm font-medium mb-2 ${
                                    strategicAnalysis.pawn_structure.execution.verdict?.includes('Good') ? 'text-green-400' :
                                    strategicAnalysis.pawn_structure.execution.verdict?.includes('Partial') ? 'text-yellow-400' :
                                    'text-red-400'
                                  }`}>
                                    {strategicAnalysis.pawn_structure.execution.verdict}
                                  </p>
                                  {strategicAnalysis.pawn_structure.execution.details?.map((detail, i) => (
                                    <p key={i} className="text-sm text-muted-foreground">{detail}</p>
                                  ))}
                                  
                                  {/* Critical Moment - Clickable */}
                                  {strategicAnalysis.pawn_structure.execution.critical_moment && (
                                    <button 
                                      className="mt-3 p-2 rounded bg-red-500/10 border border-red-500/30 w-full text-left hover:bg-red-500/20 transition-colors"
                                      onClick={() => {
                                        const moveNum = strategicAnalysis.pawn_structure.execution.critical_moment.move_number;
                                        if (moveNum) {
                                          const targetIdx = (moveNum - 1) * 2 + (userColor === 'black' ? 1 : 0);
                                          goToMove(targetIdx);
                                        }
                                      }}
                                    >
                                      <p className="text-xs text-red-400 uppercase mb-1">Critical Moment</p>
                                      <p className="text-sm text-red-400">
                                        {strategicAnalysis.pawn_structure.execution.critical_moment.what_went_wrong}
                                      </p>
                                    </button>
                                  )}
                                </div>
                              )}
                              
                              {/* Pawn Breaks */}
                              {strategicAnalysis.pawn_structure.pawn_breaks?.length > 0 && (
                                <div className="space-y-1 mb-2">
                                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Pawn Breaks</p>
                                  {strategicAnalysis.pawn_structure.pawn_breaks.map((breakMove, i) => (
                                    <p key={i} className="text-sm text-yellow-400 font-mono">{breakMove}</p>
                                  ))}
                                </div>
                              )}
                              
                              {/* Key Squares */}
                              {strategicAnalysis.pawn_structure.key_squares?.length > 0 && (
                                <div className="space-y-1">
                                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Key Squares</p>
                                  {strategicAnalysis.pawn_structure.key_squares.map((sq, i) => (
                                    <p key={i} className="text-sm text-muted-foreground">{sq}</p>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}

                          {/* STRATEGIC THEMES */}
                          {strategicAnalysis.strategic_themes?.length > 0 && (
                            <div className="p-4 rounded-lg bg-gradient-to-r from-purple-500/10 to-violet-500/10 border border-purple-500/20">
                              <div className="flex items-center gap-2 mb-3">
                                <Brain className="w-5 h-5 text-purple-500" />
                                <p className="font-semibold">Strategic Themes in This Game</p>
                              </div>
                              
                              <div className="space-y-3">
                                {strategicAnalysis.strategic_themes.map((theme, idx) => (
                                  <div key={idx} className="p-3 rounded bg-background/50 border border-border/50">
                                    <div className="flex items-center gap-2 mb-1">
                                      {getThemeIcon(theme.icon)}
                                      <span className="font-medium text-sm">{theme.theme}</span>
                                    </div>
                                    <p className="text-sm text-muted-foreground mb-2">{theme.description}</p>
                                    
                                    {/* Verdict */}
                                    {theme.verdict && (
                                      <p className={`text-sm font-medium mb-2 ${
                                        theme.verdict.includes('✓') ? 'text-green-400' :
                                        theme.verdict.includes('⚠') ? 'text-yellow-400' :
                                        'text-red-400'
                                      }`}>
                                        {theme.verdict}
                                      </p>
                                    )}
                                    
                                    {/* Critical Moment - Clickable */}
                                    {theme.critical_moment && (
                                      <button 
                                        className="p-2 rounded bg-red-500/10 border border-red-500/20 mb-2 w-full text-left hover:bg-red-500/20 transition-colors"
                                        onClick={() => {
                                          const moveNum = theme.critical_moment.move_number;
                                          if (moveNum) {
                                            const targetIdx = (moveNum - 1) * 2 + (userColor === 'black' ? 1 : 0);
                                            goToMove(targetIdx);
                                          }
                                        }}
                                      >
                                        <p className="text-xs text-red-400 uppercase mb-1">Move {theme.critical_moment.move_number}</p>
                                        <p className="text-sm text-red-400">{theme.critical_moment.description}</p>
                                        {theme.critical_moment.impact && (
                                          <p className="text-xs text-muted-foreground mt-1">{theme.critical_moment.impact}</p>
                                        )}
                                      </button>
                                    )}
                                    
                                    {theme.principle && <p className="text-sm">{theme.principle}</p>}
                                    {theme.remember && (
                                      <p className="text-xs text-purple-400 mt-2 italic">Remember: {theme.remember}</p>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* FUTURE ADVICE */}
                          {strategicAnalysis.future_advice?.length > 0 && (
                            <div className="p-4 rounded-lg bg-gradient-to-r from-blue-500/10 to-cyan-500/10 border border-blue-500/20">
                              <div className="flex items-center gap-2 mb-3">
                                <Lightbulb className="w-5 h-5 text-blue-500" />
                                <p className="font-semibold">For Future Games Like This</p>
                              </div>
                              
                              <div className="space-y-3">
                                {strategicAnalysis.future_advice.map((advice, idx) => (
                                  <div key={idx} className="p-3 rounded bg-background/50 border border-border/50">
                                    <div className="flex items-center gap-2 mb-1">
                                      {getAdviceIcon(advice.icon)}
                                      <span className="text-xs text-muted-foreground uppercase tracking-wide">{advice.category}</span>
                                    </div>
                                    {advice.advice && <p className="text-sm font-medium">{advice.advice}</p>}
                                    {advice.action && <p className="text-sm text-muted-foreground mt-1">{advice.action}</p>}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="text-center py-8 text-muted-foreground">
                          <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-30" />
                          <p>Strategic analysis not available</p>
                          <p className="text-sm mt-2">Re-analyze this game to see opening, pawn structure, and strategic insights.</p>
                        </div>
                      )}
                    </TabsContent>

                    {/* MISTAKES TAB - Most Important */}
                    <TabsContent value="mistakes" className="p-4 space-y-4 m-0">
                      {groupedMistakes.length > 0 ? (
                        groupedMistakes.map((group) => (
                          <MistakeGroup 
                            key={group.type}
                            group={group}
                            userColor={userColor}
                            onMoveClick={(moveNum) => {
                              const targetIdx = (moveNum - 1) * 2 + (userColor === 'black' ? 1 : 0);
                              goToMove(targetIdx);
                            }}
                          />
                        ))
                      ) : (
                        <div className="text-center py-8">
                          <CheckCircle2 className="w-12 h-12 mx-auto mb-4 text-green-500" />
                          <p className="font-medium text-green-500">No significant mistakes!</p>
                          <p className="text-sm text-muted-foreground">Great game - keep it up!</p>
                        </div>
                      )}
                    </TabsContent>
                  </ScrollArea>
                </Tabs>
              ) : (
                <div className="flex-1 flex items-center justify-center">
                  <div className="text-center p-8">
                    <Brain className="w-16 h-16 mx-auto mb-4 text-muted-foreground/30" />
                    <p className="text-muted-foreground">Analyze the game to see insights</p>
                    <Button onClick={handleAnalyze} disabled={analyzing} className="mt-4">
                      {analyzing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                      Analyze Game
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* Collapse toggle */}
          <button 
            className="absolute right-0 top-1/2 -translate-y-1/2 z-30 bg-muted hover:bg-muted/80 p-1 rounded-l"
            onClick={() => setRightPanelCollapsed(!rightPanelCollapsed)}
          >
            {rightPanelCollapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>

        {/* PRACTICE MODE OVERLAY */}
        {practiceMode && (
          <PracticeModeOverlay 
            positions={practicePositions}
            currentIndex={practiceIndex}
            onNext={() => {
              if (practiceIndex < practicePositions.length - 1) {
                setPracticeIndex(i => i + 1);
              } else {
                setPracticeMode(false);
                toast.success("Practice complete!");
              }
            }}
            onClose={() => setPracticeMode(false)}
            userColor={userColor}
          />
        )}
      </div>
    </Layout>
  );
};

// Helper components
const StrategySection = ({ icon, title, color, children, compact }) => (
  <div className={`p-3 rounded-lg bg-${color}-500/10 border border-${color}-500/20 ${compact ? 'text-sm' : ''}`}>
    <div className="flex items-center gap-2 mb-2">
      {icon}
      <p className={`font-medium ${compact ? 'text-sm' : ''}`}>{title}</p>
    </div>
    {children}
  </div>
);

const ExecutionBadge = ({ verdict }) => {
  const isGood = verdict?.includes('Excellent') || verdict?.includes('Good') || verdict?.includes('Solid');
  const isOk = verdict?.includes('Partial') || verdict?.includes('acceptable');
  
  return (
    <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
      isGood ? 'bg-green-500/20 text-green-400' :
      isOk ? 'bg-yellow-500/20 text-yellow-400' :
      'bg-red-500/20 text-red-400'
    }`}>
      {isGood ? <CheckCircle2 className="w-3 h-3" /> :
       isOk ? <AlertCircle className="w-3 h-3" /> :
       <AlertTriangle className="w-3 h-3" />}
      {verdict?.split(' - ')[0] || verdict}
    </div>
  );
};

const CriticalMoveCard = ({ label, text, onClick }) => (
  <button 
    className="mt-2 p-2 rounded bg-red-500/10 border border-red-500/20 text-left w-full hover:bg-red-500/20 transition-colors"
    onClick={onClick}
  >
    <p className="text-xs text-red-400 uppercase mb-0.5">{label}</p>
    <p className="text-sm text-red-400">{text}</p>
  </button>
);

const MistakeGroup = ({ group, userColor, onMoveClick }) => (
  <div className="space-y-2">
    <div className="flex items-center justify-between">
      <h3 className="font-medium flex items-center gap-2">
        {getMistakeIcon(group.type)}
        {group.label}
      </h3>
      <Badge variant="outline" className="text-xs">{group.count}</Badge>
    </div>
    <div className="space-y-1">
      {group.items.map((mistake, idx) => (
        <MistakeItem 
          key={idx} 
          mistake={mistake} 
          onClick={() => onMoveClick(mistake.move_number)}
        />
      ))}
    </div>
  </div>
);

const MistakeItem = ({ mistake, onClick }) => {
  const cpLossInfo = formatCpLoss(mistake.cp_loss);
  
  return (
    <button
      className={`w-full text-left p-2 rounded-lg border-l-4 hover:ring-1 hover:ring-primary/30 transition-all ${
        mistake.isBlunder ? 'border-l-red-500 bg-red-500/5' :
        mistake.isMistake ? 'border-l-orange-500 bg-orange-500/5' :
        'border-l-yellow-500 bg-yellow-500/5'
      }`}
      onClick={onClick}
      data-testid={`mistake-${mistake.move_number}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm">Move {mistake.move_number}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${cpLossInfo.className} bg-current/10`}>
            {cpLossInfo.text}
          </span>
        </div>
        <span className="text-xs text-muted-foreground">{mistake.phase}</span>
      </div>
      
      <div className="flex items-center gap-2 mt-1">
        <span className="text-sm">
          <span className="text-muted-foreground">Played:</span>{' '}
          <span className="font-mono text-red-400">{mistake.move}</span>
        </span>
        <span className="text-muted-foreground">→</span>
        <span className="text-sm">
          <span className="text-muted-foreground">Better:</span>{' '}
          <span className="font-mono text-green-400">{mistake.best_move}</span>
        </span>
      </div>
      
      {mistake.context && (
        <p className="text-xs text-muted-foreground mt-1">{mistake.context}</p>
      )}
      
      <p className="text-xs text-primary mt-1 opacity-70">
        What should you have checked here?
      </p>
    </button>
  );
};

const PracticeModeOverlay = ({ positions, currentIndex, onNext, onClose, userColor }) => {
  const [selectedMove, setSelectedMove] = useState(null);
  const [showResult, setShowResult] = useState(false);
  const pos = positions[currentIndex];
  
  const handleCheck = () => {
    setShowResult(true);
  };
  
  const handleNext = () => {
    setShowResult(false);
    setSelectedMove(null);
    onNext();
  };
  
  return (
    <div className="fixed inset-0 z-50 bg-background/95 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Target className="w-5 h-5 text-primary" />
            Practice Critical Positions
          </h2>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {currentIndex + 1} / {positions.length}
            </span>
            <Button variant="ghost" size="sm" onClick={onClose}>Exit</Button>
          </div>
        </div>
        
        <div className="flex gap-6">
          <div className="w-[350px]">
            <Chessboard
              position={pos?.fen || "start"}
              boardOrientation={userColor}
              arePiecesDraggable={false}
              customBoardStyle={{
                borderRadius: '8px',
                boxShadow: '0 4px 20px rgba(0,0,0,0.3)'
              }}
            />
          </div>
          
          <div className="flex-1 flex flex-col justify-center">
            <p className="text-lg mb-4">Move {pos?.move_number}: What's the best move?</p>
            
            {!showResult ? (
              <>
                <div className="space-y-2 mb-4">
                  <Button
                    variant={selectedMove === pos?.best_move ? "default" : "outline"}
                    className="w-full justify-start font-mono"
                    onClick={() => setSelectedMove(pos?.best_move)}
                  >
                    {pos?.best_move}
                  </Button>
                  <Button
                    variant={selectedMove === pos?.played_move ? "default" : "outline"}
                    className="w-full justify-start font-mono"
                    onClick={() => setSelectedMove(pos?.played_move)}
                  >
                    {pos?.played_move} <span className="ml-auto text-xs text-muted-foreground">(what you played)</span>
                  </Button>
                </div>
                <Button onClick={handleCheck} disabled={!selectedMove}>Check</Button>
              </>
            ) : (
              <div className={`p-4 rounded-lg ${selectedMove === pos?.best_move ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
                {selectedMove === pos?.best_move ? (
                  <div className="flex items-center gap-2 text-green-500 mb-2">
                    <CheckCircle2 className="w-5 h-5" />
                    <span className="font-bold">Correct!</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-red-500 mb-2">
                    <AlertTriangle className="w-5 h-5" />
                    <span className="font-bold">Not quite</span>
                  </div>
                )}
                <p className="text-sm mb-3">
                  Best move: <span className="font-mono text-green-400">{pos?.best_move}</span>
                </p>
                <Button onClick={handleNext}>
                  {currentIndex < positions.length - 1 ? 'Next Position' : 'Finish'}
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Utility functions
const getContextLabel = (move) => {
  const evalBefore = move.eval_before || 0;
  if (evalBefore > 2) return "After gaining advantage";
  if (evalBefore > 0.5) return "In a comfortable position";
  if (evalBefore < -2) return "Under pressure";
  return "";
};

const formatGroupLabel = (type) => {
  const labels = {
    blunders: "Major Blunders",
    hanging_pieces: "Hanging Pieces",
    tactical_misses: "Missed Tactics",
    positional_errors: "Positional Errors",
    other: "Other Mistakes"
  };
  return labels[type] || type;
};

const getMistakeIcon = (type) => {
  const icons = {
    blunders: <AlertTriangle className="w-4 h-4 text-red-500" />,
    hanging_pieces: <AlertCircle className="w-4 h-4 text-orange-500" />,
    tactical_misses: <Zap className="w-4 h-4 text-yellow-500" />,
    positional_errors: <Target className="w-4 h-4 text-blue-500" />,
    other: <AlertCircle className="w-4 h-4 text-muted-foreground" />
  };
  return icons[type] || icons.other;
};

const getThemeIcon = (iconName) => {
  const icons = {
    'trending-up': <TrendingUp className="w-4 h-4 text-green-500" />,
    'trending-down': <TrendingDown className="w-4 h-4 text-red-500" />,
    'shield': <Target className="w-4 h-4 text-blue-500" />,
    'target': <Target className="w-4 h-4 text-amber-500" />,
    'zap': <Zap className="w-4 h-4 text-yellow-500" />,
    'lightbulb': <Lightbulb className="w-4 h-4 text-amber-500" />,
    'book-open': <BookOpen className="w-4 h-4 text-green-500" />
  };
  return icons[iconName] || <Brain className="w-4 h-4 text-purple-500" />;
};

export default Lab;
