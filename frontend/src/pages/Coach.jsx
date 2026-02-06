import { useState, useEffect } from "react";
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
  Target,
  Link as LinkIcon,
  ExternalLink
} from "lucide-react";

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
      toast.success("Account linked! Games will sync shortly.");
      setPlatform(null);
      setUsername("");
      fetchCoachData();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLinking(false);
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

  const hasAccount = accounts.chess_com || accounts.lichess;
  const hasHabit = coachData?.has_active_habit;

  return (
    <Layout user={user}>
      <div className="max-w-xl mx-auto" data-testid="coach-page">
        {/* No Account Linked State */}
        {!hasAccount && (
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
                      className="gap-2"
                      data-testid="link-chesscom-btn"
                    >
                      Chess.com
                    </Button>
                    <Button 
                      onClick={() => setPlatform("lichess")} 
                      variant="outline"
                      size="lg"
                      className="gap-2"
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

        {/* Account Linked - Show Coach Mode */}
        {hasAccount && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-8 space-y-8"
          >
            {/* Coach's Focus */}
            <div className="text-center space-y-2">
              <p className="text-sm text-muted-foreground uppercase tracking-wider">
                Today&apos;s Focus
              </p>
              <div className="h-px w-16 bg-border mx-auto" />
            </div>

            {hasHabit ? (
              <>
                {/* Active Habit Card */}
                <Card className="border-0 shadow-lg bg-gradient-to-br from-card to-card/80">
                  <CardContent className="py-12 px-8 text-center">
                    <div className="w-12 h-12 rounded-full bg-amber-500/10 flex items-center justify-center mx-auto mb-6">
                      <Target className="w-6 h-6 text-amber-500" />
                    </div>
                    
                    <h1 className="font-heading font-bold text-2xl md:text-3xl mb-4 text-foreground">
                      {coachData.habit?.name}
                    </h1>
                    
                    <p className="text-muted-foreground text-lg max-w-md mx-auto leading-relaxed">
                      {coachData.habit?.rule}
                    </p>
                  </CardContent>
                </Card>

                {/* Go Play Button */}
                <div className="text-center">
                  <Button
                    size="lg"
                    className="h-14 px-12 text-lg font-semibold gap-2"
                    onClick={() => {
                      // Open chess platform in new tab
                      const url = accounts.chess_com 
                        ? `https://chess.com/play/online` 
                        : `https://lichess.org`;
                      window.open(url, '_blank');
                    }}
                    data-testid="go-play-btn"
                  >
                    Go Play. I&apos;ll review.
                    <ExternalLink className="w-5 h-5" />
                  </Button>
                  <p className="text-xs text-muted-foreground mt-3">
                    Your games will be analyzed automatically
                  </p>
                </div>
              </>
            ) : (
              /* No Active Habit Yet */
              <Card className="border-0 shadow-lg">
                <CardContent className="py-12 px-8 text-center">
                  <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-6">
                    <Target className="w-6 h-6 text-muted-foreground" />
                  </div>
                  
                  <h2 className="font-heading font-semibold text-xl mb-3">
                    Analyzing Your Games
                  </h2>
                  
                  <p className="text-muted-foreground max-w-sm mx-auto mb-6">
                    I&apos;m reviewing your recent games to identify what to focus on. Play a few more games and check back soon.
                  </p>

                  <Button
                    variant="outline"
                    onClick={() => {
                      const url = accounts.chess_com 
                        ? `https://chess.com/play/online` 
                        : `https://lichess.org`;
                      window.open(url, '_blank');
                    }}
                  >
                    Play Some Games
                    <ExternalLink className="w-4 h-4 ml-2" />
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* View Progress Link */}
            <div className="text-center">
              <button
                onClick={() => navigate('/progress')}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1"
                data-testid="view-progress-link"
              >
                View Progress
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            {/* Connected Account Info */}
            <div className="text-center text-xs text-muted-foreground/60">
              Connected: {accounts.chess_com || accounts.lichess}
            </div>
          </motion.div>
        )}
      </div>
    </Layout>
  );
};

export default Coach;
