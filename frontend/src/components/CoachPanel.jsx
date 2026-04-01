/**
 * CoachPanel.jsx — Single conversational coach voice
 * 
 * One flow, not separate cards:
 * - After your move: feedback
 * - After opponent: what they did + what to notice + your hint (all in one)
 * - Read the Board: position features
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { 
  Loader2, BookOpen, Brain, Eye,
  AlertTriangle, Target, ChevronDown, ChevronUp, Swords,
} from "lucide-react";

const CoachPanel = ({ sessionId, fen, isPlayerTurn, openingKey, introMessage, curriculumFeedback, lastCoachMove }) => {
  const [guidance, setGuidance] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastFetchedFen, setLastFetchedFen] = useState(null);
  const [introDismissed, setIntroDismissed] = useState(false);
  const [showEngine, setShowEngine] = useState(false);
  const [positionRead, setPositionRead] = useState(null);

  useEffect(() => {
    if (!sessionId || !fen) return;
    if (fen === lastFetchedFen) return;

    const doFetch = async () => {
      setLoading(true);
      try {
        // Guidance
        const res = await fetch(`${API}/coach/play/opening-guide`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ session_id: sessionId, opening_key: openingKey || "" }),
        });
        if (res.ok) setGuidance(await res.json());
      } catch {}

      // Engine candidates when off-book
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

      // Position reader
      try {
        const posRes = await fetch(`${API}/coach/play/read-position`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ session_id: sessionId }),
        });
        if (posRes.ok) {
          const data = await posRes.json();
          setPositionRead(data.features?.length > 0 ? data : null);
        }
      } catch {}

      setLastFetchedFen(fen);
      setLoading(false);
    };

    doFetch();
  }, [sessionId, fen, openingKey]);

  const showIntro = introMessage && !introDismissed;

  return (
    <div className="space-y-3" data-testid="coach-panel">

      {/* ─── INTRO ─── */}
      {showIntro && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="p-4 rounded-lg bg-primary/10 border border-primary/20">
          <div className="flex items-start gap-2">
            <BookOpen className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" strokeWidth={1.5} />
            <div className="text-sm flex-1">
              <Badge variant="outline" className="text-xs border-primary/30 text-primary mb-1.5">Today's Lesson</Badge>
              <p className="text-foreground whitespace-pre-line">{introMessage}</p>
              <button onClick={() => setIntroDismissed(true)}
                className="mt-3 text-xs text-primary hover:text-primary/80 font-medium">
                Got it — let's start
              </button>
            </div>
          </div>
        </motion.div>
      )}

      {/* ─── COACH MESSAGE: One unified card per state ─── */}
      {!showIntro && (
        <motion.div key={`coach-${fen}`} initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-lg bg-primary/10 border border-primary/20">
          <div className="flex items-start gap-2">
            <Brain className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" strokeWidth={1.5} />
            <div className="text-sm flex-1 space-y-2">

              {/* Your move feedback */}
              {curriculumFeedback && (
                <p className="text-foreground">{curriculumFeedback}</p>
              )}

              {/* Opponent move */}
              {lastCoachMove && guidance?.opponent_commentary && (
                <div className="border-l-2 border-red-400/50 pl-2.5">
                  <span className="text-xs font-mono font-bold text-red-500">{lastCoachMove}</span>
                  <span className="text-xs text-muted-foreground ml-1.5">— {guidance.opponent_commentary}</span>
                </div>
              )}

              {/* Hint for next move */}
              {isPlayerTurn && guidance?.hint && (
                <p className="text-foreground font-medium">{guidance.hint}</p>
              )}

              {/* Trap warning */}
              {guidance?.trap_warning && (
                <div className="flex items-start gap-1.5 text-xs text-amber-600">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" strokeWidth={1.5} />
                  <span><span className="font-medium">{guidance.trap_warning.name}:</span> {guidance.trap_warning.description}</span>
                </div>
              )}

              {/* Weak spot */}
              {guidance?.is_weak_spot && (
                <p className="text-xs text-destructive/80 font-medium">You've gotten this wrong before.</p>
              )}

              {/* Waiting for coach */}
              {!isPlayerTurn && !lastCoachMove && !curriculumFeedback && (
                <div className="flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
                  <span className="text-muted-foreground">Coach is thinking...</span>
                </div>
              )}

              {/* Nothing to show */}
              {!curriculumFeedback && !lastCoachMove && !guidance?.hint && isPlayerTurn && (
                <p className="text-muted-foreground">Your turn — make a move.</p>
              )}
            </div>
          </div>
        </motion.div>
      )}

      {/* ─── READ THE BOARD ─── */}
      {!showIntro && positionRead && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="p-3 rounded-lg bg-muted/30 border border-border">
          <div className="flex items-center gap-2 mb-2">
            <Eye className="w-4 h-4 text-primary" strokeWidth={1.5} />
            <span className="text-xs font-medium text-foreground">Read the Board</span>
            <span className="text-[10px] text-muted-foreground ml-auto">{positionRead.eval_text}</span>
          </div>
          <div className="space-y-2">
            {positionRead.features.map((f, i) => (
              <div key={i} className="border-l-2 border-primary/30 pl-2.5">
                <p className="text-xs font-medium text-foreground">{f.title}</p>
                <p className="text-xs text-muted-foreground">{f.description}</p>
                <p className="text-[11px] text-primary/70 mt-0.5">{f.actionable}</p>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* ─── ENGINE PICKS (off-book) ─── */}
      {!showIntro && candidates.length > 0 && (
        <div className="border border-border rounded-lg overflow-hidden">
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
        <div className="flex items-center justify-center py-3">
          <Loader2 className="w-4 h-4 animate-spin text-primary mr-2" />
          <span className="text-xs text-muted-foreground">Loading...</span>
        </div>
      )}
    </div>
  );
};

export default CoachPanel;
