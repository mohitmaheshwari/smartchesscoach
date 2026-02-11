import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Loader2,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle2,
  Target,
  Swords,
  Brain,
  Crown,
  Shield,
  Trophy,
  Eye,
  Clock,
  ExternalLink,
  Play,
  RotateCcw,
  Send,
  MessageCircle,
  Sparkles,
  ArrowRight
} from "lucide-react";

// Badge icon mapping
const BADGE_ICONS = {
  opening: Target,
  tactical: Swords,
  positional: Brain,
  endgame: Crown,
  defense: Shield,
  converting: Trophy,
  focus: Eye,
  time: Clock
};

// Star rating component
const StarRating = ({ score, size = "lg" }) => {
  const fullStars = Math.floor(score);
  const hasHalf = score - fullStars >= 0.3 && score - fullStars < 0.8;
  const sizeClass = size === "lg" ? "text-xl" : "text-base";
  
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <span 
          key={star} 
          className={`${sizeClass} ${
            star <= fullStars 
              ? "text-yellow-500" 
              : star === fullStars + 1 && hasHalf 
                ? "text-yellow-500/50" 
                : "text-gray-300 dark:text-gray-600"
          }`}
        >
          ★
        </span>
      ))}
      <span className="ml-2 text-lg font-bold">{score.toFixed(1)}</span>
    </div>
  );
};

