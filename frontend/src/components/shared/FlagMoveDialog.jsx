/**
 * FlagMoveDialog.jsx — Developer-grade coaching flag system
 *
 * Every coaching message gets a flag button. When flagged, captures:
 * - Exact coaching text, FEN, move, eval data
 * - Severity, phase, component, concept
 * - Goal/consequence/better_approach from V5 coaching
 * 
 * Used in Lab (GameDecryptionV5) and Coach (CoachPlay).
 */

import { useState } from "react";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Flag, Loader2, Check, ChevronDown, ChevronUp } from "lucide-react";

export const FlagMoveButton = ({ 
  source, 
  gameId, 
  sessionId, 
  moveNumber, 
  fen, 
  moveSan, 
  coachingText,
  // Developer diagnostic props
  severity,
  cpLoss,
  bestMove,
  evalBefore,
  evalAfter,
  phase,
  component,
  conceptId,
  goal,
  consequence,
  betterApproach,
  yourPlanNow,
  className = "",
  iconOnly = false 
}) => {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  const handleSubmit = async () => {
    if (!note.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/feedback/flag`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          source,
          game_id: gameId || null,
          session_id: sessionId || null,
          move_number: moveNumber || null,
          fen: fen || "",
          move_san: moveSan || null,
          coaching_text: coachingText || null,
          user_note: note.trim(),
          // Diagnostic data
          severity: severity || null,
          cp_loss: cpLoss != null ? cpLoss : null,
          best_move: bestMove || null,
          eval_before: evalBefore != null ? evalBefore : null,
          eval_after: evalAfter != null ? evalAfter : null,
          phase: phase || null,
          component: component || null,
          concept_id: conceptId || null,
          goal: goal || null,
          consequence: consequence || null,
          better_approach: betterApproach || null,
          your_plan_now: yourPlanNow || null,
        }),
      });
      if (res.ok) {
        setSubmitted(true);
        setTimeout(() => {
          setOpen(false);
          setSubmitted(false);
          setNote("");
        }, 1500);
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Build diagnostic summary for display
  const diagnosticItems = [
    severity && { label: "Severity", value: severity },
    cpLoss != null && { label: "CP Loss", value: cpLoss },
    bestMove && { label: "Best Move", value: bestMove },
    evalBefore != null && { label: "Eval Before", value: evalBefore },
    evalAfter != null && { label: "Eval After", value: evalAfter },
    phase && { label: "Phase", value: phase },
    component && { label: "Component", value: component },
    conceptId && { label: "Concept", value: conceptId },
    goal && { label: "Goal", value: goal },
    consequence && { label: "Consequence", value: consequence },
    betterApproach && { label: "Better Approach", value: betterApproach },
    yourPlanNow && { label: "Your Plan Now", value: yourPlanNow },
  ].filter(Boolean);

  return (
    <>
      <button
        className={`text-xs text-zinc-500 hover:text-red-400 transition-colors flex items-center gap-1 ${className}`}
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
        data-testid="flag-move-btn"
        title="Report incorrect coaching"
      >
        <Flag className="w-3 h-3" />
        {!iconOnly && <span>Flag</span>}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-lg" data-testid="flag-move-dialog">
          <DialogHeader>
            <DialogTitle className="text-sm">Report Incorrect Coaching</DialogTitle>
            <DialogDescription className="text-xs">
              Help us improve. Describe what seems wrong — all position data is auto-captured.
            </DialogDescription>
          </DialogHeader>

          {submitted ? (
            <div className="flex flex-col items-center gap-2 py-4" data-testid="flag-submitted">
              <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                <Check className="w-5 h-5 text-emerald-400" />
              </div>
              <p className="text-sm text-emerald-400">Feedback submitted with full diagnostics!</p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Move context */}
              <div className="text-xs bg-zinc-800 rounded p-2 space-y-1">
                <div className="flex items-center gap-3 flex-wrap">
                  {moveSan && (
                    <span><span className="text-muted-foreground">Move: </span><span className="font-mono font-medium">{moveSan}</span></span>
                  )}
                  {moveNumber && (
                    <span className="text-muted-foreground">(#{moveNumber})</span>
                  )}
                  {severity && (
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      severity === 'good' ? 'bg-emerald-500/20 text-emerald-400' :
                      severity === 'inaccuracy' ? 'bg-amber-500/20 text-amber-400' :
                      severity === 'mistake' ? 'bg-orange-500/20 text-orange-400' :
                      severity === 'blunder' ? 'bg-red-500/20 text-red-400' :
                      'bg-zinc-700 text-zinc-400'
                    }`}>{severity}</span>
                  )}
                  {phase && <span className="text-zinc-500">{phase}</span>}
                </div>
                {fen && (
                  <div className="font-mono text-[10px] text-zinc-600 truncate">FEN: {fen}</div>
                )}
              </div>

              {/* Coaching text being flagged */}
              {coachingText && (
                <div className="text-xs bg-red-950/30 border border-red-900/30 rounded p-2 max-h-24 overflow-y-auto">
                  <span className="text-red-400/70 text-[10px] uppercase tracking-wide">Flagged text: </span>
                  <span className="text-zinc-300 block mt-0.5">{coachingText}</span>
                </div>
              )}

              {/* Diagnostics accordion */}
              {diagnosticItems.length > 0 && (
                <button
                  className="text-[10px] text-zinc-500 hover:text-zinc-400 flex items-center gap-1 transition-colors"
                  onClick={() => setShowDiagnostics(!showDiagnostics)}
                >
                  {showDiagnostics ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  {showDiagnostics ? "Hide" : "Show"} diagnostic data ({diagnosticItems.length} fields captured)
                </button>
              )}
              {showDiagnostics && diagnosticItems.length > 0 && (
                <div className="text-[10px] bg-zinc-800/50 rounded p-2 space-y-0.5 max-h-32 overflow-y-auto border border-zinc-700/50">
                  {diagnosticItems.map((item, i) => (
                    <div key={i} className="flex">
                      <span className="text-zinc-500 w-24 flex-shrink-0">{item.label}:</span>
                      <span className="text-zinc-300 truncate">{String(item.value)}</span>
                    </div>
                  ))}
                </div>
              )}

              <Textarea
                placeholder="What's wrong? e.g., 'Knight is not actually outnumbered — queen+king vs knight+pawn means value favors the attacker...'"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="bg-zinc-800 border-zinc-700 min-h-[80px] text-sm"
                data-testid="flag-note-input"
              />
              <Button
                className="w-full"
                onClick={handleSubmit}
                disabled={submitting || !note.trim()}
                data-testid="flag-submit-btn"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Submit Flag"}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};
