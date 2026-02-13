import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import Layout from "@/components/Layout";
import { toast } from "sonner";
import { SectionHeader, AnimatedList, AnimatedItem } from "@/components/ui/premium";
import { 
  Loader2, 
  RefreshCw, 
  Target,
  TrendingUp,
  TrendingDown,
  ChevronRight,
  Zap,
  Brain,
  BookOpen,
  Clock,
  Crosshair,
  Crown,
  ArrowUp,
  ArrowDown,
  Minus,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  BarChart3,
  Swords,
  Shield
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { 
  XPProgressBar, 
  StreakDisplay, 
  DailyRewardButton, 
  StatsGrid,
  XPToast
} from "@/components/Gamification";

const Journey = ({ user }) => {
  const [loading, setLoading] = useState(true);
  const [journeyData, setJourneyData] = useState(null);
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
  
  const navigate = useNavigate();

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const [res1, res2, res3] = await Promise.all([
        fetch(API + "/journey/linked-accounts", { credentials: "include" }),
        fetch(API + "/journey/v2", { credentials: "include" }),
        fetch(API + "/gamification/progress", { credentials: "include" })
      ]);
      
      if (res1.ok) setAccounts(await res1.json());
      if (res2.ok) setJourneyData(await res2.json());
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
          toast.success(`Claimed ${totalXP} XP!`);
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

  return (
    <Layout user={user}>
      <div className="space-y-8 max-w-4xl" data-testid="journey-page">
        {/* Header */}
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

        {/* Main Journey Content */}
        {hasAccount && journeyData && (
          <AnimatedList className="space-y-6">
            {/* NEW: Progress Tracker - Baseline vs Current */}
            <ProgressTrackerSection 
              baseline={journeyData.baseline}
              current={journeyData.current_stats}
              progress={journeyData.progress}
              hasBaseline={journeyData.has_baseline}
              gamesUntilBaseline={journeyData.games_until_baseline}
            />

            {/* Section 1: Chess Fundamentals Assessment */}
            <FundamentalsSection 
              data={journeyData.fundamentals} 
              onViewGame={(gameId) => navigate(`/lab/${gameId}`)}
            />

            {/* Section 2: Rating Ceiling Assessment */}
            <RatingCeilingSection data={journeyData.rating_ceiling} />

            {/* Section 3: Opening Progress */}
            <OpeningProgressSection 
              data={journeyData.opening_progress}
              onViewGame={(gameId) => navigate(`/lab/${gameId}`)}
            />
          </AnimatedList>
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

// ============================================
// Section 1: Chess Fundamentals Assessment
// ============================================
const FundamentalsSection = ({ data, onViewGame }) => {
  if (!data?.has_data) {
    return (
      <AnimatedItem>
        <Card className="surface">
          <CardContent className="py-8 text-center">
            <Brain className="w-10 h-10 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">{data?.message || "Analyze more games to see your fundamentals assessment"}</p>
          </CardContent>
        </Card>
      </AnimatedItem>
    );
  }

  const fundamentalIcons = {
    positional_play: <Shield className="w-5 h-5" />,
    tactics: <Zap className="w-5 h-5" />,
    opening: <BookOpen className="w-5 h-5" />,
    endgame: <Crown className="w-5 h-5" />,
    time_management: <Clock className="w-5 h-5" />
  };

  const levelColors = {
    strong: "text-emerald-500",
    developing: "text-blue-500",
    needs_work: "text-amber-500",
    focus_area: "text-red-500"
  };

  const levelBgColors = {
    strong: "bg-emerald-500/10",
    developing: "bg-blue-500/10",
    needs_work: "bg-amber-500/10",
    focus_area: "bg-red-500/10"
  };

  return (
    <AnimatedItem>
      <Card className="surface" data-testid="fundamentals-section">
        <CardContent className="py-6">
          <SectionHeader 
            label="Chess Fundamentals" 
            action={
              <span className="text-xs text-muted-foreground">
                How you compare across key areas
              </span>
            }
          />
          
          <div className="space-y-4 mt-4">
            {data.fundamentals.map((fund) => (
              <div key={fund.key} className="group">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${levelBgColors[fund.level]}`}>
                      {fundamentalIcons[fund.key] || <Target className="w-5 h-5" />}
                    </div>
                    <div>
                      <p className="font-medium">{fund.name}</p>
                      <p className="text-xs text-muted-foreground">{fund.description}</p>
                    </div>
                  </div>
                  <span className={`text-sm font-semibold ${levelColors[fund.level]}`}>
                    {fund.score}%
                  </span>
                </div>
                
                {/* Progress Bar */}
                <div className="relative">
                  <Progress value={fund.score} className="h-2" />
                </div>
                
                {/* Suggestions (show on hover or always for weak areas) */}
                {fund.level === "focus_area" || fund.level === "needs_work" ? (
                  <div className="mt-2 p-3 rounded-lg bg-muted/50">
                    <p className="text-sm text-muted-foreground">
                      <AlertTriangle className="w-4 h-4 inline mr-1 text-amber-500" />
                      {fund.suggestions?.[0]}
                    </p>
                    {/* Tagged Games */}
                    {fund.tagged_games?.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        <span className="text-xs text-muted-foreground">Practice games:</span>
                        {fund.tagged_games.map((game, i) => (
                          <button
                            key={i}
                            onClick={() => onViewGame(game.game_id)}
                            className="text-xs px-2 py-1 rounded bg-muted hover:bg-accent transition-colors"
                          >
                            vs {game.opponent}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            ))}
          </div>

          {/* Summary */}
          {data.strongest && data.weakest && (
            <div className="mt-6 pt-4 border-t border-border grid grid-cols-2 gap-4">
              <div className="p-3 rounded-lg bg-emerald-500/10">
                <p className="text-xs text-emerald-500 font-medium mb-1">Strongest Area</p>
                <p className="font-medium">{data.strongest.name}</p>
              </div>
              <div className="p-3 rounded-lg bg-red-500/10">
                <p className="text-xs text-red-500 font-medium mb-1">Focus Area</p>
                <p className="font-medium">{data.weakest.name}</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </AnimatedItem>
  );
};

// ============================================
// Section 2: Rating Ceiling Assessment
// ============================================
const RatingCeilingSection = ({ data }) => {
  if (!data?.has_data) {
    return (
      <AnimatedItem>
        <Card className="surface">
          <CardContent className="py-8 text-center">
            <BarChart3 className="w-10 h-10 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">{data?.message || "Analyze more games to see your rating ceiling"}</p>
          </CardContent>
        </Card>
      </AnimatedItem>
    );
  }

  const urgencyColors = {
    high: "border-l-red-500",
    medium: "border-l-amber-500",
    low: "border-l-emerald-500"
  };

  return (
    <AnimatedItem>
      <Card className={`surface border-l-4 ${urgencyColors[data.urgency]}`} data-testid="rating-ceiling-section">
        <CardContent className="py-6">
          <SectionHeader 
            label="Rating Ceiling Assessment" 
            action={
              <span className="text-xs text-muted-foreground">
                You're not bad, you're unstable
              </span>
            }
          />
          
          {/* Main Stats */}
          <div className="grid grid-cols-2 gap-6 mt-6">
            <div className="text-center p-4 rounded-lg bg-muted/50">
              <p className="text-xs text-muted-foreground mb-1">Stable Level</p>
              <p className="text-3xl font-bold text-foreground">{data.stable_level}</p>
              <p className="text-xs text-muted-foreground mt-1">
                Based on {data.stable_games_count} clean games
              </p>
            </div>
            <div className="text-center p-4 rounded-lg bg-primary/10">
              <p className="text-xs text-muted-foreground mb-1">Demonstrated Peak</p>
              <p className="text-3xl font-bold text-primary">{data.peak_level}</p>
              <p className="text-xs text-muted-foreground mt-1">
                Top 30% games ({data.peak_accuracy}% accuracy)
              </p>
            </div>
          </div>

          {/* Gap Analysis */}
          <div className="mt-6 p-4 rounded-lg bg-muted/30">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-muted-foreground">Performance Gap</span>
              <span className="font-bold text-lg">
                {data.gap > 0 ? (
                  <span className="text-amber-500">+{data.gap} points</span>
                ) : (
                  <span className="text-emerald-500">Consistent!</span>
                )}
              </span>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-gradient-to-r from-emerald-500 to-primary transition-all"
                    style={{ width: `${Math.min(100, (data.stable_level / data.peak_level) * 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Gap Driver */}
          {data.gap > 50 && (
            <div className="mt-4 p-4 rounded-lg border border-amber-500/30 bg-amber-500/5">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5" />
                <div>
                  <p className="font-medium text-amber-500">Gap Driver: {data.gap_driver}</p>
                  <p className="text-sm text-muted-foreground mt-1">{data.gap_description}</p>
                  <p className="text-sm mt-2 font-medium">{data.fix_suggestion}</p>
                </div>
              </div>
            </div>
          )}

          {/* Message */}
          <p className="text-sm text-muted-foreground mt-4 text-center italic">
            {data.message}
          </p>
        </CardContent>
      </Card>
    </AnimatedItem>
  );
};

// ============================================
// Section 3: Opening Progress
// ============================================
const OpeningProgressSection = ({ data, onViewGame }) => {
  const [showColor, setShowColor] = useState("white");

  if (!data?.has_data) {
    return (
      <AnimatedItem>
        <Card className="surface">
          <CardContent className="py-8 text-center">
            <BookOpen className="w-10 h-10 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">{data?.message || "Play more games to see your opening progress"}</p>
          </CardContent>
        </Card>
      </AnimatedItem>
    );
  }

  const statusIcons = {
    working: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
    struggling: <XCircle className="w-4 h-4 text-red-500" />,
    error_prone: <AlertTriangle className="w-4 h-4 text-amber-500" />,
    needs_study: <BookOpen className="w-4 h-4 text-blue-500" />,
    neutral: <Minus className="w-4 h-4 text-muted-foreground" />
  };

  const currentData = showColor === "white" ? data.as_white : data.as_black;

  return (
    <AnimatedItem>
      <Card className="surface" data-testid="opening-progress-section">
        <CardContent className="py-6">
          <SectionHeader 
            label="Opening Progress" 
            action={
              <div className="flex gap-2">
                <button
                  onClick={() => setShowColor("white")}
                  className={`px-3 py-1 text-xs rounded-full transition-colors ${
                    showColor === "white" 
                      ? "bg-primary text-primary-foreground" 
                      : "bg-muted hover:bg-accent"
                  }`}
                >
                  As White ({data.as_white.total_games})
                </button>
                <button
                  onClick={() => setShowColor("black")}
                  className={`px-3 py-1 text-xs rounded-full transition-colors ${
                    showColor === "black" 
                      ? "bg-primary text-primary-foreground" 
                      : "bg-muted hover:bg-accent"
                  }`}
                >
                  As Black ({data.as_black.total_games})
                </button>
              </div>
            }
          />
          
          {/* Opening List */}
          <div className="space-y-3 mt-4">
            {currentData.openings.map((opening, idx) => (
              <div 
                key={idx}
                className="p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {statusIcons[opening.status]}
                    <span className="font-medium">{opening.name}</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-muted-foreground">{opening.games} games</span>
                    <span className={
                      opening.win_rate >= 60 ? "text-emerald-500 font-semibold" :
                      opening.win_rate < 40 ? "text-red-500 font-semibold" :
                      "text-foreground"
                    }>
                      {opening.win_rate}% WR
                    </span>
                  </div>
                </div>
                
                {/* Win/Loss Bar */}
                <div className="flex h-2 rounded-full overflow-hidden bg-muted">
                  <div 
                    className="bg-emerald-500 transition-all"
                    style={{ width: `${(opening.wins / opening.games) * 100}%` }}
                  />
                  <div 
                    className="bg-slate-400 transition-all"
                    style={{ width: `${(opening.draws / opening.games) * 100}%` }}
                  />
                  <div 
                    className="bg-red-500 transition-all"
                    style={{ width: `${(opening.losses / opening.games) * 100}%` }}
                  />
                </div>
                
                {/* Stats */}
                <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    {opening.wins}W
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-slate-400" />
                    {opening.draws}D
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-red-500" />
                    {opening.losses}L
                  </span>
                  {opening.avg_accuracy > 0 && (
                    <span className="ml-auto">
                      {opening.avg_accuracy}% avg accuracy
                    </span>
                  )}
                </div>
                
                {/* Suggestion */}
                {opening.suggestion && (
                  <p className="text-xs text-muted-foreground mt-2 pl-6 border-l-2 border-primary/30">
                    {opening.suggestion}
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* Summary Cards */}
          {(data.working_well?.length > 0 || data.needs_work?.length > 0) && (
            <div className="mt-6 pt-4 border-t border-border grid grid-cols-2 gap-4">
              {data.working_well?.length > 0 && (
                <div className="p-3 rounded-lg bg-emerald-500/10">
                  <p className="text-xs text-emerald-500 font-medium mb-2">Working Well</p>
                  <div className="space-y-1">
                    {data.working_well.slice(0, 2).map((o, i) => (
                      <p key={i} className="text-sm truncate">{o.name}</p>
                    ))}
                  </div>
                </div>
              )}
              {data.needs_work?.length > 0 && (
                <div className="p-3 rounded-lg bg-red-500/10">
                  <p className="text-xs text-red-500 font-medium mb-2">Needs Work</p>
                  <div className="space-y-1">
                    {data.needs_work.slice(0, 2).map((o, i) => (
                      <p key={i} className="text-sm truncate">{o.name}</p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </AnimatedItem>
  );
};

export default Journey;
