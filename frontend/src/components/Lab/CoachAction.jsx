/**
 * CoachAction.jsx — "Diagnose → Drill → Track"
 * 
 * Replaces the narrative Coach Review with an action-oriented format:
 * 1. WHAT WENT WRONG — One line diagnosis
 * 2. FIX IT NOW — Solve practice positions
 * 3. BEFORE NEXT GAME — One rule
 * 4. YOUR TREND — Getting better or worse?
 */

import { useState, useEffect, useCallback } from "react";
import { Chess } from "chess.js";
import { API } from "@/App";
import { motion, AnimatePresence } from "framer-motion";
import LichessBoard from "@/components/LichessBoard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  Loader2, AlertTriangle, Target, ChevronRight,
  CheckCircle2, XCircle, TrendingUp, TrendingDown,
  Minus, Lightbulb, Zap, RotateCcw, Brain,
} from "lucide-react";

const DIAGNOSIS_COLORS = {
  THROW: "text-red-600 bg-red-500/10 border-red-500/20",
  MATE_BLIND: "text-red-500 bg-red-500/10 border-red-500/20",
  SLOW_BLEED: "text-amber-600 bg-amber-500/10 border-amber-500/20",
  OPENING_COLLAPSE: "text-orange-500 bg-orange-500/10 border-orange-500/20",
  PIECE_GIVEAWAY: "text-orange-500 bg-orange-500/10 border-orange-500/20",
  TACTICAL_MISS: "text-amber-600 bg-amber-500/10 border-amber-500/20",
  TIME_COLLAPSE: "text-orange-500 bg-orange-500/10 border-orange-500/20",
  WON_CLEAN: "text-emerald-600 bg-emerald-500/10 border-emerald-500/20",
  WON_OPPONENT_BLUNDER: "text-yellow-600 bg-yellow-500/10 border-yellow-500/20",
  DRAW: "text-gray-500 bg-gray-500/10 border-gray-500/20",
};

// ─── Drill Board ─────────────────────────────────────────────

