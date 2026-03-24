/**
 * GameDecryptionV5.jsx - "Thinking Simulator"
 * 
 * Vision:
 * - Coach on EVERY move (user + opponent)
 * - Show PLANS (transferable knowledge, not just moves)
 * - "I understand" button for concept acknowledgment
 * - Clickable moves to show the future on the board
 * - Simple, 1200-friendly language
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { Chess } from "chess.js";
import LichessBoard from "@/components/LichessBoard";
import ClickableLine, { extractMovesFromText } from "@/components/ClickableLine";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  AlertTriangle,
  CheckCircle2,
  Lightbulb,
  Target,
  ThumbsDown,
  Send,
  X,
  Loader2,
  BookOpen,
  Brain,
  Eye,
  Swords,
  GraduationCap,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Zap,
  Trophy,
  ArrowRight,
  Check
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const GameDecryptionV5 = ({ gameId, analysis, pgn, userColor, onBack }) => {
  const [decryptionData, setDecryptionData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [boardFen, setBoardFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [acknowledgedConcepts, setAcknowledgedConcepts] = useState(new Set());
  const [showingFutureMoves, setShowingFutureMoves] = useState(false);
  const [futureMoveIndex, setFutureMoveIndex] = useState(0);
  const [highlights, setHighlights] = useState([]);
  const [arrows, setArrows] = useState([]);
  const boardRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => { fetchDecryptionData(); }, [gameId]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
      switch (e.key) {
        case 'ArrowRight': e.preventDefault(); goForward(); break;
        case 'ArrowLeft': e.preventDefault(); goBackward(); break;
        case 'ArrowUp': e.preventDefault(); goToStart(); break;
        case 'ArrowDown': e.preventDefault(); goToEnd(); break;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [decryptionData, currentMoveIndex]);

  const fetchDecryptionData = async (isRetry = false) => {
    try {
      if (!isRetry) setLoading(true);
      setError(null);
      
      // Use V5 endpoint
      const res = await fetch(`${API}/coach/decryption/v5/${gameId}`, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch decryption data");
      const data = await res.json();
      
      if (data.status === "generating") {
        setLoading(true);
        setTimeout(() => fetchDecryptionData(true), 5000);
        return;
      }
      
      if (data.error || !data.decryption_data) {
        setError(data.error || "Decryption data not available");
        return;
      }
      
      setDecryptionData(data.decryption_data);
      
      // Pre-load acknowledged concepts
      if (data.decryption_data) {
        const acked = new Set();
        data.decryption_data.forEach(m => {
          if (m.already_acknowledged && m.concept_id) {
            acked.add(m.concept_id);
          }
        });
        setAcknowledgedConcepts(acked);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const goForward = useCallback(() => {
    if (!decryptionData || currentMoveIndex >= decryptionData.length - 1) return;
    resetFutureView();
    const i = currentMoveIndex + 1;
    setCurrentMoveIndex(i);
    setBoardFen(decryptionData[i].fen_after);
    
    // Show highlight squares if any
    const m = decryptionData[i];
    if (m.highlight_squares?.length) {
      setHighlights(m.highlight_squares);
    } else {
      setHighlights([]);
    }
  }, [decryptionData, currentMoveIndex]);

  const goBackward = useCallback(() => {
    if (!decryptionData || currentMoveIndex < 0) return;
    resetFutureView();
    const i = currentMoveIndex - 1;
    setCurrentMoveIndex(i);
    setBoardFen(i === -1 ? "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" : decryptionData[i].fen_after);
    setHighlights([]);
  }, [decryptionData, currentMoveIndex]);

  const goToStart = useCallback(() => {
    resetFutureView();
    setCurrentMoveIndex(-1);
    setBoardFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    setHighlights([]);
  }, []);

  const goToEnd = useCallback(() => {
    if (!decryptionData?.length) return;
    resetFutureView();
    const i = decryptionData.length - 1;
    setCurrentMoveIndex(i);
    setBoardFen(decryptionData[i].fen_after);
    setHighlights([]);
  }, [decryptionData]);

  const goToMove = useCallback((i) => {
    if (!decryptionData || i < -1 || i >= decryptionData.length) return;
    resetFutureView();
    setCurrentMoveIndex(i);
    setBoardFen(i === -1 ? "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" : decryptionData[i].fen_after);
    
    if (i >= 0 && decryptionData[i].highlight_squares?.length) {
      setHighlights(decryptionData[i].highlight_squares);
    } else {
      setHighlights([]);
    }
  }, [decryptionData]);

  const resetFutureView = () => {
    setShowingFutureMoves(false);
    setFutureMoveIndex(0);
    setArrows([]);
  };

  // Play future moves on the board (clickable line feature)
  const showFutureMoves = useCallback((moves, upToIndex) => {
    if (!decryptionData || currentMoveIndex < 0) return;
    
    const currentMove = decryptionData[currentMoveIndex];
    const startFen = currentMove.fen_after;
    
    try {
      const chess = new Chess(startFen);
      
      // Play moves up to the clicked one
      for (let i = 0; i <= upToIndex && i < moves.length; i++) {
        const move = chess.move(moves[i]);
        if (!move) break;
      }
      
      setBoardFen(chess.fen());
      setShowingFutureMoves(true);
      setFutureMoveIndex(upToIndex);
      
      // Draw arrow for last move
      const history = chess.history({ verbose: true });
      if (history.length > 0) {
        const lastMove = history[history.length - 1];
        setArrows([[lastMove.from, lastMove.to, "green"]]);
      }
    } catch (err) {
      console.error("Error showing future moves:", err);
    }
  }, [decryptionData, currentMoveIndex]);

  const resetToCurrentMove = useCallback(() => {
    if (!decryptionData || currentMoveIndex < 0) return;
    setBoardFen(decryptionData[currentMoveIndex].fen_after);
    setShowingFutureMoves(false);
    setFutureMoveIndex(0);
    setArrows([]);
  }, [decryptionData, currentMoveIndex]);

  // Acknowledge a concept
  const acknowledgeConceptHandler = async (conceptId) => {
    try {
      const res = await fetch(`${API}/coach/decryption/acknowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ concept_id: conceptId })
      });
      
      if (res.ok) {
        setAcknowledgedConcepts(prev => new Set([...prev, conceptId]));
        toast.success("Got it! I'll remember you understand this.");
      }
    } catch (err) {
      toast.error("Failed to save acknowledgment");
    }
  };

  const handleSubmitFeedback = async () => {
    if (!feedbackText.trim() || currentMoveIndex < 0) return;
    const m = decryptionData[currentMoveIndex];
    try {
      setSubmittingFeedback(true);
      const res = await fetch(`${API}/coach/decryption/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          game_id: gameId,
          move_number: m.move_number,
          fen: m.fen_before,
          coach_explanation: m.narrative || "",
          user_feedback: "not_helpful",
          user_correction: feedbackText,
          is_user_move: m.is_user_move
        })
      });
      if (res.ok) {
        toast.success("Feedback saved — thanks!");
        setFeedbackOpen(false);
        setFeedbackText("");
      }
    } catch (err) {
      toast.error("Failed to send feedback");
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const currentMove = currentMoveIndex >= 0 ? decryptionData?.[currentMoveIndex] : null;
  const orientation = userColor === "black" ? "black" : "white";

  if (loading) return (
    <div className="flex flex-col items-center justify-center h-96" data-testid="decryption-loading">
      <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
      <span className="mt-3 text-zinc-400">Your coach is analyzing every move...</span>
      <span className="mt-1 text-zinc-600 text-sm">This takes about 45 seconds for V5 analysis</span>
    </div>
  );

  if (error) return (
    <div className="flex flex-col items-center justify-center h-96 text-center" data-testid="decryption-error">
      <AlertTriangle className="w-12 h-12 text-amber-400 mb-4" />
      <p className="text-zinc-300 mb-2">{error}</p>
      <Button variant="outline" onClick={() => fetchDecryptionData()} className="mt-4">Try Again</Button>
    </div>
  );

  return (
    <div ref={containerRef} className="flex flex-col lg:flex-row gap-4 p-4" data-testid="game-decryption-v5">
      {/* LEFT: Board + Controls */}
      <div className="lg:w-1/2 space-y-4">
        <div className="aspect-square max-w-[500px] mx-auto relative">
          <LichessBoard 
            ref={boardRef}
            fen={boardFen} 
            orientation={orientation} 
            viewOnly={true}
            lastMove={currentMove && !showingFutureMoves ? getLastMoveSquares(currentMove) : null}
            arrows={arrows}
            highlights={highlights}
          />
          
          {/* Future moves indicator */}
          {showingFutureMoves && (
            <div className="absolute top-2 left-2 bg-emerald-500/90 text-white text-xs px-2 py-1 rounded flex items-center gap-1">
              <Eye className="w-3 h-3" />
              Showing future line
              <button 
                onClick={resetToCurrentMove}
                className="ml-2 bg-white/20 hover:bg-white/30 px-1.5 py-0.5 rounded text-xs"
              >
                Reset
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="icon" onClick={goToStart} disabled={currentMoveIndex === -1} data-testid="btn-go-start">
            <ChevronsLeft className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={goBackward} disabled={currentMoveIndex === -1} data-testid="btn-go-back">
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="px-4 text-sm text-zinc-400 min-w-[100px] text-center">
            {currentMoveIndex === -1 ? "Start" : `Move ${currentMove?.move_number || ""}`}
            {currentMove && !currentMove.is_user_move && " (opp)"}
          </span>
          <Button variant="outline" size="icon" onClick={goForward} disabled={!decryptionData || currentMoveIndex >= decryptionData.length - 1} data-testid="btn-go-forward">
            <ChevronRight className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={goToEnd} disabled={!decryptionData || currentMoveIndex >= decryptionData.length - 1} data-testid="btn-go-end">
            <ChevronsRight className="w-4 h-4" />
          </Button>
        </div>

        <MoveListV5 
          decryptionData={decryptionData} 
          currentMoveIndex={currentMoveIndex} 
          onMoveClick={goToMove} 
        />
      </div>

      {/* RIGHT: Coaching */}
      <div className="lg:w-1/2 space-y-4">
        {currentMoveIndex === -1 ? (
          <GameStartCard decryptionData={decryptionData} />
        ) : (
          <MoveCoachingCardV5 
            move={currentMove}
            acknowledgedConcepts={acknowledgedConcepts}
            onAcknowledge={acknowledgeConceptHandler}
            onShowFutureMoves={showFutureMoves}
            onFeedbackClick={() => setFeedbackOpen(true)}
          />
        )}
        
        {feedbackOpen && currentMove && (
          <FeedbackPanel 
            move={currentMove} 
            feedbackText={feedbackText} 
            setFeedbackText={setFeedbackText}
            onSubmit={handleSubmitFeedback} 
            onCancel={() => { setFeedbackOpen(false); setFeedbackText(""); }}
            submitting={submittingFeedback} 
          />
        )}
        
        <div className="text-xs text-zinc-600 text-center">
          Arrow keys: left/right navigate • Click moves in explanation to see on board
        </div>
      </div>
    </div>
  );
};


