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
  Brain
} from "lucide-react";

// PDR - Personalized Decision Reconstruction Component
const DecisionReconstruction = ({ pdr }) => {
  const [selectedMove, setSelectedMove] = useState(null);
  const [revealed, setRevealed] = useState(false);
  
  if (!pdr || !pdr.fen || !pdr.candidates || pdr.candidates.length < 2) return null;
  
  const handleMoveSelect = (move) => {
    setSelectedMove(move);
    setRevealed(true);
  };
  
  const isCorrect = selectedMove?.is_best;
  const choseOriginalMistake = selectedMove?.is_user_move;
  
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
          {/* Chessboard */}
          <div className="flex justify-center mb-6">
            <div className="w-[280px] h-[280px] rounded-lg overflow-hidden shadow-lg">
              <Chessboard
                position={pdr.fen}
                boardWidth={280}
                arePiecesDraggable={false}
                boardOrientation={pdr.player_color === "black" ? "black" : "white"}
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
                className="text-center px-4"
              >
                {/* Result Icon */}
                <div className={`w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4 ${
                  isCorrect ? "bg-emerald-500/20" : "bg-amber-500/20"
                }`}>
                  {isCorrect ? (
                    <CheckCircle className="w-6 h-6 text-emerald-500" />
                  ) : (
                    <AlertCircle className="w-6 h-6 text-amber-500" />
                  )}
                </div>
                
                {/* Feedback Text */}
                <div className="space-y-3">
                  {isCorrect ? (
                    <>
                      <p className="font-semibold text-emerald-500">Good.</p>
                      <p className="text-sm text-muted-foreground">
                        This is the correction we are training.
                      </p>
                      <p className="text-sm">
                        In your original game, you chose <span className="font-mono font-semibold text-red-400">{pdr.user_original_move}</span>.
                      </p>
                      {pdr.habit_context && (
                        <p className="text-sm text-muted-foreground">{pdr.habit_context}</p>
                      )}
                      <p className="text-sm font-medium mt-4">Continue this discipline.</p>
                    </>
                  ) : choseOriginalMistake ? (
                    <>
                      <p className="font-semibold text-amber-500">You chose the same pattern again.</p>
                      <p className="text-sm text-muted-foreground">
                        This is the habit we are correcting.
                      </p>
                      <p className="text-sm">
                        Before this move, you did not fully consider your opponent's reply.
                      </p>
                      <p className="text-sm text-muted-foreground">
                        This small oversight affects your rating stability.
                      </p>
                      <div className="mt-4 p-3 bg-background/50 rounded-lg">
                        <p className="text-sm font-medium">Remember:</p>
                        <p className="text-sm italic">"What is my opponent's best reply?"</p>
                      </div>
                    </>
                  ) : (
                    <>
                      <p className="font-semibold text-amber-500">Not quite.</p>
                      <p className="text-sm text-muted-foreground">
                        The stronger move was <span className="font-mono font-semibold text-emerald-400">{pdr.best_move}</span>.
                      </p>
                      <p className="text-sm">
                        In your original game, you played <span className="font-mono font-semibold text-red-400">{pdr.user_original_move}</span>.
                      </p>
                      <p className="text-sm text-muted-foreground mt-2">
                        Take a moment to understand why this position required careful calculation.
                      </p>
                    </>
                  )}
                </div>
                
                {/* Show what the best move was */}
                {!isCorrect && (
                  <div className="mt-4 pt-4 border-t border-border/50">
                    <p className="text-xs text-muted-foreground">
                      Better was: <span className="font-mono text-emerald-400">{pdr.best_move}</span>
                    </p>
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
