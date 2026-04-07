/**
 * Coach Replay — "This is the exact moment your thinking broke."
 *
 * Guided. Behavioral. Minimal.
 * The coach drives. The user watches, thinks, realizes.
 *
 * Steps:
 * 1. Setup — "You were in control here. Nothing was going wrong."
 * 2. User move — board animates, "Then you made your move."
 * 3. Think — "What can your opponent do next?" [Show me]
 * 4. Reveal — board shows opponent reply, "This is what you missed."
 * 5. Realization — "You stopped your thinking at your move."
 * 6. Rule — the coaching card
 * 7. Exit — full analysis link + back to lab
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
  const mistakeKey = coaching?.root_problem?.pattern || "calculation_depth";

  // If no replay data, fall back to full analysis
  if (!replay || !replay.mistake_fen) {
    navigate(`/game/${gameId}`, { replace: true });
    return null;
  }

  const userColor = pg.user_color || "white";

  // Board FEN per step
  const getFen = () => {
    switch (step) {
      case 0: return replay.setup_fen || replay.mistake_fen; // Setup — calm position
      case 1: return replay.after_move_fen || replay.mistake_fen; // After user's move
      case 2: return replay.after_move_fen || replay.mistake_fen; // Think — same position
      case 3: return replay.after_reply_fen || replay.after_move_fen; // Reveal — opponent's reply
      case 4: return replay.after_reply_fen || replay.after_move_fen; // Realization
      case 5: return replay.mistake_fen; // Rule — back to before mistake
      case 6: return replay.mistake_fen; // Exit
      default: return replay.mistake_fen;
    }
  };

  const advance = () => {
    if (step < 6) setStep(step + 1);
  };

  return (
    <Layout user={user}>
      <div className="h-[calc(100vh-80px)] flex" data-testid="coach-replay">

        {/* LEFT: Board */}
        <div className="w-1/2 flex items-center justify-center bg-muted/20 p-6">
          <div className="w-full max-w-[520px] aspect-square">
            <LichessBoard
              fen={getFen()}
              orientation={userColor}
              viewOnly={true}
            />
          </div>
        </div>

        {/* RIGHT: Coaching narrative */}
        <div className="w-1/2 flex flex-col justify-center px-10 py-8">
          <AnimatePresence mode="wait">

            {/* Step 0: Setup — user consciously enters */}
            {step === 0 && (
              <NarrativeStep key="setup">
                <p className="text-xl font-heading text-foreground leading-snug mb-2">
                  You were in control here.
                </p>
                <p className="text-base text-muted-foreground mb-8">
                  Nothing was going wrong.
                </p>
                <p className="text-xs text-muted-foreground/50 mb-3">Take a second to look at the position.</p>
                <button onClick={advance}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5">
                  Continue <ChevronRight className="w-3.5 h-3.5 opacity-60" />
                </button>
              </NarrativeStep>
            )}

            {/* Step 1: User move — mental checkpoint */}
            {step === 1 && (
              <NarrativeStep key="move">
                <p className="text-xl font-heading text-foreground leading-snug mb-3">
                  Then you made your move.
                </p>
                <p className="text-base text-muted-foreground mb-8">
                  Now pause here.
                </p>
                <button onClick={advance}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5">
                  Continue <ChevronRight className="w-3.5 h-3.5 opacity-60" />
                </button>
              </NarrativeStep>
            )}

            {/* Step 2: Think — forced engagement */}
            {step === 2 && (
              <NarrativeStep key="think">
                <p className="text-lg text-foreground leading-relaxed mb-2">
                  Look at this position.
                </p>
                <p className="text-lg text-foreground leading-relaxed mb-8">
                  If you make your move here...
                  <br />
                  <span className="text-foreground/60">what can your opponent do next?</span>
                </p>
                <button onClick={advance}
                  className="px-5 py-2.5 text-sm font-semibold rounded-lg border border-border text-foreground hover:bg-card transition-all flex items-center gap-2">
                  <Eye className="w-4 h-4" strokeWidth={1.5} />
                  Show me
                </button>
              </NarrativeStep>
            )}

            {/* Step 3: Reveal — with emphasis on threat */}
            {step === 3 && (
              <NarrativeStep key="reveal">
                <p className="text-xl font-heading text-foreground leading-snug mb-3">
                  This is what you missed.
                </p>
                <p className="text-base text-muted-foreground mb-8">
                  This move creates a threat you didn't see.
                </p>
                <button onClick={advance}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5">
                  Continue <ChevronRight className="w-3.5 h-3.5 opacity-60" />
                </button>
              </NarrativeStep>
            )}

            {/* Step 4: Realization */}
            {step === 4 && (
              <NarrativeStep key="realize">
                <div className="space-y-4 mb-8">
                  <p className="text-base text-foreground leading-relaxed">
                    You stopped your thinking at your move.
                  </p>
                  <p className="text-base text-foreground/60 leading-relaxed">
                    You didn't stay to see what changes after it.
                  </p>
                  <p className="text-base text-foreground font-medium">
                    That's where it slipped.
                  </p>
                </div>
                <button onClick={advance}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5">
                  Continue <ChevronRight className="w-3.5 h-3.5 opacity-60" />
                </button>
              </NarrativeStep>
            )}

            {/* Step 5: Rule */}
            {step === 5 && (
              <NarrativeStep key="rule">
                {rule && (
                  <div className="rounded-xl bg-amber-500/[0.05] border border-amber-500/15 p-6 mb-8">
                    <p className="text-lg font-heading font-semibold text-foreground mb-2">
                      {rule.name}
                    </p>
                    <p className="text-base text-foreground/80 leading-relaxed">
                      {rule.rule}
                    </p>
                  </div>
                )}
                <button onClick={advance}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5">
                  Continue <ChevronRight className="w-3.5 h-3.5 opacity-60" />
                </button>
              </NarrativeStep>
            )}

            {/* Step 6: Closing — directional */}
            {step === 6 && (
              <NarrativeStep key="exit">
                <p className="text-base text-foreground/70 font-medium mb-8">
                  Next time you play — catch this before you move.
                </p>
                <div className="space-y-3">
                  <button onClick={() => navigate(`/game/${pg.game_id}`)}
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
              </NarrativeStep>
            )}

          </AnimatePresence>
        </div>
      </div>
    </Layout>
  );
};

const NarrativeStep = ({ children }) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -8 }}
    transition={{ duration: 0.4 }}
  >
    {children}
  </motion.div>
);

export default CoachReplay;