// ─── GAME START CARD ────────────────────────────────────────────────

const GameStartCard = ({ decryptionData }) => {
  if (!decryptionData?.length) return null;
  
  // Calculate stats
  const userMoves = decryptionData.filter(m => m.is_user_move);
  const mistakes = userMoves.filter(m => m.severity === 'mistake' || m.severity === 'blunder').length;
  const goodMoves = userMoves.filter(m => m.severity === 'good').length;
  const bestMoves = userMoves.filter(m => m.is_best_move).length;
  const openingName = decryptionData[0]?.opening_name;
  
  return (
    <Card className="bg-zinc-900/50 border-zinc-800" data-testid="game-start-card">
      <CardContent className="p-5 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <BookOpen className="w-5 h-5 text-emerald-400" />
          <h3 className="font-semibold text-white">Game Overview</h3>
        </div>
        
        {openingName && (
          <div className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-500/20">
            <p className="text-xs text-emerald-400 mb-1">Opening</p>
            <p className="text-white font-medium">{openingName}</p>
          </div>
        )}
        
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="bg-zinc-800/50 rounded-lg p-3">
            <p className="text-2xl font-bold text-white">{userMoves.length}</p>
            <p className="text-xs text-zinc-500">Your Moves</p>
          </div>
          <div className="bg-zinc-800/50 rounded-lg p-3">
            <p className="text-2xl font-bold text-emerald-400">{bestMoves}</p>
            <p className="text-xs text-zinc-500">Best Moves</p>
          </div>
          <div className="bg-zinc-800/50 rounded-lg p-3">
            <p className="text-2xl font-bold text-red-400">{mistakes}</p>
            <p className="text-xs text-zinc-500">Mistakes</p>
          </div>
        </div>
        
        <div className="bg-zinc-800/30 rounded-lg p-4">
          <p className="text-zinc-300 text-sm">
            This analysis coaches you on <strong>every move</strong> — yours and your opponent's.
            Look for the <span className="text-amber-400">"I understand"</span> buttons to track your learning.
          </p>
        </div>
        
        <div className="pt-2 border-t border-zinc-800">
          <p className="text-sm text-emerald-400 flex items-center gap-2">
            <ChevronRight className="w-4 h-4" /> Press right arrow to begin
          </p>
        </div>
      </CardContent>
    </Card>
  );
};


