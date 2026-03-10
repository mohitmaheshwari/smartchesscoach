/**
 * LabV2.jsx - Game Review Like a Coach
 * 
 * The Lab page redesigned to feel like a coaching session.
 * Top-to-bottom flow: Story → Learning → Action
 * 
 * NO engine dumps. NO cp values. Just coach talk.
 * 
 * Structure:
 * 1. Game Summary - The story
 * 2. Critical Moments - Interactive learning  
 * 3. Strategic Themes - Big picture
 * 4. Missed Tactics - Pattern recognition
 * 5. Habits to Improve - Homework
 */

import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Chess } from "chess.js";
import { motion } from "framer-motion";
import LichessBoard from "@/components/LichessBoard";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Layout from "@/components/Layout";
import { toast } from "sonner";
import {
  ArrowLeft,
  Play,
  Pause,
  ChevronLeft,
  ChevronRight,
  SkipBack,
  SkipForward,
  RotateCcw,
  Loader2,
  Brain,
  Target,
  Zap,
  BookOpen,
  MessageSquare,
  ChevronDown,
  History
} from "lucide-react";

// Import new coach-style components
import GameSummary from "@/components/lab/GameSummary";
import CriticalMoments from "@/components/lab/CriticalMoments";
import StrategicThemes from "@/components/lab/StrategicThemes";
import MissedTactics from "@/components/lab/MissedTactics";
import HabitsToImprove from "@/components/lab/HabitsToImprove";
import DeepMemoryPanel from "@/components/DeepMemoryPanel";

// Feedback modal (reused from Lab.jsx)
import FeedbackModal from "@/components/FeedbackModal";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

// Helper to convert FEN to position object
const fenToPositionObject = (fen) => {
  const chess = new Chess(fen);
  const board = chess.board();
  const position = {};
  
  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      const piece = board[row][col];
      if (piece) {
        const file = String.fromCharCode(97 + col);
        const rank = 8 - row;
        const square = `${file}${rank}`;
        const pieceCode = piece.color === 'w' 
          ? piece.type.toUpperCase() 
          : piece.type.toLowerCase();
        position[square] = pieceCode;
      }
    }
  }
  return position;
};

