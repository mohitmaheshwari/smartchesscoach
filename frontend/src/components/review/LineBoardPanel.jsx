/**
 * The words under the review board while the student plays their own line
 * (docs/play_any_line_scope.md). Every sentence comes from the server; this
 * component computes no chess.
 */
import { Loader2, RotateCcw, Sparkles, Undo2 } from "lucide-react";

import { Button } from "@/components/ui/button";

function MoveList({ steps }) {
  return (
    <p className="font-mono text-sm text-gray-900 leading-relaxed" data-testid="line-moves">
      {steps.map((s, i) => (
        <span key={i}>
          <span className="text-blue-700">{s.student.san}</span>{" "}
          {s.reply && <span className="text-red-700">{s.reply.san} </span>}
        </span>
      ))}
    </p>
  );
}

export function LineBoardHint() {
  return (
    <p className="text-xs text-gray-500 text-center" data-testid="line-hint">
      Move any piece to try your own idea.
    </p>
  );
}

export default function LineBoardPanel({ lb, gameFen }) {
  const last = lb.steps.length ? lb.steps[lb.steps.length - 1] : null;
  return (
    <div className="rounded-lg border border-blue-500/30 bg-blue-500/5 p-3 space-y-2" data-testid="line-panel">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-blue-700">Your line</p>
      {lb.steps.length > 0 && <MoveList steps={lb.steps} />}

      {lb.busy && (
        <p className="flex items-center gap-2 text-sm text-gray-500">
          <Loader2 className="w-4 h-4 animate-spin" /> The coach is looking…
        </p>
      )}
      {lb.error && <p className="text-sm text-red-600">{lb.error}</p>}

      {last && !lb.busy && (
        <div className="space-y-1.5 text-sm text-gray-800" data-testid="line-words">
          <p data-testid="line-student">{last.student.text}</p>
          {last.why_state === "loading" && (
            <p className="flex items-center gap-2 text-xs text-gray-500">
              <Loader2 className="w-3 h-3 animate-spin" /> Working out why…
            </p>
          )}
          {last.why && <p className="text-gray-900" data-testid="line-why">{last.why}</p>}
          {/* The why sentence usually names the reply already ("After Qf3,
              Bxb5 takes your bishop"); saying it twice reads as noise. */}
          {last.reply && !(last.why && last.why.includes(last.reply.san)) && (
            <p data-testid="line-reply">{last.reply.text}</p>
          )}
          {last.count_text && <p className="text-gray-600" data-testid="line-count">{last.count_text}</p>}
          {!last.reply && <p className="text-gray-600">The line ends here.</p>}
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        <Button size="sm" variant="outline" onClick={lb.back} disabled={lb.busy || lb.steps.length === 0}
          data-testid="line-back">
          <Undo2 className="w-3 h-3 mr-1" /> Back one
        </Button>
        <Button size="sm" variant="outline" onClick={() => lb.best(gameFen)}
          disabled={lb.busy || (last && !last.reply)} data-testid="line-best">
          <Sparkles className="w-3 h-3 mr-1" /> Best move here
        </Button>
        <Button size="sm" variant="ghost" onClick={lb.exit} data-testid="line-exit">
          <RotateCcw className="w-3 h-3 mr-1" /> Back to the game
        </Button>
      </div>
    </div>
  );
}
