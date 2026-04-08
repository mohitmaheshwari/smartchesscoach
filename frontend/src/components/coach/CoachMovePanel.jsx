/**
 * CoachMovePanel — Right panel for Coach tab in game review
 *
 * Shows per-move coaching when navigating important moves:
 * 1. Reflection — "Why did you play this?" (text input + board play)
 * 2. What's on the board — position reading
 * 3. Candidate plans — 3-4 ideas (not engine moves)
 * 4. Golden rule — phase-specific wisdom
 *
 * Updates dynamically as user navigates between moves.
 */

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { InlineFlag } from "@/components/shared/FlagMoveDialog";
import {
  Brain, ChevronRight, MessageSquare, Lightbulb, AlertTriangle, Send, Check
} from "lucide-react";

const CoachMovePanel = ({
  gameId,
  currentMoveIndex,
  moves,
  analysis,
  userColor,
  currentFen,
}) => {
  const [reflection, setReflection] = useState("");
  const [reflectionSaved, setReflectionSaved] = useState(false);
  const [savingReflection, setSavingReflection] = useState(false);
  const [boardReading, setBoardReading] = useState(null);
  const [loadingReading, setLoadingReading] = useState(false);

  const evals = analysis?.stockfish_analysis?.move_evaluations || [];
  const currentMove = currentMoveIndex >= 0 ? moves[currentMoveIndex] : null;
  const currentEval = currentMoveIndex >= 0 ? evals[currentMoveIndex] : null;

  const isUserMove = currentMove && (
    (userColor === "white" && currentMoveIndex % 2 === 0) ||
    (userColor === "black" && currentMoveIndex % 2 === 1)
  );

  const severity = currentEval?.classification || currentEval?.evaluation || "";
  const isImportant = ["blunder", "mistake", "inaccuracy"].some(s => severity.toLowerCase().includes(s));
  const cpLoss = Math.abs(currentEval?.cp_loss || 0);
  const bestMove = currentEval?.best_move || "";

  // Reset state when move changes
  useEffect(() => {
    setReflection("");
    setReflectionSaved(false);
    setBoardReading(null);

    // Fetch board reading for important moves
    if (isImportant && currentFen) {
      setLoadingReading(true);
      fetch(`${API}/position/read`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ fen: currentFen, user_color: userColor }),
      })
        .then(r => r.ok ? r.json() : null)
        .then(data => setBoardReading(data))
        .catch(() => {})
        .finally(() => setLoadingReading(false));
    }
  }, [currentMoveIndex]);

  const saveReflection = async () => {
    if (!reflection.trim()) return;
    setSavingReflection(true);
    try {
      await fetch(`${API}/games/${gameId}/thought`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          move_number: currentEval?.move_number || Math.floor(currentMoveIndex / 2) + 1,
          thought: reflection.trim(),
          fen: currentFen,
        }),
      });
      setReflectionSaved(true);
    } catch (e) { console.error(e); }
    finally { setSavingReflection(false); }
  };

  // No move selected
  if (currentMoveIndex < 0) {
    return (
      <div className="flex items-center justify-center h-full text-center px-6">
        <div>
          <Brain className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">Navigate to a move to see coaching.</p>
          <p className="text-xs text-muted-foreground/50 mt-1">Use the arrows to jump between important moments.</p>
        </div>
      </div>
    );
  }

  // Not an important move — show minimal
  if (!isImportant && isUserMove) {
    return (
      <div className="p-5">
        <p className="text-sm text-emerald-500 font-medium mb-1">Good move.</p>
        <p className="text-xs text-muted-foreground">Nothing to fix here. Move to the next highlighted position.</p>
      </div>
    );
  }

  // Opponent move
  if (!isUserMove) {
    const oppSeverity = severity.toLowerCase();
    const oppBlundered = oppSeverity.includes("blunder") || oppSeverity.includes("mistake");

    return (
      <div className="p-5 space-y-4">
        <p className="text-sm text-foreground font-medium">Opponent's move</p>
        {oppBlundered ? (
          <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/15">
            <p className="text-sm text-emerald-600">Your opponent made a mistake here. Did you see it?</p>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">Navigate to your next move to see coaching.</p>
        )}
      </div>
    );
  }

  // ═══ IMPORTANT USER MOVE — full coaching panel ═══
  return (
    <div className="p-5 space-y-5 overflow-y-auto">
      <AnimatePresence mode="wait">
        <motion.div key={currentMoveIndex} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>

          {/* ── 1. SEVERITY BADGE ── */}
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold mb-4 ${
            severity.includes("blunder") ? "bg-red-500/15 text-red-400" :
            severity.includes("mistake") ? "bg-orange-500/15 text-orange-500" :
            "bg-amber-500/10 text-amber-500"
          }`}>
            <AlertTriangle className="w-3 h-3" strokeWidth={2.5} />
            {severity.includes("blunder") ? "Blunder" : severity.includes("mistake") ? "Mistake" : "Inaccuracy"}
          </div>

          {/* ── 2. REFLECTION — "What were you thinking?" ── */}
          <div className="mb-5">
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
              <MessageSquare className="w-3 h-3 inline mr-1" />
              What were you thinking here?
            </p>
            {!reflectionSaved ? (
              <div className="space-y-2">
                <Textarea
                  placeholder="Why did you play this move? What did you see?"
                  className="text-sm min-h-[60px] resize-none"
                  value={reflection}
                  onChange={(e) => setReflection(e.target.value)}
                />
                <Button
                  size="sm"
                  onClick={saveReflection}
                  disabled={!reflection.trim() || savingReflection}
                  className="text-xs"
                >
                  <Send className="w-3 h-3 mr-1" />
                  {savingReflection ? "Saving..." : "Save reflection"}
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-xs text-emerald-500">
                <Check className="w-3.5 h-3.5" strokeWidth={2} />
                Reflection saved
              </div>
            )}
          </div>

          {/* ── 3. WHAT'S ON THE BOARD ── */}
          {boardReading && (
            <div className="mb-5">
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
                <Brain className="w-3 h-3 inline mr-1" />
                What was happening on the board
              </p>
              <div className="p-3 rounded-lg bg-blue-500/5 border border-blue-500/15 group">
                <p className="text-sm text-foreground leading-relaxed inline">
                  {boardReading.summary || boardReading.plan || "Take a look at the position."}
                </p>
                <InlineFlag
                  section="board_reading"
                  flaggedText={boardReading.summary || boardReading.plan || ""}
                  context={{ fen: currentFen, source: "coach_tab" }}
                />
              </div>
            </div>
          )}
          {loadingReading && (
            <div className="mb-5 flex items-center gap-2 text-xs text-muted-foreground">
              <div className="w-3 h-3 border border-primary/30 border-t-primary rounded-full animate-spin" />
              Reading the position...
            </div>
          )}

          {/* ── 4. CANDIDATE PLANS ── */}
          {currentEval && (
            <div className="mb-5">
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
                <Lightbulb className="w-3 h-3 inline mr-1" />
                What you could have done
              </p>
              <CandidatePlans
                evalData={currentEval}
                fen={currentFen}
                gameId={gameId}
                moveIndex={currentMoveIndex}
              />
            </div>
          )}

          {/* ── 5. GOLDEN RULE ── */}
          {currentEval?.golden_rule && (
            <div className="p-4 rounded-xl bg-amber-500/[0.05] border border-amber-500/15 group">
              <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1">Remember this</p>
              <p className="text-sm text-foreground font-medium inline">{currentEval.golden_rule}</p>
              <InlineFlag
                section="golden_rule"
                flaggedText={currentEval.golden_rule}
                context={{ fen: currentFen, source: "coach_tab" }}
              />
            </div>
          )}

        </motion.div>
      </AnimatePresence>
    </div>
  );
};


/**
 * CandidatePlans — Shows 3-4 alternative ideas (not raw engine moves)
 * Flags generic "engine says" text for feedback
 */
const CandidatePlans = ({ evalData, fen, gameId, moveIndex }) => {
  // Get candidate moves from eval data
  const candidates = evalData?.stockfish_candidates || [];
  const bestMove = evalData?.best_move || "";

  // Also build from PV if no candidates
  const plans = [];

  if (candidates.length > 0) {
    candidates.forEach((c, i) => {
      plans.push({
        move: c.move || "",
        idea: c.idea || c.explanation || "",
        type: c.type || "engine_choice",
        isBest: c.is_best || c.move === bestMove,
        isGeneric: !c.idea || c.idea.includes("strong move") || c.idea.includes("according to"),
      });
    });
  } else if (bestMove) {
    plans.push({
      move: bestMove,
      idea: evalData?.best_move_explanation || "",
      type: "best",
      isBest: true,
      isGeneric: !evalData?.best_move_explanation,
    });
  }

  if (plans.length === 0) return null;

  return (
    <div className="space-y-2">
      {plans.slice(0, 4).map((plan, i) => (
        <div key={i} className={`p-3 rounded-lg border group ${
          plan.isBest ? "border-emerald-500/20 bg-emerald-500/[0.03]" : "border-border bg-card"
        }`}>
          <div className="flex items-center gap-2 mb-1">
            {plan.isBest && <span className="text-[9px] font-bold uppercase tracking-wider text-emerald-500">Best</span>}
            {plan.type && plan.type !== "engine_choice" && plan.type !== "best" && (
              <span className="text-[9px] text-muted-foreground/50 uppercase">{plan.type.replace(/_/g, " ")}</span>
            )}
          </div>

          {plan.isGeneric ? (
            // Generic engine text — flag it
            <div className="flex items-start gap-2">
              <p className="text-sm text-amber-500 font-medium flex-1 inline">
                {plan.idea || `${plan.move} — no explanation available`}
              </p>
              <InlineFlag
                section="candidate_plan"
                flaggedText={plan.idea || plan.move}
                context={{ fen, moveSan: plan.move, source: "coach_tab", component: "candidate_plan" }}
              />
            </div>
          ) : (
            <div className="group">
              <p className="text-sm text-foreground leading-relaxed inline">{plan.idea}</p>
              <InlineFlag
                section="candidate_plan"
                flaggedText={plan.idea}
                context={{ fen, moveSan: plan.move, source: "coach_tab", component: "candidate_plan" }}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default CoachMovePanel;
