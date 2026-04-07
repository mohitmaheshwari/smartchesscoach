/**
 * Coach Replay — "This is the exact moment your thinking broke."
 *
 * Guided. Behavioral. Cinematic.
 *
 * Every step: fade, breathe, impact.
 * Board is the teacher. Text is support.
 */

import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { ChevronRight, ArrowLeft, Eye, BookOpen } from "lucide-react";

const CoachReplay = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  const [coaching, setCoaching] = useState(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(0);
  const [boardDimmed, setBoardDimmed] = useState(false);
  const [showThreatHighlight, setShowThreatHighlight] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/lab-coach-pick`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setCoaching(data.coaching);
        }
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, [gameId]);

  if (loading) {
    return <Layout user={user}><div className="flex items-center justify-center h-[60vh]"><div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" /></div></Layout>;
  }

  const pg = coaching?.priority_game;
  const replay = pg?.replay;
  const rule = coaching?.rule;

  if (!replay || !replay.mistake_fen) {
    navigate(`/game/${gameId}`, { replace: true });
    return null;
  }

  const userColor = pg.user_color || "white";

  const getFen = () => {
    switch (step) {
      case 0: return replay.setup_fen || replay.mistake_fen;
      case 1: return replay.after_move_fen || replay.mistake_fen;
      case 2: return replay.after_move_fen || replay.mistake_fen;
      case 3: return replay.after_reply_fen || replay.after_move_fen;
      case 4: return replay.after_reply_fen || replay.after_move_fen;
      case 5: return replay.mistake_fen;
      case 6: return replay.mistake_fen;
      default: return replay.mistake_fen;
    }
  };

  const advance = (nextStep) => {
    const target = nextStep !== undefined ? nextStep : step + 1;
    if (target > 6) return;

    // Step-specific effects
    if (target === 2) setBoardDimmed(true);      // Thinking step — dim board
    if (target === 3) {
      setBoardDimmed(false);                      // Reveal — undim
      setShowThreatHighlight(true);               // Show threat
      setTimeout(() => setShowThreatHighlight(false), 3000); // Pulse fades
    }
    if (target !== 2) setBoardDimmed(false);

    setStep(target);
  };

  return (
    <Layout user={user}>
      <div className="h-[calc(100vh-80px)] flex" data-testid="coach-replay">

        {/* LEFT: Board */}
        <div className="w-1/2 flex items-center justify-center bg-muted/20 p-6 relative">
          <motion.div
            className="w-full max-w-[520px] aspect-square relative"
            animate={{
              scale: step === 3 ? 1.02 : 1,
              opacity: boardDimmed ? 0.6 : 1,
            }}
            transition={{ duration: 0.4, ease: "easeInOut" }}
          >
            <LichessBoard
              fen={getFen()}
              orientation={userColor}
              viewOnly={true}
            />

            {/* Board overlay label */}
            {step === 0 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
                className="absolute top-2 left-2 bg-black/60 text-white text-[10px] font-medium px-2.5 py-1 rounded backdrop-blur-sm"
              >
                Before your mistake
              </motion.div>
            )}

            {/* Threat pulse effect */}
            {showThreatHighlight && step === 3 && (
              <motion.div
                className="absolute inset-0 rounded pointer-events-none"
                initial={{ boxShadow: "inset 0 0 0 0 rgba(239,68,68,0)" }}
                animate={{
                  boxShadow: [
                    "inset 0 0 0 0 rgba(239,68,68,0)",
                    "inset 0 0 30px 5px rgba(239,68,68,0.15)",
                    "inset 0 0 0 0 rgba(239,68,68,0)",
                  ],
                }}
                transition={{ duration: 1.5, times: [0, 0.5, 1], repeat: 1 }}
              />
            )}
          </motion.div>
        </div>

        {/* RIGHT: Coaching narrative */}
        <div className="w-1/2 flex flex-col justify-center px-10 py-8">
          <AnimatePresence mode="wait">

            {/* Step 0: Setup */}
            {step === 0 && (
              <Step key="s0">
                <h2 className="text-xl font-heading text-foreground leading-snug mb-2">
                  You were in control here.
                </h2>
                <p className="text-base text-muted-foreground mb-8">
                  Nothing was going wrong.
                </p>
                <Subtle>Take a second to look at the position.</Subtle>
                <Continue onClick={() => advance(1)} />
              </Step>
            )}

            {/* Step 1: User move */}
            {step === 1 && (
              <Step key="s1">
                <h2 className="text-xl font-heading text-foreground leading-snug mb-3">
                  Then you made your move.
                </h2>
                <p className="text-base text-muted-foreground mb-8">
                  Now pause here.
                </p>
                <Continue onClick={() => advance(2)} />
              </Step>
            )}

            {/* Step 2: Think */}
            {step === 2 && (
              <Step key="s2">
                <p className="text-lg text-foreground leading-relaxed mb-2">
                  Look at this position.
                </p>
                <p className="text-lg text-foreground/60 leading-relaxed mb-8">
                  If you make your move here...<br />
                  what can your opponent do next?
                </p>
                <motion.button
                  onClick={() => advance(3)}
                  className="px-5 py-2.5 text-sm font-semibold rounded-lg border border-border text-foreground hover:bg-card transition-all flex items-center gap-2"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <Eye className="w-4 h-4" strokeWidth={1.5} />
                  Show me
                </motion.button>
              </Step>
            )}

            {/* Step 3: Reveal */}
            {step === 3 && (
              <Step key="s3">
                <motion.h2
                  className="text-xl font-heading text-foreground leading-snug mb-3"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4, duration: 0.4 }}
                >
                  This is what you missed.
                </motion.h2>
                <motion.p
                  className="text-base text-muted-foreground mb-8"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.8, duration: 0.4 }}
                >
                  This move creates a threat you didn't see.
                </motion.p>
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 1.2 }}
                >
                  <Continue onClick={() => advance(4)} />
                </motion.div>
              </Step>
            )}

            {/* Step 4: Realization */}
            {step === 4 && (
              <Step key="s4">
                <div className="space-y-4 mb-8">
                  <motion.p className="text-base text-foreground leading-relaxed"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
                    You stopped your thinking at your move.
                  </motion.p>
                  <motion.p className="text-base text-foreground/50 leading-relaxed"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
                    You didn't stay to see what changes after it.
                  </motion.p>
                  <motion.p className="text-base text-foreground font-medium"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.9 }}>
                    That's where it slipped.
                  </motion.p>
                </div>
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.3 }}>
                  <Continue onClick={() => advance(5)} />
                </motion.div>
              </Step>
            )}

            {/* Step 5: Rule */}
            {step === 5 && (
              <Step key="s5">
                {rule && (
                  <motion.div
                    className="rounded-xl bg-amber-500/[0.05] border border-amber-500/15 p-6 mb-8"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2, duration: 0.5 }}
                  >
                    <p className="text-lg font-heading font-semibold text-foreground mb-2">
                      {rule.name}
                    </p>
                    <p className="text-base text-foreground/80 leading-relaxed">
                      {rule.rule}
                    </p>
                  </motion.div>
                )}
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }}>
                  <Continue onClick={() => advance(6)} />
                </motion.div>
              </Step>
            )}

            {/* Step 6: Exit */}
            {step === 6 && (
              <Step key="s6">
                <motion.p
                  className="text-base text-foreground/70 font-medium mb-8"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.2 }}
                >
                  Next time you play — catch this before you move.
                </motion.p>
                <motion.div className="space-y-3"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
                  <motion.button
                    onClick={() => navigate(`/game/${pg.game_id}`)}
                    className="w-full py-3 text-sm font-medium rounded-xl border border-border text-foreground hover:bg-card transition-all flex items-center justify-center gap-2"
                    whileHover={{ scale: 1.01 }}
                  >
                    <BookOpen className="w-4 h-4" strokeWidth={1.5} />
                    Open full analysis
                  </motion.button>
                  <button onClick={() => navigate("/lab")}
                    className="w-full py-3 text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-1.5">
                    <ArrowLeft className="w-3.5 h-3.5" />
                    Back to Lab
                  </button>
                </motion.div>
              </Step>
            )}

          </AnimatePresence>
        </div>
      </div>
    </Layout>
  );
};

// ── Reusable components ──

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