// Interactive Chess Board with playable lines
const InteractiveBoard = ({ 
  fen,  // Position AFTER the move (what happened)
  fenBefore,  // Position BEFORE the move (where best move should be played from)
  bestMove, 
  playedMove, 
  pvLine = [], 
  userColor = "white",
  onAskAI 
}) => {
  const chessRef = useRef(new Chess());
  const [currentFen, setCurrentFen] = useState("start");
  const [lineIndex, setLineIndex] = useState(-1);
  const [isShowingLine, setIsShowingLine] = useState(false);
  const [highlightSquares, setHighlightSquares] = useState({});
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState("after"); // "after" = what you played, "before" = where you should play

  // Reset when FEN changes - show position AFTER the move by default
  useEffect(() => {
    const chess = chessRef.current;
    setError(null);
    setViewMode("after");
    setIsShowingLine(false);
    setLineIndex(-1);
    
    const displayFen = fen && fen.length > 10 ? fen : (fenBefore && fenBefore.length > 10 ? fenBefore : "start");
    
    if (displayFen && displayFen !== "start") {
      try {
        chess.load(displayFen);
        setCurrentFen(displayFen);
        setHighlightSquares({});
      } catch (e) {
        console.error("Invalid FEN:", displayFen, e);
        setError("Invalid position");
        setCurrentFen("start");
      }
    } else {
      setCurrentFen("start");
    }
  }, [fen, fenBefore]);

  // Toggle between "what you played" and "what you should have played"
  const toggleView = useCallback(() => {
    const chess = chessRef.current;
    
    if (viewMode === "after" && fenBefore) {
      // Switch to "before" view - show where best move should be played
      try {
        chess.load(fenBefore);
        setCurrentFen(fenBefore);
        setViewMode("before");
        setHighlightSquares({});
        setIsShowingLine(false);
        setLineIndex(-1);
      } catch (e) {
        console.error("Error loading fenBefore:", e);
      }
    } else if (viewMode === "before" && fen) {
      // Switch back to "after" view - show what happened
      try {
        chess.load(fen);
        setCurrentFen(fen);
        setViewMode("after");
        setHighlightSquares({});
        setIsShowingLine(false);
        setLineIndex(-1);
      } catch (e) {
        console.error("Error loading fen:", e);
      }
    }
  }, [viewMode, fen, fenBefore]);

  // Play through the best line (from the position BEFORE the mistake)
  const playNextMove = useCallback(() => {
    const chess = chessRef.current;
    if (!pvLine || pvLine.length === 0 || !fenBefore) return;
    
    const nextIndex = lineIndex + 1;
    if (nextIndex >= pvLine.length) return;

    try {
      // Reset to starting position (before the mistake)
      chess.load(fenBefore);
    
      // Play all moves up to nextIndex
      for (let i = 0; i <= nextIndex; i++) {
        try {
          chess.move(pvLine[i]);
        } catch (e) {
          console.error("Invalid move in PV:", pvLine[i]);
          return;
        }
      }
      
      setCurrentFen(chess.fen());
      setLineIndex(nextIndex);
      setIsShowingLine(true);
      setViewMode("line");
      
      // Highlight the last move
      const history = chess.history({ verbose: true });
      if (history.length > 0) {
        const lastMove = history[history.length - 1];
        setHighlightSquares({
          [lastMove.from]: { backgroundColor: "rgba(34, 197, 94, 0.4)" },
          [lastMove.to]: { backgroundColor: "rgba(34, 197, 94, 0.4)" }
        });
      }
    } catch (e) {
      console.error("Error playing line:", e);
    }
  }, [fenBefore, pvLine, lineIndex]);

  // Go back one move
  const playPrevMove = useCallback(() => {
    const chess = chessRef.current;
    if (lineIndex < 0 || !fenBefore) return;
    
    try {
      const prevIndex = lineIndex - 1;
      chess.load(fenBefore);
      
      if (prevIndex >= 0) {
        for (let i = 0; i <= prevIndex; i++) {
          try {
            chess.move(pvLine[i]);
          } catch (e) {
            return;
          }
        }
        
        const history = chess.history({ verbose: true });
        if (history.length > 0) {
          const lastMove = history[history.length - 1];
          setHighlightSquares({
            [lastMove.from]: { backgroundColor: "rgba(34, 197, 94, 0.4)" },
            [lastMove.to]: { backgroundColor: "rgba(34, 197, 94, 0.4)" }
          });
        }
        setViewMode("line");
      } else {
        setHighlightSquares({});
        setViewMode("before");
      }
      
      setCurrentFen(chess.fen());
      setLineIndex(prevIndex);
      setIsShowingLine(prevIndex >= 0);
    } catch (e) {
      console.error("Error going back:", e);
    }
  }, [fenBefore, pvLine, lineIndex]);

  // Reset to "after" position (what happened)
  const resetPosition = useCallback(() => {
    const chess = chessRef.current;
    const displayFen = fen || fenBefore;
    if (!displayFen) return;
    
    try {
      chess.load(displayFen);
      setCurrentFen(displayFen);
      setLineIndex(-1);
      setIsShowingLine(false);
      setHighlightSquares({});
      setViewMode("after");
    } catch (e) {
      console.error("Error resetting:", e);
    }
  }, [fen, fenBefore]);

  // Show best move from the "before" position
  const showBestMove = useCallback(() => {
    const chess = chessRef.current;
    if (!bestMove || !fenBefore) return;
    
    try {
      chess.load(fenBefore);
      const move = chess.move(bestMove);
      if (move) {
        setHighlightSquares({
          [move.from]: { backgroundColor: "rgba(34, 197, 94, 0.5)" },
          [move.to]: { backgroundColor: "rgba(34, 197, 94, 0.5)" }
        });
        setCurrentFen(chess.fen());
        setLineIndex(0);
        setIsShowingLine(true);
        setViewMode("line");
      }
    } catch (e) {
      console.error("Invalid best move:", bestMove);
    }
  }, [fenBefore, bestMove]);

  const hasPvLine = pvLine && pvLine.length > 0;

  return (
    <div className="flex flex-col items-center">
      {/* Error State */}
      {error && (
        <div className="text-red-500 text-sm mb-2">{error}</div>
      )}
      
      {/* Chess Board */}
      <div className="w-full max-w-[320px] aspect-square rounded-lg overflow-hidden border-2 border-border shadow-lg">
        <Chessboard 
          position={currentFen}
          boardWidth={320}
          arePiecesDraggable={false}
          boardOrientation={userColor === "black" ? "black" : "white"}
          customSquareStyles={highlightSquares}
          customBoardStyle={{
            borderRadius: "4px"
          }}
        />
      </div>
      
      {/* Line indicator */}
      {isShowingLine && hasPvLine && (
        <div className="mt-2 text-center">
          <p className="text-xs text-muted-foreground">
            Showing: <span className="font-mono text-green-500">
              {pvLine.slice(0, lineIndex + 1).join(" → ")}
            </span>
          </p>
        </div>
      )}
      
      {/* Controls */}
      <div className="flex items-center gap-2 mt-3">
        <Button
          variant="outline"
          size="sm"
          onClick={resetPosition}
          className="h-8 px-2"
          title="Reset to position"
        >
          <RotateCcw className="w-4 h-4" />
        </Button>
        
        {hasPvLine && (
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={playPrevMove}
              disabled={lineIndex < 0}
              className="h-8 px-2"
              title="Previous move"
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            
            <Button
              variant="default"
              size="sm"
              onClick={playNextMove}
              disabled={lineIndex >= pvLine.length - 1}
              className="h-8 px-3 gap-1"
              title="Play next move in line"
            >
              <Play className="w-3 h-3" />
              Next
            </Button>
            
            <Button
              variant="outline"
              size="sm"
              onClick={playPrevMove}
              disabled={lineIndex >= pvLine.length - 1}
              className="h-8 px-2"
              title="Next move"
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </>
        )}
        
        {bestMove && !isShowingLine && (
          <Button
            variant="secondary"
            size="sm"
            onClick={showBestMove}
            className="h-8 px-3 gap-1"
          >
            <Sparkles className="w-3 h-3" />
            Show Best
          </Button>
        )}
      </div>
      
      {/* Line notation */}
      {hasPvLine && (
        <div className="mt-3 p-2 rounded bg-muted/50 text-center">
          <p className="text-xs text-muted-foreground mb-1">Best continuation:</p>
          <p className="text-sm font-mono">
            {pvLine.map((move, i) => (
              <span 
                key={i} 
                className={`${i <= lineIndex ? 'text-green-500 font-bold' : 'text-muted-foreground'}`}
              >
                {move}{i < pvLine.length - 1 ? ' ' : ''}
              </span>
            ))}
          </p>
        </div>
      )}
      
      {/* Ask AI Button */}
      <Button
        variant="outline"
        size="sm"
        onClick={onAskAI}
        className="mt-3 w-full gap-2"
      >
        <MessageCircle className="w-4 h-4" />
        Ask AI About This Position
      </Button>
    </div>
  );
};

