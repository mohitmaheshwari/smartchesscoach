import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";
import { 
  Loader2, 
  ChevronRight,
  Link as LinkIcon,
  ExternalLink,
  AlertCircle,
  CheckCircle,
  Lightbulb,
  Brain,
  ArrowRight,
  HelpCircle,
  Play,
  RotateCcw
} from "lucide-react";

// PDR Component with Visual Explanation
const DecisionReconstruction = ({ pdr }) => {
  const [phase, setPhase] = useState("choose"); // choose -> verify -> result
  const [selectedMove, setSelectedMove] = useState(null);
  const [selectedReason, setSelectedReason] = useState(null);
  const [currentFen, setCurrentFen] = useState(pdr?.fen || "start");
  const [customArrows, setCustomArrows] = useState([]);
  const [highlightSquares, setHighlightSquares] = useState({});
  const [explanationStep, setExplanationStep] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const [lineIndex, setLineIndex] = useState(0);
  
  // Reset state when pdr changes
  useEffect(() => {
    if (pdr?.fen) {
      setCurrentFen(pdr.fen);
      setPhase("choose");
      setSelectedMove(null);
      setSelectedReason(null);
      setCustomArrows([]);
      setHighlightSquares({});
      setExplanationStep(0);
    }
  }, [pdr?.fen]);
  
  const startWrongAnswerAnimation = useCallback(() => {
    if (!pdr?.refutation) {
      setExplanationStep(5);
      return;
    }
    
    setIsAnimating(true);
    const ref = pdr.refutation;
    
    // Step 1: Show user's move with arrow
    setTimeout(() => {
      setCurrentFen(ref.fen_after_user_move);
      setCustomArrows([]);
      setHighlightSquares({});
      setExplanationStep(1);
    }, 300);
    
    // Step 2: Show opponent's threat with arrow
    setTimeout(() => {
      setCustomArrows([
        [ref.from_square, ref.threat_square, "rgba(255, 80, 80, 0.8)"]
      ]);
      setHighlightSquares({
        [ref.threat_square]: { 
          backgroundColor: "rgba(255, 50, 50, 0.6)",
          boxShadow: "inset 0 0 10px rgba(255,0,0,0.5)"
        }
      });
      setExplanationStep(2);
    }, 1500);
    
    // Step 3: Play refutation move
    setTimeout(() => {
      setCurrentFen(ref.fen_after_refutation);
      setCustomArrows([]);
      setHighlightSquares({
        [ref.threat_square]: { 
          backgroundColor: "rgba(255, 50, 50, 0.7)",
        }
      });
      setExplanationStep(3);
    }, 3000);
    
    // Step 4: Show better move
    setTimeout(() => {
      if (pdr?.fen) {
        setCurrentFen(pdr.fen); // Reset to original position
        // Show arrow for best move
        try {
          const game = new Chess(pdr.fen);
          const move = game.move(pdr.best_move);
          if (move) {
            setCustomArrows([
              [move.from, move.to, "rgba(80, 200, 80, 0.8)"]
            ]);
            setHighlightSquares({
              [move.to]: { backgroundColor: "rgba(80, 200, 80, 0.5)" }
            });
          }
        } catch (e) {
          console.error(e);
        }
      }
      setExplanationStep(4);
    }, 4500);
    
    // Step 5: Show full explanation
    setTimeout(() => {
      setIsAnimating(false);
      setExplanationStep(5);
    }, 6000);
    
  }, [pdr]);
  
  const animateBestLine = useCallback(() => {
    const bestLine = pdr?.why_options?.best_line;
    if (!bestLine || bestLine.length < 1 || !pdr?.fen) return;
    
    setIsAnimating(true);
    
    try {
      const game = new Chess(pdr.fen);
      let idx = 0;
      
      const playNext = () => {
        if (idx >= bestLine.length) {
          setIsAnimating(false);
          return;
        }
        
        try {
          const move = game.move(bestLine[idx]);
          if (move) {
            setCurrentFen(game.fen());
            setCustomArrows([[move.from, move.to, "rgba(80, 200, 80, 0.8)"]]);
            setHighlightSquares({
              [move.from]: { backgroundColor: "rgba(80, 200, 80, 0.3)" },
              [move.to]: { backgroundColor: "rgba(80, 200, 80, 0.5)" }
            });
            setLineIndex(idx + 1);
          }
          idx++;
          setTimeout(playNext, 1200);
        } catch (e) {
          setIsAnimating(false);
        }
      };
      
      setTimeout(playNext, 500);
    } catch (e) {
      setIsAnimating(false);
    }
  }, [pdr]);
  
  const replayExplanation = useCallback(() => {
    if (pdr?.fen) {
      setCurrentFen(pdr.fen);
      setCustomArrows([]);
      setHighlightSquares({});
      setExplanationStep(0);
      setTimeout(() => startWrongAnswerAnimation(), 300);
    }
  }, [pdr, startWrongAnswerAnimation]);
  
  const handleMoveSelect = useCallback((move) => {
    setSelectedMove(move);
    
    if (move.is_best) {
      setPhase("verify");
    } else {
      setPhase("result");
      startWrongAnswerAnimation();
    }
  }, [startWrongAnswerAnimation]);
  
  const handleReasonSelect = useCallback((option) => {
    setSelectedReason(option);
    setPhase("result");
    
    if (option.is_correct) {
      animateBestLine();
    }
  }, [animateBestLine]);
  
  // Early return after all hooks
  if (!pdr || !pdr.fen || !pdr.candidates || pdr.candidates.length < 2) return null;
  
  const isCorrectMove = selectedMove?.is_best;
  const isCorrectReason = selectedReason?.is_correct;
  const ideaChain = pdr.idea_chain;
  const refutation = pdr.refutation;
  const whyOptions = pdr.why_options;
  
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-8"
    >
      <div className="flex items-center gap-2 mb-3">
        <Brain className="w-4 h-4 text-purple-500" />
        <span className="text-xs font-medium uppercase tracking-wider text-purple-500">
          Decision Moment
        </span>
      </div>
      
      <Card className="border-purple-500/20 bg-gradient-to-br from-purple-500/5 to-purple-600/10 overflow-hidden">
        <CardContent className="py-6">
          {/* Chessboard with arrows */}
          <div className="flex justify-center mb-6">
            <div className="w-[300px] h-[300px] rounded-lg overflow-hidden shadow-lg">
              <Chessboard
                position={currentFen}
                boardWidth={300}
                arePiecesDraggable={false}
                boardOrientation={pdr.player_color === "black" ? "black" : "white"}
                customArrows={customArrows}
                customSquareStyles={highlightSquares}
                customBoardStyle={{ borderRadius: "8px" }}
                customDarkSquareStyle={{ backgroundColor: "#4a4a4a" }}
                customLightSquareStyle={{ backgroundColor: "#8b8b8b" }}
              />
            </div>
          </div>
          
          <AnimatePresence mode="wait">
            {/* PHASE 1: Choose Move */}
            {phase === "choose" && (
              <motion.div key="choose" initial={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="text-center mb-6 px-4">
                  <p className="text-sm text-muted-foreground mb-2">Pause here.</p>
                  <p className="text-sm text-muted-foreground mb-3">
                    You are <span className="font-semibold text-foreground">{pdr.player_color}</span>.
                  </p>
                  <p className="text-lg font-medium">What would you play?</p>
                </div>
                
                <div className="flex justify-center gap-4">
                  {pdr.candidates.map((candidate, idx) => (
                    <Button
                      key={idx}
                      variant="outline"
                      size="lg"
                      onClick={() => handleMoveSelect(candidate)}
                      className="min-w-[100px] font-mono text-xl hover:bg-purple-500/10 hover:border-purple-500/50 h-14"
                    >
                      {candidate.move}
                    </Button>
                  ))}
                </div>
              </motion.div>
            )}
            
            {/* PHASE 2: Verify Understanding */}
            {phase === "verify" && whyOptions && (
              <motion.div key="verify" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                <div className="text-center mb-4">
                  <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-3">
                    <HelpCircle className="w-5 h-5 text-emerald-500" />
                  </div>
                  <p className="font-semibold text-emerald-500 mb-2">
                    Good choice: <span className="font-mono">{pdr.best_move}</span>
                  </p>
                  <p className="text-sm text-muted-foreground">But tell me — why is this better?</p>
                </div>
                
                <div className="space-y-2 max-w-sm mx-auto">
                  {whyOptions.options.map((option, idx) => (
                    <Button
                      key={idx}
                      variant="outline"
                      className="w-full justify-start text-left h-auto py-3 px-4 hover:bg-purple-500/10"
                      onClick={() => handleReasonSelect(option)}
                    >
                      <span className="text-sm">{option.text}</span>
                    </Button>
                  ))}
                </div>
              </motion.div>
            )}
            
            {/* PHASE 3: Result */}
            {phase === "result" && (
              <motion.div key="result" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="px-4">
                
                {/* CORRECT MOVE + CORRECT REASON */}
                {isCorrectMove && isCorrectReason && (
                  <div className="text-center">
                    <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-4">
                      <CheckCircle className="w-6 h-6 text-emerald-500" />
                    </div>
                    <p className="font-semibold text-emerald-500 mb-2">Excellent.</p>
                    <p className="text-sm text-muted-foreground mb-3">You understood the position correctly.</p>
                    <p className="text-sm mb-4">
                      In your game, you played <span className="font-mono font-semibold text-red-400">{pdr.user_original_move}</span> instead.
                    </p>
                    {whyOptions?.best_line && lineIndex > 0 && (
                      <div className="p-3 bg-emerald-500/10 rounded-lg mb-4">
                        <p className="text-xs text-emerald-400 mb-1">The line:</p>
                        <p className="font-mono text-sm">{whyOptions.best_line.slice(0, lineIndex).join(" ")}</p>
                      </div>
                    )}
                    <p className="text-sm font-medium">This is the discipline we are building.</p>
                  </div>
                )}
                
                {/* CORRECT MOVE + WRONG REASON */}
                {isCorrectMove && !isCorrectReason && (
                  <div className="text-center">
                    <div className="w-12 h-12 rounded-full bg-amber-500/20 flex items-center justify-center mx-auto mb-4">
                      <AlertCircle className="w-6 h-6 text-amber-500" />
                    </div>
                    <p className="font-semibold text-amber-500 mb-2">Right move, but...</p>
                    <p className="text-sm text-muted-foreground mb-4">Your reasoning needs work.</p>
                    <div className="p-4 bg-emerald-500/10 rounded-lg border border-emerald-500/20 mb-4">
                      <p className="text-sm font-medium text-emerald-400 mb-1">The real reason:</p>
                      <p className="text-sm">{whyOptions?.correct_explanation}</p>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Getting the move right is good. Understanding WHY makes it stick.
                    </p>
                  </div>
                )}
                
                {/* WRONG MOVE - Visual Explanation */}
                {!isCorrectMove && (
                  <div className="space-y-4">
                    {/* Step indicator */}
                    {isAnimating && (
                      <div className="flex justify-center items-center gap-2 text-sm text-purple-400">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>
                          {explanationStep === 1 && "You played " + pdr.user_original_move + "..."}
                          {explanationStep === 2 && "But now your opponent threatens..."}
                          {explanationStep === 3 && refutation?.refutation_move + "!"}
                          {explanationStep === 4 && "Better was " + pdr.best_move}
                        </span>
                      </div>
                    )}
                    
                    {/* Full explanation after animation */}
                    {explanationStep >= 5 && ideaChain && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                        {/* Replay button */}
                        <div className="flex justify-center">
                          <Button variant="ghost" size="sm" onClick={replayExplanation} className="text-xs">
                            <RotateCcw className="w-3 h-3 mr-1" /> Replay on board
                          </Button>
                        </div>
                        
                        {/* Idea Chain */}
                        <div className="space-y-3 p-4 bg-background/50 rounded-lg">
                          <StepItem 
                            num="1" 
                            label="Your plan" 
                            text={ideaChain.your_plan}
                            move={pdr.user_original_move}
                          />
                          
                          <div className="flex justify-center">
                            <ArrowRight className="w-4 h-4 text-muted-foreground" />
                          </div>
                          
                          <StepItem 
                            num="2" 
                            label="Why it felt right" 
                            text={ideaChain.why_felt_right}
                          />
                          
                          <div className="flex justify-center">
                            <ArrowRight className="w-4 h-4 text-red-400" />
                          </div>
                          
                          <StepItem 
                            num="3" 
                            label="But opponent plays" 
                            text={ideaChain.opponent_counter}
                            move={refutation?.refutation_move}
                            variant="danger"
                          />
                          
                          <div className="flex justify-center">
                            <ArrowRight className="w-4 h-4 text-red-400" />
                          </div>
                          
                          <StepItem 
                            num="4" 
                            label="Why it hurts" 
                            text={ideaChain.why_it_works}
                            variant="danger"
                          />
                          
                          <div className="flex justify-center">
                            <ArrowRight className="w-4 h-4 text-emerald-400" />
                          </div>
                          
                          <StepItem 
                            num="5" 
                            label="Better was" 
                            text={ideaChain.better_plan}
                            move={pdr.best_move}
                            variant="success"
                          />
                        </div>
                        
                        {/* Rule */}
                        <div className="p-4 bg-blue-500/10 rounded-lg border border-blue-500/20">
                          <p className="text-xs text-blue-400 uppercase tracking-wider mb-1">Remember</p>
                          <p className="text-sm font-medium">{ideaChain.rule}</p>
                        </div>
                      </motion.div>
                    )}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </CardContent>
      </Card>
    </motion.section>
  );
};

// Step item component for idea chain
const StepItem = ({ num, label, text, move, variant }) => {
  const colors = {
    danger: { bg: "bg-red-500/10", border: "border-red-500/20", text: "text-red-400" },
    success: { bg: "bg-emerald-500/10", border: "border-emerald-500/20", text: "text-emerald-400" },
    default: { bg: "bg-muted/50", border: "border-border", text: "text-muted-foreground" }
  };
  const c = colors[variant] || colors.default;
  
  return (
    <div className={`p-3 rounded-lg ${c.bg} border ${c.border}`}>
      <div className="flex items-start gap-3">
        <div className={`w-6 h-6 rounded-full bg-background flex items-center justify-center flex-shrink-0 ${c.text}`}>
          <span className="text-xs font-bold">{num}</span>
        </div>
        <div className="flex-1">
          <p className={`text-xs uppercase tracking-wider mb-1 ${c.text}`}>{label}</p>
          <p className="text-sm">
            {move && <span className={`font-mono font-bold ${c.text} mr-1`}>{move}</span>}
            {text}
          </p>
        </div>
      </div>
    </div>
  );
};

// Main Coach Component
const Coach = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [coachData, setCoachData] = useState(null);
  const [accounts, setAccounts] = useState({ chess_com: null, lichess: null });
  const [platform, setPlatform] = useState(null);
  const [username, setUsername] = useState("");
  const [linking, setLinking] = useState(false);

  useEffect(() => {
    fetchCoachData();
  }, []);

  const fetchCoachData = async () => {
    try {
      const [coachRes, accountsRes] = await Promise.all([
        fetch(`${API}/coach/today`, { credentials: "include" }),
        fetch(`${API}/journey/linked-accounts`, { credentials: "include" })
      ]);
      
      if (coachRes.ok) setCoachData(await coachRes.json());
      if (accountsRes.ok) setAccounts(await accountsRes.json());
    } catch (e) {
      console.error("Failed to fetch coach data:", e);
    } finally {
      setLoading(false);
    }
  };

  const linkAccount = async () => {
    if (!username.trim()) return toast.error("Enter username");
    setLinking(true);
    try {
      const res = await fetch(`${API}/journey/link-account`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ platform, username: username.trim() })
      });
      if (!res.ok) throw new Error((await res.json()).detail);
      toast.success("Account linked. Games will sync shortly.");
      setPlatform(null);
      setUsername("");
      fetchCoachData();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLinking(false);
    }
  };

  const handleGoPlay = () => {
    const url = accounts.chess_com ? "https://chess.com/play/online" : "https://lichess.org";
    window.open(url, "_blank");
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  const needsAccountLink = coachData?.message === "Link your chess account to get started";
  const hasData = coachData?.has_data;

  return (
    <Layout user={user}>
      <div className="max-w-xl mx-auto" data-testid="coach-page">
        
        {needsAccountLink && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mt-12">
            <Card className="border-2 border-dashed border-muted-foreground/20">
              <CardContent className="py-16 text-center">
                <div className="w-20 h-20 rounded-full bg-muted flex items-center justify-center mx-auto mb-6">
                  <LinkIcon className="w-8 h-8 text-muted-foreground" />
                </div>
                <h2 className="font-heading font-semibold text-2xl mb-3">Link Your Chess Account</h2>
                <p className="text-muted-foreground mb-8 max-w-sm mx-auto">
                  Connect your Chess.com or Lichess account so I can analyze your games and coach you.
                </p>
                {!platform ? (
                  <div className="flex justify-center gap-3">
                    <Button onClick={() => setPlatform("chess.com")} variant="outline" size="lg">Chess.com</Button>
                    <Button onClick={() => setPlatform("lichess")} variant="outline" size="lg">Lichess</Button>
                  </div>
                ) : (
                  <div className="max-w-xs mx-auto space-y-3">
                    <p className="text-sm text-muted-foreground mb-2">Enter your {platform} username</p>
                    <Input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} disabled={linking} />
                    <div className="flex gap-2">
                      <Button onClick={linkAccount} disabled={linking} className="flex-1">
                        {linking && <Loader2 className="w-4 h-4 animate-spin mr-2" />}Connect
                      </Button>
                      <Button variant="ghost" onClick={() => setPlatform(null)}>Cancel</Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {!needsAccountLink && !hasData && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mt-16 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">{coachData?.message || "Analyzing your games..."}</p>
          </motion.div>
        )}

        {hasData && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-8">
            {coachData.pdr && <DecisionReconstruction pdr={coachData.pdr} />}

            <div className="space-y-6">
              {coachData.correction && (
                <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
                  <div className="flex items-center gap-2 mb-3">
                    <AlertCircle className="w-4 h-4 text-amber-500" />
                    <span className="text-xs font-medium uppercase tracking-wider text-amber-500">Correct This</span>
                  </div>
                  <Card className="border-amber-500/20 bg-amber-500/5">
                    <CardContent className="py-6">
                      <h2 className="font-heading font-bold text-xl mb-2">{coachData.correction.title}</h2>
                      <p className="text-muted-foreground text-sm mb-2">{coachData.correction.context}</p>
                      <p className="text-sm text-foreground/80">{coachData.correction.severity}</p>
                    </CardContent>
                  </Card>
                </motion.section>
              )}

              {coachData.reinforcement && (
                <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
                  <div className="flex items-center gap-2 mb-3">
                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                    <span className="text-xs font-medium uppercase tracking-wider text-emerald-500">Keep Doing This</span>
                  </div>
                  <Card className="border-emerald-500/20 bg-emerald-500/5">
                    <CardContent className="py-6">
                      <h2 className="font-heading font-bold text-xl mb-2">{coachData.reinforcement.title}</h2>
                      <p className="text-muted-foreground text-sm mb-2">{coachData.reinforcement.context}</p>
                      <p className="text-sm text-foreground/80">{coachData.reinforcement.trend}</p>
                    </CardContent>
                  </Card>
                </motion.section>
              )}

              {coachData.rule && (
                <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
                  <div className="flex items-center gap-2 mb-3">
                    <Lightbulb className="w-4 h-4 text-blue-500" />
                    <span className="text-xs font-medium uppercase tracking-wider text-blue-500">Remember</span>
                  </div>
                  <Card className="border-blue-500/20 bg-gradient-to-br from-blue-500/5 to-blue-600/10">
                    <CardContent className="py-8 text-center">
                      <p className="text-lg font-medium whitespace-pre-line leading-relaxed">{coachData.rule}</p>
                    </CardContent>
                  </Card>
                </motion.section>
              )}

              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="pt-4 text-center">
                <Button size="lg" className="h-14 px-12 text-lg font-semibold" onClick={handleGoPlay}>
                  Go Play. I'll review.
                  <ExternalLink className="w-5 h-5 ml-2" />
                </Button>
                <p className="text-xs text-muted-foreground mt-3">Games auto-analyzed from Chess.com / Lichess</p>
              </motion.div>

              <div className="text-center pt-4">
                <button onClick={() => navigate("/progress")} className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1">
                  View Progress<ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </Layout>
  );
};

export default Coach;
