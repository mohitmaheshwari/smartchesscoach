/**
 * CoachPanel.jsx — Right panel for Play with Coach
 * 
 * Styled like the original coach chat — primary/blue background cards with Brain icon.
 * 
 * Sections:
 * 1. INTRO — "Today we're learning London..."
 * 2. YOUR MOVE — Feedback after user plays
 * 3. OPPONENT MOVE — What coach played + why
 * 4. THINK FIRST — Hint for next move
 * 5. ENGINE PICKS — Off-book candidates
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { 
  Loader2, BookOpen, HelpCircle, CheckCircle2, Brain,
  AlertTriangle, Target, ChevronDown, ChevronUp, Swords,
} from "lucide-react";

// Coach message card — matches the original blue/primary style
const CoachCard = ({ icon: Icon, label, labelColor, bgColor, borderColor, children }) => (
  <motion.div 
    initial={{ opacity: 0, y: -5 }} 
    animate={{ opacity: 1, y: 0 }}
    className={`p-3 rounded-lg ${bgColor || "bg-primary/10"} border ${borderColor || "border-primary/20"}`}
  >
    <div className="flex items-start gap-2">
      <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${labelColor || "text-primary"}`} strokeWidth={1.5} />
      <div className="text-sm flex-1">
        {label && (
          <Badge variant="outline" className={`text-xs mb-1.5 ${labelColor ? `border-current ${labelColor}` : "border-primary/30 text-primary"}`}>
            {label}
          </Badge>
        )}
        <div className="text-foreground leading-relaxed">{children}</div>
      </div>
    </div>
  </motion.div>
);

const CoachPanel = ({ sessionId, fen, isPlayerTurn, openingKey, introMessage, curriculumFeedback, lastCoachMove }) => {
  const [guidance, setGuidance] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastFetchedFen, setLastFetchedFen] = useState(null);
  const [introDismissed, setIntroDismissed] = useState(false);
  const [showEngine, setShowEngine] = useState(false);

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
          setGuidance(data);
        }
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
        <CoachCard icon={BookOpen} label="Today's Lesson">
          <p className="whitespace-pre-line">{introMessage}</p>
          <button onClick={() => setIntroDismissed(true)}
            className="mt-3 text-xs text-primary hover:text-primary/80 font-medium block">
            Got it — let's start
          </button>
        </CoachCard>
      )}

      {/* ─── YOUR MOVE ─── */}
      {!showIntro && curriculumFeedback && (
        <CoachCard 
          key={`fb-${fen}`}
          icon={CheckCircle2} 
          label="Your Move"
          labelColor="text-emerald-600"
          bgColor="bg-emerald-50 dark:bg-emerald-500/10"
          borderColor="border-emerald-200 dark:border-emerald-500/20"
        >
          <p>{curriculumFeedback}</p>
        </CoachCard>
      )}

      {/* ─── OPPONENT MOVE ─── */}
      {!showIntro && lastCoachMove && guidance?.opponent_commentary && (
        <CoachCard 
          key={`opp-${lastCoachMove}`}
          icon={Swords} 
          label={`Opponent played ${lastCoachMove}`}
          labelColor="text-red-500 dark:text-red-400"
          bgColor="bg-red-50 dark:bg-red-500/10"
          borderColor="border-red-200 dark:border-red-500/20"
        >
          <p>{guidance.opponent_commentary}</p>
        </CoachCard>
      )}

      {/* ─── THINK FIRST ─── */}
      {!showIntro && isPlayerTurn && guidance?.hint && (
        <CoachCard icon={Brain} label="Think First">
          <p>{guidance.hint}</p>
          {guidance.trap_warning && (
            <div className="flex items-start gap-2 p-2 rounded bg-amber-500/10 border border-amber-500/20 mt-2">
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
        </CoachCard>
      )}

      {/* ─── WAITING ─── */}
      {!showIntro && !isPlayerTurn && !lastCoachMove && (
        <CoachCard icon={Loader2}>
          <p className="text-muted-foreground">Coach is thinking...</p>
        </CoachCard>
      )}

      {/* ─── ENGINE PICKS ─── */}
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
        <CoachCard icon={Loader2}>
          <p className="text-muted-foreground">Loading...</p>
        </CoachCard>
      )}

      {/* ─── EMPTY STATE ─── */}
      {!showIntro && !curriculumFeedback && !lastCoachMove && !guidance?.hint && !loading && candidates.length === 0 && (
        <CoachCard icon={Brain}>
          <p className="text-muted-foreground">Your turn — make a move on the board.</p>
        </CoachCard>
      )}
    </div>
  );
};

export default CoachPanel;
