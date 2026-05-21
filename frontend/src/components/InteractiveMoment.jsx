/**
 * InteractiveMoment — "What would you play here?" puzzle on a real
 * game's critical position.
 *
 * Three candidate moves: the user's actual move, the engine's best, and
 * a plausible distractor. User picks one → the board animates that
 * move's line (2-3 ply) → a short caption explains the outcome.
 *
 * Designed for 600-1300 players who don't read long prose. They DO,
 * they don't read.
 *
 * Props:
 *   fen           — starting FEN (the critical position)
 *   userColor     — "white" | "black" — board orientation
 *   moveNumber    — for the eyebrow caption
 *   candidates    — array of:
 *     { san, line: [san, san, ...], caption, isCorrect }
 *     - san:       the user-facing move label
 *     - line:      the moves to animate, starting with the candidate move
 *     - caption:   short text shown after animation completes
 *     - isCorrect: was this the move the user should have played?
 */

import { useState } from "react";
import { Chess } from "chess.js";
import LichessBoard from "@/components/LichessBoard";
import { API } from "@/App";
import { Check, X, RotateCw, Flag } from "lucide-react";

const ANIMATION_DELAY_MS = 750;


/**
 * Inline flag widget — shown after the puzzle reveals its result.
 * Posts to /feedback/flag (existing endpoint, move_feedback collection)
 * with full position context so the coach can review the complaint
 * with the FEN, the played move, and the caption that was shown.
 */