const LabV2 = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  
  // Data states
  const [loading, setLoading] = useState(true);
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [labData, setLabData] = useState(null);
  const [deepStrategy, setDeepStrategy] = useState(null);
  const [loadingDeepStrategy, setLoadingDeepStrategy] = useState(false);
  const [focusModule, setFocusModule] = useState(null);
  
  // Board states
  const [moves, setMoves] = useState([]);
  const [allFens, setAllFens] = useState([START_FEN]);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [positionObject, setPositionObject] = useState(() => fenToPositionObject(START_FEN));
  const [boardOrientation, setBoardOrientation] = useState("white");
  const [lastMoveSquares, setLastMoveSquares] = useState({});
  const [isPlaying, setIsPlaying] = useState(false);
  const [boardArrows, setBoardArrows] = useState([]); // NEW: Arrows for the board
  
  // UI states
  const [activeTab, setActiveTab] = useState("summary");
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackContext, setFeedbackContext] = useState(null);
  
  // Derived data
  const userColor = game?.user_color || "white";
  const result = game?.result || "1/2-1/2";
  const accuracy = analysis?.stockfish_analysis?.accuracy || labData?.accuracy;
  const currentFen = allFens[currentMoveIndex + 1] || START_FEN;
  
  // Fetch all data
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch game
        const gameRes = await fetch(`${API}/games/${gameId}`, { credentials: "include" });
        if (!gameRes.ok) throw new Error("Game not found");
        const gameData = await gameRes.json();
        setGame(gameData);
        setBoardOrientation(gameData.user_color === "black" ? "black" : "white");
        
        // Fetch analysis
        const analysisRes = await fetch(`${API}/analysis/${gameId}`, { credentials: "include" });
        if (analysisRes.ok) {
          setAnalysis(await analysisRes.json());
        }
        
        // Fetch lab data
        const labRes = await fetch(`${API}/lab/${gameId}`, { credentials: "include" });
        if (labRes.ok) {
          setLabData(await labRes.json());
        }
        
        // Fetch focus module
        try {
          const focusRes = await fetch(`${API}/cognitive/training-priority`, { credentials: "include" });
          if (focusRes.ok) {
            const focusData = await focusRes.json();
            if (focusData.primary_focus) {
              setFocusModule(focusData.primary_focus);
            }
          }
        } catch (e) {
          // Focus module not critical
        }
        
      } catch (error) {
        toast.error("Failed to load game");
        navigate("/lab");
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [gameId, navigate]);
  
  // Fetch deep strategy (for critical moments detail)
  useEffect(() => {
    const fetchDeepStrategy = async () => {
      if (!gameId || deepStrategy || loadingDeepStrategy) return;
      
      setLoadingDeepStrategy(true);
      try {
        const res = await fetch(`${API}/lab/${gameId}/deep-strategy`, { credentials: "include" });
        if (res.ok) {
          setDeepStrategy(await res.json());
        }
      } catch (e) {
        console.log("Deep strategy not available");
      } finally {
        setLoadingDeepStrategy(false);
      }
    };
    
    fetchDeepStrategy();
  }, [gameId, deepStrategy, loadingDeepStrategy]);
  
  // Build moves and FENs from game
  useEffect(() => {
    if (!game?.pgn) return;
    
    try {
      const chess = new Chess();
      chess.loadPgn(game.pgn);
      const history = chess.history({ verbose: true });
      
      // Build FENs
      const fens = [START_FEN];
      const tempChess = new Chess();
      
      history.forEach(move => {
        tempChess.move(move.san);
        fens.push(tempChess.fen());
      });
      
      setMoves(history);
      setAllFens(fens);
      setPositionObject(fenToPositionObject(START_FEN));
    } catch (e) {
      console.error("Failed to parse PGN:", e);
    }
  }, [game?.pgn]);
  
  // Update position when move index changes
  useEffect(() => {
    const fen = allFens[currentMoveIndex + 1] || START_FEN;
    setPositionObject(fenToPositionObject(fen));
    
    // Update last move squares
    if (currentMoveIndex >= 0 && moves[currentMoveIndex]) {
      const move = moves[currentMoveIndex];
      setLastMoveSquares({
        [move.from]: { background: "rgba(255, 255, 0, 0.4)" },
        [move.to]: { background: "rgba(255, 255, 0, 0.4)" }
      });
    } else {
      setLastMoveSquares({});
    }
  }, [currentMoveIndex, allFens, moves]);
  
  // Navigation functions
  const goToMove = (index, clearArrows = true) => {
    setCurrentMoveIndex(Math.max(-1, Math.min(index, moves.length - 1)));
    setIsPlaying(false);
    if (clearArrows) {
      setBoardArrows([]); // Clear arrows on manual navigation
    }
  };
  
  const goToStart = () => goToMove(-1);
  const goToEnd = () => goToMove(moves.length - 1);
  const goToPrev = () => goToMove(currentMoveIndex - 1);
  const goToNext = () => goToMove(currentMoveIndex + 1);
  
  // Navigate to a specific move number (from critical moments) with optional arrows
  const navigateToMoveNumber = (moveNum, yourMove = null, bestMove = null) => {
    // Move number to index: move 24 by white = index 46-47 area
    // For white moves: (moveNum - 1) * 2
    // For black moves: (moveNum - 1) * 2 + 1
    const baseIndex = (moveNum - 1) * 2;
    const targetIndex = userColor === "black" ? baseIndex + 1 : baseIndex;
    goToMove(Math.min(targetIndex, moves.length - 1), false); // Don't clear arrows
    
    // Set arrows if moves are provided
    const newArrows = [];
    if (yourMove && yourMove.length >= 4) {
      // Red arrow for user's move
      const from = yourMove.substring(0, 2);
      const to = yourMove.substring(2, 4);
      newArrows.push([from, to, "red"]);
    }
    if (bestMove && bestMove.length >= 4) {
      // Green arrow for best move
      const from = bestMove.substring(0, 2);
      const to = bestMove.substring(2, 4);
      newArrows.push([from, to, "green"]);
    }
    setBoardArrows(newArrows);
  };
  
  // Auto-play
  useEffect(() => {
    if (!isPlaying) return;
    
    const interval = setInterval(() => {
      setCurrentMoveIndex(prev => {
        if (prev >= moves.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 1000);
    
    return () => clearInterval(interval);
  }, [isPlaying, moves.length]);
  
  // Handle feedback
  const handleFeedback = (context) => {
    setFeedbackContext(context);
    setFeedbackOpen(true);
  };
  
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }
  
  return (
    <Layout user={user} hideNav>
      <div className="h-screen flex flex-col overflow-hidden bg-background">
        {/* Top Bar - Clean, simple */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/lab")}
              className="gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </Button>
            
            <div className="flex items-center gap-3">
              <h1 className="font-semibold">Game Review</h1>
              <span className="text-muted-foreground">
                vs {game?.opponent_name || "Opponent"}
              </span>
              <Badge 
                variant={result.includes("1-0") && userColor === "white" || result.includes("0-1") && userColor === "black" 
                  ? "default" 
                  : result === "1/2-1/2" 
                    ? "secondary" 
                    : "destructive"
                }
              >
                {result.includes("1-0") && userColor === "white" || result.includes("0-1") && userColor === "black"
                  ? "Won"
                  : result === "1/2-1/2"
                    ? "Draw"
                    : "Lost"
                }
              </Badge>
              <span className="text-sm text-muted-foreground">
                {accuracy ? `${accuracy.toFixed(0)}% accuracy` : ""}
              </span>
            </div>
          </div>
        </div>
        
        {/* Main Content - Board left, Analysis right */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Board and controls */}
          <div className="w-[55%] flex flex-col border-r border-border">
            {/* Board */}
            <div className="flex-1 flex items-center justify-center p-4">
              <div className="w-full max-w-[560px] aspect-square">
                <LichessBoard
                  fen={currentFen}
                  orientation={boardOrientation}
                  viewOnly={true}
                  lastMove={currentMoveIndex >= 0 && moves[currentMoveIndex] ? [moves[currentMoveIndex].from, moves[currentMoveIndex].to] : null}
                  arrows={boardArrows}
                />
              </div>
            </div>
            
            {/* Move controls */}
            <div className="p-4 border-t border-border flex items-center justify-center gap-2">
              <Button variant="ghost" size="sm" onClick={goToStart}>
                <SkipBack className="w-4 h-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={goToPrev}>
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <Button 
                variant={isPlaying ? "secondary" : "default"} 
                size="sm"
                onClick={() => setIsPlaying(!isPlaying)}
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </Button>
              <Button variant="ghost" size="sm" onClick={goToNext}>
                <ChevronRight className="w-4 h-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={goToEnd}>
                <SkipForward className="w-4 h-4" />
              </Button>
              <Button 
                variant="ghost" 
                size="sm"
                onClick={() => setBoardOrientation(o => o === "white" ? "black" : "white")}
              >
                <RotateCcw className="w-4 h-4" />
              </Button>
              
              <span className="ml-4 text-sm text-muted-foreground">
                Move {currentMoveIndex + 1} / {moves.length}
              </span>
            </div>
            
            {/* Move list (compact) */}
            <div className="h-32 overflow-y-auto p-3 border-t border-border bg-muted/20">
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm font-mono">
                {moves.map((move, idx) => {
                  const isWhite = idx % 2 === 0;
                  const moveNum = Math.floor(idx / 2) + 1;
                  
                  return (
                    <span key={idx} className="inline-flex items-center">
                      {isWhite && <span className="text-muted-foreground mr-1">{moveNum}.</span>}
                      <button
                        onClick={() => goToMove(idx)}
                        className={`px-1 rounded hover:bg-primary/20 ${
                          idx === currentMoveIndex ? "bg-primary/30 text-primary" : ""
                        }`}
                      >
                        {move.san}
                      </button>
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
          
          {/* Right: Coach Analysis */}
          <div className="w-[45%] flex flex-col overflow-hidden">
            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
              <TabsList className="grid w-full grid-cols-5 rounded-none border-b shrink-0">
                <TabsTrigger value="summary" className="gap-1.5 text-xs">
                  <BookOpen className="w-3.5 h-3.5" />
                  Summary
                </TabsTrigger>
                <TabsTrigger value="moments" className="gap-1.5 text-xs">
                  <Target className="w-3.5 h-3.5" />
                  Moments
                </TabsTrigger>
                <TabsTrigger value="ideas" className="gap-1.5 text-xs">
                  <Brain className="w-3.5 h-3.5" />
                  Ideas
                </TabsTrigger>
                <TabsTrigger value="habits" className="gap-1.5 text-xs">
                  <Zap className="w-3.5 h-3.5" />
                  Habits
                </TabsTrigger>
                <TabsTrigger value="memory" className="gap-1.5 text-xs">
                  <History className="w-3.5 h-3.5" />
                  Memory
                </TabsTrigger>
              </TabsList>
              
              {/* Tab content - scrollable */}
              <div className="flex-1 overflow-y-auto">
                {/* Summary Tab */}
                <TabsContent value="summary" className="p-4 m-0">
                  {loadingDeepStrategy ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-6 h-6 animate-spin text-primary" />
                    </div>
                  ) : (
                    <GameSummary
                      game={game}
                      labData={labData}
                      userColor={userColor}
                      result={result}
                      accuracy={accuracy}
                      deepStrategy={deepStrategy}
                      patternContext={labData?.pattern_context}
                    />
                  )}
                </TabsContent>
                
                {/* Critical Moments Tab */}
                <TabsContent value="moments" className="p-4 m-0">
                  {loadingDeepStrategy ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-6 h-6 animate-spin text-primary" />
                    </div>
                  ) : (
                    <CriticalMoments
                      moments={deepStrategy?.critical_moments || []}
                      userColor={userColor}
                      onNavigateToMove={navigateToMoveNumber}
                      onFeedback={handleFeedback}
                      gameId={gameId}
                    />
                  )}
                </TabsContent>
                
                {/* Ideas Tab (Strategic Themes + Missed Tactics) */}
                <TabsContent value="ideas" className="p-4 m-0 space-y-6">
                  {loadingDeepStrategy ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-6 h-6 animate-spin text-primary" />
                    </div>
                  ) : (
                    <>
                      <StrategicThemes
                        deepStrategy={deepStrategy}
                        labData={labData}
                        game={game}
                      />
                      
                      <MissedTactics
                        deepStrategy={deepStrategy}
                        labData={labData}
                        onNavigateToMove={navigateToMoveNumber}
                      />
                    </>
                  )}
                </TabsContent>
                
                {/* Habits Tab */}
                <TabsContent value="habits" className="p-4 m-0">
                  <HabitsToImprove
                    patternContext={labData?.pattern_context}
                    focusModule={focusModule}
                    labData={labData}
                    deepStrategy={deepStrategy}
                    onStartTraining={() => navigate("/training/prescribed")}
                  />
                </TabsContent>
                
                {/* Memory Tab - Deep Coach Memory Profile */}
                <TabsContent value="memory" className="p-4 m-0">
                  <div className="space-y-4">
                    <div className="text-sm text-muted-foreground mb-4">
                      Your coach's memory of your playing patterns, style, and areas for improvement.
                    </div>
                    <DeepMemoryPanel compact={false} />
                  </div>
                </TabsContent>
              </div>
            </Tabs>
          </div>
        </div>
        
        {/* Feedback Modal */}
        <FeedbackModal
          isOpen={feedbackOpen}
          onClose={() => setFeedbackOpen(false)}
          context={feedbackContext}
        />
      </div>
    </Layout>
  );
};

export default LabV2;
