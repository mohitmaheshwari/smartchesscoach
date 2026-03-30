/**
 * CandidateMoves.jsx — "Your 3 best options" + Opening Curriculum Guide
 * 
 * Shows before each move:
 * 1. Curriculum guidance (if in a known opening): "Play Bf4 — THE London move"
 * 2. 3 candidate moves from Stockfish with explanations
 * 3. Position hint
 * 4. Trap warnings
 * 5. Golden rules
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { 
  Loader2, Lightbulb, ChevronDown, ChevronUp, 
  Star, Zap, Shield, Target, AlertTriangle, BookOpen,
} from "lucide-react";

const TYPE_ICONS = {
  tactical: Zap,
  counter_attack: Zap,
  development: Star,
  central: Target,
  king_safety: Shield,
  prophylactic: Shield,
  positional: Target,
  engine_choice: Star,
};

const CandidateMoves = ({ sessionId, fen, isPlayerTurn, onHighlightMove, openingKey }) => {
  const [candidates, setCandidates] = useState([]);
  const [hint, setHint] = useState("");
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [lastFetchedFen, setLastFetchedFen] = useState(null);
  
  // Curriculum guidance
  const [guidance, setGuidance] = useState(null);

  useEffect(() => {
    if (!sessionId || !fen || !isPlayerTurn) {
      setCandidates([]);
      setHint("");
      setGuidance(null);
      return;
    }

    if (fen === lastFetchedFen) return;

    const fetchAll = async () => {
      setLoading(true);
      try {
        // Fetch both in parallel
        const [candRes, guideRes] = await Promise.all([
          fetch(`${API}/coach/play/candidates`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ session_id: sessionId }),
          }),
          fetch(`${API}/coach/play/opening-guide`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ session_id: sessionId, opening_key: openingKey || "london_system" }),
          }).catch(() => null),
        ]);

        if (candRes.ok) {
          const data = await candRes.json();
          setCandidates(data.candidates || []);
          setHint(data.position_hint || "");
        }

        if (guideRes && guideRes.ok) {
          const data = await guideRes.json();
          if (data.has_guidance) {
            setGuidance(data);
          } else {
            setGuidance(null);
          }
        }

        setLastFetchedFen(fen);
      } catch (e) {
        console.log("Guidance fetch failed:", e);
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
  }, [sessionId, fen, isPlayerTurn, lastFetchedFen, openingKey]);

  if (!isPlayerTurn || (!loading && candidates.length === 0 && !guidance)) return null;

  return (
    <div className="space-y-3" data-testid="candidate-moves">
      
      {/* Curriculum Guidance — "Your coach says" */}
      {guidance && guidance.suggested_move && (
        <motion.div
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="border border-primary/30 rounded bg-primary/[0.05] p-3"
        >
          <div className="flex items-center gap-2 mb-2">
            <BookOpen className="w-4 h-4 text-primary" strokeWidth={1.5} />
            <span className="text-xs font-medium text-foreground">Coach says</span>
            {guidance.position_name && guidance.position_name !== "Off Book" && (
              <Badge variant="outline" className="text-[9px] ml-auto">{guidance.position_name}</Badge>
            )}
          </div>

          {/* Suggested move */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl font-mono font-bold text-primary">{guidance.suggested_move}</span>
            <p className="text-sm text-foreground leading-snug">{guidance.idea}</p>
          </div>

          {/* Plan */}
          {guidance.plan && (
            <p className="text-xs text-muted-foreground mb-2">{guidance.plan}</p>
          )}

          {/* Trap Warning */}
          {guidance.trap_warning && (
            <div className="flex items-start gap-2 p-2 rounded bg-amber-500/10 border border-amber-500/20 mt-2">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" strokeWidth={1.5} />
              <div>
                <p className="text-xs font-medium text-amber-600">{guidance.trap_warning.name}</p>
                <p className="text-xs text-muted-foreground">{guidance.trap_warning.description}</p>
                {guidance.trap_warning.how_to_set && (
                  <p className="text-xs text-amber-600/80 mt-1">{guidance.trap_warning.how_to_set}</p>
                )}
              </div>
            </div>
          )}

          {/* Golden Rule */}
          {guidance.golden_rule && (
            <div className="flex items-center gap-1.5 mt-2">
              <Lightbulb className="w-3 h-3 text-primary/60" strokeWidth={1.5} />
              <p className="text-[11px] text-primary/80 italic">{guidance.golden_rule}</p>
            </div>
          )}
        </motion.div>
      )}

      {/* Off-book notice */}
      {guidance && !guidance.is_in_book && (
        <div className="text-xs text-muted-foreground italic px-1">
          You're off the main line — that's OK. Use the engine suggestions below.
        </div>
      )}

      {/* Stockfish Candidates — collapsible */}
      <div className="border border-border rounded overflow-hidden">
        <button 
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-3 py-2 hover:bg-muted/50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Target className="w-3.5 h-3.5 text-muted-foreground" strokeWidth={1.5} />
            <span className="text-xs text-muted-foreground">Engine picks</span>
          </div>
          {expanded ? <ChevronUp className="w-3 h-3 text-muted-foreground" /> : <ChevronDown className="w-3 h-3 text-muted-foreground" />}
        </button>

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              {hint && !guidance && (
                <div className="px-3 pb-2">
                  <p className="text-xs text-muted-foreground italic">{hint}</p>
                </div>
              )}

              {loading ? (
                <div className="flex items-center justify-center py-3">
                  <Loader2 className="w-4 h-4 animate-spin text-primary mr-2" />
                  <span className="text-xs text-muted-foreground">Thinking...</span>
                </div>
              ) : (
                <div className="px-3 pb-3 space-y-1">
                  {candidates.map((c, i) => {
                    const Icon = TYPE_ICONS[c.move_type] || Star;
                    const isGuidanceMatch = guidance && c.move === guidance.suggested_move;
                    return (
                      <button
                        key={i}
                        className={`w-full text-left p-2 rounded border transition-all group ${
                          isGuidanceMatch 
                            ? "border-primary/30 bg-primary/5" 
                            : "border-transparent hover:border-border hover:bg-muted/30"
                        }`}
                        onClick={() => onHighlightMove?.(c.move)}
                        data-testid={`candidate-${i}`}
                      >
                        <div className="flex items-start gap-2">
                          <div className="flex items-center gap-1 shrink-0">
                            <span className="text-sm font-mono font-bold text-foreground">{c.move}</span>
                            {c.is_best && <Badge variant="outline" className="text-[8px] px-1 py-0 h-3.5">best</Badge>}
                          </div>
                          <p className="text-[11px] text-muted-foreground leading-relaxed flex-1">{c.idea}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default CandidateMoves;
