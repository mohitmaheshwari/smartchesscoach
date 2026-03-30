/**
 * CandidateMoves.jsx — "Your 3 best options"
 * 
 * Shows before each move: 3 candidate moves with simple explanations.
 * The player learns HOW TO THINK, not what to memorize.
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { 
  Loader2, Lightbulb, ChevronDown, ChevronUp, 
  Star, Zap, Shield, Target,
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

const CandidateMoves = ({ sessionId, fen, isPlayerTurn, onHighlightMove }) => {
  const [candidates, setCandidates] = useState([]);
  const [hint, setHint] = useState("");
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [lastFetchedFen, setLastFetchedFen] = useState(null);

  useEffect(() => {
    if (!sessionId || !fen || !isPlayerTurn) {
      setCandidates([]);
      setHint("");
      return;
    }

    // Don't re-fetch for the same position
    if (fen === lastFetchedFen) return;

    const fetchCandidates = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API}/coach/play/candidates`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ session_id: sessionId }),
        });
        if (res.ok) {
          const data = await res.json();
          setCandidates(data.candidates || []);
          setHint(data.position_hint || "");
          setLastFetchedFen(fen);
        }
      } catch (e) {
        console.log("Candidates fetch failed:", e);
      } finally {
        setLoading(false);
      }
    };

    fetchCandidates();
  }, [sessionId, fen, isPlayerTurn, lastFetchedFen]);

  // Don't show when not player's turn or no candidates
  if (!isPlayerTurn || (!loading && candidates.length === 0)) return null;

  return (
    <div className="border border-primary/20 rounded bg-primary/[0.03] overflow-hidden" data-testid="candidate-moves">
      {/* Header */}
      <button 
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-primary/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Lightbulb className="w-4 h-4 text-primary" strokeWidth={1.5} />
          <span className="text-xs font-medium text-foreground">Your 3 best options</span>
        </div>
        {expanded ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {/* Hint */}
            {hint && (
              <div className="px-3 pb-2">
                <p className="text-xs text-muted-foreground italic">{hint}</p>
              </div>
            )}

            {loading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-4 h-4 animate-spin text-primary mr-2" />
                <span className="text-xs text-muted-foreground">Thinking...</span>
              </div>
            ) : (
              <div className="px-3 pb-3 space-y-1.5">
                {candidates.map((c, i) => {
                  const Icon = TYPE_ICONS[c.move_type] || Star;
                  return (
                    <button
                      key={i}
                      className="w-full text-left p-2.5 rounded border border-border hover:border-primary/30 hover:bg-primary/5 transition-all group"
                      onClick={() => onHighlightMove?.(c.move)}
                      data-testid={`candidate-${i}`}
                    >
                      <div className="flex items-start gap-2.5">
                        <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
                          <span className="text-base font-mono font-bold text-foreground group-hover:text-primary transition-colors">
                            {c.move}
                          </span>
                          {c.is_best && (
                            <Badge variant="outline" className="text-[9px] px-1 py-0 h-4 text-primary border-primary/30">
                              best
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed flex-1">
                          {c.idea}
                        </p>
                        <Icon className="w-3.5 h-3.5 text-muted-foreground/50 shrink-0 mt-0.5" strokeWidth={1.5} />
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
  );
};

export default CandidateMoves;
