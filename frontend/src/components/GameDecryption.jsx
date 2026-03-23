/**
 * GameDecryption.jsx - V3: Coach-Quality Game Understanding
 * 
 * Philosophy: "A great coach first understands your thinking, then guides you forward"
 * 
 * V3 Features:
 * - Opening Introduction Card: Sets context at the start
 * - Intent Acknowledgment: "I see you played h6 to prevent Ng5..."
 * - Main Line Theory: Shows what theory recommends and why
 * - Empathetic Sideline Warnings: Validates your thinking before correcting
 * 
 * Controls:
 * - Arrow keys for navigation
 * - Not Helpful button for feedback
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { Chess } from "chess.js";
import LichessBoard from "@/components/LichessBoard";
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
  MessageCircle,
  Sparkles
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const GameDecryption = ({ 
  gameId, 
  analysis, 
  pgn, 
  userColor,
  onBack 
}) => {
  const [decryptionData, setDecryptionData] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [boardFen, setBoardFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [submittedFeedback, setSubmittedFeedback] = useState(new Set());
  
  const chessRef = useRef(new Chess());
  const containerRef = useRef(null);
  
  useEffect(() => {
    fetchDecryptionData();
  }, [gameId]);
  
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
      
      switch (e.key) {
        case 'ArrowRight':
          e.preventDefault();
          goForward();
          break;
        case 'ArrowLeft':
          e.preventDefault();
          goBackward();
          break;
        case 'ArrowUp':
          e.preventDefault();
          goToStart();
          break;
        case 'ArrowDown':
          e.preventDefault();
          goToEnd();
          break;
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [decryptionData, currentMoveIndex]);
  
  const fetchDecryptionData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const res = await fetch(`${API}/coach/decryption/${gameId}`, {
        credentials: "include"
      });
      
      if (!res.ok) {
        throw new Error("Failed to fetch decryption data");
      }
      
      const data = await res.json();
      
      if (data.error || !data.decryption_data) {
        setError(data.error || "Decryption data not available");
        if (data.needs_reanalysis) {
          setError("This game was analyzed before the decryption feature. Please re-analyze to see explanations.");
        }
        return;
      }
      
      setDecryptionData(data.decryption_data);
      setSummary(data.summary);
      
      if (pgn) {
        chessRef.current.loadPgn(pgn);
        chessRef.current.reset();
      }
      
    } catch (err) {
      console.error("Error fetching decryption:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  const goForward = useCallback(() => {
    if (!decryptionData) return;
    if (currentMoveIndex < decryptionData.length - 1) {
      const newIndex = currentMoveIndex + 1;
      setCurrentMoveIndex(newIndex);
      setBoardFen(decryptionData[newIndex].fen_after);
    }
  }, [decryptionData, currentMoveIndex]);
  
  const goBackward = useCallback(() => {
    if (!decryptionData) return;
    if (currentMoveIndex > -1) {
      const newIndex = currentMoveIndex - 1;
      setCurrentMoveIndex(newIndex);
      if (newIndex === -1) {
        setBoardFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
      } else {
        setBoardFen(decryptionData[newIndex].fen_after);
      }
    }
  }, [decryptionData, currentMoveIndex]);
  
  const goToStart = useCallback(() => {
    setCurrentMoveIndex(-1);
    setBoardFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  }, []);
  
  const goToEnd = useCallback(() => {
    if (!decryptionData || decryptionData.length === 0) return;
    const lastIndex = decryptionData.length - 1;
    setCurrentMoveIndex(lastIndex);
    setBoardFen(decryptionData[lastIndex].fen_after);
  }, [decryptionData]);
  
  const goToMove = useCallback((index) => {
    if (!decryptionData) return;
    if (index >= -1 && index < decryptionData.length) {
      setCurrentMoveIndex(index);
      if (index === -1) {
        setBoardFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
      } else {
        setBoardFen(decryptionData[index].fen_after);
      }
    }
  }, [decryptionData]);
  
  const handleSubmitFeedback = async () => {
    if (!feedbackText.trim() || currentMoveIndex < 0) return;
    
    const currentMove = decryptionData[currentMoveIndex];
    
    try {
      setSubmittingFeedback(true);
      
      const res = await fetch(`${API}/coach/decryption/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          game_id: gameId,
          move_number: currentMove.move_number,
          fen: currentMove.fen_before,
          coach_explanation: currentMove.what_happened + " " + (currentMove.move_idea || ""),
          user_feedback: "not_helpful",
          user_correction: feedbackText,
          is_user_move: currentMove.is_user_move
        })
      });
      
      if (res.ok) {
        toast.success("Thanks for your feedback!");
        setSubmittedFeedback(prev => new Set([...prev, currentMoveIndex]));
        setFeedbackOpen(false);
        setFeedbackText("");
      } else {
        toast.error("Failed to submit feedback");
      }
    } catch (err) {
      console.error("Error submitting feedback:", err);
      toast.error("Failed to submit feedback");
    } finally {
      setSubmittingFeedback(false);
    }
  };
  
  const currentMove = currentMoveIndex >= 0 ? decryptionData?.[currentMoveIndex] : null;
  const orientation = userColor === "black" ? "black" : "white";
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-96" data-testid="decryption-loading">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
        <span className="ml-3 text-zinc-400">Decrypting your game...</span>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-center" data-testid="decryption-error">
        <AlertTriangle className="w-12 h-12 text-amber-400 mb-4" />
        <p className="text-zinc-300 mb-2">{error}</p>
        <Button variant="outline" onClick={fetchDecryptionData} className="mt-4">
          Try Again
        </Button>
      </div>
    );
  }
  
  return (
    <div 
      ref={containerRef}
      className="flex flex-col lg:flex-row gap-4 p-4"
      data-testid="game-decryption"
    >
      {/* LEFT: Board + Controls */}
      <div className="lg:w-1/2 space-y-4">
        <div className="aspect-square max-w-[500px] mx-auto">
          <LichessBoard
            fen={boardFen}
            orientation={orientation}
            viewOnly={true}
            lastMove={currentMove ? getLastMoveSquares(currentMove) : null}
          />
        </div>
        
        {/* Navigation Controls */}
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={goToStart}
            disabled={currentMoveIndex === -1}
            title="Go to start"
            data-testid="btn-go-start"
          >
            <ChevronsLeft className="w-4 h-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={goBackward}
            disabled={currentMoveIndex === -1}
            title="Previous move"
            data-testid="btn-go-back"
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          
          <span className="px-4 text-sm text-zinc-400 min-w-[80px] text-center">
            {currentMoveIndex === -1 ? "Start" : `Move ${currentMove?.move_number || ""}`}
            {currentMove && !currentMove.is_user_move && " (opp)"}
          </span>
          
          <Button
            variant="outline"
            size="icon"
            onClick={goForward}
            disabled={!decryptionData || currentMoveIndex >= decryptionData.length - 1}
            title="Next move"
            data-testid="btn-go-forward"
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={goToEnd}
            disabled={!decryptionData || currentMoveIndex >= decryptionData.length - 1}
            title="Go to end"
            data-testid="btn-go-end"
          >
            <ChevronsRight className="w-4 h-4" />
          </Button>
        </div>
        
        <MoveList 
          decryptionData={decryptionData}
          currentMoveIndex={currentMoveIndex}
          onMoveClick={goToMove}
          userColor={userColor}
        />
      </div>
      
      {/* RIGHT: Coaching Panel */}
      <div className="lg:w-1/2 space-y-4">
        {currentMoveIndex === -1 ? (
          <GameSummaryCard summary={summary} decryptionData={decryptionData} />
        ) : (
          <MoveCoachingCard 
            move={currentMove}
            hasFeedback={submittedFeedback.has(currentMoveIndex)}
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
          Use arrow keys: left/right to navigate, up to start, down to end
        </div>
      </div>
    </div>
  );
};


