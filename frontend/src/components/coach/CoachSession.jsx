/**
 * CoachSession — Guided game review that feels like sitting with a coach.
 *
 * Flow:
 *   Step 0: "Let's look at your game." — Phase bars, what happened.
 *   Step 1: "This is the moment." — Interactive board, try the move.
 *   Step 2: "Here's what you missed." — Arrows, threat, explanation.
 *   Step 3: "This isn't just this game." — Pattern history, before/after.
 *   Step 4: "One habit to build." — Rule, training, play again.
 *
 * Not a dashboard. A conversation.
 */

import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import LichessBoard from "@/components/LichessBoard";
import {
  ChevronRight, Target, Swords, Trophy, XCircle, Minus,
  Check, ArrowRight, Zap, Eye
} from "lucide-react";

const CoachSession = ({ review, onComplete, gameId }) => {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [tryResult, setTryResult] = useState(null); // null | "correct" | "wrong"
  const [showThreat, setShowThreat] = useState(false);
  const boardRef = useRef(null);

  if (!review?.session) return null;

  const s = review.session;
  const phases = review.phases || {};
  const moment = s.primary_moment;
  const pattern = review.pattern_context;
  const opening = review.opening_analysis;
  const behaviors = review.behaviors || [];

  const resultIcon = s.game_result === "1-0" || s.game_result === "0-1"
    ? (review.user_color === "white" ? (s.game_result === "1-0" ? "win" : "loss") : (s.game_result === "0-1" ? "win" : "loss"))
    : "draw";

  const next = () => {
    // Skip step 1+2 if no interactive moment
    if (step === 0 && !moment?.fen) {
      setStep(3);
    } else if (step === 2) {
      setStep(pattern?.is_recurring ? 3 : 4);
    } else {
      setStep(step + 1);
    }
  };

  // Handle user trying a move on the interactive board
  const handleTryMove = (moveData) => {
    if (!moment?.best_move || tryResult) return;

    const bestClean = (moment.best_move || "").replace(/[+#]/g, "").toLowerCase();
    let playedSan = "";

    try {
      const chess = new Chess(moment.fen);
      const move = chess.move({ from: moveData.from, to: moveData.to, promotion: "q" });
      if (move) playedSan = move.san.replace(/[+#]/g, "").toLowerCase();
    } catch (e) {
      return;
    }

    if (playedSan === bestClean) {
      setTryResult("correct");
    } else {
      setTryResult("wrong");
    }

    // Auto-advance after a beat
    setTimeout(() => setStep(2), 1500);
  };

  const pageTransition = {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -20 },
    transition: { duration: 0.3 },
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-6">
      <AnimatePresence mode="wait">

        {/* ═══ STEP 0: THE INSIGHT ═══ */}
        {step === 0 && (
          <motion.div key="step0" {...pageTransition} className="space-y-5">
            <p className="text-lg font-heading text-foreground">
              Let's look at your game against {s.opponent}.
            </p>

            {/* Phase bars */}
            <div className="flex gap-2">
              {["opening", "middlegame", "endgame"].map(key => {
                const p = phases[key];
                if (!p) return null;
                const icon = p.accuracy >= 75 ? <Check className="w-3.5 h-3.5 text-emerald-500" strokeWidth={2.5} />
                  : <XCircle className="w-3.5 h-3.5 text-red-400" strokeWidth={2} />;
                return (
                  <div key={key} className={`flex-1 rounded-xl p-3 border ${
                    p.accuracy >= 75 ? "border-emerald-500/20 bg-emerald-500/[0.04]"
                    : p.accuracy >= 50 ? "border-amber-500/20 bg-amber-500/[0.04]"
                    : "border-red-500/20 bg-red-500/[0.04]"
                  }`}>
                    <div className="flex items-center gap-1.5 mb-0.5">
                      {icon}
                      <span className="text-xs font-medium text-foreground">{p.name}</span>
                    </div>
                    <p className="text-[10px] text-muted-foreground">{p.verdict}</p>
                  </div>
                );
              })}
            </div>

            {/* What happened */}
            <p className="text-sm text-muted-foreground leading-relaxed">
              {s.phase_story}
            </p>

            {/* Opening note */}
            {opening && (
              <p className="text-xs text-muted-foreground">
                Opening: {opening.name}
                {opening.moves_in_theory > 0 && ` — ${opening.moves_in_theory} moves in theory`}
                {opening.traps?.length > 0 && (
                  <span className="text-amber-400 ml-1">
                    {opening.traps[0].story}
                  </span>
                )}
              </p>
            )}

            <button onClick={next}
              className="w-full py-3.5 text-sm font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2"
            >
              {moment?.fen ? "Show me the key moment" : "Show me the pattern"}
              <ChevronRight className="w-4 h-4 opacity-60" />
            </button>

            <button onClick={onComplete}
              className="w-full py-2 text-xs text-muted-foreground/40 hover:text-muted-foreground transition-colors"
            >
              Skip to full game replay
            </button>
          </motion.div>
        )}

        {/* ═══ STEP 1: THE MOMENT — interactive ═══ */}
        {step === 1 && moment?.fen && (
          <motion.div key="step1" {...pageTransition} className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Move {moment.move_number}. {moment.phase === "opening" ? "Still in the opening." : moment.phase === "endgame" ? "In the endgame." : "Middlegame."}
              {resultIcon === "loss" && " You were about to lose this game."}
            </p>

            <p className="text-lg font-heading text-foreground">
              What would you play here?
            </p>

            <div className="rounded-xl overflow-hidden border-2 border-primary/20">
              <LichessBoard
                ref={boardRef}
                fen={moment.fen}
                orientation={review.user_color === "black" ? "black" : "white"}
                interactive={!tryResult}
                viewOnly={!!tryResult}
                onMove={handleTryMove}
              />
            </div>

            {tryResult === "correct" && (
              <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
                className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20"
              >
                <div className="flex items-center gap-2">
                  <Check className="w-5 h-5 text-emerald-500" strokeWidth={2.5} />
                  <span className="text-sm font-medium text-emerald-400">
                    Exactly. You found {moment.best_move}.
                  </span>
                </div>
              </motion.div>
            )}

            {tryResult === "wrong" && (
              <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
                className="p-4 rounded-xl bg-red-500/10 border border-red-500/20"
              >
                <div className="flex items-center gap-2">
                  <XCircle className="w-5 h-5 text-red-400" strokeWidth={2} />
                  <span className="text-sm font-medium text-red-400">
                    Not quite. Let's see what happened...
                  </span>
                </div>
              </motion.div>
            )}

            {!tryResult && (
              <button onClick={() => { setTryResult("skipped"); setTimeout(() => setStep(2), 500); }}
                className="text-xs text-muted-foreground/40 hover:text-muted-foreground transition-colors"
              >
                Show me the answer
              </button>
            )}
          </motion.div>
        )}

        {/* ═══ STEP 2: WHAT YOU MISSED ═══ */}
        {step === 2 && moment && (
          <motion.div key="step2" {...pageTransition} className="space-y-4">
            <p className="text-lg font-heading text-foreground">
              {tryResult === "correct"
                ? "You got it right this time. But in the game..."
                : "Here's what happened."
              }
            </p>

            {/* Board with arrows */}
            <div className="rounded-xl overflow-hidden border border-border">
              <LichessBoard
                fen={moment.fen}
                orientation={review.user_color === "black" ? "black" : "white"}
                viewOnly={true}
                arrows={[
                  // Red arrow: what you played
                  ...(moment.your_move ? [] : []),
                  // Green arrow: best move (if we can parse it)
                ]}
              />
            </div>

            <div className="space-y-3">
              <div className="p-3 rounded-xl bg-red-500/[0.05] border border-red-500/15">
                <p className="text-xs text-red-400/60 font-bold uppercase tracking-widest mb-1">You played</p>
                <p className="text-sm text-foreground font-mono">{moment.your_move}</p>
              </div>

              <div className="p-3 rounded-xl bg-emerald-500/[0.05] border border-emerald-500/15">
                <p className="text-xs text-emerald-400/60 font-bold uppercase tracking-widest mb-1">Better was</p>
                <p className="text-sm text-foreground font-mono">{moment.best_move}</p>
              </div>

              {moment.threat && (
                <div className="p-3 rounded-xl bg-amber-500/[0.05] border border-amber-500/15">
                  <p className="text-xs text-amber-400/60 font-bold uppercase tracking-widest mb-1">What you missed</p>
                  <p className="text-sm text-foreground">
                    Their move <span className="font-mono text-amber-400">{moment.threat}</span> was threatening.
                  </p>
                </div>
              )}

              {moment.commentary && (
                <p className="text-xs text-muted-foreground leading-relaxed">{moment.commentary}</p>
              )}
            </div>

            <button onClick={next}
              className="w-full py-3.5 text-sm font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2"
            >
              {pattern?.is_recurring ? "Is this a pattern?" : "What should I do about it?"}
              <ChevronRight className="w-4 h-4 opacity-60" />
            </button>
          </motion.div>
        )}

        {/* ═══ STEP 3: THE PATTERN — cross-game ═══ */}
        {step === 3 && (
          <motion.div key="step3" {...pageTransition} className="space-y-5">
            {pattern?.is_recurring ? (
              <>
                <p className="text-lg font-heading text-foreground">
                  This isn't just this game.
                </p>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {pattern.label} — this happened in {pattern.games_with} of your last {pattern.games_checked} games.
                </p>

                {pattern.is_improving ? (
                  <div className="p-4 rounded-xl bg-emerald-500/[0.04] border border-emerald-500/15">
                    <p className="text-sm text-foreground">
                      But it's getting better. You went {pattern.recent_clean_streak} games without this.
                      Keep going.
                    </p>
                  </div>
                ) : (
                  <div className="p-4 rounded-xl bg-red-500/[0.04] border border-red-500/15">
                    <p className="text-sm text-foreground">
                      This is your most consistent problem right now.
                      One habit will fix it.
                    </p>
                  </div>
                )}
              </>
            ) : (
              <>
                <p className="text-lg font-heading text-foreground">
                  {behaviors.length > 0
                    ? `The main issue: ${behaviors[0].label.toLowerCase()}.`
                    : "Let's make sure this doesn't become a pattern."
                  }
                </p>
                <p className="text-sm text-muted-foreground">
                  This is the first time this specific issue stood out. Catch it now before it repeats.
                </p>
              </>
            )}

            <button onClick={() => setStep(4)}
              className="w-full py-3.5 text-sm font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2"
            >
              What do I do about it?
              <ChevronRight className="w-4 h-4 opacity-60" />
            </button>
          </motion.div>
        )}

        {/* ═══ STEP 4: THE RULE + ACTION ═══ */}
        {step === 4 && (
          <motion.div key="step4" {...pageTransition} className="space-y-5">
            <p className="text-lg font-heading text-foreground">
              One habit to build.
            </p>

            {/* The rule */}
            <div className="p-5 rounded-xl bg-amber-500/[0.04] border-2 border-amber-500/15">
              <p className="text-[10px] uppercase tracking-widest font-bold text-amber-500/60 mb-2">
                {s.rule_name || "Your rule"}
              </p>
              <p className="text-base text-foreground font-medium leading-snug">
                {s.rule}
              </p>
            </div>

            {/* Actions */}
            <div className="space-y-2">
              {/* Practice */}
              <button
                onClick={() => {
                  const patternMap = {
                    threat_awareness: "piece_safety", calculation: "calculation_depth",
                    patience: "calculation_depth", coordination: "piece_safety",
                    planning: "calculation_depth",
                  };
                  navigate(`/training/prescribed?weakness=${patternMap[s.focus_cluster] || "calculation_depth"}`);
                }}
                className="w-full py-3.5 text-sm font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2"
              >
                <Target className="w-4 h-4" strokeWidth={2} />
                Practice this — 3 min
                <ChevronRight className="w-4 h-4 opacity-60" />
              </button>

              {/* Play again */}
              <button
                onClick={() => navigate("/play-with-coach")}
                className="w-full py-3 text-sm font-medium rounded-xl border border-border text-foreground hover:bg-muted/50 transition-all flex items-center justify-center gap-2"
              >
                <Swords className="w-4 h-4" strokeWidth={2} />
                Play with Coach
              </button>

              {/* Full replay */}
              <button
                onClick={onComplete}
                className="w-full py-2.5 text-xs text-muted-foreground/50 hover:text-muted-foreground transition-colors flex items-center justify-center gap-1"
              >
                <Eye className="w-3 h-3" />
                See full game replay
              </button>
            </div>
          </motion.div>
        )}

      </AnimatePresence>
    </div>
  );
};

export default CoachSession;