// ─── MOVE COACHING CARD V5 ──────────────────────────────────────────

const MoveCoachingCardV5 = ({ move, acknowledgedConcepts, onAcknowledge, onShowFutureMoves, onFeedbackClick }) => {
  const [expanded, setExpanded] = useState(false);
  if (!move) return null;

  const isUser = move.is_user_move;
  const severity = move.severity || 'good';
  const hasPlan = !!move.plan;
  const needsAck = move.needs_acknowledgment && move.concept_id && !acknowledgedConcepts.has(move.concept_id);
  const wasAcked = move.concept_id && acknowledgedConcepts.has(move.concept_id);

  // Determine card style based on move type
  let borderClass = 'border-zinc-800 bg-zinc-900/50';
  let headerIcon = <Brain className="w-5 h-5 text-blue-400" />;
  
  if (!isUser) {
    borderClass = 'border-indigo-500/30 bg-indigo-950/10';
    headerIcon = <Target className="w-5 h-5 text-indigo-400" />;
  } else if (severity === 'blunder' || severity === 'mistake') {
    borderClass = 'border-red-500/30 bg-red-950/10';
    headerIcon = <AlertTriangle className="w-5 h-5 text-red-400" />;
  } else if (severity === 'inaccuracy') {
    borderClass = 'border-orange-500/30 bg-orange-950/10';
    headerIcon = <Lightbulb className="w-5 h-5 text-orange-400" />;
  } else if (move.is_best_move) {
    borderClass = 'border-emerald-500/30 bg-emerald-950/10';
    headerIcon = <Trophy className="w-5 h-5 text-emerald-400" />;
  } else if (severity === 'good') {
    borderClass = 'border-emerald-500/20 bg-emerald-950/5';
    headerIcon = <CheckCircle2 className="w-5 h-5 text-emerald-400" />;
  }

  return (
    <Card className={`border ${borderClass}`} data-testid="move-coaching-card-v5">
      <CardContent className="p-5 space-y-3">
        {/* ─── HEADER ──────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {headerIcon}
            <span className="font-bold text-white text-lg">{move.move_san}</span>
            <Badge variant={isUser ? "default" : "secondary"} className="text-xs">
              {isUser ? "Your move" : "Opponent"}
            </Badge>
            {severity !== 'good' && severity !== 'context' && (
              <Badge variant="outline" className={`text-xs ${
                severity === 'blunder' ? 'text-red-400 border-red-500/30' :
                severity === 'mistake' ? 'text-red-400 border-red-500/30' :
                'text-orange-400 border-orange-500/30'
              }`}>
                {severity}
              </Badge>
            )}
            {move.is_best_move && (
              <Badge className="text-xs bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                Best move!
              </Badge>
            )}
          </div>
          <Badge variant="outline" className="text-xs text-zinc-400">{move.phase}</Badge>
        </div>

        {/* ─── NARRATIVE ────────────────────────────────────── */}
        {move.narrative && (
          <div className="leading-relaxed" data-testid="move-narrative">
            <p className="text-sm text-zinc-200">{move.narrative}</p>
          </div>
        )}

        {/* ─── OPPONENT MOVE: YOUR PLAN NOW ─────────────────── */}
        {!isUser && move.your_plan_now && (
          <div className="bg-indigo-500/10 rounded-lg p-3 border border-indigo-500/30" data-testid="your-plan-now">
            <p className="text-xs text-indigo-400 mb-1 flex items-center gap-1">
              <Swords className="w-3 h-3" /> What's your plan now?
            </p>
            <p className="text-white text-sm">{move.your_plan_now}</p>
          </div>
        )}

        {/* ─── PLAN (THE TRANSFERABLE LEARNING) ─────────────── */}
        {hasPlan && (
          <div className="space-y-2">
            {/* Consequence with clickable moves */}
            {move.plan.consequence && (
              <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/20" data-testid="plan-consequence">
                <p className="text-xs text-red-400 mb-1">What happens</p>
                <ClickableMoves 
                  text={move.plan.consequence}
                  moves={move.future_moves || []}
                  onMoveClick={onShowFutureMoves}
                />
              </div>
            )}
            
            {/* Better approach */}
            {move.plan.better_approach && (
              <div className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-500/20" data-testid="plan-better">
                <p className="text-xs text-emerald-400 mb-1">Better approach</p>
                <p className="text-white text-sm">{move.plan.better_approach}</p>
              </div>
            )}
            
            {/* Transferable learning */}
            {move.plan.transferable_learning && (
              <div className="bg-amber-500/10 rounded-lg p-4 border border-amber-500/30" data-testid="transferable-learning">
                <div className="flex items-center gap-2 mb-1">
                  <GraduationCap className="w-4 h-4 text-amber-400" />
                  <p className="text-xs font-semibold text-amber-400">Learning</p>
                </div>
                <p className="text-white text-sm font-medium">{move.plan.transferable_learning}</p>
                
                {/* I Understand button */}
                {needsAck && (
                  <div className="mt-3 pt-3 border-t border-amber-500/20">
                    <p className="text-xs text-zinc-400 mb-2">{move.acknowledgment_prompt || "Click when this concept is clear to you."}</p>
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => onAcknowledge(move.concept_id)}
                      className="text-amber-400 border-amber-500/30 hover:bg-amber-500/10"
                      data-testid="btn-i-understand"
                    >
                      <Check className="w-3 h-3 mr-1" /> I understand
                    </Button>
                  </div>
                )}
                
                {wasAcked && (
                  <div className="mt-2 flex items-center gap-1 text-xs text-emerald-400">
                    <CheckCircle2 className="w-3 h-3" /> You've learned this
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ─── CONCEPT APPLIED (for good moves) ──────────────── */}
        {move.concept_applied && !hasPlan && (
          <div className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-500/20" data-testid="concept-applied">
            <p className="text-xs text-emerald-400 mb-1 flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> You demonstrated
            </p>
            <p className="text-white text-sm">{move.concept_applied.replace(/_/g, ' ')}</p>
          </div>
        )}

        {/* ─── FUTURE MOVES (clickable) ───────────────────────── */}
        {move.future_moves?.length > 0 && !hasPlan && (
          <div className="bg-zinc-800/50 rounded-lg p-3">
            <p className="text-xs text-zinc-400 mb-2">The line continues:</p>
            <div className="flex flex-wrap gap-1">
              {move.future_moves.slice(0, 4).map((m, i) => (
                <button
                  key={i}
                  onClick={() => onShowFutureMoves(move.future_moves, i)}
                  className="font-mono text-sm bg-zinc-700/50 hover:bg-emerald-500/20 px-2 py-1 rounded text-white transition-colors"
                  title={`Click to see position after ${m}`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ─── FEEDBACK ──────────────────────────────────────── */}
        <div className="flex items-center justify-end pt-2 border-t border-zinc-800/50">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={onFeedbackClick} 
            className="text-xs text-zinc-500 hover:text-red-400" 
            data-testid="btn-not-helpful"
          >
            <ThumbsDown className="w-3 h-3 mr-1" /> Not helpful
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};


// ─── CLICKABLE MOVES COMPONENT ──────────────────────────────────────

const ClickableMoves = ({ text, moves, onMoveClick }) => {
  if (!moves?.length || !text) {
    return <p className="text-white text-sm">{text}</p>;
  }
  
  // Parse text and make moves clickable
  const movePattern = /\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O)\b/g;
  const parts = [];
  let lastIndex = 0;
  let moveIndex = 0;
  let match;
  
  while ((match = movePattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: text.slice(lastIndex, match.index) });
    }
    
    const moveSan = match[0];
    const foundIndex = moves.findIndex((m, i) => 
      i >= moveIndex && m.replace(/[+#]/g, '') === moveSan.replace(/[+#]/g, '')
    );
    
    if (foundIndex !== -1) {
      parts.push({ type: 'move', content: moveSan, moveIndex: foundIndex });
      moveIndex = foundIndex + 1;
    } else {
      parts.push({ type: 'move-inactive', content: moveSan });
    }
    
    lastIndex = match.index + match[0].length;
  }
  
  if (lastIndex < text.length) {
    parts.push({ type: 'text', content: text.slice(lastIndex) });
  }
  
  return (
    <p className="text-white text-sm">
      {parts.map((part, i) => {
        if (part.type === 'move') {
          return (
            <button
              key={i}
              onClick={() => onMoveClick(moves, part.moveIndex)}
              className="font-mono font-bold text-amber-400 hover:text-amber-300 hover:underline cursor-pointer transition-colors"
              title={`Click to see this on the board`}
            >
              {part.content}
            </button>
          );
        }
        if (part.type === 'move-inactive') {
          return <span key={i} className="font-mono font-semibold text-zinc-300">{part.content}</span>;
        }
        return <span key={i}>{part.content}</span>;
      })}
    </p>
  );
};


// ─── FEEDBACK PANEL ─────────────────────────────────────────────────

const FeedbackPanel = ({ move, feedbackText, setFeedbackText, onSubmit, onCancel, submitting }) => (
  <Card className="bg-zinc-900 border-zinc-700" data-testid="feedback-panel">
    <CardContent className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-white">What should the explanation say?</p>
        <Button variant="ghost" size="icon" onClick={onCancel} className="h-6 w-6">
          <X className="w-4 h-4" />
        </Button>
      </div>
      <Textarea 
        value={feedbackText} 
        onChange={(e) => setFeedbackText(e.target.value)}
        placeholder="Write a better explanation..." 
        className="min-h-[100px] bg-zinc-800 border-zinc-700 text-white" 
        data-testid="feedback-textarea" 
      />
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel}>Cancel</Button>
        <Button size="sm" onClick={onSubmit} disabled={!feedbackText.trim() || submitting} data-testid="submit-feedback-btn">
          {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />} Submit
        </Button>
      </div>
    </CardContent>
  </Card>
);


// ─── MOVE LIST V5 ───────────────────────────────────────────────────

const MoveListV5 = ({ decryptionData, currentMoveIndex, onMoveClick }) => {
  if (!decryptionData?.length) return null;
  
  const pairs = [];
  for (let i = 0; i < decryptionData.length; i += 2) {
    pairs.push({
      num: decryptionData[i].move_number,
      w: decryptionData[i],
      b: decryptionData[i + 1] || null,
      wi: i,
      bi: i + 1
    });
  }
  
  const moveClass = (m, idx) => {
    if (currentMoveIndex === idx) return 'bg-emerald-500/30 text-white ring-1 ring-emerald-500/50';
    
    const severity = m.severity || 'good';
    if (severity === 'blunder') return 'text-red-400 bg-red-500/10 hover:bg-red-500/20';
    if (severity === 'mistake') return 'text-red-400 hover:bg-red-500/10';
    if (severity === 'inaccuracy') return 'text-orange-400 hover:bg-orange-500/10';
    if (m.is_best_move) return 'text-emerald-400 hover:bg-emerald-500/10';
    if (!m.is_user_move) return 'text-zinc-500 hover:bg-zinc-800';
    return 'text-zinc-300 hover:bg-zinc-800';
  };
  
  const indicator = (m) => {
    const severity = m.severity || 'good';
    if (severity === 'blunder') return <span className="text-red-400 ml-0.5">??</span>;
    if (severity === 'mistake') return <span className="text-red-400 ml-0.5">?</span>;
    if (severity === 'inaccuracy') return <span className="text-orange-400 ml-0.5">?!</span>;
    if (m.is_best_move) return <span className="text-emerald-400 ml-0.5">!</span>;
    return null;
  };

  return (
    <ScrollArea className="h-[180px] rounded-lg border border-zinc-800 bg-zinc-900/30">
      <div className="p-2 space-y-1">
        {pairs.map(p => (
          <div key={p.num} className="flex items-center gap-1 text-sm">
            <span className="w-8 text-zinc-500 text-right shrink-0">{p.num}.</span>
            <button 
              onClick={() => onMoveClick(p.wi)} 
              className={`px-2 py-0.5 rounded font-mono transition-colors ${moveClass(p.w, p.wi)}`}
            >
              {p.w.move_san}{indicator(p.w)}
            </button>
            {p.b && (
              <button 
                onClick={() => onMoveClick(p.bi)} 
                className={`px-2 py-0.5 rounded font-mono transition-colors ${moveClass(p.b, p.bi)}`}
              >
                {p.b.move_san}{indicator(p.b)}
              </button>
            )}
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};


// ─── HELPER ─────────────────────────────────────────────────────────

const getLastMoveSquares = (move) => {
  if (!move?.fen_before || !move?.move_san) return null;
  try {
    const c = new Chess(move.fen_before);
    const p = c.move(move.move_san);
    return p ? [p.from, p.to] : null;
  } catch { 
    return null; 
  }
};


export default GameDecryptionV5;
