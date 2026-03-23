/**
 * GameDecryption.jsx - V4: Thinking Simulator
 * 
 * "You are NOT building a move explanation system.
 *  You ARE building a thinking simulator of a strong chess player."
 * 
 * Card Structure:
 * - TOP: Narrative (flowing story — THE HOOK)
 * - MIDDLE: Thinking Gap (BIG, BOLD — THE MOAT)
 * - BOTTOM: Expandable breakdown (position, better plan, principle)
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
  ChevronDown,
  ChevronUp,
  Sparkles,
  Zap
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const GameDecryption = ({ gameId, analysis, pgn, userColor, onBack }) => {
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

  const fetchDecryptionData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${API}/coach/decryption/${gameId}`, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch decryption data");
      const data = await res.json();
      if (data.error || !data.decryption_data) {
        setError(data.error || "Decryption data not available");
        if (data.needs_reanalysis) setError("This game needs re-analysis for the decryption feature.");
        return;
      }
      setDecryptionData(data.decryption_data);
      setSummary(data.summary);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const goForward = useCallback(() => {
    if (!decryptionData || currentMoveIndex >= decryptionData.length - 1) return;
    const i = currentMoveIndex + 1;
    setCurrentMoveIndex(i);
    setBoardFen(decryptionData[i].fen_after);
  }, [decryptionData, currentMoveIndex]);

  const goBackward = useCallback(() => {
    if (!decryptionData || currentMoveIndex < 0) return;
    const i = currentMoveIndex - 1;
    setCurrentMoveIndex(i);
    setBoardFen(i === -1 ? "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" : decryptionData[i].fen_after);
  }, [decryptionData, currentMoveIndex]);

  const goToStart = useCallback(() => {
    setCurrentMoveIndex(-1);
    setBoardFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  }, []);

  const goToEnd = useCallback(() => {
    if (!decryptionData?.length) return;
    const i = decryptionData.length - 1;
    setCurrentMoveIndex(i);
    setBoardFen(decryptionData[i].fen_after);
  }, [decryptionData]);

  const goToMove = useCallback((i) => {
    if (!decryptionData || i < -1 || i >= decryptionData.length) return;
    setCurrentMoveIndex(i);
    setBoardFen(i === -1 ? "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" : decryptionData[i].fen_after);
  }, [decryptionData]);

  const handleSubmitFeedback = async () => {
    if (!feedbackText.trim() || currentMoveIndex < 0) return;
    const m = decryptionData[currentMoveIndex];
    try {
      setSubmittingFeedback(true);
      const res = await fetch(`${API}/coach/decryption/feedback`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({
          game_id: gameId, move_number: m.move_number, fen: m.fen_before,
          coach_explanation: m.narrative || "", user_feedback: "not_helpful",
          user_correction: feedbackText, is_user_move: m.is_user_move
        })
      });
      if (res.ok) {
        toast.success("Feedback saved — thanks!");
        setSubmittedFeedback(prev => new Set([...prev, currentMoveIndex]));
        setFeedbackOpen(false);
        setFeedbackText("");
      }
    } catch (err) { toast.error("Failed to send feedback"); }
    finally { setSubmittingFeedback(false); }
  };

  const currentMove = currentMoveIndex >= 0 ? decryptionData?.[currentMoveIndex] : null;
  const orientation = userColor === "black" ? "black" : "white";

  if (loading) return (
    <div className="flex items-center justify-center h-96" data-testid="decryption-loading">
      <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
      <span className="ml-3 text-zinc-400">Decrypting your game...</span>
    </div>
  );

  if (error) return (
    <div className="flex flex-col items-center justify-center h-96 text-center" data-testid="decryption-error">
      <AlertTriangle className="w-12 h-12 text-amber-400 mb-4" />
      <p className="text-zinc-300 mb-2">{error}</p>
      <Button variant="outline" onClick={fetchDecryptionData} className="mt-4">Try Again</Button>
    </div>
  );

  return (
    <div ref={containerRef} className="flex flex-col lg:flex-row gap-4 p-4" data-testid="game-decryption">
      {/* LEFT: Board + Controls */}
      <div className="lg:w-1/2 space-y-4">
        <div className="aspect-square max-w-[500px] mx-auto">
          <LichessBoard fen={boardFen} orientation={orientation} viewOnly={true}
            lastMove={currentMove ? getLastMoveSquares(currentMove) : null} />
        </div>

        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="icon" onClick={goToStart} disabled={currentMoveIndex === -1} data-testid="btn-go-start"><ChevronsLeft className="w-4 h-4" /></Button>
          <Button variant="outline" size="icon" onClick={goBackward} disabled={currentMoveIndex === -1} data-testid="btn-go-back"><ChevronLeft className="w-4 h-4" /></Button>
          <span className="px-4 text-sm text-zinc-400 min-w-[80px] text-center">
            {currentMoveIndex === -1 ? "Start" : `Move ${currentMove?.move_number || ""}`}
            {currentMove && !currentMove.is_user_move && " (opp)"}
          </span>
          <Button variant="outline" size="icon" onClick={goForward} disabled={!decryptionData || currentMoveIndex >= decryptionData.length - 1} data-testid="btn-go-forward"><ChevronRight className="w-4 h-4" /></Button>
          <Button variant="outline" size="icon" onClick={goToEnd} disabled={!decryptionData || currentMoveIndex >= decryptionData.length - 1} data-testid="btn-go-end"><ChevronsRight className="w-4 h-4" /></Button>
        </div>

        <MoveList decryptionData={decryptionData} currentMoveIndex={currentMoveIndex} onMoveClick={goToMove} />
      </div>

      {/* RIGHT: Coaching */}
      <div className="lg:w-1/2 space-y-4">
        {currentMoveIndex === -1
          ? <GameSummaryCard summary={summary} />
          : <MoveCoachingCard move={currentMove} hasFeedback={submittedFeedback.has(currentMoveIndex)} onFeedbackClick={() => setFeedbackOpen(true)} />
        }
        {feedbackOpen && currentMove && (
          <FeedbackPanel move={currentMove} feedbackText={feedbackText} setFeedbackText={setFeedbackText}
            onSubmit={handleSubmitFeedback} onCancel={() => { setFeedbackOpen(false); setFeedbackText(""); }}
            submitting={submittingFeedback} />
        )}
        <div className="text-xs text-zinc-600 text-center">Arrow keys: left/right navigate, up = start, down = end</div>
      </div>
    </div>
  );
};


