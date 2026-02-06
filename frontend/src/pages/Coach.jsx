import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Chessboard } from "react-chessboard";
import { 
  Loader2, 
  ChevronRight,
  Link as LinkIcon,
  ExternalLink,
  AlertCircle,
  CheckCircle,
  Lightbulb,
  Brain,
  ArrowRight
} from "lucide-react";

// PDR - Personalized Decision Reconstruction Component with Animation
const DecisionReconstruction = ({ pdr }) => {
  const [selectedMove, setSelectedMove] = useState(null);
  const [revealed, setRevealed] = useState(false);
  const [currentFen, setCurrentFen] = useState(pdr?.fen);
  const [animationStep, setAnimationStep] = useState(0);
  const [highlightSquares, setHighlightSquares] = useState({});
  
  useEffect(() => {
    setCurrentFen(pdr?.fen);
  }, [pdr?.fen]);
  
  if (!pdr || !pdr.fen || !pdr.candidates || pdr.candidates.length < 2) return null;
  
  const handleMoveSelect = (move) => {
    setSelectedMove(move);
    setRevealed(true);
    
    // If wrong answer and we have refutation, animate it
    if (!move.is_best && pdr.refutation) {
      // Step 1: Show position after user's move
      setTimeout(() => {
        setCurrentFen(pdr.refutation.fen_after_user_move);
        setAnimationStep(1);
      }, 500);
      
      // Step 2: Highlight the threat square and show refutation
      setTimeout(() => {
        setHighlightSquares({
          [pdr.refutation.from_square]: { backgroundColor: "rgba(255, 100, 100, 0.5)" },
          [pdr.refutation.threat_square]: { backgroundColor: "rgba(255, 50, 50, 0.7)" }
        });
        setAnimationStep(2);
      }, 1500);
      
      // Step 3: Show position after refutation
      setTimeout(() => {
        setCurrentFen(pdr.refutation.fen_after_refutation);
        setAnimationStep(3);
      }, 2500);
    }
  };
  
  const isCorrect = selectedMove?.is_best;
  const ideaChain = pdr.idea_chain;
  const refutation = pdr.refutation;
  
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
          {/* Chessboard with animation */}
          <div className="flex justify-center mb-6">
            <div className="w-[280px] h-[280px] rounded-lg overflow-hidden shadow-lg">
              <Chessboard
                position={currentFen}
                boardWidth={280}
                arePiecesDraggable={false}
                boardOrientation={pdr.player_color === "black" ? "black" : "white"}
                customSquareStyles={highlightSquares}
                customBoardStyle={{
                  borderRadius: "8px",
                }}
                customDarkSquareStyle={{ backgroundColor: "#4a4a4a" }}
                customLightSquareStyle={{ backgroundColor: "#8b8b8b" }}
              />
            </div>
          </div>
          
          <AnimatePresence mode="wait">
            {!revealed ? (
              <motion.div
                key="question"
                initial={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                {/* Question */}
                <div className="text-center mb-6 px-4">
                  <p className="text-sm text-muted-foreground mb-2">Pause here.</p>
                  <p className="text-sm text-muted-foreground mb-3">
                    You are <span className="font-semibold text-foreground">{pdr.player_color}</span>.
                  </p>
                  <p className="text-lg font-medium">
                    Before you move — what would you play?
                  </p>
                </div>
                
                {/* Move Buttons */}
                <div className="flex flex-wrap justify-center gap-3">
                  {pdr.candidates.map((candidate, idx) => (
                    <Button
                      key={idx}
                      variant="outline"
                      size="lg"
                      onClick={() => handleMoveSelect(candidate)}
                      className="min-w-[80px] font-mono text-lg hover:bg-purple-500/10 hover:border-purple-500/50"
                    >
                      {candidate.move}
                    </Button>
                  ))}
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="feedback"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="px-4"
              >
                {isCorrect ? (
                  /* Correct Answer Feedback */
                  <div className="text-center">
                    <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-4">
                      <CheckCircle className="w-6 h-6 text-emerald-500" />
                    </div>
                    <p className="font-semibold text-emerald-500 mb-2">Good.</p>
                    <p className="text-sm text-muted-foreground mb-3">
                      This is the correction we are training.
                    </p>
                    <p className="text-sm mb-4">
                      In your original game, you chose{" "}
                      <span className="font-mono font-semibold text-red-400">{pdr.user_original_move}</span>.
                    </p>
                    <p className="text-sm font-medium">Continue this discipline.</p>
                  </div>
                ) : (
                  /* Wrong Answer - Idea Chain Explanation */
                  <div className="space-y-4">
                    {/* Animation Status */}
                    {animationStep > 0 && animationStep < 3 && (
                      <div className="text-center text-sm text-amber-500 mb-4">
                        <Loader2 className="w-4 h-4 animate-spin inline mr-2" />
                        {animationStep === 1 && "After your move..."}
                        {animationStep === 2 && "Your opponent replies..."}
                      </div>
                    )}
                    
                    {/* Refutation Move Highlight */}
                    {refutation && animationStep >= 2 && (
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="text-center p-3 bg-red-500/10 rounded-lg border border-red-500/20"
                      >
                        <p className="text-sm text-muted-foreground">Opponent plays:</p>
                        <p className="font-mono text-xl font-bold text-red-400">
                          {refutation.refutation_move}
                          {refutation.is_check && <span className="text-red-500">+</span>}
                        </p>
                        {refutation.is_capture && refutation.captured_piece && (
                          <p className="text-xs text-red-400/80 mt-1">
                            Winning the {refutation.captured_piece}
                          </p>
                        )}
                      </motion.div>
                    )}
                    
                    {/* Idea Chain - Only show after animation completes */}
                    {ideaChain && animationStep >= 3 && (
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="space-y-3 pt-4 border-t border-border/50"
                      >
                        {/* Your Plan */}
                        <div className="flex items-start gap-2">
                          <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center flex-shrink-0 mt-0.5">
                            <span className="text-xs">1</span>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">Your plan</p>
                            <p className="text-sm">{ideaChain.your_plan}</p>
                          </div>
                        </div>
                        
                        <ArrowRight className="w-4 h-4 text-muted-foreground mx-auto" />
                        
                        {/* Why It Felt Right */}
                        <div className="flex items-start gap-2">
                          <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center flex-shrink-0 mt-0.5">
                            <span className="text-xs">2</span>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">Why it felt right</p>
                            <p className="text-sm">{ideaChain.why_felt_right}</p>
                          </div>
                        </div>
                        
                        <ArrowRight className="w-4 h-4 text-muted-foreground mx-auto" />
                        
                        {/* Opponent's Counter */}
                        <div className="flex items-start gap-2">
                          <div className="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <span className="text-xs text-red-400">3</span>
                          </div>
                          <div>
                            <p className="text-xs text-red-400 uppercase tracking-wider">Opponent's counter</p>
                            <p className="text-sm text-red-400">{ideaChain.opponent_counter}</p>
                          </div>
                        </div>
                        
                        <ArrowRight className="w-4 h-4 text-muted-foreground mx-auto" />
                        
                        {/* Why It Works */}
                        <div className="flex items-start gap-2">
                          <div className="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <span className="text-xs text-red-400">4</span>
                          </div>
                          <div>
                            <p className="text-xs text-red-400 uppercase tracking-wider">Why it works</p>
                            <p className="text-sm">{ideaChain.why_it_works}</p>
                          </div>
                        </div>
                        
                        <ArrowRight className="w-4 h-4 text-muted-foreground mx-auto" />
                        
                        {/* Better Plan */}
                        <div className="flex items-start gap-2">
                          <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <span className="text-xs text-emerald-400">5</span>
                          </div>
                          <div>
                            <p className="text-xs text-emerald-400 uppercase tracking-wider">Better plan</p>
                            <p className="text-sm">
                              <span className="font-mono font-semibold text-emerald-400">{pdr.best_move}</span>
                              {" "}{ideaChain.better_plan}
                            </p>
                          </div>
                        </div>
                        
                        {/* Rule */}
                        <div className="mt-4 p-4 bg-blue-500/10 rounded-lg border border-blue-500/20">
                          <p className="text-xs text-blue-400 uppercase tracking-wider mb-1">Remember</p>
                          <p className="text-sm font-medium">{ideaChain.rule}</p>
                        </div>
                      </motion.div>
                    )}
                    
                    {/* Loading state while waiting for animation */}
                    {(!ideaChain || animationStep < 3) && animationStep > 0 && (
                      <div className="flex justify-center py-4">
                        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                      </div>
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
    const url = accounts.chess_com 
      ? "https://chess.com/play/online" 
      : "https://lichess.org";
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
        
        {/* No Account Linked State */}
        {needsAccountLink && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-12"
          >
            <Card className="border-2 border-dashed border-muted-foreground/20">
              <CardContent className="py-16 text-center">
                <div className="w-20 h-20 rounded-full bg-muted flex items-center justify-center mx-auto mb-6">
                  <LinkIcon className="w-8 h-8 text-muted-foreground" />
                </div>
                <h2 className="font-heading font-semibold text-2xl mb-3">
                  Link Your Chess Account
                </h2>
                <p className="text-muted-foreground mb-8 max-w-sm mx-auto">
                  Connect your Chess.com or Lichess account so I can analyze your games and coach you.
                </p>
                
                {!platform ? (
                  <div className="flex justify-center gap-3">
                    <Button 
                      onClick={() => setPlatform("chess.com")} 
                      variant="outline"
                      size="lg"
                      data-testid="link-chesscom-btn"
                    >
                      Chess.com
                    </Button>
                    <Button 
                      onClick={() => setPlatform("lichess")} 
                      variant="outline"
                      size="lg"
                      data-testid="link-lichess-btn"
                    >
                      Lichess
                    </Button>
                  </div>
                ) : (
                  <div className="max-w-xs mx-auto space-y-3">
                    <p className="text-sm text-muted-foreground mb-2">
                      Enter your {platform} username
                    </p>
                    <Input
                      placeholder="Username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      disabled={linking}
                      data-testid="username-input"
                    />
                    <div className="flex gap-2">
                      <Button 
                        onClick={linkAccount} 
                        disabled={linking}
                        className="flex-1"
                      >
                        {linking && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                        Connect
                      </Button>
                      <Button 
                        variant="ghost" 
                        onClick={() => setPlatform(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Analyzing State */}
        {!needsAccountLink && !hasData && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-16 text-center"
          >
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">
              {coachData?.message || "Analyzing your games..."}
            </p>
          </motion.div>
        )}

        {/* Main Coach Mode */}
        {hasData && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-8"
          >
            {/* PDR - Decision Reconstruction */}
            {coachData.pdr && (
              <DecisionReconstruction pdr={coachData.pdr} />
            )}

            <div className="space-y-6">
              {/* Section 1: Correct This */}
              {coachData.correction && (
                <motion.section
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 }}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <AlertCircle className="w-4 h-4 text-amber-500" />
                    <span className="text-xs font-medium uppercase tracking-wider text-amber-500">
                      Correct This
                    </span>
                  </div>
                  <Card className="border-amber-500/20 bg-amber-500/5">
                    <CardContent className="py-6">
                      <h2 className="font-heading font-bold text-xl mb-2">
                        {coachData.correction.title}
                      </h2>
                      <p className="text-muted-foreground text-sm mb-2">
                        {coachData.correction.context}
                      </p>
                      <p className="text-sm text-foreground/80">
                        {coachData.correction.severity}
                      </p>
                    </CardContent>
                  </Card>
                </motion.section>
              )}

              {/* Section 2: Keep Doing This */}
              {coachData.reinforcement && (
                <motion.section
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                    <span className="text-xs font-medium uppercase tracking-wider text-emerald-500">
                      Keep Doing This
                    </span>
                  </div>
                  <Card className="border-emerald-500/20 bg-emerald-500/5">
                    <CardContent className="py-6">
                      <h2 className="font-heading font-bold text-xl mb-2">
                        {coachData.reinforcement.title}
                      </h2>
                      <p className="text-muted-foreground text-sm mb-2">
                        {coachData.reinforcement.context}
                      </p>
                      <p className="text-sm text-foreground/80">
                        {coachData.reinforcement.trend}
                      </p>
                    </CardContent>
                  </Card>
                </motion.section>
              )}

              {/* Section 3: Remember This Rule */}
              {coachData.rule && (
                <motion.section
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <Lightbulb className="w-4 h-4 text-blue-500" />
                    <span className="text-xs font-medium uppercase tracking-wider text-blue-500">
                      Remember
                    </span>
                  </div>
                  <Card className="border-blue-500/20 bg-gradient-to-br from-blue-500/5 to-blue-600/10">
                    <CardContent className="py-8 text-center">
                      <p className="text-lg font-medium whitespace-pre-line leading-relaxed">
                        {coachData.rule}
                      </p>
                    </CardContent>
                  </Card>
                </motion.section>
              )}

              {/* Action Button */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="pt-4 text-center"
              >
                <Button
                  size="lg"
                  className="h-14 px-12 text-lg font-semibold"
                  onClick={handleGoPlay}
                  data-testid="go-play-btn"
                >
                  Go Play. I'll review.
                  <ExternalLink className="w-5 h-5 ml-2" />
                </Button>
                <p className="text-xs text-muted-foreground mt-3">
                  Games auto-analyzed from Chess.com / Lichess
                </p>
              </motion.div>

              {/* View Progress Link */}
              <div className="text-center pt-4">
                <button
                  onClick={() => navigate("/progress")}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1"
                  data-testid="view-progress-link"
                >
                  View Progress
                  <ChevronRight className="w-4 h-4" />
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