/**
 * Opening Introduction Card - V3 feature
 */
const OpeningIntroCard = ({ intro }) => {
  if (!intro) return null;
  
  return (
    <div className="bg-gradient-to-br from-indigo-500/10 to-violet-500/10 rounded-lg p-4 border border-indigo-500/20" data-testid="opening-intro-card">
      <div className="flex items-center gap-2 mb-3">
        <GraduationCap className="w-4 h-4 text-indigo-400" />
        <p className="text-sm font-semibold text-indigo-300">About this Opening</p>
      </div>
      
      <p className="text-zinc-300 text-sm mb-3 leading-relaxed">{intro.description}</p>
      
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-zinc-800/50 rounded-lg p-3">
          <p className="text-xs text-emerald-400 mb-1 flex items-center gap-1">
            <Swords className="w-3 h-3" /> Your Plan
          </p>
          <p className="text-zinc-300 text-xs leading-relaxed">{intro.your_plan}</p>
        </div>
        <div className="bg-zinc-800/50 rounded-lg p-3">
          <p className="text-xs text-red-400 mb-1 flex items-center gap-1">
            <Target className="w-3 h-3" /> Their Plan
          </p>
          <p className="text-zinc-300 text-xs leading-relaxed">{intro.their_plan}</p>
        </div>
      </div>
      
      {intro.key_focus && (
        <div className="mt-3 bg-zinc-800/30 rounded-lg p-2.5">
          <p className="text-xs text-amber-400 mb-0.5">Key Focus</p>
          <p className="text-zinc-400 text-xs">{intro.key_focus}</p>
        </div>
      )}
    </div>
  );
};