// ─── OPENING INTRO ──────────────────────────────────────────────────

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
          <p className="text-xs text-emerald-400 mb-1 flex items-center gap-1"><Swords className="w-3 h-3" /> Your Plan</p>
          <p className="text-zinc-300 text-xs leading-relaxed">{intro.your_plan}</p>
        </div>
        <div className="bg-zinc-800/50 rounded-lg p-3">
          <p className="text-xs text-red-400 mb-1 flex items-center gap-1"><Target className="w-3 h-3" /> Their Plan</p>
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


// ─── GAME SUMMARY ───────────────────────────────────────────────────

const GameSummaryCard = ({ summary }) => {
  if (!summary) return null;
  return (
    <Card className="bg-zinc-900/50 border-zinc-800" data-testid="game-summary">
      <CardContent className="p-5 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <BookOpen className="w-5 h-5 text-emerald-400" />
          <h3 className="font-semibold text-white">Game Overview</h3>
        </div>
        {summary.opening_name && (
          <div className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-500/20">
            <p className="text-xs text-emerald-400 mb-1">Opening</p>
            <p className="text-white font-medium">{summary.opening_name}</p>
          </div>
        )}
        {summary.opening_introduction && <OpeningIntroCard intro={summary.opening_introduction} />}
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
        <div className="bg-zinc-800/30 rounded-lg p-4">
          <p className="text-zinc-300 text-sm">{summary.overall_message}</p>
        </div>
        {summary.key_moments?.length > 0 && (
          <div>
            <p className="text-xs text-zinc-500 mb-2">Key Moments</p>
            <div className="space-y-1">
              {summary.key_moments.slice(0, 3).map((m, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <Badge variant="destructive" className="text-xs shrink-0">Move {m.move_number}</Badge>
                  <span className="text-zinc-400 truncate">{m.summary}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="pt-2 border-t border-zinc-800">
          <p className="text-sm text-emerald-400 flex items-center gap-2">
            <ChevronRight className="w-4 h-4" /> Press right arrow to begin
          </p>
        </div>
      </CardContent>
    </Card>
  );
};


// ─── MOVE COACHING CARD (V4) ────────────────────────────────────────

const MoveCoachingCard = ({ move, hasFeedback, onFeedbackClick }) => {
  const [expanded, setExpanded] = useState(false);
  if (!move) return null;

  const isMistake = move.is_mistake;
  const hasLLM = !!move.thinking_gap || !!move.position_breakdown;
  const isUser = move.is_user_move;

  // Determine card border color
  const borderClass = isMistake
    ? 'border-red-500/30 bg-red-950/10'
    : move.cp_loss <= 10 && isUser
      ? 'border-emerald-500/30 bg-emerald-950/10'
      : 'border-zinc-800 bg-zinc-900/50';

  return (
    <Card className={`border ${borderClass}`} data-testid="move-coaching-card">
      <CardContent className="p-5 space-y-3">
        {/* ─── HEADER ──────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isMistake ? <AlertTriangle className="w-5 h-5 text-red-400" />
              : move.cp_loss <= 10 && isUser ? <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              : <Brain className="w-5 h-5 text-blue-400" />}
            <span className="font-bold text-white text-lg">{move.move_san}</span>
            <Badge variant={isUser ? "default" : "secondary"} className="text-xs">
              {isUser ? "Your move" : "Opponent"}
            </Badge>
            {move.mistake_analysis?.type && (
              <Badge variant="outline" className="text-xs text-orange-400 border-orange-500/30">
                {move.mistake_analysis.type}
              </Badge>
            )}
          </div>
          <Badge variant="outline" className="text-xs text-zinc-400">{move.phase}</Badge>
        </div>

        {/* ─── NARRATIVE (THE HOOK) ────────────────────────── */}
        {move.narrative && (
          <div className="leading-relaxed" data-testid="move-narrative">
            <p className={`text-sm ${hasLLM ? 'text-zinc-200' : 'text-zinc-400'}`}>
              {move.narrative}
            </p>
          </div>
        )}

        {/* ─── THINKING GAP (BIG + BOLD — THE MOAT) ──────── */}
        {move.thinking_gap && (
          <div className="bg-gradient-to-r from-red-500/15 to-orange-500/15 rounded-lg p-4 border border-red-500/30" data-testid="thinking-gap">
            <div className="flex items-center gap-2 mb-1">
              <Zap className="w-4 h-4 text-red-400" />
              <p className="text-xs font-semibold text-red-400 uppercase tracking-wider">You Missed This</p>
            </div>
            <p className="text-white font-medium text-base leading-snug">{move.thinking_gap}</p>
          </div>
        )}

        {/* ─── SIDELINE / OPENING THEORY ─────────────────── */}
        {move.is_sideline && move.sideline_warning && (
          <div className="bg-orange-500/10 rounded-lg p-3 border border-orange-500/30" data-testid="sideline-warning">
            <p className="text-xs text-orange-400 mb-1 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> Opening Theory
            </p>
            <p className="text-orange-200 text-sm">{move.sideline_warning}</p>
            {move.main_line_moves?.length > 0 && (
              <div className="mt-2 pt-2 border-t border-orange-500/20">
                <p className="text-xs text-zinc-400 mb-1">Main line moves:</p>
                <div className="flex gap-2">
                  {move.main_line_moves.map((m, i) => (
                    <span key={i} className="text-white font-mono bg-zinc-800/60 px-2 py-0.5 rounded text-sm">{m}</span>
                  ))}
                </div>
              </div>
            )}
            {move.main_line_theory?.lines && (
              <div className="mt-2 pt-2 border-t border-orange-500/20 space-y-1" data-testid="main-line-theory">
                <p className="text-xs text-zinc-400 flex items-center gap-1"><Sparkles className="w-3 h-3" /> Why these moves:</p>
                {Object.entries(move.main_line_theory.lines).map(([name, desc]) => (
                  <div key={name} className="flex gap-2 text-sm">
                    <span className="text-white font-mono font-semibold shrink-0">{name}:</span>
                    <span className="text-zinc-400">{desc}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ─── BETTER PLAN ───────────────────────────────── */}
        {move.better_plan && (
          <div className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-500/20" data-testid="better-plan">
            <p className="text-xs text-emerald-400 mb-1">Better plan</p>
            <p className="text-white font-mono text-lg">{move.better_plan.move}</p>
            {move.better_plan.idea && <p className="text-zinc-300 text-sm mt-1">{move.better_plan.idea}</p>}
            {move.better_plan.what_happens_next && (
              <p className="text-zinc-500 text-xs mt-1 italic">Then: {move.better_plan.what_happens_next}</p>
            )}
          </div>
        )}

        {/* ─── EXPANDABLE DETAILS ────────────────────────── */}
        {hasLLM && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center justify-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 transition-colors py-1"
            data-testid="toggle-details"
          >
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {expanded ? "Less detail" : "More detail"}
          </button>
        )}

        {expanded && (
          <div className="space-y-3 pt-1 border-t border-zinc-800/50">
            {/* Position Breakdown */}
            {move.position_breakdown && (
              <div className="space-y-2" data-testid="position-breakdown">
                {move.position_breakdown.your_intent && (
                  <div>
                    <p className="text-xs text-blue-400 mb-0.5">Your intent</p>
                    <p className="text-zinc-400 text-sm">{move.position_breakdown.your_intent}</p>
                  </div>
                )}
                {move.position_breakdown.opponent_counterplay && (
                  <div>
                    <p className="text-xs text-amber-400 mb-0.5">Opponent gets</p>
                    <p className="text-zinc-400 text-sm">{move.position_breakdown.opponent_counterplay}</p>
                  </div>
                )}
                {move.position_breakdown.hidden_problem && (
                  <div>
                    <p className="text-xs text-red-400 mb-0.5">Hidden problem</p>
                    <p className="text-zinc-400 text-sm">{move.position_breakdown.hidden_problem}</p>
                  </div>
                )}
              </div>
            )}

            {/* Mistake Analysis */}
            {move.mistake_analysis && (
              <div data-testid="mistake-analysis">
                <p className="text-xs text-red-400 mb-0.5">Why it fails</p>
                <p className="text-zinc-400 text-sm">{move.mistake_analysis.why_it_fails}</p>
              </div>
            )}

            {/* Principle */}
            {move.principle && (
              <div className="bg-zinc-800/50 rounded-lg p-3" data-testid="principle">
                <p className="text-xs text-amber-400 mb-1 flex items-center gap-1"><BookOpen className="w-3 h-3" /> Remember this</p>
                <p className="text-white italic text-sm">"{move.principle}"</p>
              </div>
            )}
          </div>
        )}

        {/* ─── FEEDBACK ──────────────────────────────────── */}
        <div className="flex items-center justify-between pt-2">
          {move.confidence && (
            <span className={`text-xs ${move.confidence === 'high' ? 'text-emerald-500' : move.confidence === 'medium' ? 'text-amber-500' : 'text-zinc-500'}`}>
              {move.confidence} confidence
            </span>
          )}
          <div className="ml-auto">
            {hasFeedback
              ? <span className="text-xs text-zinc-500 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Feedback sent</span>
              : <Button variant="ghost" size="sm" onClick={onFeedbackClick} className="text-xs text-zinc-500 hover:text-red-400" data-testid="btn-not-helpful">
                  <ThumbsDown className="w-3 h-3 mr-1" /> Not helpful
                </Button>
            }
          </div>
        </div>
      </CardContent>
    </Card>
  );
};


// ─── FEEDBACK PANEL ─────────────────────────────────────────────────

const FeedbackPanel = ({ move, feedbackText, setFeedbackText, onSubmit, onCancel, submitting }) => (
  <Card className="bg-zinc-900 border-zinc-700" data-testid="feedback-panel">
    <CardContent className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-white">What should the explanation say?</p>
        <Button variant="ghost" size="icon" onClick={onCancel} className="h-6 w-6"><X className="w-4 h-4" /></Button>
      </div>
      <Textarea value={feedbackText} onChange={(e) => setFeedbackText(e.target.value)}
        placeholder="Write a better explanation..." className="min-h-[100px] bg-zinc-800 border-zinc-700 text-white" data-testid="feedback-textarea" />
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel}>Cancel</Button>
        <Button size="sm" onClick={onSubmit} disabled={!feedbackText.trim() || submitting} data-testid="submit-feedback-btn">
          {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />} Submit
        </Button>
      </div>
    </CardContent>
  </Card>
);


// ─── MOVE LIST ──────────────────────────────────────────────────────

const MoveList = ({ decryptionData, currentMoveIndex, onMoveClick }) => {
  if (!decryptionData?.length) return null;
  const pairs = [];
  for (let i = 0; i < decryptionData.length; i += 2) {
    pairs.push({
      num: decryptionData[i].move_number,
      w: decryptionData[i], b: decryptionData[i + 1] || null,
      wi: i, bi: i + 1
    });
  }
  const moveClass = (m, idx) => {
    if (currentMoveIndex === idx) return 'bg-emerald-500/30 text-white';
    if (m.is_mistake) return 'text-red-400 hover:bg-red-500/10';
    if (m.thinking_gap) return 'text-orange-400 hover:bg-orange-500/10';
    if (m.is_sideline) return 'text-orange-400 hover:bg-orange-500/10';
    return 'text-zinc-300 hover:bg-zinc-800';
  };
  const indicator = (m) => {
    if (m.is_mistake) return <span className="text-red-400 ml-0.5">?</span>;
    if (m.thinking_gap && !m.is_mistake) return <span className="text-orange-400 ml-0.5">!</span>;
    if (m.is_sideline) return <span className="text-orange-400 ml-0.5">~</span>;
    return null;
  };

  return (
    <ScrollArea className="h-[180px] rounded-lg border border-zinc-800 bg-zinc-900/30">
      <div className="p-2 space-y-1">
        {pairs.map(p => (
          <div key={p.num} className="flex items-center gap-1 text-sm">
            <span className="w-8 text-zinc-500 text-right">{p.num}.</span>
            <button onClick={() => onMoveClick(p.wi)} className={`px-2 py-0.5 rounded font-mono ${moveClass(p.w, p.wi)}`}>
              {p.w.move_san}{indicator(p.w)}
            </button>
            {p.b && (
              <button onClick={() => onMoveClick(p.bi)} className={`px-2 py-0.5 rounded font-mono ${moveClass(p.b, p.bi)}`}>
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
  } catch { return null; }
};


export default GameDecryption;