const DrillPosition = ({ position, index, onSolved }) => {
  const [state, setState] = useState("ready"); // ready | correct | wrong
  const [arrows, setArrows] = useState([]);
  const fen = position.fen;
  const bestUci = position.best_move_uci || "";

  // Determine which color to move from FEN
  const colorToMove = fen?.split(" ")[1] === "w" ? "white" : "black";

  const handleMove = useCallback((moveData) => {
    if (state !== "ready") return false;
    const userUci = moveData.from + moveData.to;

    if (userUci === bestUci.slice(0, 4)) {
      setState("correct");
      setArrows([[moveData.from, moveData.to, "green"]]);
      onSolved?.();
      return true;
    } else {
      setState("wrong");
      setArrows([
        [moveData.from, moveData.to, "red"],
        [bestUci.slice(0, 2), bestUci.slice(2, 4), "green"],
      ]);
      return false;
    }
  }, [state, bestUci, onSolved]);

  const retry = () => {
    setState("ready");
    setArrows([]);
  };

  return (
    <div className="border border-border rounded p-3" data-testid={`drill-position-${index}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-muted-foreground">Position {index + 1}</span>
        <div className="flex items-center gap-2">
          {position.source === "your_game" && (
            <Badge variant="outline" className="text-[10px]">From your game</Badge>
          )}
          {state === "correct" && <CheckCircle2 className="w-4 h-4 text-emerald-600" />}
          {state === "wrong" && <XCircle className="w-4 h-4 text-red-500" />}
        </div>
      </div>

      <div className="w-full max-w-[240px] aspect-square mx-auto mb-2">
        <LichessBoard
          fen={fen}
          orientation={colorToMove}
          viewOnly={state !== "ready"}
          interactive={state === "ready"}
          movableColor={state === "ready" ? colorToMove : undefined}
          arrows={arrows}
          onMove={state === "ready" ? handleMove : undefined}
        />
      </div>

      {state === "ready" && (
        <p className="text-xs text-center text-muted-foreground">Find the best move</p>
      )}
      {state === "correct" && (
        <p className="text-xs text-center text-emerald-600 font-medium">
          {position.best_move}
        </p>
      )}
      {state === "wrong" && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-red-500">Best: <span className="font-mono">{position.best_move}</span></p>
          <Button variant="ghost" size="sm" className="text-xs h-6" onClick={retry}>
            <RotateCcw className="w-3 h-3 mr-1" /> Retry
          </Button>
        </div>
      )}
    </div>
  );
};

// ─── Main Component ──────────────────────────────────────────

const CoachAction = ({ gameId, onMoveClick }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [drillsSolved, setDrillsSolved] = useState(0);

  useEffect(() => {
    if (!gameId) return;
    const fetch_ = async () => {
      setLoading(true);
      setError(null);
      setDrillsSolved(0);
      try {
        const res = await fetch(`${API}/lab/${gameId}/coach-action`, { credentials: "include" });
        if (!res.ok) throw new Error("Failed to load");
        setData(await res.json());
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetch_();
  }, [gameId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="coach-action-loading">
        <Loader2 className="w-5 h-5 animate-spin text-primary mr-3" />
        <span className="text-sm text-muted-foreground">Analyzing...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-16" data-testid="coach-action-error">
        <AlertTriangle className="w-8 h-8 mx-auto mb-3 text-muted-foreground" strokeWidth={1.5} />
        <p className="text-sm text-muted-foreground">{error || "No data"}</p>
      </div>
    );
  }

  const { diagnosis, drill, rule, trend, game_stats, brain } = data;
  const diagColors = DIAGNOSIS_COLORS[diagnosis.type] || DIAGNOSIS_COLORS.DRAW;
  const worstMove = diagnosis.worst_move;
  const isWin = diagnosis.type === "WON_CLEAN" || diagnosis.type === "WON_OPPONENT_BLUNDER";

  return (
    <div className="space-y-6" data-testid="coach-action-panel">

      {/* ─── 1. DIAGNOSIS — Hero Section ──────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className={`border rounded-lg overflow-hidden ${diagColors}`}>
          <div className="p-5">
            <div className="flex items-center gap-2 mb-1">
              <AlertTriangle className="w-4 h-4 opacity-70" strokeWidth={1.5} />
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] opacity-60">Diagnosis</span>
            </div>
            <p className="text-xl font-bold tracking-tight mb-1.5">{diagnosis.label}</p>
            <p className="text-sm opacity-80 leading-relaxed">{diagnosis.short}</p>
          </div>
          
          {/* Quick stats bar */}
          {game_stats && (
            <div className="flex items-center gap-0 border-t border-current/10 divide-x divide-current/10 text-xs">
              {game_stats.accuracy != null && (
                <div className="flex-1 text-center py-2.5">
                  <span className="font-bold text-sm" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{game_stats.accuracy.toFixed(0)}%</span>
                  <span className="block text-[10px] opacity-50 mt-0.5">Accuracy</span>
                </div>
              )}
              <div className="flex-1 text-center py-2.5">
                <span className="font-bold text-sm text-red-500" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{game_stats.blunders || 0}</span>
                <span className="block text-[10px] opacity-50 mt-0.5">Blunders</span>
              </div>
              <div className="flex-1 text-center py-2.5">
                <span className="font-bold text-sm text-amber-500" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{game_stats.mistakes || 0}</span>
                <span className="block text-[10px] opacity-50 mt-0.5">Mistakes</span>
              </div>
            </div>
          )}
        </div>

        {/* Worst move — clickable with position context */}
        {worstMove && worstMove.cp_loss >= 100 && (
          <button
            onClick={() => onMoveClick?.(worstMove.move_number, worstMove.move_uci, worstMove.best_move_uci)}
            className="mt-3 w-full text-left p-4 border border-border rounded-lg hover:border-primary/40 hover:bg-primary/5 transition-all group"
            data-testid="worst-move-btn"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                  <span className="text-xs font-bold text-red-500" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{worstMove.move_number}</span>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-foreground">{worstMove.move_san}</span>
                    <span className="text-xs text-muted-foreground">→</span>
                    <span className="font-mono text-sm text-primary font-medium">{worstMove.best_move}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Lost {(worstMove.cp_loss / 100).toFixed(1)} pawns of advantage
                  </p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
          </button>
        )}
      </motion.div>

      {/* ─── 2. FIX IT NOW ────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Target className="w-4 h-4 text-primary" strokeWidth={1.5} />
          <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground">Fix It Now</span>
          {drill.count > 0 && drillsSolved > 0 && (
            <Badge variant="outline" className="text-[10px] ml-auto">
              {drillsSolved}/{drill.count} solved
            </Badge>
          )}
        </div>

        {drill.count > 0 ? (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Solve these positions — same mistake type. Train your pattern recognition.
            </p>
            {drill.positions.map((pos, i) => (
              <DrillPosition
                key={pos.position_id || i}
                position={pos}
                index={i}
                onSolved={() => setDrillsSolved(prev => prev + 1)}
              />
            ))}

            {drillsSolved === drill.count && drill.count > 0 && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-center">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 mx-auto mb-1" />
                <p className="text-sm text-emerald-600 font-medium">All solved. Nice work.</p>
              </div>
            )}
          </div>
        ) : (
          <div className="p-4 border border-dashed border-border rounded-lg text-center">
            <Target className="w-5 h-5 text-muted-foreground/40 mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">
              {isWin ? "No drill needed — you played well!" : "Practice positions will appear as you play more games with similar patterns."}
            </p>
          </div>
        )}
      </motion.div>

      {/* ─── 3. BEFORE NEXT GAME ──────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb className="w-4 h-4 text-amber-500" strokeWidth={1.5} />
          <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground">Before Next Game</span>
        </div>

        <div className="relative bg-amber-500/5 border border-amber-500/20 rounded-lg p-5">
          <div className="absolute top-0 left-5 w-0.5 h-full bg-amber-500/20 -translate-y-3" />
          <p className="text-sm text-foreground font-medium leading-relaxed pl-4">{rule}</p>
        </div>
      </motion.div>

      {/* ─── 4. BRAIN FOCUS (if available) ─────────────── */}
      {brain?.focus_message && brain.top_weakness && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-4 h-4 text-purple-500" strokeWidth={1.5} />
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground">Your Brain Says</span>
          </div>
          <div className="bg-purple-500/5 border border-purple-500/15 rounded-lg p-4">
            <p className="text-sm text-foreground leading-relaxed">{brain.focus_message}</p>
          </div>
        </motion.div>
      )}

      {/* ─── 5. YOUR TREND ────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <div className="flex items-center gap-2 mb-3">
          {trend.direction === "improving" ? (
            <TrendingUp className="w-4 h-4 text-emerald-600" strokeWidth={1.5} />
          ) : trend.direction === "worsening" ? (
            <TrendingDown className="w-4 h-4 text-red-500" strokeWidth={1.5} />
          ) : (
            <Minus className="w-4 h-4 text-muted-foreground" strokeWidth={1.5} />
          )}
          <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground">Your Trend</span>
        </div>

        <p className="text-sm text-muted-foreground">{trend.message}</p>

        {trend.has_data && trend.occurrences > 0 && (
          <div className="mt-2 flex items-center gap-3">
            <div className="flex-1 bg-muted rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all ${
                  trend.direction === "improving" ? "bg-emerald-500" :
                  trend.direction === "worsening" ? "bg-red-500" : "bg-amber-500"
                }`}
                style={{ width: `${Math.min(100, (trend.occurrences / trend.total_games) * 100)}%` }}
              />
            </div>
            <span className="text-xs font-mono text-muted-foreground">
              {trend.occurrences}/{trend.total_games}
            </span>
          </div>
        )}
      </motion.div>
    </div>
  );
};

export default CoachAction;
