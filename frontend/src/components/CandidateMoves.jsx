/**
 * CandidateMoves.jsx — "Think First" Coach Panel
 * 
 * BEFORE the move: Shows a HINT (question), not the answer
 * AFTER the move: Shows feedback (right/wrong + explanation)
 * 
 * Also shows Stockfish candidates as a collapsible "engine picks" section
 */

import { useState, useEffect, useRef } from "react";
import { API } from "@/App";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { 
  Loader2, Lightbulb, ChevronDown, ChevronUp, 
  Star, Zap, Shield, Target, AlertTriangle, 
  BookOpen, HelpCircle, CheckCircle2, XCircle,
} from "lucide-react";

const TYPE_ICONS = {
  tactical: Zap, counter_attack: Zap, development: Star,
  central: Target, king_safety: Shield, prophylactic: Shield,
  positional: Target, engine_choice: Star,
};

const CandidateMoves = ({ sessionId, fen, isPlayerTurn, onHighlightMove, openingKey, introMessage, curriculumFeedback, lastCoachMove }) => {
  const [candidates, setCandidates] = useState([]);
  const [hint, setHint] = useState("");
  const [loading, setLoading] = useState(false);
  const [showEngine, setShowEngine] = useState(false);
  const [lastFetchedFen, setLastFetchedFen] = useState(null);
  const [introDismissed, setIntroDismissed] = useState(false);
  
  // Curriculum guidance (hint mode)
  const [guidance, setGuidance] = useState(null);
  
  // Post-move feedback
  const [feedback, setFeedback] = useState(null);
  const prevFenRef = useRef(null);

  // Detect when position changes (player made a move) → show feedback
  useEffect(() => {
    if (prevFenRef.current && prevFenRef.current !== fen && guidance && guidance.mode === "think") {
      // Position changed — player moved. Check if they played the expected move.
      // We can't easily check here since we don't have the move SAN.
      // The feedback will come from the next guidance fetch.
      setFeedback(null);
    }
    prevFenRef.current = fen;
  }, [fen, guidance]);

  useEffect(() => {
    if (!sessionId || !fen) {
      setCandidates([]);
      setHint("");
      setGuidance(null);
      setFeedback(null);
      return;
    }

    if (fen === lastFetchedFen) return;

    const fetchAll = async () => {
      setLoading(true);
      setFeedback(null);
      try {
        // First: always fetch curriculum guidance
        let guidanceData = null;
        try {
          const guideRes = await fetch(`${API}/coach/play/opening-guide`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ session_id: sessionId, opening_key: openingKey }),
          });
          if (guideRes.ok) {
            const data = await guideRes.json();
            if (data.has_guidance !== false) {
              guidanceData = data;
              setGuidance(data);
            } else {
              setGuidance(null);
            }
          }
        } catch { setGuidance(null); }

        // Second: fetch engine candidates ONLY when curriculum is not actively guiding
        const curriculumActive = guidanceData && guidanceData.is_in_book && guidanceData.mode === "think";
        if (!curriculumActive) {
          try {
            const candRes = await fetch(`${API}/coach/play/candidates`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              credentials: "include",
              body: JSON.stringify({ session_id: sessionId }),
            });
            if (candRes.ok) {
              const data = await candRes.json();
              setCandidates(data.candidates || []);
              setHint(data.position_hint || "");
            }
          } catch { /* ok */ }
        } else {
          setCandidates([]);
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

  // Show nothing only if there's truly nothing to display
  if (!loading && candidates.length === 0 && !guidance && !introMessage && !curriculumFeedback) return null;

  return (
    <div className="space-y-3" data-testid="candidate-moves">
      
      {/* ─── INTRO: Show opening introduction before first move ─── */}
      {introMessage && !introDismissed && (
        <motion.div
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="border border-primary/30 rounded bg-primary/[0.05] p-4"
        >
          <div className="flex items-center gap-2 mb-3">
            <BookOpen className="w-4 h-4 text-primary" strokeWidth={1.5} />
            <span className="text-xs font-medium text-foreground">Today's Lesson</span>
          </div>
          <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">
            {introMessage}
          </p>
          <button
            onClick={() => setIntroDismissed(true)}
            className="mt-3 text-xs text-primary hover:text-primary/80 font-medium"
          >
            Got it — let's start
          </button>
        </motion.div>
      )}

      {/* ─── CURRICULUM FEEDBACK: Show after user plays a move ─── */}
      {curriculumFeedback && (!introMessage || introDismissed) && (
        <motion.div
          key={`feedback-${curriculumFeedback}`}
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="border border-emerald-500/30 rounded bg-emerald-500/[0.05] p-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" strokeWidth={1.5} />
            <span className="text-xs font-medium text-emerald-600">Good move</span>
          </div>
          <p className="text-sm text-foreground leading-relaxed">
            {curriculumFeedback}
          </p>
        </motion.div>
      )}

      {/* ─── OPPONENT MOVE: Highlighted section ─── */}
      {(!introMessage || introDismissed) && lastCoachMove && guidance && guidance.opponent_commentary && (
        <motion.div
          key={`opp-${lastCoachMove}`}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          className="border-l-4 border-red-400/60 bg-red-500/[0.04] rounded-r p-4"
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded bg-red-500/10 flex items-center justify-center">
              <span className="text-base font-mono font-bold text-red-400">{lastCoachMove}</span>
            </div>
            <div>
              <p className="text-[10px] font-mono uppercase tracking-widest text-red-400/70">Opponent played</p>
            </div>
          </div>
          <p className="text-sm text-foreground leading-relaxed">
            {guidance.opponent_commentary}
          </p>
        </motion.div>
      )}

      {/* ─── CURRICULUM: Think Mode — ONLY the question, nothing else ─── */}
      {(!introMessage || introDismissed) && guidance && guidance.mode === "think" && (
        <motion.div
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="border border-primary/30 rounded bg-primary/[0.05] p-4"
        >
          <div className="flex items-center gap-2 mb-3">
            <HelpCircle className="w-4 h-4 text-primary" strokeWidth={1.5} />
            <span className="text-xs font-medium text-foreground">Think first</span>
          </div>

          {/* ONLY the question — no plan, no golden rule, no future moves */}
          <p className="text-sm text-foreground leading-relaxed">
            {guidance.hint}
          </p>

          {/* Trap warning is OK to show — it's about the current position, not future moves */}
          {guidance.trap_warning && (
            <div className="flex items-start gap-2 p-2 rounded bg-amber-500/10 border border-amber-500/20 mt-3">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" strokeWidth={1.5} />
              <div>
                <p className="text-xs font-medium text-amber-600">{guidance.trap_warning.name}</p>
                <p className="text-xs text-muted-foreground">{guidance.trap_warning.description}</p>
              </div>
            </div>
          )}

          {/* Weak spot indicator — extra emphasis, no answer */}
          {guidance.is_weak_spot && (
            <div className="mt-2 text-xs text-destructive/80 font-medium">
              You've gotten this wrong before. Take your time.
            </div>
          )}
        </motion.div>
      )}

      {/* ─── CURRICULUM: Waiting Mode ─── */}
      {guidance && guidance.mode === "waiting" && (
        <div className="border border-border rounded p-3">
          <p className="text-xs text-muted-foreground">{guidance.hint}</p>
        </div>
      )}

      {/* ─── ENGINE PICKS — show when curriculum guidance has ended ─── */}
      {(!guidance || !guidance.is_in_book) && candidates.length > 0 && (
      <div className="border border-border rounded overflow-hidden">
        <button 
          onClick={() => setShowEngine(!showEngine)}
          className="w-full flex items-center justify-between px-3 py-2 hover:bg-muted/50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Target className="w-3.5 h-3.5 text-muted-foreground" strokeWidth={1.5} />
            <span className="text-xs text-muted-foreground">
              {guidance ? "Need a hint? Top moves here" : "Your best options"}
            </span>
          </div>
          {showEngine ? <ChevronUp className="w-3 h-3 text-muted-foreground" /> : <ChevronDown className="w-3 h-3 text-muted-foreground" />}
        </button>

        <AnimatePresence>
          {showEngine && (
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
                  {candidates.map((c, i) => (
                    <button
                      key={i}
                      className="w-full text-left p-2 rounded border border-transparent hover:border-border hover:bg-muted/30 transition-all"
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
                  ))}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      )}
    </div>
  );
};

export default CandidateMoves;