// Ask AI Panel Component
const AskAIPanel = ({ fen, bestMove, playedMove, badgeKey, gameId, onClose }) => {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversation, setConversation] = useState([]);
  const scrollRef = useRef(null);

  const suggestedQuestions = [
    "Why is this move bad?",
    "What pattern should I recognize here?",
    "How do I avoid this mistake in future games?",
    "Explain the best move step by step"
  ];

  const handleAsk = async (q) => {
    const questionText = q || question;
    if (!questionText.trim() || loading) return;

    setLoading(true);
    setQuestion("");

    // Add user question to conversation
    setConversation(prev => [...prev, { type: "user", text: questionText }]);

    try {
      const response = await fetch(`${API}/game/${gameId}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen_before: fen,
          question: questionText,
          context: `Badge focus: ${badgeKey}. User played: ${playedMove}. Best was: ${bestMove}.`,
          conversation_history: conversation.map(c => ({
            question: c.type === "user" ? c.text : "",
            answer: c.type === "ai" ? c.text : ""
          })).filter(c => c.question || c.answer)
        })
      });

      if (!response.ok) throw new Error("Failed to get response");
      
      const data = await response.json();
      
      // Add AI response to conversation
      setConversation(prev => [...prev, { 
        type: "ai", 
        text: data.response || data.answer || "I couldn't analyze this position. Please try again.",
        pvLine: data.pv_line || data.stockfish?.pv_line || []
      }]);

    } catch (error) {
      console.error("Ask AI error:", error);
      setConversation(prev => [...prev, { 
        type: "ai", 
        text: "Sorry, I couldn't analyze this position. Please try again.",
        error: true
      }]);
    } finally {
      setLoading(false);
    }
  };

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [conversation]);

  return (
    <div className="p-4 border-t bg-gradient-to-b from-violet-500/5 to-transparent">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-medium flex items-center gap-2">
          <Brain className="w-4 h-4 text-violet-500" />
          Ask Your Coach
        </h4>
        <Button variant="ghost" size="sm" onClick={onClose} className="h-6 px-2 text-xs">
          Close
        </Button>
      </div>

      {/* Conversation History */}
      {conversation.length > 0 && (
        <ScrollArea className="h-48 mb-3 pr-2" ref={scrollRef}>
          <div className="space-y-3">
            {conversation.map((msg, i) => (
              <div key={i} className={`flex ${msg.type === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] p-3 rounded-lg ${
                  msg.type === "user" 
                    ? "bg-primary text-primary-foreground" 
                    : msg.error 
                      ? "bg-red-500/10 border border-red-500/20"
                      : "bg-muted"
                }`}>
                  <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
                  {msg.pvLine && msg.pvLine.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border/50">
                      <p className="text-xs text-muted-foreground">Best line:</p>
                      <p className="text-xs font-mono text-green-500">
                        {msg.pvLine.join(" → ")}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-muted p-3 rounded-lg">
                  <Loader2 className="w-4 h-4 animate-spin" />
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
      )}

      {/* Suggested Questions */}
      {conversation.length === 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {suggestedQuestions.map((q, i) => (
            <button
              key={i}
              onClick={() => handleAsk(q)}
              className="text-xs px-3 py-1.5 rounded-full bg-violet-500/20 text-violet-600 dark:text-violet-400 hover:bg-violet-500/30 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2">
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask anything about this position..."
          onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          disabled={loading}
          className="flex-1"
        />
        <Button 
          onClick={() => handleAsk()} 
          disabled={!question.trim() || loading}
          size="icon"
        >
          <Send className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
};

// Single game card with interactive board and moves
const GameCard = ({ game, badgeKey, onViewGame }) => {
  const [expanded, setExpanded] = useState(false);
  const [selectedMove, setSelectedMove] = useState(null);
  const [showAskAI, setShowAskAI] = useState(false);
  
  // Auto-select first move when expanded
  useEffect(() => {
    if (expanded && game.moves?.length > 0 && !selectedMove) {
      setSelectedMove(game.moves[0]);
    }
  }, [expanded, game.moves, selectedMove]);
  
  const getMoveTypeColor = (type) => {
    switch(type) {
      case "mistake":
      case "missed":
      case "positional_error":
      case "endgame_error":
      case "defensive_collapse":
      case "threw_advantage":
      case "focus_error":
      case "time_trouble_blunder":
        return "border-red-500/30 bg-red-500/5";
      case "good":
      case "found":
      case "good_positional":
      case "good_defense":
        return "border-green-500/30 bg-green-500/5";
      default:
        return "border-border bg-muted/50";
    }
  };

  const getMoveTypeLabel = (type) => {
    const labels = {
      mistake: "Opening Mistake",
      missed: "Missed Tactic",
      found: "Found Tactic!",
      positional_error: "Positional Error",
      good_positional: "Good Position",
      endgame_error: "Endgame Error",
      defensive_collapse: "Defense Failed",
      good_defense: "Good Defense",
      threw_advantage: "Threw Advantage",
      focus_error: "Focus Error",
      time_trouble_blunder: "Time Trouble"
    };
    return labels[type] || type;
  };

  const hasNegativeMoves = game.moves?.some(m => 
    ["mistake", "missed", "positional_error", "endgame_error", "defensive_collapse", "threw_advantage", "focus_error", "time_trouble_blunder"].includes(m.type)
  );

  return (
    <Card className="overflow-hidden border" data-testid={`game-card-${game.game_id}`}>
      {/* Header */}
      <div 
        className="p-4 cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
              game.converted === false ? "bg-red-500/20 text-red-500" :
              game.saved_game ? "bg-green-500/20 text-green-500" :
              hasNegativeMoves ? "bg-amber-500/20 text-amber-500" :
              "bg-green-500/20 text-green-500"
            }`}>
              {game.converted === false || hasNegativeMoves ? (
                <AlertTriangle className="w-5 h-5" />
              ) : (
                <CheckCircle2 className="w-5 h-5" />
              )}
            </div>
            <div>
              <p className="font-medium">vs {game.opponent}</p>
              <p className="text-sm text-muted-foreground">
                {game.result} • {game.moves?.length || 0} key moments
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {game.was_winning && !game.converted && (
              <span className="text-xs px-2 py-1 rounded bg-red-500/10 text-red-500 font-medium">
                Thrown
              </span>
            )}
            {game.saved_game && (
              <span className="text-xs px-2 py-1 rounded bg-green-500/10 text-green-500 font-medium">
                Saved!
              </span>
            )}
            {expanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </div>
        </div>
      </div>
      
      {/* Expanded Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="p-4 pt-0 border-t">
              {game.moves && game.moves.length > 0 ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Interactive Board */}
                  <div>
                    <InteractiveBoard
                      fen={selectedMove?.fen_after || selectedMove?.fen_before || selectedMove?.fen || "start"}
                      fenBefore={selectedMove?.fen_before}
                      bestMove={selectedMove?.best_move}
                      playedMove={selectedMove?.move_played}
                      pvLine={selectedMove?.pv_after_best || []}
                      userColor={game.user_color}
                      onAskAI={() => setShowAskAI(true)}
                    />
                    
                    {/* Ask AI Panel */}
                    {showAskAI && selectedMove && (
                      <AskAIPanel
                        fen={selectedMove.fen_before || selectedMove.fen}
                        bestMove={selectedMove.best_move}
                        playedMove={selectedMove.move_played}
                        badgeKey={badgeKey}
                        gameId={game.game_id}
                        onClose={() => setShowAskAI(false)}
                      />
                    )}
                  </div>
                  
                  {/* Moves List */}
                  <div>
                    <p className="text-sm font-medium mb-3 flex items-center gap-2">
                      <Target className="w-4 h-4 text-amber-500" />
                      Key Moments in This Game
                    </p>
                    <ScrollArea className="h-[400px] pr-2">
                      <div className="space-y-3">
                        {game.moves.map((move, idx) => (
                          <div
                            key={idx}
                            onClick={() => {
                              setSelectedMove(move);
                              setShowAskAI(false);
                            }}
                            className={`p-4 rounded-lg border cursor-pointer transition-all ${
                              selectedMove === move 
                                ? "ring-2 ring-amber-500 border-amber-500/50 bg-amber-500/5" 
                                : getMoveTypeColor(move.type) + " hover:border-amber-500/30"
                            }`}
                          >
                            {/* Move Header */}
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-bold">
                                  Move {move.move_number}
                                </span>
                                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                                  move.type.includes("found") || move.type.includes("good") 
                                    ? "bg-green-500/20 text-green-500"
                                    : "bg-red-500/20 text-red-500"
                                }`}>
                                  {getMoveTypeLabel(move.type)}
                                </span>
                              </div>
                              {move.cp_loss > 0 && (
                                <span className="text-xs text-red-500">
                                  -{move.cp_loss} cp
                                </span>
                              )}
                            </div>
                            
                            {/* What was played vs Best */}
                            <div className="grid grid-cols-2 gap-2 mb-3">
                              <div className="p-2 rounded bg-red-500/10">
                                <p className="text-xs text-red-500 mb-1">You played:</p>
                                <p className="font-mono font-bold">{move.move_played}</p>
                              </div>
                              <div className="p-2 rounded bg-green-500/10">
                                <p className="text-xs text-green-500 mb-1">Best was:</p>
                                <p className="font-mono font-bold text-green-600">{move.best_move}</p>
                              </div>
                            </div>
                            
                            {/* Explanation */}
                            <p className="text-sm text-muted-foreground">
                              {move.explanation}
                            </p>
                            
                            {/* Threat indicator */}
                            {move.threat && (
                              <div className="mt-2 p-2 rounded bg-amber-500/10 border border-amber-500/20">
                                <p className="text-xs">
                                  <span className="text-amber-500 font-medium">Threat you faced: </span>
                                  <span className="font-mono">{move.threat}</span>
                                </p>
                              </div>
                            )}
                            
                            {/* PV Line preview */}
                            {move.pv_after_best && move.pv_after_best.length > 0 && (
                              <div className="mt-2 text-xs text-muted-foreground">
                                <span className="text-green-500">Best line: </span>
                                <span className="font-mono">{move.pv_after_best.slice(0, 4).join(" ")}</span>
                                {move.pv_after_best.length > 4 && "..."}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No specific moves to highlight for this badge</p>
                </div>
              )}
              
              {/* View Full Game Button */}
              <div className="mt-4 pt-4 border-t">
                <Button 
                  variant="default"
                  className="w-full gap-2"
                  onClick={(e) => {
                    e.stopPropagation();
                    onViewGame(game.game_id, badgeKey);
                  }}
                >
                  View Full Game Analysis
                  <ExternalLink className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
};

const BadgeDetailModal = ({ isOpen, onClose, badgeKey, badgeName }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  
  const Icon = BADGE_ICONS[badgeKey] || Target;

  useEffect(() => {
    if (isOpen && badgeKey) {
      fetchBadgeDetails();
    }
  }, [isOpen, badgeKey]);

  const fetchBadgeDetails = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`${API}/badges/${badgeKey}/details`, {
        credentials: "include"
      });
      
      if (!response.ok) {
        throw new Error("Failed to fetch badge details");
      }
      
      const result = await response.json();
      setData(result);
    } catch (err) {
      console.error("Badge details fetch error:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleViewGame = (gameId, focus) => {
    onClose();
    navigate(`/game/${gameId}?focus=${focus}`);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[95vh] overflow-y-auto p-0" data-testid="badge-detail-modal">
        <DialogHeader className="p-6 pb-4 border-b bg-gradient-to-r from-amber-500/10 to-orange-500/10">
          <DialogTitle className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-amber-500/20">
              <Icon className="w-6 h-6 text-amber-500" />
            </div>
            <div>
              <span className="block text-xl">{data?.badge_name || badgeName}</span>
              <span className="text-sm font-normal text-muted-foreground">
                {data?.badge_description}
              </span>
            </div>
          </DialogTitle>
        </DialogHeader>

        <div className="p-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="w-10 h-10 animate-spin text-amber-500 mb-4" />
              <p className="text-muted-foreground">Loading your game data...</p>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
              <p className="text-lg font-medium mb-2">Unable to load details</p>
              <p className="text-muted-foreground mb-4">{error}</p>
              <Button variant="outline" onClick={fetchBadgeDetails}>
                Try Again
              </Button>
            </div>
          ) : data ? (
            <div className="space-y-6">
              {/* Score Card */}
              <Card className="overflow-hidden">
                <CardContent className="p-0">
                  <div className="grid grid-cols-1 md:grid-cols-2">
                    {/* Score */}
                    <div className="p-6 flex flex-col justify-center">
                      <p className="text-sm text-muted-foreground mb-2">Your Score</p>
                      <StarRating score={data.score || 2.5} />
                    </div>
                    
                    {/* Why This Score */}
                    <div className="p-6 bg-muted/30 border-l">
                      <p className="text-sm font-medium mb-2 flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-amber-500" />
                        Why this score?
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {data.why_this_score}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Summary Stats */}
              {data.summary && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(data.summary).map(([key, value]) => (
                    <div key={key} className="p-4 rounded-xl bg-muted/30 border text-center">
                      <p className="text-3xl font-bold text-foreground">
                        {typeof value === "boolean" ? (value ? "✓" : "✗") : value}
                      </p>
                      <p className="text-xs text-muted-foreground capitalize mt-1">
                        {key.replace(/_/g, " ")}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {/* Coach Insight */}
              {data.insight && (
                <div className="p-4 rounded-xl border-2 border-amber-500/30 bg-gradient-to-r from-amber-500/5 to-orange-500/5">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-amber-500/20">
                      <Brain className="w-5 h-5 text-amber-500" />
                    </div>
                    <div>
                      <p className="font-medium mb-1">Coach's Insight</p>
                      <p className="text-sm text-muted-foreground">{data.insight}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Games Section */}
              <div>
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  Games That Affected Your Score
                  <span className="text-sm font-normal text-muted-foreground">
                    ({data.relevant_games?.length || 0} games)
                  </span>
                </h3>
                
                {data.relevant_games && data.relevant_games.length > 0 ? (
                  <div className="space-y-4">
                    {data.relevant_games.map((game, idx) => (
                      <GameCard 
                        key={game.game_id || idx} 
                        game={game} 
                        badgeKey={badgeKey}
                        onViewGame={handleViewGame}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 border-2 border-dashed rounded-xl">
                    <Target className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                    <p className="text-lg font-medium mb-2">No games to show yet</p>
                    <p className="text-sm text-muted-foreground">
                      Analyze more games to see detailed insights for this badge.
                    </p>
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default BadgeDetailModal;