function FlagFeedback({ gameId, moveNumber, moveSan, fen, coachingText, chosenSan }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const submit = async () => {
    if (!note.trim()) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/feedback/flag`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: "decryption_moment",
          game_id: gameId,
          move_number: moveNumber,
          fen: fen,
          move_san: moveSan,
          coaching_text: coachingText,
          // user_note carries both the user's complaint and which
          // candidate's caption was on screen — without that the
          // coach can't tell what was being flagged.
          user_note: chosenSan
            ? `[viewing ${chosenSan}] ${note.trim()}`
            : note.trim(),
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaved(true);
      setNote("");
      setTimeout(() => { setOpen(false); setSaved(false); }, 1800);
    } catch (e) {
      console.error("flag failed", e);
      alert("Flag failed — check console.");
    }
    setSaving(false);
  };

  if (saved) {
    return (
      <p className="text-[12px] text-emerald-600 dark:text-emerald-400 mt-3">
        ✓ Flagged. Thanks — we'll review.
      </p>
    );
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="mt-4 text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground hover:text-rose-600 dark:hover:text-rose-400 inline-flex items-center gap-1.5 font-semibold transition-colors"
      >
        <Flag className="w-3 h-3" strokeWidth={2.4} />
        Flag this explanation
      </button>
    );
  }

  return (
    <div className="mt-4 space-y-2 border-t border-border/40 pt-3">
      <label className="text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">
        What's wrong or missing?
      </label>
      <textarea
        autoFocus
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={3}
        placeholder="e.g. it doesn't mention the king must take and then queen forks..."
        className="w-full text-[13.5px] p-2 rounded border border-border/50 bg-background"
      />
      <div className="flex gap-2 items-center">
        <button
          onClick={submit}
          disabled={saving || !note.trim()}
          className="px-3 py-1.5 text-[12px] font-semibold rounded text-white disabled:opacity-50"
          style={{ background: "rgb(159 18 57)" }}
        >
          {saving ? "Sending..." : "Send"}
        </button>
        <button
          onClick={() => { setOpen(false); setNote(""); }}
          className="px-3 py-1.5 text-[12px] text-muted-foreground hover:text-foreground"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}


export default function InteractiveMoment({ fen, userColor, moveNumber, candidates, gameId, moveSan }) {
  const [chosenIdx, setChosenIdx] = useState(null);
  const [currentFen, setCurrentFen] = useState(fen);
  const [arrows, setArrows] = useState([]);
  const [animating, setAnimating] = useState(false);
  const [showResult, setShowResult] = useState(false);

  const orientation = userColor === "black" ? "black" : "white";

  const animateLine = async (lineSans) => {
    setAnimating(true);
    const board = new Chess(fen);
    const steps = [];

    for (const san of lineSans) {
      try {
        const move = board.move(san);
        if (!move) break;
        steps.push({
          fen: board.fen(),
          arrow: [move.from, move.to, "#dc2626"],
        });
      } catch {
        break;
      }
    }

    // Walk through the steps with a delay between each.
    for (const step of steps) {
      await new Promise((r) => setTimeout(r, ANIMATION_DELAY_MS));
      setCurrentFen(step.fen);
      setArrows([step.arrow]);
    }

    await new Promise((r) => setTimeout(r, 400));
    setShowResult(true);
    setAnimating(false);
  };

  const handleChoice = (idx) => {
    setChosenIdx(idx);
    const cand = candidates[idx];
    animateLine(cand.line || [cand.san]);
  };

  const reset = () => {
    setChosenIdx(null);
    setCurrentFen(fen);
    setArrows([]);
    setShowResult(false);
  };

  const chosen = chosenIdx != null ? candidates[chosenIdx] : null;

  return (
    <div className="rounded-2xl border border-amber-500/30 bg-gradient-to-b from-amber-500/[0.04] to-transparent p-6 md:p-7">
      <div className="text-[10.5px] uppercase tracking-[0.22em] text-amber-600 dark:text-amber-300 font-semibold mb-3">
        {moveNumber ? `Move ${moveNumber} · ` : ""}what would you play?
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-6 md:gap-8 items-start">
        {/* Board */}
        <div className="aspect-square w-full max-w-[280px] mx-auto md:mx-0">
          <LichessBoard
            fen={currentFen}
            orientation={orientation}
            viewOnly={true}
            arrows={arrows}
          />
        </div>

        {/* Right column: choices OR result */}
        <div className="self-center min-h-[200px]">
          {chosenIdx === null ? (
            <>
              <p className="text-[13px] text-muted-foreground mb-4">
                {candidates.length === 3
                  ? "Three options. Pick one."
                  : `${candidates.length} options — multiple may be correct. Pick one.`}
              </p>
              <div className="space-y-2">
                {candidates.map((c, i) => (
                  <button
                    key={i}
                    onClick={() => handleChoice(i)}
                    className="w-full text-left font-serif text-[17px] text-foreground/90 px-4 py-3 rounded-lg border border-border/50 hover:border-amber-500/50 hover:bg-amber-500/[0.06] transition-all"
                  >
                    {c.san}
                  </button>
                ))}
              </div>
            </>
          ) : animating ? (
            <p className="text-[14px] text-muted-foreground italic">
              Playing it out...
            </p>
          ) : (
            showResult && (
              <>
                <div className="flex items-center gap-2 mb-3">
                  {chosen.isCorrect ? (
                    <Check
                      className="w-5 h-5 text-emerald-500"
                      strokeWidth={2.6}
                    />
                  ) : (
                    <X
                      className="w-5 h-5 text-rose-500"
                      strokeWidth={2.6}
                    />
                  )}
                  <span
                    className={`text-[11px] uppercase tracking-[0.18em] font-semibold ${
                      chosen.isCorrect
                        ? "text-emerald-600 dark:text-emerald-300"
                        : "text-rose-600 dark:text-rose-300"
                    }`}
                  >
                    {chosen.isCorrect ? "That's the move" : "Doesn't work"}
                  </span>
                </div>
                <p className="font-serif text-[16px] md:text-[17px] text-foreground/90 leading-relaxed mb-5">
                  {chosen.caption}
                </p>
                <button
                  onClick={reset}
                  className="text-[11.5px] uppercase tracking-[0.18em] text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 font-semibold transition-colors"
                >
                  <RotateCw className="w-3 h-3" strokeWidth={2.4} />
                  Try another
                </button>
                {gameId && (
                  <FlagFeedback
                    gameId={gameId}
                    moveNumber={moveNumber}
                    moveSan={moveSan}
                    fen={fen}
                    coachingText={chosen.caption}
                    chosenSan={chosen.san}
                  />
                )}
              </>
            )
          )}
        </div>
      </div>
    </div>
  );
}