/**
 * Game Summary Card - shown at starting position. V3: includes opening intro
 */
const GameSummaryCard = ({ summary, decryptionData }) => {
  if (!summary) return null;
  
  return (
    <Card className="bg-zinc-900/50 border-zinc-800" data-testid="game-summary">
      <CardContent className="p-5 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <BookOpen className="w-5 h-5 text-emerald-400" />
          <h3 className="font-semibold text-white">Game Overview</h3>
        </div>
        
        {/* Opening Name */}
        {summary.opening_name && (
          <div className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-500/20">
            <p className="text-xs text-emerald-400 mb-1">Opening</p>
            <p className="text-white font-medium">{summary.opening_name}</p>
          </div>
        )}
        
        {/* V3: Opening Introduction */}
        {summary.opening_introduction && (
          <OpeningIntroCard intro={summary.opening_introduction} />
        )}
        
        {/* Stats */}
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="bg-zinc-800/50 rounded-lg p-3">
            <p className="text-2xl font-bold text-white">{summary.total_moves}</p>
            <p className="text-xs text-zinc-500">Total Moves</p>
          </div>
          <div className="bg-zinc-800/50 rounded-lg p-3">
            <p className="text-2xl font-bold text-emerald-400">{summary.good_moves || 0}</p>
            <p className="text-xs text-zinc-500">Good Moves</p>
          </div>
          <div className="bg-zinc-800/50 rounded-lg p-3">
            <p className="text-2xl font-bold text-red-400">{summary.mistakes || 0}</p>
            <p className="text-xs text-zinc-500">Mistakes</p>
          </div>
        </div>
        
        {/* Overall message */}
        <div className="bg-zinc-800/30 rounded-lg p-4">
          <p className="text-zinc-300 text-sm">{summary.overall_message}</p>
        </div>
        
        {/* Key moments */}
        {summary.key_moments && summary.key_moments.length > 0 && (
          <div>
            <p className="text-xs text-zinc-500 mb-2">Key Moments</p>
            <div className="space-y-1">
              {summary.key_moments.slice(0, 3).map((moment, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <Badge variant="destructive" className="text-xs">
                    Move {moment.move_number}
                  </Badge>
                  <span className="text-zinc-400 truncate">{moment.summary}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        
        <div className="pt-2 border-t border-zinc-800">
          <p className="text-sm text-emerald-400 flex items-center gap-2">
            <ChevronRight className="w-4 h-4" />
            Press right arrow or click Next to begin
          </p>
        </div>
      </CardContent>
    </Card>
  );
};


/**
 * Move Coaching Card - V3: shows intent acknowledgment & main line theory
 */
const MoveCoachingCard = ({ move, hasFeedback, onFeedbackClick }) => {
  if (!move) return null;
  
  const isUserMove = move.is_user_move;
  const isMistake = move.is_mistake;
  const isGoodMove = move.is_good_move;
  
  return (
    <Card 
      className={`border ${
        isMistake ? 'border-red-500/30 bg-red-950/10' : 
        isGoodMove ? 'border-emerald-500/30 bg-emerald-950/10' : 
        'border-zinc-800 bg-zinc-900/50'
      }`}
      data-testid="move-coaching-card"
    >
      <CardContent className="p-5 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isMistake ? (
              <AlertTriangle className="w-5 h-5 text-red-400" />
            ) : isGoodMove ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            ) : (
              <Brain className="w-5 h-5 text-blue-400" />
            )}
            <div>
              <span className="font-bold text-white text-lg">{move.move_san}</span>
              <Badge 
                variant={isUserMove ? "default" : "secondary"} 
                className="ml-2 text-xs"
              >
                {isUserMove ? "Your move" : "Opponent"}
              </Badge>
            </div>
          </div>
          
          <Badge variant="outline" className="text-xs text-zinc-400">
            {move.phase}
          </Badge>
        </div>
        
        {/* V3: Intent Acknowledgment — the empathetic coach speaks first */}
        {move.intent_acknowledged && isUserMove && (
          <div className="bg-indigo-500/10 rounded-lg p-3 border border-indigo-500/20" data-testid="intent-acknowledged">
            <p className="text-xs text-indigo-400 mb-1 flex items-center gap-1">
              <MessageCircle className="w-3 h-3" /> Your Coach
            </p>
            <p className="text-indigo-200 text-sm italic">{move.intent_acknowledged}</p>
          </div>
        )}
        
        {/* What happened */}
        <div className="space-y-3">
          <div>
            <p className="text-xs text-zinc-500 mb-1">What happened</p>
            <p className="text-white">{move.what_happened}</p>
          </div>
          
          {/* Move idea */}
          {move.move_idea && (
            <div>
              <p className="text-xs text-zinc-500 mb-1 flex items-center gap-1">
                <Lightbulb className="w-3 h-3" /> The idea
              </p>
              <p className="text-zinc-300">{move.move_idea}</p>
            </div>
          )}
          
          {/* Opponent's last idea */}
          {isUserMove && move.opponent_last_idea && (
            <div className="bg-amber-500/10 rounded-lg p-3 border border-amber-500/20">
              <p className="text-xs text-amber-400 mb-1 flex items-center gap-1">
                <Eye className="w-3 h-3" /> What opponent was trying to do
              </p>
              <p className="text-zinc-300">{move.opponent_last_idea}</p>
            </div>
          )}
          
          {/* SIDELINE WARNING — V3: Empathetic, with main line theory */}
          {move.is_sideline && move.sideline_warning && (
            <div className="bg-orange-500/10 rounded-lg p-3 border border-orange-500/30" data-testid="sideline-warning">
              <p className="text-xs text-orange-400 mb-1 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Opening Theory
              </p>
              <p className="text-orange-200 text-sm">{move.sideline_warning}</p>
              
              {/* Main line moves */}
              {move.main_line_moves && move.main_line_moves.length > 0 && (
                <div className="mt-2 pt-2 border-t border-orange-500/20">
                  <p className="text-xs text-zinc-400 mb-1">Main line moves:</p>
                  <div className="flex gap-2">
                    {move.main_line_moves.map((m, i) => (
                      <span key={i} className="text-white font-mono bg-zinc-800/60 px-2 py-0.5 rounded text-sm">
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              
              {/* V3: Main line theory explanations */}
              {move.main_line_theory && move.main_line_theory.lines && (
                <div className="mt-2 pt-2 border-t border-orange-500/20 space-y-1.5" data-testid="main-line-theory">
                  <p className="text-xs text-zinc-400 flex items-center gap-1">
                    <Sparkles className="w-3 h-3" /> Why these moves are recommended:
                  </p>
                  {Object.entries(move.main_line_theory.lines).map(([moveName, explanation]) => (
                    <div key={moveName} className="flex gap-2 text-sm">
                      <span className="text-white font-mono font-semibold shrink-0">{moveName}:</span>
                      <span className="text-zinc-400">{explanation}</span>
                    </div>
                  ))}
                  {move.main_line_theory.explanation && (
                    <p className="text-zinc-500 text-xs mt-1 italic">{move.main_line_theory.explanation}</p>
                  )}
                </div>
              )}
            </div>
          )}
          
          {/* Your focus (only when no sideline) */}
          {move.your_focus && !move.is_sideline && (
            <div className="bg-blue-500/10 rounded-lg p-3 border border-blue-500/20">
              <p className="text-xs text-blue-400 mb-1 flex items-center gap-1">
                <Target className="w-3 h-3" /> What to think about here
              </p>
              <p className="text-zinc-300">{move.your_focus}</p>
            </div>
          )}
        </div>
        
        {/* Mistake section */}
        {isMistake && (
          <div className="border-t border-red-500/20 pt-4 space-y-3">
            <p className="text-red-400 font-medium flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              This was a {move.mistake_type || "mistake"}
            </p>
            
            {move.what_you_missed && (
              <div>
                <p className="text-xs text-zinc-500 mb-1">What you missed</p>
                <p className="text-zinc-300">{move.what_you_missed}</p>
              </div>
            )}
            
            {move.better_move && (
              <div className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-500/20">
                <p className="text-xs text-emerald-400 mb-1">Better move</p>
                <p className="text-white font-mono text-lg">{move.better_move}</p>
                {move.better_move_idea && (
                  <p className="text-zinc-400 text-sm mt-1">{move.better_move_idea}</p>
                )}
              </div>
            )}
            
            {move.principle && (
              <div className="bg-zinc-800/50 rounded-lg p-3">
                <p className="text-xs text-amber-400 mb-1 flex items-center gap-1">
                  <BookOpen className="w-3 h-3" /> Remember this
                </p>
                <p className="text-white italic">"{move.principle}"</p>
              </div>
            )}
          </div>
        )}
        
        {/* Good move praise */}
        {isGoodMove && move.praise && (
          <div className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-500/20">
            <p className="text-emerald-400">{move.praise}</p>
          </div>
        )}
        
        {/* Feedback button */}
        <div className="flex justify-end pt-2">
          {hasFeedback ? (
            <span className="text-xs text-zinc-500 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> Feedback sent
            </span>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              onClick={onFeedbackClick}
              className="text-xs text-zinc-500 hover:text-red-400"
              data-testid="btn-not-helpful"
            >
              <ThumbsDown className="w-3 h-3 mr-1" />
              Not helpful
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
};


/**
 * Feedback Panel
 */
const FeedbackPanel = ({ move, feedbackText, setFeedbackText, onSubmit, onCancel, submitting }) => {
  return (
    <Card className="bg-zinc-900 border-zinc-700" data-testid="feedback-panel">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-white">What should the explanation say?</p>
          <Button variant="ghost" size="icon" onClick={onCancel} className="h-6 w-6">
            <X className="w-4 h-4" />
          </Button>
        </div>
        
        <p className="text-xs text-zinc-500">
          Current: "{move.what_happened}"
        </p>
        
        <Textarea
          value={feedbackText}
          onChange={(e) => setFeedbackText(e.target.value)}
          placeholder="Write a better explanation for this position..."
          className="min-h-[100px] bg-zinc-800 border-zinc-700 text-white"
          data-testid="feedback-textarea"
        />
        
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button 
            size="sm" 
            onClick={onSubmit}
            disabled={!feedbackText.trim() || submitting}
            data-testid="submit-feedback-btn"
          >
            {submitting ? (
              <Loader2 className="w-4 h-4 animate-spin mr-1" />
            ) : (
              <Send className="w-4 h-4 mr-1" />
            )}
            Submit
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};


/**
 * Move List
 */
const MoveList = ({ decryptionData, currentMoveIndex, onMoveClick, userColor }) => {
  if (!decryptionData || decryptionData.length === 0) return null;
  
  const movePairs = [];
  for (let i = 0; i < decryptionData.length; i += 2) {
    const whiteMove = decryptionData[i];
    const blackMove = decryptionData[i + 1] || null;
    movePairs.push({ 
      moveNumber: whiteMove.move_number, 
      white: whiteMove, 
      black: blackMove,
      whiteIndex: i,
      blackIndex: i + 1
    });
  }
  
  return (
    <ScrollArea className="h-[180px] rounded-lg border border-zinc-800 bg-zinc-900/30">
      <div className="p-2 space-y-1">
        {movePairs.map((pair) => (
          <div key={pair.moveNumber} className="flex items-center gap-1 text-sm">
            <span className="w-8 text-zinc-500 text-right">{pair.moveNumber}.</span>
            
            <button
              onClick={() => onMoveClick(pair.whiteIndex)}
              className={`px-2 py-0.5 rounded font-mono ${
                currentMoveIndex === pair.whiteIndex 
                  ? 'bg-emerald-500/30 text-white' 
                  : pair.white.is_mistake 
                    ? 'text-red-400 hover:bg-red-500/10' 
                    : pair.white.is_sideline
                      ? 'text-orange-400 hover:bg-orange-500/10'
                      : 'text-zinc-300 hover:bg-zinc-800'
              }`}
            >
              {pair.white.move_san}
              {pair.white.is_mistake && <span className="text-red-400 ml-0.5">?</span>}
              {pair.white.is_sideline && !pair.white.is_mistake && <span className="text-orange-400 ml-0.5">~</span>}
            </button>
            
            {pair.black && (
              <button
                onClick={() => onMoveClick(pair.blackIndex)}
                className={`px-2 py-0.5 rounded font-mono ${
                  currentMoveIndex === pair.blackIndex 
                    ? 'bg-emerald-500/30 text-white' 
                    : pair.black.is_mistake 
                      ? 'text-red-400 hover:bg-red-500/10' 
                      : pair.black.is_sideline
                        ? 'text-orange-400 hover:bg-orange-500/10'
                        : 'text-zinc-300 hover:bg-zinc-800'
                }`}
              >
                {pair.black.move_san}
                {pair.black.is_mistake && <span className="text-red-400 ml-0.5">?</span>}
                {pair.black.is_sideline && !pair.black.is_mistake && <span className="text-orange-400 ml-0.5">~</span>}
              </button>
            )}
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};


const getLastMoveSquares = (move) => {
  if (!move || !move.fen_before || !move.move_san) return null;
  
  try {
    const chess = new Chess(move.fen_before);
    const parsed = chess.move(move.move_san);
    if (parsed) {
      return [parsed.from, parsed.to];
    }
  } catch (e) {
    // Ignore parsing errors
  }
  
  return null;
};


export default GameDecryption;
