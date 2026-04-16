/**
 * FlagMoveDialog.jsx — Inline flag system for every coaching text element
 *
 * InlineFlag: tiny flag icon next to each coaching text. One click opens a 
 * pre-filled dialog with FULL context: game_id, FEN, side, move, classification,
 * eval data, the exact text being flagged, and which section it's from.
 * 
 * Developer gets: game_id + position + side + section + text + eval + classification
 * = instant understanding of what to fix.
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
import { Flag, Loader2, Check, Copy, ChevronDown, ChevronUp } from "lucide-react";

/**
 * InlineFlag — tiny flag icon placed next to any coaching text.
 * Auto-captures full context when clicked.
 * 
 * Props:
 *  - section: "narrative" | "goal" | "consequence" | "better_approach" | "your_plan_now" | "candidate_move" | "tactical_warning" | etc.
 *  - flaggedText: the exact text being flagged
 *  - context: { gameId, sessionId, moveNumber, fen, moveSan, side, severity, cpLoss, bestMove, evalBefore, evalAfter, phase, component, opening }
 */
export const InlineFlag = ({ section, flaggedText, context = {} }) => {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [showContext, setShowContext] = useState(false);

  const handleSubmit = async () => {
    if (!note.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/feedback/flag`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          source: context.source || "lab",
          game_id: context.gameId || null,
          session_id: context.sessionId || null,
          move_number: context.moveNumber || null,
          fen: context.fen || "",
          move_san: context.moveSan || null,
          coaching_text: flaggedText || null,
          user_note: note.trim(),
          severity: context.severity || null,
          cp_loss: context.cpLoss != null ? context.cpLoss : null,
          best_move: context.bestMove || null,
          eval_before: context.evalBefore != null ? context.evalBefore : null,
          eval_after: context.evalAfter != null ? context.evalAfter : null,
          phase: context.phase || null,
          component: context.component || null,
          concept_id: section || null,
          goal: context.goal || null,
          consequence: context.consequence || null,
          better_approach: context.betterApproach || null,
          your_plan_now: context.yourPlanNow || null,
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

  // Build context items for display
  const contextItems = [
    context.gameId && { label: "Game ID", value: context.gameId },
    context.fen && { label: "Position (FEN)", value: context.fen },
    context.moveSan && { label: "Move", value: `${context.moveSan}${context.moveNumber ? ` (#${context.moveNumber})` : ''}` },
    context.side && { label: "Side", value: context.side },
    section && { label: "Section", value: section },
    context.severity && { label: "Classification", value: context.severity },
    context.cpLoss != null && { label: "CP Loss", value: context.cpLoss },
    context.bestMove && { label: "Best Move (Stockfish)", value: context.bestMove },
    context.evalBefore != null && { label: "Eval Before", value: context.evalBefore },
    context.evalAfter != null && { label: "Eval After", value: context.evalAfter },
    context.phase && { label: "Phase", value: context.phase },
    context.component && { label: "Component", value: context.component },
    context.opening && { label: "Opening", value: context.opening },
  ].filter(Boolean);

  return (
    <>
      <button
        className="inline-flex items-center text-zinc-600 hover:text-red-400 transition-colors ml-1 align-middle opacity-0 group-hover:opacity-100 focus:opacity-100"
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
        data-testid={`inline-flag-${section}`}
        title={`Flag this ${section}`}
      >
        <Flag className="w-3 h-3" />
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-card border-border max-w-lg" data-testid="flag-dialog">
          <DialogHeader>
            <DialogTitle className="text-sm flex items-center gap-2">
              <Flag className="w-4 h-4 text-red-400" />
              Flag Coaching Issue
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              All position data auto-captured. Just describe what's wrong.
            </DialogDescription>
          </DialogHeader>

          {submitted ? (
            <div className="flex flex-col items-center gap-2 py-4" data-testid="flag-submitted">
              <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                <Check className="w-5 h-5 text-emerald-400" />
              </div>
              <p className="text-sm text-emerald-400">Flagged with full diagnostics!</p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* What's being flagged */}
              <div className="bg-red-950/30 border border-red-900/30 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-red-400/70 uppercase tracking-wider font-medium">
                    Flagging: {section}
                  </span>
                  {context.severity && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                      context.severity === 'good' ? 'bg-emerald-500/20 text-emerald-400' :
                      context.severity === 'inaccuracy' ? 'bg-amber-500/20 text-amber-400' :
                      context.severity === 'mistake' ? 'bg-orange-500/20 text-orange-400' :
                      context.severity === 'blunder' ? 'bg-red-500/20 text-red-400' :
                      'bg-secondary text-muted-foreground'
                    }`}>{context.severity}</span>
                  )}
                </div>
                <p className="text-sm text-zinc-200 leading-relaxed">{flaggedText}</p>
              </div>

              {/* Position summary */}
              <div className="bg-muted/50 rounded-lg p-2.5 text-xs space-y-1">
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  {context.moveSan && (
                    <span><span className="text-muted-foreground">Move:</span> <span className="font-mono font-medium text-foreground">{context.moveSan}</span></span>
                  )}
                  {context.moveNumber && (
                    <span className="text-muted-foreground">#{context.moveNumber}</span>
                  )}
                  {context.side && (
                    <span><span className="text-muted-foreground">Side:</span> <span className="text-zinc-300">{context.side}</span></span>
                  )}
                  {context.phase && (
                    <span><span className="text-muted-foreground">Phase:</span> <span className="text-zinc-300">{context.phase}</span></span>
                  )}
                  {context.cpLoss != null && (
                    <span><span className="text-muted-foreground">CP Loss:</span> <span className="text-zinc-300">{context.cpLoss}</span></span>
                  )}
                  {context.bestMove && context.bestMove !== context.moveSan && (
                    <span><span className="text-muted-foreground">Best:</span> <span className="text-emerald-400 font-mono">{context.bestMove}</span></span>
                  )}
                </div>
                {context.fen && (
                  <div className="flex items-center gap-2 mt-1">
                    <div className="font-mono text-[10px] text-zinc-500 flex-1 break-all select-all bg-black/20 rounded px-2 py-1">
                      {context.fen}
                    </div>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(context.fen);
                      }}
                      className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-0.5 shrink-0"
                      title="Copy FEN"
                    >
                      <Copy className="w-3 h-3" /> Copy
                    </button>
                  </div>
                )}
              </div>

              {/* Copy all debug info */}
              <button
                onClick={() => {
                  const debug = contextItems.map(i => `${i.label}: ${i.value}`).join("\n");
                  const full = `Flagged: ${section}\nText: ${flaggedText}\n${debug}`;
                  navigator.clipboard.writeText(full);
                }}
                className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
              >
                <Copy className="w-3 h-3" /> Copy all debug info
              </button>

              {/* Full context accordion */}
              {contextItems.length > 0 && (
                <button
                  className="text-[10px] text-muted-foreground hover:text-muted-foreground flex items-center gap-1 transition-colors"
                  onClick={() => setShowContext(!showContext)}
                >
                  {showContext ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  {contextItems.length} fields auto-captured for developer
                </button>
              )}
              {showContext && (
                <div className="text-[10px] bg-muted/30 rounded p-2 space-y-0.5 max-h-40 overflow-y-auto border border-border">
                  {contextItems.map((item, i) => (
                    <div key={i} className="flex">
                      <span className="text-muted-foreground w-28 flex-shrink-0">{item.label}:</span>
                      <span className="text-zinc-300 break-all">{String(item.value)}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* User note */}
              <Textarea
                placeholder="What's wrong? e.g., 'Knight is not outnumbered — queen+king vs knight+pawn, value favors the attacker...'"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="bg-muted border-border min-h-[80px] text-sm"
                data-testid="flag-note-input"
                autoFocus
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

// Legacy export for backward compat
export const FlagMoveButton = InlineFlag;
