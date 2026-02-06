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
  Brain,
  ArrowRight,
  HelpCircle,
  RotateCcw,
  TrendingDown,
  TrendingUp,
  Minus,
  Play,
  CheckCircle,
  AlertCircle
} from "lucide-react";

// ============================================
// PDR Component - Personalized Decision Reconstruction
// ============================================
const DecisionReconstruction = ({ pdr }) => {
  const [phase, setPhase] = useState("choose");
  const [selectedMove, setSelectedMove] = useState(null);
  const [selectedReason, setSelectedReason] = useState(null);
  const [currentFen, setCurrentFen] = useState(pdr?.fen || "start");
  const [customArrows, setCustomArrows] = useState([]);
  const [highlightSquares, setHighlightSquares] = useState({});
  const [explanationStep, setExplanationStep] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const [lineIndex, setLineIndex] = useState(0);
  
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
    
    setTimeout(() => {
      setCurrentFen(ref.fen_after_user_move);
      setCustomArrows([]);
      setHighlightSquares({});
      setExplanationStep(1);
    }, 300);
    
    setTimeout(() => {
      setCustomArrows([
        { from: ref.from_square, to: ref.threat_square, color: "rgba(255, 80, 80, 0.9)" }
      ]);
      setHighlightSquares({
        [ref.threat_square]: { backgroundColor: "rgba(255, 50, 50, 0.6)" }
      });
      setExplanationStep(2);
    }, 1500);
    
    setTimeout(() => {
      setCurrentFen(ref.fen_after_refutation);
      setCustomArrows([]);
      setHighlightSquares({ [ref.threat_square]: { backgroundColor: "rgba(255, 50, 50, 0.7)" } });
      setExplanationStep(3);
    }, 3000);
    
    setTimeout(() => {
      if (pdr?.fen) {
        setCurrentFen(pdr.fen);
        try {
          const game = new Chess(pdr.fen);
          const move = game.move(pdr.best_move);
          if (move) {
            setCustomArrows([{ from: move.from, to: move.to, color: "rgba(80, 200, 80, 0.9)" }]);
            setHighlightSquares({ [move.to]: { backgroundColor: "rgba(80, 200, 80, 0.5)" } });
          }
        } catch (e) {}
      }
      setExplanationStep(4);
    }, 4500);
    
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
        if (idx >= bestLine.length) { setIsAnimating(false); return; }
        try {
          const move = game.move(bestLine[idx]);
          if (move) {
            setCurrentFen(game.fen());
            setCustomArrows([{ from: move.from, to: move.to, color: "rgba(80, 200, 80, 0.9)" }]);
            setHighlightSquares({
              [move.from]: { backgroundColor: "rgba(80, 200, 80, 0.3)" },
              [move.to]: { backgroundColor: "rgba(80, 200, 80, 0.5)" }
            });
            setLineIndex(idx + 1);
          }
          idx++;
          setTimeout(playNext, 1200);
        } catch (e) { setIsAnimating(false); }
      };
      setTimeout(playNext, 500);
    } catch (e) { setIsAnimating(false); }
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
    if (option.is_correct) animateBestLine();
  }, [animateBestLine]);
  
  if (!pdr || !pdr.fen || !pdr.candidates || pdr.candidates.length < 2) return null;
  
  const isCorrectMove = selectedMove?.is_best;
  const isCorrectReason = selectedReason?.is_correct;
  const ideaChain = pdr.idea_chain;
  const refutation = pdr.refutation;
  const whyOptions = pdr.why_options;
  const gameContext = pdr.game_context;
  
  return (
    <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-purple-500" />
          <span className="text-xs font-medium uppercase tracking-wider text-purple-500">Reflection Moment</span>
        </div>
        {gameContext && (
          <div className="text-xs text-muted-foreground">
            vs {gameContext.opponent || "Opponent"} • {gameContext.platform || "Chess.com"}
          </div>
        )}
      </div>
      
      <Card className="border-purple-500/20 bg-gradient-to-br from-purple-500/5 to-purple-600/10">
        <CardContent className="py-6">
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
            {phase === "choose" && (
              <motion.div key="choose" exit={{ opacity: 0 }}>
                <div className="text-center mb-6 px-4">
                  <p className="text-muted-foreground mb-2">Pause here.</p>
                  <p className="text-lg font-medium">Before you move — what would you play?</p>
                </div>
                <div className="flex justify-center gap-4">
                  {pdr.candidates.map((c, i) => (
                    <Button key={i} variant="outline" size="lg" onClick={() => handleMoveSelect(c)}
                      className="min-w-[100px] font-mono text-xl h-14 hover:bg-purple-500/10">
                      {c.move}
                    </Button>
                  ))}
                </div>
              </motion.div>
            )}
            
            {phase === "verify" && whyOptions && (
              <motion.div key="verify" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                <div className="text-center mb-4">
                  <HelpCircle className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                  <p className="font-semibold text-emerald-500">Good choice: <span className="font-mono">{pdr.best_move}</span></p>
                  <p className="text-sm text-muted-foreground mt-1">But tell me — why is this better?</p>
                </div>
                <div className="space-y-2 max-w-sm mx-auto">
                  {whyOptions.options.map((o, i) => (
                    <Button key={i} variant="outline" className="w-full justify-start text-left h-auto py-3 px-4"
                      onClick={() => handleReasonSelect(o)}>
                      <span className="text-sm">{o.text}</span>
                    </Button>
                  ))}
                </div>
              </motion.div>
            )}
            
            {phase === "result" && (
              <motion.div key="result" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="px-4">
                {isCorrectMove && isCorrectReason && (
                  <div className="text-center">
                    <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
                    <p className="font-semibold text-emerald-500 mb-2">Excellent.</p>
                    <p className="text-sm text-muted-foreground mb-3">You understood the position.</p>
                    <p className="text-sm">In your game, you played <span className="font-mono text-red-400">{pdr.user_original_move}</span> instead.</p>
                    <p className="text-sm font-medium mt-4">This is the discipline we're building.</p>
                  </div>
                )}
                
                {isCorrectMove && !isCorrectReason && (
                  <div className="text-center">
                    <AlertCircle className="w-10 h-10 text-amber-500 mx-auto mb-3" />
                    <p className="font-semibold text-amber-500 mb-2">Right move, but...</p>
                    <div className="p-3 bg-emerald-500/10 rounded-lg mt-3">
                      <p className="text-sm"><strong>The real reason:</strong> {whyOptions?.correct_explanation}</p>
                    </div>
                  </div>
                )}
                
                {!isCorrectMove && (
                  <div className="space-y-4">
                    {isAnimating && (
                      <div className="text-center text-sm text-purple-400">
                        <Loader2 className="w-4 h-4 animate-spin inline mr-2" />
                        {explanationStep === 1 && `You played ${pdr.user_original_move}...`}
                        {explanationStep === 2 && "But your opponent threatens..."}
                        {explanationStep === 3 && `${refutation?.refutation_move}!`}
                        {explanationStep === 4 && `Better was ${pdr.best_move}`}
                      </div>
                    )}
                    
                    {explanationStep >= 5 && ideaChain && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
                        <Button variant="ghost" size="sm" onClick={replayExplanation} className="w-full text-xs">
                          <RotateCcw className="w-3 h-3 mr-1" /> Replay on board
                        </Button>
                        
                        <IdeaStep num="1" label="Your Idea" text={ideaChain.your_plan} move={pdr.user_original_move} />
                        <IdeaStep num="2" label="Why It Felt Right" text={ideaChain.why_felt_right} />
                        <IdeaStep num="3" label="Opponent's Counter" text={ideaChain.opponent_counter} move={refutation?.refutation_move} variant="danger" />
                        <IdeaStep num="4" label="Why That Works" text={ideaChain.why_it_works} variant="danger" />
                        <IdeaStep num="5" label="Better Approach" text={ideaChain.better_plan} move={pdr.best_move} variant="success" />
                        
                        <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20 mt-4">
                          <p className="text-xs text-blue-400 uppercase mb-1">Rule</p>
                          <p className="text-sm">{ideaChain.rule}</p>
                        </div>
                      </motion.div>
                    )}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
          
          {gameContext && phase === "result" && (
            <div className="mt-4 pt-4 border-t border-border/50 flex justify-between text-xs text-muted-foreground">
              <span>{gameContext.date} {gameContext.time_control && `• ${gameContext.time_control}`}</span>
              <div className="flex gap-3">
                {gameContext.game_url && (
                  <a href={gameContext.game_url} target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 flex items-center gap-1">
                    View on {gameContext.platform}<ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.section>
  );
};

const IdeaStep = ({ num, label, text, move, variant }) => {
  const colors = {
    danger: "border-red-500/30 bg-red-500/5",
    success: "border-emerald-500/30 bg-emerald-500/5",
  };
  const moveColors = { danger: "text-red-400", success: "text-emerald-400" };
  
  return (
    <div className={`p-3 rounded-lg border ${colors[variant] || "border-border bg-muted/30"}`}>
      <p className={`text-xs uppercase tracking-wider mb-1 ${variant === "danger" ? "text-red-400" : variant === "success" ? "text-emerald-400" : "text-muted-foreground"}`}>
        {num}. {label}
      </p>
      <p className="text-sm">
        {move && <span className={`font-mono font-bold mr-1 ${moveColors[variant] || "text-foreground"}`}>{move}</span>}
        {text}
      </p>
    </div>
  );
};

// ============================================
// Main Coach Component
// ============================================
const Coach = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [coachData, setCoachData] = useState(null);
  const [accounts, setAccounts] = useState({ chess_com: null, lichess: null });
  const [platform, setPlatform] = useState(null);
  const [username, setUsername] = useState("");
  const [linking, setLinking] = useState(false);
  const [sessionState, setSessionState] = useState("idle"); // idle, playing, analyzing
  const [sessionResult, setSessionResult] = useState(null);

  useEffect(() => { fetchCoachData(); }, []);

  const fetchCoachData = async () => {
    try {
      const [coachRes, accountsRes] = await Promise.all([
        fetch(`${API}/coach/today`, { credentials: "include" }),
        fetch(`${API}/journey/linked-accounts`, { credentials: "include" })
      ]);
      if (coachRes.ok) {
        const data = await coachRes.json();
        setCoachData(data);
        // Check session status
        if (data.session_status?.status === "playing") {
          setSessionState("playing");
        } else if (data.session_status?.status === "pending" || data.session_status?.status === "analyzing") {
          setSessionState("analyzing");
        }
      }
      if (accountsRes.ok) setAccounts(await accountsRes.json());
    } catch (e) {
      console.error(e);
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
      toast.success("Account linked.");
      setPlatform(null);
      setUsername("");
      fetchCoachData();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLinking(false);
    }
  };

  const handleGoPlay = async () => {
    // Start session
    try {
      await fetch(`${API}/coach/start-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ platform: accounts.chess_com ? "chess.com" : "lichess" })
      });
      setSessionState("playing");
      
      // Open chess platform
      const url = accounts.chess_com ? "https://chess.com/play/online" : "https://lichess.org";
      window.open(url, "_blank");
    } catch (e) {
      console.error(e);
    }
  };

  const handleDonePlaying = async () => {
    setSessionState("analyzing");
    try {
      const res = await fetch(`${API}/coach/end-session`, {
        method: "POST",
        credentials: "include"
      });
      const data = await res.json();
      setSessionResult(data);
      
      if (data.status === "analyzing" || data.status === "already_analyzed") {
        toast.success(data.message);
        // Refresh data after a delay
        setTimeout(() => {
          fetchCoachData();
          setSessionState("idle");
          setSessionResult(null);
        }, 5000);
      } else {
        toast.info(data.message);
        setSessionState("idle");
      }
    } catch (e) {
      toast.error("Failed to end session");
      setSessionState("idle");
    }
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
      <div className="max-w-xl mx-auto py-6" data-testid="coach-page">
        
        {/* Link Account State */}
        {needsAccountLink && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mt-8">
            <Card className="border-2 border-dashed border-muted-foreground/20">
              <CardContent className="py-16 text-center">
                <LinkIcon className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                <h2 className="font-heading font-semibold text-2xl mb-3">Link Your Chess Account</h2>
                <p className="text-muted-foreground mb-8 max-w-sm mx-auto">
                  Connect your Chess.com or Lichess account so I can analyze your games.
                </p>
                {!platform ? (
                  <div className="flex justify-center gap-3">
                    <Button onClick={() => setPlatform("chess.com")} variant="outline" size="lg">Chess.com</Button>
                    <Button onClick={() => setPlatform("lichess")} variant="outline" size="lg">Lichess</Button>
                  </div>
                ) : (
                  <div className="max-w-xs mx-auto space-y-3">
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

        {/* Main Coach Mode */}
        {hasData && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
            
            {/* PDR - Reflection Moment */}
            {coachData.pdr && <DecisionReconstruction pdr={coachData.pdr} />}
            
            {/* Coach's Note */}
            {coachData.coach_note && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
                className="text-center py-4 px-6 bg-muted/30 rounded-lg border border-border/50">
                <p className="text-sm text-foreground">{coachData.coach_note.line1}</p>
                <p className="text-sm text-muted-foreground">{coachData.coach_note.line2}</p>
              </motion.div>
            )}
            
            {/* Light Stats */}
            {coachData.light_stats && coachData.light_stats.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
                className="flex justify-center gap-6">
                {coachData.light_stats.map((stat, i) => (
                  <div key={i} className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      <span className="text-lg font-semibold">{stat.value}</span>
                      {stat.trend === "down" && <TrendingDown className="w-4 h-4 text-emerald-500" />}
                      {stat.trend === "up" && <TrendingUp className="w-4 h-4 text-red-500" />}
                      {stat.trend === "stable" && <Minus className="w-4 h-4 text-muted-foreground" />}
                    </div>
                    <p className="text-xs text-muted-foreground">{stat.label}</p>
                  </div>
                ))}
              </motion.div>
            )}
            
            {/* Next Game Plan */}
            {coachData.next_game_plan && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
                className="p-4 bg-blue-500/5 rounded-lg border border-blue-500/20">
                <p className="text-xs text-blue-400 uppercase tracking-wider mb-1">Next Game Plan</p>
                <p className="text-sm">{coachData.next_game_plan}</p>
              </motion.div>
            )}
            
            {/* Play Session Button */}
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
              className="text-center pt-4">
              
              {sessionState === "idle" && (
                <Button size="lg" className="h-14 px-10 text-lg font-semibold" onClick={handleGoPlay}>
                  <Play className="w-5 h-5 mr-2" />
                  Go Play. I'll watch this game.
                </Button>
              )}
              
              {sessionState === "playing" && (
                <Button size="lg" variant="outline" className="h-14 px-10 text-lg font-semibold" onClick={handleDonePlaying}>
                  <CheckCircle className="w-5 h-5 mr-2" />
                  Done Playing
                </Button>
              )}
              
              {sessionState === "analyzing" && (
                <div className="py-4">
                  <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-purple-500" />
                  <p className="text-sm text-muted-foreground">
                    {sessionResult?.message || "Your game is being reviewed..."}
                  </p>
                </div>
              )}
              
              <p className="text-xs text-muted-foreground mt-3">
                {accounts.chess_com ? "Chess.com" : "Lichess"} games auto-analyzed
              </p>
            </motion.div>

            {/* View Progress Link */}
            <div className="text-center">
              <button onClick={() => navigate("/progress")}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1">
                View Progress<ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        )}
        
        {/* Loading/Analyzing State */}
        {!needsAccountLink && !hasData && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mt-16 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">{coachData?.message || "Analyzing your games..."}</p>
          </motion.div>
        )}
      </div>
    </Layout>
  );
};

export default Coach;
