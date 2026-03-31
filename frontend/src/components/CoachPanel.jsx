/**
 * CoachPanel.jsx — The right panel for Play with Coach
 * 
 * ALWAYS shows content. Never empty. Four sections:
 * 
 * 1. INTRO — First time: "Today we're learning London..."
 * 2. YOUR MOVE — After user plays: feedback (good/bad + why)
 * 3. OPPONENT MOVE — After coach plays: what they did + why
 * 4. THINK FIRST — Before user's next move: the question
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { 
  Loader2, BookOpen, HelpCircle, CheckCircle2, 
  AlertTriangle, Target, ChevronDown, ChevronUp,
} from "lucide-react";

const CoachPanel = ({ sessionId, fen, isPlayerTurn, openingKey, introMessage, curriculumFeedback, lastCoachMove }) => {
  const [guidance, setGuidance] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastFetchedFen, setLastFetchedFen] = useState(null);
  const [introDismissed, setIntroDismissed] = useState(false);
  const [showEngine, setShowEngine] = useState(false);

  // Fetch guidance whenever position changes
  useEffect(() => {
    if (!sessionId || !fen) return;
    if (fen === lastFetchedFen) return;

    const fetchGuidance = async () => {
      setLoading(true);
      try {
        // Always fetch curriculum guidance
        const guideRes = await fetch(`${API}/coach/play/opening-guide`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ session_id: sessionId, opening_key: openingKey }),
        });
        if (guideRes.ok) {
          const data = await guideRes.json();
          setGuidance(data.has_guidance !== false ? data : null);
        }

        // Fetch engine candidates only when off-book
        const g = guidance;
        if (!g || !g.is_in_book) {
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
            }
          } catch {}
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

    fetchGuidance();
  }, [sessionId, fen, openingKey]);

  return (
    <div className="space-y-3" data-testid="coach-panel">

      {/* ─── INTRO ─── */}
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
          <p className="text-sm text-foreground leading-relaxed whitespace-pre-line" style={{ fontFamily: "'Outfit', sans-serif" }}>
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

      {/* ─── YOUR MOVE FEEDBACK ─── */}
      {curriculumFeedback && (!introMessage || introDismissed) && (
        <motion.div
          key={`fb-${curriculumFeedback}`}
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="border border-emerald-500/30 rounded bg-emerald-500/[0.05] p-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" strokeWidth={1.5} />
            <span className="text-xs font-medium text-emerald-600">Your move</span>
          </div>
          <p className="text-sm text-foreground leading-relaxed" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {curriculumFeedback}
          </p>
        </motion.div>
      )}

      {/* ─── OPPONENT MOVE ─── */}
      {lastCoachMove && (!introMessage || introDismissed) && guidance?.opponent_commentary && (
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
            <p className="text-[10px] font-mono uppercase tracking-widest text-red-400/70">Opponent played</p>
          </div>
          <p className="text-sm text-foreground leading-relaxed" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {guidance.opponent_commentary}
          </p>
        </motion.div>
      )}

      {/* ─── THINK FIRST (user's turn) ─── */}
      {(!introMessage || introDismissed) && isPlayerTurn && guidance?.mode === "think" && (
        <motion.div
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="border border-primary/30 rounded bg-primary/[0.05] p-4"
        >
          <div className="flex items-center gap-2 mb-3">
            <HelpCircle className="w-4 h-4 text-primary" strokeWidth={1.5} />
            <span className="text-xs font-medium text-foreground">Think first</span>
          </div>
          <p className="text-sm text-foreground leading-relaxed" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {guidance.hint}
          </p>
          {guidance.trap_warning && (
            <div className="flex items-start gap-2 p-2 rounded bg-amber-500/10 border border-amber-500/20 mt-3">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" strokeWidth={1.5} />
              <div>
                <p className="text-xs font-medium text-amber-600">{guidance.trap_warning.name}</p>
                <p className="text-xs text-muted-foreground">{guidance.trap_warning.description}</p>
              </div>
            </div>
          )}
          {guidance.is_weak_spot && (
            <div className="mt-2 text-xs text-destructive/80 font-medium">
              You've gotten this wrong before. Take your time.
            </div>
          )}
        </motion.div>
      )}

      {/* ─── WAITING (coach's turn) ─── */}
      {(!introMessage || introDismissed) && !isPlayerTurn && guidance?.mode === "waiting" && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="border border-border rounded p-3"
        >
          <div className="flex items-center gap-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
            <p className="text-xs text-muted-foreground">{guidance.hint || "Coach is thinking..."}</p>
          </div>
        </motion.div>
      )}

      {/* ─── ENGINE PICKS (off-book only) ─── */}
      {(!guidance || !guidance.is_in_book) && candidates.length > 0 && (
        <div className="border border-border rounded overflow-hidden">
          <button 
            onClick={() => setShowEngine(!showEngine)}
            className="w-full flex items-center justify-between px-3 py-2 hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Target className="w-3.5 h-3.5 text-muted-foreground" strokeWidth={1.5} />
              <span className="text-xs text-muted-foreground">Your best options</span>
            </div>
            {showEngine ? <ChevronUp className="w-3 h-3 text-muted-foreground" /> : <ChevronDown className="w-3 h-3 text-muted-foreground" />}
          </button>
          {showEngine && (
            <div className="px-3 pb-3 space-y-1">
              {candidates.map((c, i) => (
                <div key={i} className="p-2 rounded border border-transparent hover:border-border hover:bg-muted/30 transition-all">
                  <div className="flex items-start gap-2">
                    <span className="text-sm font-mono font-bold text-foreground">{c.move}</span>
                    {c.is_best && <Badge variant="outline" className="text-[8px] px-1 py-0 h-3.5">best</Badge>}
                    <p className="text-[11px] text-muted-foreground leading-relaxed flex-1">{c.idea}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ─── LOADING ─── */}
      {loading && !guidance && !curriculumFeedback && (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="w-4 h-4 animate-spin text-primary mr-2" />
          <span className="text-xs text-muted-foreground">Loading...</span>
        </div>
      )}
    </div>
  );
};

export default CoachPanel;
