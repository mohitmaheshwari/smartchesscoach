/**
 * CoachPanel.jsx — Right panel for Play with Coach
 * 
 * Simple rules:
 * - Show intro until dismissed
 * - Show feedback when it exists
 * - Show opponent move when coach played
 * - Show hint when it's user's turn
 * - Show engine picks when off-book
 * 
 * NEVER empty.
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

    const doFetch = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API}/coach/play/opening-guide`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ session_id: sessionId, opening_key: openingKey || "" }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.has_guidance !== false) {
            setGuidance(data);
          } else {
            setGuidance(data); // Still set it — might have opponent_commentary
          }
        }
      } catch {}

      // Engine candidates — only when guidance is off-book or missing
      if (!guidance?.is_in_book) {
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
          }
        } catch {}
      } else {
        setCandidates([]);
      }

      setLastFetchedFen(fen);
      setLoading(false);
    };

    doFetch();
  }, [sessionId, fen, openingKey]);

  // Show intro
  const showIntro = introMessage && !introDismissed;

  return (
    <div className="space-y-3" data-testid="coach-panel">

      {/* ─── 1. INTRO ─── */}
      {showIntro && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="border border-primary/30 rounded bg-primary/[0.05] p-4">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen className="w-4 h-4 text-primary" strokeWidth={1.5} />
            <span className="text-xs font-medium text-foreground">Today's Lesson</span>
          </div>
          <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">
            {introMessage}
          </p>
          <button onClick={() => setIntroDismissed(true)}
            className="mt-3 text-xs text-primary hover:text-primary/80 font-medium">
            Got it — let's start
          </button>
        </motion.div>
      )}

      {/* ─── 2. YOUR MOVE FEEDBACK ─── */}
      {!showIntro && curriculumFeedback && (
        <motion.div key={`fb-${fen}`} initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }}
          className="border border-emerald-500/30 rounded bg-emerald-500/[0.05] p-4">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" strokeWidth={1.5} />
            <span className="text-xs font-medium text-emerald-600">Your move</span>
          </div>
          <p className="text-sm text-foreground leading-relaxed">{curriculumFeedback}</p>
        </motion.div>
      )}

      {/* ─── 3. OPPONENT MOVE ─── */}
      {!showIntro && lastCoachMove && guidance?.opponent_commentary && (
        <motion.div key={`opp-${lastCoachMove}`} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
          className="border-l-4 border-red-400/60 bg-red-500/[0.04] rounded-r p-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded bg-red-500/10 flex items-center justify-center">
              <span className="text-base font-mono font-bold text-red-400">{lastCoachMove}</span>
            </div>
            <p className="text-[10px] font-mono uppercase tracking-widest text-red-400/70">Opponent played</p>
          </div>
          <p className="text-sm text-foreground leading-relaxed">{guidance.opponent_commentary}</p>
        </motion.div>
      )}

      {/* ─── 4. THINK FIRST (user's turn) ─── */}
      {!showIntro && isPlayerTurn && guidance?.hint && (
        <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }}
          className="border border-primary/30 rounded bg-primary/[0.05] p-4">
          <div className="flex items-center gap-2 mb-3">
            <HelpCircle className="w-4 h-4 text-primary" strokeWidth={1.5} />
            <span className="text-xs font-medium text-foreground">Think first</span>
          </div>
          <p className="text-sm text-foreground leading-relaxed">{guidance.hint}</p>
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
            <p className="mt-2 text-xs text-destructive/80 font-medium">You've gotten this wrong before.</p>
          )}
        </motion.div>
      )}

      {/* ─── 5. WAITING (coach's turn) ─── */}
      {!showIntro && !isPlayerTurn && !lastCoachMove && (
        <div className="border border-border rounded p-3">
          <div className="flex items-center gap-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
            <p className="text-xs text-muted-foreground">Coach is thinking...</p>
          </div>
        </div>
      )}

      {/* ─── 6. ENGINE PICKS (off-book) ─── */}
      {!showIntro && candidates.length > 0 && (
        <div className="border border-border rounded overflow-hidden">
          <button onClick={() => setShowEngine(!showEngine)}
            className="w-full flex items-center justify-between px-3 py-2 hover:bg-muted/50 transition-colors">
            <div className="flex items-center gap-2">
              <Target className="w-3.5 h-3.5 text-muted-foreground" strokeWidth={1.5} />
              <span className="text-xs text-muted-foreground">Your best options</span>
            </div>
            {showEngine ? <ChevronUp className="w-3 h-3 text-muted-foreground" /> : <ChevronDown className="w-3 h-3 text-muted-foreground" />}
          </button>
          {showEngine && (
            <div className="px-3 pb-3 space-y-1">
              {candidates.map((c, i) => (
                <div key={i} className="p-2 rounded hover:bg-muted/30 transition-all">
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

      {/* ─── EMPTY STATE — should never happen but just in case ─── */}
      {!showIntro && !curriculumFeedback && !lastCoachMove && !guidance?.hint && !loading && candidates.length === 0 && (
        <div className="border border-border rounded p-3">
          <p className="text-xs text-muted-foreground">Your turn — make a move on the board.</p>
        </div>
      )}
    </div>
  );
};

export default CoachPanel;
