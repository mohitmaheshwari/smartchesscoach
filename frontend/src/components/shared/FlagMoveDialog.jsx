/**
 * FlagMoveDialog.jsx — "This doesn't seem right" flag button + dialog
 *
 * Used in Lab (GameDecryptionV5) and Coach (CoachPlay) to let users
 * report incorrect or unhelpful coaching on a specific move.
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
import { Flag, Loader2, Check } from "lucide-react";

export const FlagMoveButton = ({ source, gameId, sessionId, moveNumber, fen, moveSan, coachingText, className = "" }) => {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

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
        <span>Flag</span>
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 max-w-md" data-testid="flag-move-dialog">
          <DialogHeader>
            <DialogTitle className="text-sm">Report Incorrect Coaching</DialogTitle>
            <DialogDescription className="text-xs">
              Help us improve. Describe what seems wrong with the coaching for this position.
            </DialogDescription>
          </DialogHeader>

          {submitted ? (
            <div className="flex flex-col items-center gap-2 py-4" data-testid="flag-submitted">
              <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                <Check className="w-5 h-5 text-emerald-400" />
              </div>
              <p className="text-sm text-emerald-400">Feedback submitted. Thank you!</p>
            </div>
          ) : (
            <div className="space-y-3">
              {moveSan && (
                <div className="text-xs bg-zinc-800 rounded p-2">
                  <span className="text-muted-foreground">Move: </span>
                  <span className="font-mono font-medium">{moveSan}</span>
                  {moveNumber && <span className="text-muted-foreground"> (move {moveNumber})</span>}
                </div>
              )}
              {coachingText && (
                <div className="text-xs bg-zinc-800 rounded p-2 max-h-20 overflow-y-auto">
                  <span className="text-muted-foreground">Coach said: </span>
                  <span className="text-zinc-300">{coachingText.slice(0, 200)}{coachingText.length > 200 ? "..." : ""}</span>
                </div>
              )}
              <Textarea
                placeholder="What seems wrong? e.g., 'The engine says this is best but the coach calls it a mistake...'"
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
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Submit Feedback"}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};
