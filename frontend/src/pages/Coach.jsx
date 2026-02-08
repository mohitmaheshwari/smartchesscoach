import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { 
  Loader2, 
  ChevronRight,
  Link as LinkIcon,
  ExternalLink,
  Brain,
  TrendingDown,
  TrendingUp,
  Minus,
  Play,
  CheckCircle,
  AlertCircle,
  Target
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import MistakeMastery from "@/components/MistakeMastery";

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
  const [showGoPlayModal, setShowGoPlayModal] = useState(false);

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

  // Retry analysis when Stockfish failed
  const retryAnalysis = async (gameId) => {
    toast.info("Retrying analysis...");
    try {
      const res = await fetch(`${API}/analyze-game`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ game_id: gameId, force: true })
      });
      if (res.ok) {
        toast.success("Analysis complete!");
        fetchCoachData();
      } else {
        const err = await res.json();
        toast.error(err.detail || "Analysis failed");
      }
    } catch (e) {
      toast.error("Analysis failed. Please try again.");
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

  // Show reminder modal before Go Play
  const handleGoPlayClick = () => {
    setShowGoPlayModal(true);
  };

  // Actually start the session and open chess platform
  const confirmGoPlay = async () => {
    setShowGoPlayModal(false);
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

  // Poll for analysis completion
  const pollAnalysisStatus = useCallback(async (gameId) => {
    let attempts = 0;
    const maxAttempts = 30; // 30 seconds max
    
    const poll = async () => {
      if (attempts >= maxAttempts) {
        setSessionState("idle");
        setSessionResult(null);
        toast.info("Analysis is taking longer than expected. Check back soon.", { duration: 4000 });
        return;
      }
      
      try {
        const res = await fetch(`${API}/coach/analysis-status/${gameId}`, {
          credentials: "include"
        });
        const data = await res.json();
        
        if (data.status === "complete") {
          setSessionResult(prev => ({ ...prev, feedback: data.feedback }));
          // Show the feedback for a moment, then transition
          setTimeout(() => {
            fetchCoachData();
            setSessionState("idle");
            setSessionResult(null);
          }, 3000);
        } else if (data.status === "failed") {
          setSessionState("idle");
          toast.error(data.message || "Analysis failed", { duration: 4000 });
        } else {
          // Still pending, poll again
          attempts++;
          setTimeout(poll, 1000);
        }
      } catch (e) {
        attempts++;
        setTimeout(poll, 1000);
      }
    };
    
    poll();
  }, [fetchCoachData]);

  const handleDonePlaying = async () => {
    setSessionState("analyzing");
    try {
      const res = await fetch(`${API}/coach/end-session`, {
        method: "POST",
        credentials: "include"
      });
      const data = await res.json();
      setSessionResult(data);
      
      if (data.status === "already_analyzed") {
        // Game already analyzed - show the real feedback immediately
        // Keep it visible for a bit so user can read it
        setTimeout(() => {
          fetchCoachData();
          setSessionState("idle");
          setSessionResult(null);
        }, 4000);
      } else if (data.status === "analyzing") {
        // New game being analyzed - poll for completion
        pollAnalysisStatus(data.game_id);
      } else if (data.status === "no_game") {
        // No game found
        setTimeout(() => {
          setSessionState("idle");
          setSessionResult(null);
          toast.info("No new game found yet. Did you finish the game?", { duration: 4000 });
        }, 2000);
      } else {
        toast.info(data.message);
        setSessionState("idle");
      }
    } catch (e) {
      toast.error("Couldn't connect. Try again?");
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
            
            {/* Mistake Mastery - The unified training system */}
            <MistakeMastery 
              token={localStorage.getItem("session_token")} 
              onComplete={() => {}} 
            />
            
            {/* Coach's Note */}
            {coachData.coach_note && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
                className="text-center py-4 px-6 bg-muted/30 rounded-lg border border-border/50">
                <p className="text-sm text-foreground">{coachData.coach_note.line1}</p>
                <p className="text-sm text-muted-foreground">{coachData.coach_note.line2}</p>
              </motion.div>
            )}
            
            {/* Last Game Summary */}
            {coachData.last_game && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
                className="p-4 bg-muted/20 rounded-lg border border-border/40">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-muted-foreground uppercase tracking-wider">Last Game</span>
                    <span className="text-xs text-muted-foreground">vs {coachData.last_game.opponent}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                      coachData.last_game.result === "Won" ? "bg-emerald-500/20 text-emerald-400" :
                      coachData.last_game.result === "Lost" ? "bg-red-500/20 text-red-400" :
                      "bg-blue-500/20 text-blue-400"
                    }`}>
                      {coachData.last_game.result}
                      {coachData.last_game.termination && ` (${coachData.last_game.termination})`}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{coachData.last_game.stats?.blunders || 0} discipline breaks</span>
                    <span>•</span>
                    <span>{coachData.last_game.stats?.mistakes || 0} slips</span>
                  </div>
                </div>
                
                {/* Warning if Stockfish analysis failed */}
                {coachData.last_game.analysis_warning && (
                  <div className="mb-2 p-2 bg-amber-500/10 rounded border border-amber-500/30 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                      <p className="text-xs text-amber-400">{coachData.last_game.analysis_warning}</p>
                    </div>
                    <button 
                      onClick={() => retryAnalysis(coachData.last_game.game_id)}
                      className="text-xs text-amber-400 hover:text-amber-300 underline"
                    >
                      Retry
                    </button>
                  </div>
                )}
                
                <p className={`text-sm ${
                  coachData.last_game.repeated_habit ? "text-amber-400" : 
                  coachData.last_game.result === "Lost" ? "text-red-300" : "text-foreground"
                }`}>
                  {coachData.last_game.comment}
                </p>
                
                {/* Critical moment if there was a blunder */}
                {coachData.last_game.critical_moment && (
                  <div className="mt-3 p-3 bg-red-500/10 rounded border border-red-500/20">
                    <p className="text-xs text-red-400 mb-1">
                      Critical moment (move {coachData.last_game.critical_moment.move_number})
                    </p>
                    <p className="text-sm">
                      You played <span className="font-mono text-red-400">{coachData.last_game.critical_moment.move}</span>
                      {coachData.last_game.critical_moment.best_move && (
                        <>, better was <span className="font-mono text-emerald-400">{coachData.last_game.critical_moment.best_move}</span></>
                      )}
                    </p>
                    {coachData.last_game.critical_moment.explanation && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {coachData.last_game.critical_moment.explanation}
                      </p>
                    )}
                  </div>
                )}
                
                <div className="flex items-center gap-3 mt-3">
                  {coachData.last_game.game_id && (
                    <button 
                      onClick={() => navigate(`/game/${coachData.last_game.game_id}`)}
                      className="text-xs text-purple-400 hover:text-purple-300 inline-flex items-center gap-1"
                    >
                      View full analysis <ChevronRight className="w-3 h-3" />
                    </button>
                  )}
                  {coachData.last_game.external_url && (
                    <a href={coachData.last_game.external_url} target="_blank" rel="noopener noreferrer"
                      className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
                      Chess.com <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
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
                <Button size="lg" className="h-14 px-10 text-lg font-semibold" onClick={handleGoPlayClick}>
                  <Play className="w-5 h-5 mr-2" />
                  Go Play. I&apos;ll watch this game.
                </Button>
              )}
              
              {sessionState === "playing" && (
                <Button size="lg" variant="outline" className="h-14 px-10 text-lg font-semibold" onClick={handleDonePlaying}>
                  <CheckCircle className="w-5 h-5 mr-2" />
                  Done Playing
                </Button>
              )}
              
              {sessionState === "analyzing" && (
                <motion.div 
                  initial={{ opacity: 0, y: 10 }} 
                  animate={{ opacity: 1, y: 0 }}
                  className="py-6 px-8 bg-muted/30 rounded-xl border border-border/50 max-w-md mx-auto"
                >
                  {/* Show real feedback when available */}
                  {sessionResult?.feedback ? (
                    <>
                      <div className="flex items-center justify-center gap-3 mb-4">
                        {sessionResult.feedback.type === "excellent" && (
                          <CheckCircle className="w-8 h-8 text-emerald-500" />
                        )}
                        {sessionResult.feedback.type === "good" && (
                          <CheckCircle className="w-8 h-8 text-emerald-400" />
                        )}
                        {sessionResult.feedback.type === "okay" && (
                          <Brain className="w-8 h-8 text-blue-400" />
                        )}
                        {sessionResult.feedback.type === "repeated" && (
                          <AlertCircle className="w-8 h-8 text-amber-500" />
                        )}
                        {sessionResult.feedback.type === "needs_work" && (
                          <AlertCircle className="w-8 h-8 text-red-400" />
                        )}
                        <span className="text-lg font-medium">
                          {sessionResult.feedback.type === "excellent" ? "Great game!" : 
                           sessionResult.feedback.type === "repeated" ? "Hmm, same pattern..." : 
                           "Game reviewed."}
                        </span>
                      </div>
                      
                      <div className="space-y-3 text-center">
                        <p className={`text-sm font-medium ${
                          sessionResult.feedback.type === "excellent" ? "text-emerald-400" :
                          sessionResult.feedback.type === "repeated" ? "text-amber-400" :
                          sessionResult.feedback.type === "needs_work" ? "text-red-400" :
                          "text-foreground"
                        }`}>
                          {sessionResult.feedback.message}
                        </p>
                        {sessionResult.feedback.detail && (
                          <p className="text-sm text-muted-foreground">
                            {sessionResult.feedback.detail}
                          </p>
                        )}
                        {sessionResult.feedback.stats && (
                          <div className="flex justify-center gap-4 pt-2 text-xs text-muted-foreground">
                            <span>Blunders: {sessionResult.feedback.stats.blunders}</span>
                            <span>Mistakes: {sessionResult.feedback.stats.mistakes}</span>
                          </div>
                        )}
                      </div>
                    </>
                  ) : (
                    <>
                      {/* Still analyzing */}
                      <div className="flex items-center justify-center gap-3 mb-4">
                        <div className="relative">
                          <Brain className="w-8 h-8 text-purple-500" />
                          <span className="absolute -top-1 -right-1 w-3 h-3 bg-purple-500 rounded-full animate-pulse"></span>
                        </div>
                        <span className="text-lg font-medium">Reviewing your game...</span>
                      </div>
                      
                      <div className="space-y-2 text-sm text-muted-foreground text-center">
                        <p className="text-foreground">
                          {sessionResult?.opponent 
                            ? `Looking at your game against ${sessionResult.opponent}...` 
                            : "Okay, let me take a look."}
                        </p>
                        <p>
                          {sessionResult?.result?.includes("1-0") ? "Congrats on the win!" : 
                           sessionResult?.result?.includes("0-1") ? "Tough loss — let's learn from it." : 
                           "Hope it went well."}
                        </p>
                        <p className="text-purple-400">
                          Checking if you repeated the old patterns...
                        </p>
                      </div>
                      
                      <div className="mt-4 flex justify-center">
                        <Loader2 className="w-5 h-5 animate-spin text-purple-500" />
                      </div>
                    </>
                  )}
                </motion.div>
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

        {/* Go Play Reminder Modal */}
        <Dialog open={showGoPlayModal} onOpenChange={setShowGoPlayModal}>
          <DialogContent className="sm:max-w-md" aria-describedby="go-play-description">
            <DialogHeader>
              <DialogTitle className="text-center">
                <Target className="w-10 h-10 mx-auto mb-3 text-purple-500" />
                Before You Play
              </DialogTitle>
            </DialogHeader>
            <div id="go-play-description" className="space-y-4 py-4">
              {/* Show the rule/plan */}
              {coachData?.rule && (
                <div className="p-4 bg-purple-500/10 rounded-lg border border-purple-500/20">
                  <p className="text-xs text-purple-400 uppercase tracking-wider mb-2">Remember This</p>
                  <p className="text-sm font-medium">{coachData.rule}</p>
                </div>
              )}
              
              {coachData?.next_game_plan && (
                <div className="p-4 bg-blue-500/10 rounded-lg border border-blue-500/20">
                  <p className="text-xs text-blue-400 uppercase tracking-wider mb-2">Your Plan</p>
                  <p className="text-sm">{coachData.next_game_plan}</p>
                </div>
              )}
              
              <p className="text-center text-sm text-muted-foreground">
                I&apos;ll be watching. Come back when you&apos;re done.
              </p>
              
              <div className="flex gap-3 pt-2">
                <Button variant="outline" className="flex-1" onClick={() => setShowGoPlayModal(false)}>
                  Cancel
                </Button>
                <Button className="flex-1" onClick={confirmGoPlay}>
                  <ExternalLink className="w-4 h-4 mr-2" />
                  Open {accounts.chess_com ? "Chess.com" : "Lichess"}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default Coach;
