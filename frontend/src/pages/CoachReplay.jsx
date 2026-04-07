/**
 * Coach Replay — Multi-moment guided game review
 *
 * Shows 3-4 key moments from the game. At each moment:
 * - Board shows the position
 * - Coach reads the board (what was happening)
 * - Explains what the user missed
 * - Connects to their behavior pattern
 *
 * Flow per moment:
 * 1. Context (eval-driven: "You were winning" / "Position was equal")
 * 2. Board reading (what's on the board — LLM-powered)
 * 3. What happened (the move, shown on board)
 * 4. Pause → "Continue"
 *
 * After all moments: Rule + Exit
 */

import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { ChevronRight, ArrowLeft, BookOpen, Eye } from "lucide-react";

const CoachReplay = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [momentIndex, setMomentIndex] = useState(0);
  const [subStep, setSubStep] = useState(0); // 0=context, 1=board reading, 2=after move

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/replay/${gameId}`, { credentials: "include" });
        if (res.ok) {
          setData(await res.json());
        } else {
          navigate(`/game/${gameId}`, { replace: true });
        }
      } catch (e) {
        navigate(`/game/${gameId}`, { replace: true });
      } finally {
        setLoading(false);
      }
    })();
  }, [gameId]);

  if (loading) {
    return <Layout user={user}><div className="flex items-center justify-center h-[60vh]"><div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" /></div></Layout>;
  }

  if (!data || !data.moments || data.moments.length === 0) {
    navigate(`/game/${gameId}`, { replace: true });
    return null;
  }

  const moments = data.moments;
  const rule = data.rule;
  const behaviorText = data.behavior;
  const userColor = data.user_color || "white";
  const totalMoments = moments.length;
  const isFinished = momentIndex >= totalMoments;

  const current = !isFinished ? moments[momentIndex] : null;

  const getFen = () => {
    if (!current) return moments[moments.length - 1]?.fen_before || "";
    if (subStep === 2 && current.fen_after) return current.fen_after;
    return current.fen_before || "";
  };

  const advanceSubStep = () => {
    if (current?.type === "context") {
      // Context only has sub-step 0 → next moment
      setMomentIndex(momentIndex + 1);
      setSubStep(0);
    } else if (subStep === 0) {
      setSubStep(1); // Show board reading
    } else if (subStep === 1) {
      if (current.fen_after) {
        setSubStep(2); // Show after-move position
      } else {
        setMomentIndex(momentIndex + 1);
        setSubStep(0);
      }
    } else {
      setMomentIndex(momentIndex + 1);
      setSubStep(0);
    }
  };

  return (
    <Layout user={user}>
      <div className="h-[calc(100vh-80px)] flex" data-testid="coach-replay">

        {/* LEFT: Board */}
        <div className="w-1/2 flex items-center justify-center bg-muted/20 p-6 relative">
          <motion.div
            className="w-full max-w-[520px] aspect-square relative"
            key={`${momentIndex}-${subStep}`}
            initial={{ opacity: 0.8 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            <LichessBoard
              fen={getFen()}
              orientation={userColor}
              viewOnly={true}
            />

            {/* Moment indicator */}
            {!isFinished && (
              <div className="absolute top-2 left-2 bg-black/60 text-white text-[10px] font-medium px-2.5 py-1 rounded backdrop-blur-sm">
                {current.type === "context" && "Before the trouble"}
                {current.type === "warning" && "First sign of trouble"}
                {current.type === "break" && "The decisive moment"}
                {current.type === "missed_chance" && "Missed opportunity"}
              </div>
            )}

            {/* Progress dots */}
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5">
              {moments.map((_, i) => (
                <div key={i} className={`w-2 h-2 rounded-full transition-all ${
                  i < momentIndex ? "bg-emerald-500/60" :
                  i === momentIndex ? "bg-white" :
                  "bg-white/20"
                }`} />
              ))}
              <div className={`w-2 h-2 rounded-full transition-all ${isFinished ? "bg-white" : "bg-white/20"}`} />
            </div>
          </motion.div>
        </div>

        {/* RIGHT: Narrative */}
        <div className="w-1/2 flex flex-col justify-center px-10 py-8">
          <AnimatePresence mode="wait">

            {/* ═══ MOMENT STEPS ═══ */}
            {!isFinished && current && (
              <Step key={`${momentIndex}-${subStep}`}>

                {/* Sub-step 0: Context — what was the position? */}
                {subStep === 0 && (
                  <>
                    <p className="text-xl font-heading text-foreground leading-snug mb-3">
                      {current.context_text}
                    </p>

                    {current.type === "context" && (
                      <Subtle>Look at the position. Everything is still ok here.</Subtle>
                    )}
                    {current.type === "warning" && (
                      <p className="text-sm text-muted-foreground mb-6">
                        Something is about to go wrong.
                      </p>
                    )}
                    {current.type === "break" && (
                      <p className="text-sm text-muted-foreground mb-6">
                        This is the moment that decided the game.
                      </p>
                    )}
                    {current.type === "missed_chance" && (
                      <p className="text-sm text-muted-foreground mb-6">
                        Your opponent gave you a chance here.
                      </p>
                    )}

                    <Continue onClick={advanceSubStep} />
                  </>
                )}

                {/* Sub-step 1: Board reading — what should user have seen? */}
                {subStep === 1 && (
                  <>
                    <p className="text-xs text-muted-foreground/50 uppercase tracking-wider mb-3">
                      What was happening on the board
                    </p>

                    {current.board_reading ? (
                      <p className="text-[15px] text-foreground leading-[1.8] mb-6">
                        {current.board_reading}
                      </p>
                    ) : (
                      <p className="text-[15px] text-muted-foreground leading-[1.8] mb-6">
                        Take a moment to look at the position.
                        What do you notice?
                      </p>
                    )}

                    {current.type !== "context" && (
                      <motion.button
                        onClick={advanceSubStep}
                        className="px-5 py-2.5 text-sm font-semibold rounded-lg border border-border text-foreground hover:bg-card transition-all flex items-center gap-2"
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                      >
                        <Eye className="w-4 h-4" strokeWidth={1.5} />
                        {current.fen_after ? "Show what happened" : "Continue"}
                      </motion.button>
                    )}
                    {current.type === "context" && <Continue onClick={advanceSubStep} />}
                  </>
                )}

                {/* Sub-step 2: After move — what happened */}
                {subStep === 2 && (
                  <>
                    {current.type === "break" && (
                      <>
                        <p className="text-xl font-heading text-foreground leading-snug mb-3">
                          This is what you missed.
                        </p>
                        <p className="text-sm text-muted-foreground mb-6">
                          The position changed. You didn't see it coming.
                        </p>
                      </>
                    )}
                    {current.type === "warning" && (
                      <>
                        <p className="text-lg text-foreground leading-snug mb-3">
                          This was the first slip.
                        </p>
                        <p className="text-sm text-muted-foreground mb-6">
                          Not fatal yet. But the position started shifting.
                        </p>
                      </>
                    )}
                    {current.type === "missed_chance" && (
                      <>
                        <p className="text-lg text-foreground leading-snug mb-3">
                          You didn't take advantage.
                        </p>
                        <p className="text-sm text-muted-foreground mb-6">
                          There was a chance here. It passed.
                        </p>
                      </>
                    )}

                    <Continue onClick={advanceSubStep} />
                  </>
                )}
              </Step>
            )}

            {/* ═══ FINISHED — Rule + Exit ═══ */}
            {isFinished && (
              <Step key="finished">
                {/* Behavior connection */}
                {behaviorText && (
                  <p className="text-[15px] text-foreground/70 leading-[1.7] mb-6">
                    {behaviorText}
                  </p>
                )}

                {/* Rule */}
                {rule && (
                  <motion.div
                    className="rounded-xl bg-amber-500/[0.05] border border-amber-500/15 p-6 mb-6"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                  >
                    <p className="text-lg font-heading font-semibold text-foreground mb-2">
                      {rule.name}
                    </p>
                    <p className="text-base text-foreground/80 leading-relaxed">
                      {rule.rule}
                    </p>
                  </motion.div>
                )}

                {/* Directive + exit */}
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
                  <p className="text-sm text-foreground/50 font-medium mb-6">
                    Next time you play — catch this before you move.
                  </p>

                  <div className="space-y-3">
                    <button onClick={() => navigate(`/game/${gameId}`)}
                      className="w-full py-3 text-sm font-medium rounded-xl border border-border text-foreground hover:bg-card transition-all flex items-center justify-center gap-2">
                      <BookOpen className="w-4 h-4" strokeWidth={1.5} />
                      Open full analysis
                    </button>
                    <button onClick={() => navigate("/lab")}
                      className="w-full py-3 text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-1.5">
                      <ArrowLeft className="w-3.5 h-3.5" />
                      Back to Lab
                    </button>
                  </div>
                </motion.div>
              </Step>
            )}

          </AnimatePresence>
        </div>
      </div>
    </Layout>
  );
};

const Step = ({ children }) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -8 }}
    transition={{ duration: 0.4 }}
  >
    {children}
  </motion.div>
);

const Continue = ({ onClick }) => (
  <motion.button
    onClick={onClick}
    className="text-sm text-muted-foreground/60 hover:text-foreground transition-colors flex items-center gap-1.5 group"
    whileHover={{ x: 2 }}
  >
    Continue
    <ChevronRight className="w-3.5 h-3.5 opacity-40 group-hover:opacity-80 transition-opacity" />
  </motion.button>
);

const Subtle = ({ children }) => (
  <p className="text-xs text-muted-foreground/40 mb-4">{children}</p>
);

export default CoachReplay;
