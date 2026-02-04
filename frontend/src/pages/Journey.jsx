import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import Layout from "@/components/Layout";
import { toast } from "sonner";
import { 
  ProgressRing, 
  StatusBadge, 
  TrendIndicator, 
  CoachMessage,
  SectionHeader,
  AnimatedList,
  AnimatedItem
} from "@/components/ui/premium";
import { 
  Loader2, 
  RefreshCw, 
  ChevronRight,
  Sparkles,
  Target,
  TrendingUp,
  CheckCircle2,
  Clock,
  Brain,
  Zap,
  Trophy,
  Flame
} from "lucide-react";
import { RatingTrajectory, TimeManagement, FastThinking, PuzzleTrainer } from "@/components/RatingTrajectory";
import { 
  XPProgressBar, 
  StreakDisplay, 
  DailyRewardButton, 
  StatsGrid,
  XPToast,
  LevelUpModal
} from "@/components/Gamification";

const Journey = ({ user }) => {
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [accounts, setAccounts] = useState({ chess_com: null, lichess: null });
  const [platform, setPlatform] = useState(null);
  const [username, setUsername] = useState("");
  const [linking, setLinking] = useState(false);
  const [syncing, setSyncing] = useState(false);
  
  // Gamification state
  const [progress, setProgress] = useState(null);
  const [showXPToast, setShowXPToast] = useState(false);
  const [xpToastData, setXpToastData] = useState({ xp: 0, action: '' });
  const [dailyClaimed, setDailyClaimed] = useState(false);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const [res1, res2, res3] = await Promise.all([
        fetch(API + "/journey/linked-accounts", { credentials: "include" }),
        fetch(API + "/journey", { credentials: "include" }),
        fetch(API + "/gamification/progress", { credentials: "include" })
      ]);
      
      if (res1.ok) setAccounts(await res1.json());
      if (res2.ok) setDashboard(await res2.json());
      if (res3.ok) setProgress(await res3.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };
  
  const claimDailyReward = async () => {
    try {
      const res = await fetch(API + "/gamification/daily-reward", {
        method: "POST",
        credentials: "include"
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.claimed) {
          const totalXP = data.xp_earned + (data.streak?.xp_bonus || 0);
          setXpToastData({ xp: totalXP, action: 'Daily Reward' });
          setShowXPToast(true);
          setDailyClaimed(true);
          setTimeout(() => setShowXPToast(false), 2500);
          toast.success(`Claimed ${totalXP} XP! 🎉`);
          fetchDashboard();
        } else {
          setDailyClaimed(true);
          toast.info("Already claimed today!");
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const linkAccount = async () => {
    if (!username.trim()) return toast.error("Enter username");
    setLinking(true);
    try {
      const res = await fetch(API + "/journey/link-account", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ platform: platform, username: username.trim() })
      });
      if (!res.ok) throw new Error((await res.json()).detail);
      toast.success("Account linked!");
      setPlatform(null);
      setUsername("");
      fetchDashboard();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLinking(false);
    }
  };

  const syncNow = async () => {
    setSyncing(true);
    try {
      const res = await fetch(API + "/journey/sync-now", {
        method: "POST",
        credentials: "include"
      });
      if (!res.ok) throw new Error((await res.json()).detail);
      toast.success("Sync started!");
      setTimeout(fetchDashboard, 5000);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSyncing(false);
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
  const games = dashboard?.games_analyzed || 0;
  const mode = dashboard?.mode || "onboarding";

  return (
    <Layout user={user}>
      <div className="space-y-8 max-w-4xl" data-testid="journey-page">
        {/* Header with Streak */}
        <motion.div 
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-end justify-between"
        >
          <div>
            <p className="label-caps mb-2">Your Progress</p>
            <h1 className="text-3xl font-heading font-bold tracking-tight">Journey</h1>
          </div>
          <div className="flex items-center gap-4">
            {progress?.current_streak > 0 && (
              <StreakDisplay streak={progress.current_streak} compact />
            )}
          </div>
        </motion.div>
        
        {/* Gamification Section */}
        {progress && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="space-y-4"
          >
            <div className="grid md:grid-cols-2 gap-4">
              <XPProgressBar progress={progress} />
              <StreakDisplay streak={progress.current_streak} />
            </div>
            
            <div className="flex justify-center">
              <DailyRewardButton onClaim={claimDailyReward} claimed={dailyClaimed} />
            </div>
            
            <StatsGrid progress={progress} />
          </motion.div>
        )}

        {/* Connect Account CTA */}
        {!hasAccount && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="border-dashed border-2 border-muted-foreground/20">
              <CardContent className="py-12 text-center">
                <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto mb-6">
                  <Target className="w-7 h-7 text-muted-foreground" />
                </div>
                <h3 className="font-heading font-semibold text-xl mb-2">Connect Your Chess Account</h3>
                <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
                  Link your account to start tracking progress and receive personalized coaching.
                </p>
                <div className="flex justify-center gap-3">
                  <Button 
                    onClick={() => setPlatform("chess.com")} 
                    variant="outline"
                    className="btn-scale"
                    data-testid="link-chesscom-btn"
                  >
                    Chess.com
                  </Button>
                  <Button 
                    onClick={() => setPlatform("lichess")} 
                    variant="outline"
                    className="btn-scale"
                    data-testid="link-lichess-btn"
                  >
                    Lichess
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Link Account Form */}
        {platform && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <Card className="surface">
              <CardContent className="py-6">
                <p className="label-caps mb-4">Link {platform}</p>
                <div className="flex gap-3">
                  <Input
                    placeholder={`Enter ${platform} username`}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    disabled={linking}
                    className="max-w-xs"
                    data-testid="username-input"
                  />
                  <Button onClick={linkAccount} disabled={linking} className="btn-scale">
                    {linking && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                    Connect
                  </Button>
                  <Button variant="ghost" onClick={() => setPlatform(null)}>
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Onboarding State */}
        {mode === "onboarding" && hasAccount && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="surface border-l-4 border-l-accent">
              <CardContent className="py-6">
                <div className="flex items-start gap-4">
                  <ProgressRing progress={Math.min(games * 20, 100)} size={64} strokeWidth={6} />
                  <div className="flex-1">
                    <p className="label-caps mb-1">Getting Started</p>
                    <p className="text-foreground leading-relaxed">
                      {dashboard?.weekly_assessment || "Play a few more games and I'll start identifying patterns in your play."}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Main Dashboard Content */}
        {mode !== "onboarding" && dashboard && (
          <AnimatedList className="space-y-6">
            {/* Coach Assessment */}
            <AnimatedItem>
              <Card className="surface">
                <CardContent className="py-6">
                  <SectionHeader label="Coach's Assessment" />
                  <CoachMessage message={dashboard.weekly_assessment} />
                </CardContent>
              </Card>
            </AnimatedItem>

            {/* Focus Areas & Trends Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Focus Areas */}
              {dashboard.focus_areas?.length > 0 && (
                <AnimatedItem>
                  <Card className="surface h-full">
                    <CardContent className="py-6">
                      <SectionHeader label="Focus Areas" />
                      <div className="space-y-3">
                        {dashboard.focus_areas.map((area, i) => (
                          <div 
                            key={i} 
                            className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
                          >
                            <div>
                              <p className="font-medium capitalize">{area.name}</p>
                              <p className="text-xs text-muted-foreground capitalize">{area.category}</p>
                            </div>
                            <StatusBadge status={area.status} />
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </AnimatedItem>
              )}

              {/* Weakness Trends */}
              {dashboard.weakness_trends?.length > 0 && (
                <AnimatedItem>
                  <Card className="surface h-full">
                    <CardContent className="py-6">
                      <SectionHeader label="Habit Trends" />
                      <div className="space-y-3">
                        {dashboard.weakness_trends.map((t, i) => (
                          <div 
                            key={i} 
                            className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
                          >
                            <div>
                              <p className="font-medium capitalize">{t.name}</p>
                              <p className="text-xs text-muted-foreground font-mono">
                                {t.occurrences_recent} recent · {t.occurrences_previous} before
                              </p>
                            </div>
                            <TrendIndicator trend={t.trend} />
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </AnimatedItem>
              )}
            </div>

            {/* Resolved & Strengths Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Resolved Habits */}
              {dashboard.resolved_habits?.length > 0 && (
                <AnimatedItem>
                  <Card className="surface border-l-4 border-l-emerald-500">
                    <CardContent className="py-6">
                      <SectionHeader 
                        label="Resolved" 
                        action={<CheckCircle2 className="w-4 h-4 text-emerald-500" />}
                      />
                      <div className="space-y-2">
                        {dashboard.resolved_habits.map((h, i) => (
                          <p key={i} className="text-sm text-muted-foreground">{h.message}</p>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </AnimatedItem>
              )}

              {/* Strengths */}
              {dashboard.strengths?.length > 0 && (
                <AnimatedItem>
                  <Card className="surface">
                    <CardContent className="py-6">
                      <SectionHeader 
                        label="Your Strengths" 
                        action={<Sparkles className="w-4 h-4 text-amber-500" />}
                      />
                      <div className="flex flex-wrap gap-2">
                        {dashboard.strengths.map((s, i) => (
                          <span 
                            key={i} 
                            className="px-3 py-1.5 text-sm bg-muted rounded-md capitalize"
                          >
                            {s.name}
                          </span>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </AnimatedItem>
              )}
            </div>
          </AnimatedList>
        )}

        {/* Rating & Training Section */}
        {hasAccount && games > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="space-y-6"
          >
            {/* Section Header */}
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-amber-500" />
              <h2 className="text-lg font-heading font-semibold">Rating Trajectory & Training</h2>
            </div>

            {/* Rating Trajectory - Full Width */}
            <RatingTrajectory />

            {/* Training Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <TimeManagement />
              <FastThinking />
              <PuzzleTrainer />
            </div>
          </motion.div>
        )}

        {/* Linked Accounts Footer */}
        {hasAccount && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            <Card className="surface">
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-6 text-sm">
                    {accounts.chess_com && (
                      <span className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-emerald-500" />
                        Chess.com: <span className="font-medium">{accounts.chess_com}</span>
                      </span>
                    )}
                    {accounts.lichess && (
                      <span className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-emerald-500" />
                        Lichess: <span className="font-medium">{accounts.lichess}</span>
                      </span>
                    )}
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    onClick={syncNow}
                    disabled={syncing}
                    className="text-muted-foreground hover:text-foreground"
                    data-testid="sync-now-btn"
                  >
                    {syncing ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <RefreshCw className="w-4 h-4 mr-2" />
                    )}
                    Sync
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Games sync automatically every 6 hours
                </p>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </div>
      
      {/* XP Toast */}
      <XPToast show={showXPToast} xp={xpToastData.xp} action={xpToastData.action} />
    </Layout>
  );
};

export default Journey;
