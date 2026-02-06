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
  Eye,
  EyeOff
} from "lucide-react";

// Reflection Moment Component
const ReflectionMoment = ({ reflection }) => {
  const [revealed, setRevealed] = useState(false);
  
  if (!reflection || !reflection.fen || reflection.is_placeholder) return null;
  
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-8"
    >
      <div className="flex items-center gap-2 mb-3">
        <Eye className="w-4 h-4 text-purple-500" />
        <span className="text-xs font-medium uppercase tracking-wider text-purple-500">
          Reflection Moment
        </span>
      </div>
      
      <Card className="border-purple-500/20 bg-gradient-to-br from-purple-500/5 to-purple-600/10 overflow-hidden">
        <CardContent className="py-6">
          {/* Chessboard */}
          <div className="flex justify-center mb-6">
            <div className="w-[280px] h-[280px] rounded-lg overflow-hidden shadow-lg">
              <Chessboard
                position={reflection.fen}
                boardWidth={280}
                arePiecesDraggable={false}
                customBoardStyle={{
                  borderRadius: "8px",
                }}
                customDarkSquareStyle={{ backgroundColor: "#4a4a4a" }}
                customLightSquareStyle={{ backgroundColor: "#8b8b8b" }}
              />
            </div>
          </div>
          
          {/* Question */}
          <p className="text-center text-lg font-medium mb-6 px-4">
            {reflection.question}
          </p>
          
          {/* Buttons */}
          <AnimatePresence mode="wait">
            {!revealed ? (
              <motion.div
                key="buttons"
                initial={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex justify-center gap-3"
              >
                <Button
                  variant="outline"
                  onClick={() => setRevealed(true)}
                  className="gap-2"
                >
                  <EyeOff className="w-4 h-4" />
                  I see it
                </Button>
                <Button
                  onClick={() => setRevealed(true)}
                  className="gap-2"
                >
                  <Eye className="w-4 h-4" />
                  Show me
                </Button>
              </motion.div>
            ) : (
              <motion.div
                key="revealed"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4 border-t border-purple-500/20 pt-4 mt-4"
              >
                {/* What you played */}
                {reflection.move_played && (
                  <div className="text-center">
                    <span className="text-sm text-muted-foreground">You played: </span>
                    <span className="font-mono font-bold text-red-400">{reflection.move_played}</span>
                  </div>
                )}
                
                {/* Better move */}
                {reflection.best_move && (
                  <div className="text-center">
                    <span className="text-sm text-muted-foreground">Better was: </span>
                    <span className="font-mono font-bold text-green-400">{reflection.best_move}</span>
                  </div>
                )}
                
                {/* Explanation */}
                {reflection.explanation && (
                  <p className="text-sm text-muted-foreground text-center px-4">
                    {reflection.explanation}
                  </p>
                )}
                
                {/* Impact */}
                {reflection.cp_loss > 0 && (
                  <p className="text-xs text-center text-muted-foreground/70">
                    This cost approximately {Math.round(reflection.cp_loss / 100 * 10) / 10} points of advantage.
                  </p>
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
            {/* Section 0: Reflection Moment */}
            {coachData.reflection && (
              <ReflectionMoment reflection={coachData.reflection} />
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
