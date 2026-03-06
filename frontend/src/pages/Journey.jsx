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
  Shield,
  Sparkles,
  Award,
  Eye,
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
  const [focusMastery, setFocusMastery] = useState(null);
  
  // Gamification state
  const [progress, setProgress] = useState(null);
  const [showXPToast, setShowXPToast] = useState(false);
  const [xpToastData, setXpToastData] = useState({ xp: 0, action: '' });
  const [dailyClaimed, setDailyClaimed] = useState(false);
  
  // NEW: Rolling Evolution state
  const [evolutionData, setEvolutionData] = useState(null);
  const [openingEvolution, setOpeningEvolution] = useState(null);
  
  const navigate = useNavigate();

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const [res1, res2, res3, res4, res5, res6] = await Promise.all([
        fetch(API + "/journey/linked-accounts", { credentials: "include" }),
        fetch(API + "/journey/v2", { credentials: "include" }),
        fetch(API + "/gamification/progress", { credentials: "include" }),
        fetch(API + "/missions/focus-mastery", { credentials: "include" }),
        fetch(API + "/progress/evolution", { credentials: "include" }),
        fetch(API + "/progress/openings", { credentials: "include" }),
      ]);
      
      if (res1.ok) setAccounts(await res1.json());
      if (res2.ok) setJourneyData(await res2.json());
      if (res3.ok) setProgress(await res3.json());
      if (res4.ok) {
        const masteryData = await res4.json();
        setFocusMastery(masteryData.focus_mastery || null);
      }
      if (res5.ok) setEvolutionData(await res5.json());
      if (res6.ok) setOpeningEvolution(await res6.json());
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
            {/* Coach Narrative Rail - Story-driven overview */}
            <CoachNarrativeRail 
              journeyData={journeyData}
              focusMastery={focusMastery}
            />

            {/* Focus Mastery Section - Cognitive Pattern Progress */}
            {focusMastery && (
              <FocusMasterySection 
                data={focusMastery}
                onNavigate={(pattern) => navigate(`/training?focus=${pattern}`)}
              />
            )}

            {/* NEW: Rolling Evolution Section - Replaces baseline comparison */}
            <RollingEvolutionSection 
              evolutionData={evolutionData}
            />

            {/* NEW: Opening Evolution Section */}
            <OpeningEvolutionSection 
              openingData={openingEvolution}
              onViewGame={(gameId) => navigate(`/lab/game/${gameId}`)}
            />

            {/* Section 1: Chess Fundamentals Assessment */}
            <FundamentalsSection 
              data={journeyData.fundamentals} 
              onViewGame={(gameId) => navigate(`/lab/${gameId}`)}
            />

            {/* Section 2: Rating Ceiling Assessment */}
            <RatingCeilingSection data={journeyData.rating_ceiling} />
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
// Coach Narrative Rail - Story-driven overview
// ============================================
const CoachNarrativeRail = ({ journeyData, focusMastery }) => {
  // Generate coach narrative based on data
  const generateNarrative = () => {
    const parts = [];
    
    if (!journeyData?.has_baseline) {
      return {
        headline: "Building Your Chess Profile",
        story: "We're getting to know your game. After a few more analyses, you'll see your personalized coaching insights here.",
        mood: "neutral",
      };
    }
    
    // Check for improvements
    const progress = journeyData?.progress;
    const improvements = [];
    const concerns = [];
    
    if (progress?.accuracy?.improved && progress.accuracy.delta >= 3) {
      improvements.push("move quality");
    }
    if (progress?.blunders_per_game?.improved && progress.blunders_per_game.delta <= -0.3) {
      improvements.push("blunder control");
    }
    if (progress?.accuracy?.delta <= -3) {
      concerns.push("accuracy dropped");
    }
    if (progress?.blunders_per_game?.delta >= 0.5) {
      concerns.push("more blunders recently");
    }
    
    // Build narrative
    let headline = "";
    let story = "";
    let mood = "neutral";
    
    if (improvements.length > 0 && concerns.length === 0) {
      headline = "You're Making Progress";
      story = `Your ${improvements.join(" and ")} ${improvements.length > 1 ? "are" : "is"} improving. Keep up the good work.`;
      mood = "positive";
    } else if (concerns.length > 0 && improvements.length === 0) {
      headline = "Time to Refocus";
      story = `Recent games show ${concerns.join(" and ")}. Let's get back on track with focused training.`;
      mood = "attention";
    } else if (improvements.length > 0 && concerns.length > 0) {
      headline = "Mixed Results";
      story = `Your ${improvements[0]} is improving, but ${concerns[0]}. Focus on one thing at a time.`;
      mood = "mixed";
    } else {
      headline = "Steady Progress";
      story = "Your game is stable. Let's push for the next level with targeted practice.";
      mood = "neutral";
    }
    
    // Add focus mastery insight
    if (focusMastery?.biggest_gap) {
      story += ` Your biggest opportunity is ${focusMastery.biggest_gap.name.toLowerCase()}.`;
    }
    
    return { headline, story, mood };
  };
  
  const narrative = generateNarrative();
  
  const moodColors = {
    positive: "from-emerald-500/10 to-emerald-500/5 border-emerald-500/30",
    attention: "from-amber-500/10 to-amber-500/5 border-amber-500/30",
    mixed: "from-blue-500/10 to-blue-500/5 border-blue-500/30",
    neutral: "from-primary/10 to-primary/5 border-primary/30",
  };
  
  const moodIcons = {
    positive: <TrendingUp className="w-6 h-6 text-emerald-500" />,
    attention: <AlertTriangle className="w-6 h-6 text-amber-500" />,
    mixed: <TrendingUp className="w-6 h-6 text-blue-500" />,
    neutral: <Sparkles className="w-6 h-6 text-primary" />,
  };
  
  return (
    <AnimatedItem>
      <Card className={`surface bg-gradient-to-r ${moodColors[narrative.mood]} border-l-4`} data-testid="coach-narrative">
        <CardContent className="py-5">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-full bg-background/50 flex items-center justify-center flex-shrink-0">
              {moodIcons[narrative.mood]}
            </div>
            <div>
              <h2 className="text-xl font-heading font-bold mb-1">{narrative.headline}</h2>
              <p className="text-muted-foreground">{narrative.story}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </AnimatedItem>
  );
};

// ============================================
// Focus Mastery Section - Cognitive Pattern Progress
// ============================================
const FocusMasterySection = ({ data, onNavigate }) => {
  if (!data?.patterns || Object.keys(data.patterns).length === 0) {
    return null;
  }
  
  // Get top patterns to display (sorted by relevance)
  const patternsArray = Object.values(data.patterns);
  const activePatterns = patternsArray
    .filter(p => data.active_patterns?.includes(p.pattern_key) || p.occurrences_total > 0)
    .sort((a, b) => b.occurrences_total - a.occurrences_total)
    .slice(0, 4);
  
  const levelColors = {
    master: "bg-yellow-500",
    proficient: "bg-emerald-500",
    competent: "bg-blue-500",
    developing: "bg-amber-500",
    novice: "bg-gray-500",
  };
  
  const levelLabels = {
    master: "Master",
    proficient: "Proficient",
    competent: "Competent",
    developing: "Developing",
    novice: "Learning",
  };
  
  const trendIcons = {
    improving: <TrendingUp className="w-3 h-3 text-emerald-500" />,
    declining: <TrendingDown className="w-3 h-3 text-red-500" />,
    stable: <Minus className="w-3 h-3 text-muted-foreground" />,
  };
  
  return (
    <AnimatedItem>
      <Card className="surface" data-testid="focus-mastery-section">
        <CardContent className="py-6">
          <SectionHeader 
            label="Focus Mastery" 
            action={
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  Overall: {data.overall_level}
                </span>
                <div className={`w-2 h-2 rounded-full ${levelColors[data.overall_level]}`} />
              </div>
            }
          />
          
          {/* Overall Progress Ring */}
          <div className="flex items-center gap-6 mt-4 mb-6">
            <div className="relative w-20 h-20">
              <svg className="w-20 h-20 transform -rotate-90">
                <circle
                  cx="40"
                  cy="40"
                  r="35"
                  stroke="currentColor"
                  strokeWidth="6"
                  fill="transparent"
                  className="text-muted"
                />
                <circle
                  cx="40"
                  cy="40"
                  r="35"
                  stroke="currentColor"
                  strokeWidth="6"
                  fill="transparent"
                  strokeDasharray={`${(data.overall_mastery / 100) * 220} 220`}
                  className={`${levelColors[data.overall_level].replace('bg-', 'text-')}`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold">{Math.round(data.overall_mastery)}%</span>
              </div>
            </div>
            
            <div className="flex-1">
              <div className="grid grid-cols-2 gap-3">
                {data.top_strength && (
                  <div className="p-2 rounded bg-emerald-500/10">
                    <p className="text-xs text-emerald-500 font-medium">Strongest</p>
                    <p className="text-sm truncate">{data.top_strength.name}</p>
                  </div>
                )}
                {data.biggest_gap && (
                  <div className="p-2 rounded bg-amber-500/10">
                    <p className="text-xs text-amber-500 font-medium">Focus Area</p>
                    <p className="text-sm truncate">{data.biggest_gap.name}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
          
          {/* Individual Pattern Progress */}
          <div className="space-y-3">
            {activePatterns.map((pattern) => (
              <div 
                key={pattern.pattern_key}
                className="p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
                onClick={() => onNavigate?.(pattern.pattern_key)}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Eye className="w-4 h-4 text-muted-foreground" />
                    <span className="font-medium text-sm">{pattern.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {trendIcons[pattern.trend]}
                    <span className={`text-xs px-2 py-0.5 rounded-full ${levelColors[pattern.mastery_level]} text-white`}>
                      {levelLabels[pattern.mastery_level]}
                    </span>
                  </div>
                </div>
                
                {/* Progress Bar */}
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <motion.div
                        className={`h-full ${levelColors[pattern.mastery_level]}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${pattern.mastery_score}%` }}
                        transition={{ duration: 0.5 }}
                      />
                    </div>
                  </div>
                  <span className="text-xs text-muted-foreground w-12 text-right">
                    {Math.round(pattern.mastery_score)}%
                  </span>
                </div>
                
                {/* Stats */}
                <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                  {pattern.occurrences_total > 0 && (
                    <span>
                      {pattern.occurrences_total} occurrence{pattern.occurrences_total !== 1 ? 's' : ''}
                    </span>
                  )}
                  {pattern.improvement_rate > 0 && (
                    <span className="text-emerald-500">
                      +{Math.round(pattern.improvement_rate)}% better
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
          
          {/* Recommended Focus */}
          {data.recommended_focus && (
            <div className="mt-4 p-3 rounded-lg border border-primary/30 bg-primary/5">
              <div className="flex items-center gap-2">
                <Award className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">
                  Recommended: Work on {data.patterns[data.recommended_focus]?.name || data.recommended_focus}
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </AnimatedItem>
  );
};

// ============================================
// Rolling Evolution Section - NEW Progress System
// ============================================
const RollingEvolutionSection = ({ evolutionData }) => {
  if (!evolutionData || evolutionData.total_games < 15) {
    return (
      <AnimatedItem>
        <Card className="surface border-2 border-dashed border-primary/30">
          <CardContent className="py-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h3 className="font-heading font-semibold">Building Your Progress Profile</h3>
                <p className="text-sm text-muted-foreground">
                  {evolutionData?.total_games || 0} games analyzed. Need 15+ for evolution tracking.
                </p>
              </div>
            </div>
            <Progress value={((evolutionData?.total_games || 0) / 15) * 100} className="h-2" />
          </CardContent>
        </Card>
      </AnimatedItem>
    );
  }

  const assessment = evolutionData.assessment || {};
  const medium = evolutionData.medium || {};
  const micro = evolutionData.micro || {};
  
  const trend = assessment.trend || "stable";
  const headline = assessment.headline || "Tracking your progress";
  const detail = assessment.detail || "";

  const getTrendIcon = (t) => {
    if (t === "improving") return <TrendingUp className="w-5 h-5 text-emerald-500" />;
    if (t === "declining") return <TrendingDown className="w-5 h-5 text-amber-500" />;
    return <Minus className="w-5 h-5 text-muted-foreground" />;
  };

  const getTrendColor = (t) => {
    if (t === "improving") return "emerald";
    if (t === "declining") return "amber";
    return "blue";
  };

  const color = getTrendColor(trend);

  return (
    <AnimatedItem>
      <Card className="surface overflow-hidden" data-testid="rolling-evolution">
        {/* Header */}
        <div className={`bg-gradient-to-r from-${color}-500/10 to-transparent px-6 py-4 border-b border-border/50`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center bg-${color}-500/20`}>
                {getTrendIcon(trend)}
              </div>
              <div>
                <h3 className="font-heading font-semibold">{headline}</h3>
                <p className="text-xs text-muted-foreground">{detail}</p>
              </div>
            </div>
            <div className={`px-3 py-1.5 rounded-full text-sm font-medium bg-${color}-500/10 text-${color}-500`}>
              {evolutionData.total_games} games
            </div>
          </div>
        </div>
        
        <CardContent className="py-5">
          {/* Comparison Windows */}
          <div className="grid md:grid-cols-2 gap-4">
            {/* Recent 10 vs Previous 10 */}
            {medium.recent && medium.previous && (
              <div className="p-4 rounded-lg bg-muted/30 border border-border/50">
                <p className="text-xs text-muted-foreground mb-3 flex items-center gap-1">
                  <BarChart3 className="w-3 h-3" />
                  Last 10 vs Previous 10 Games
                </p>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Win Rate</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono">{Math.round((medium.recent.win_rate || 0) * 100)}%</span>
                      <DeltaBadge delta={(medium.delta?.win_rate_delta || 0) * 100} suffix="%" />
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Blunders/Game</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono">{(medium.recent.blunders_per_game || 0).toFixed(1)}</span>
                      <DeltaBadge delta={-(medium.delta?.blunders_delta || 0)} invert />
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            {/* Recent 5 vs Previous 5 (This Week) */}
            {micro.recent && micro.previous && (
              <div className="p-4 rounded-lg bg-muted/30 border border-border/50">
                <p className="text-xs text-muted-foreground mb-3 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  This Week (5 vs 5 Games)
                </p>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Win Rate</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono">{Math.round((micro.recent.win_rate || 0) * 100)}%</span>
                      <DeltaBadge delta={(micro.delta?.win_rate_delta || 0) * 100} suffix="%" />
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Record</span>
                    <span className="font-mono">
                      {micro.recent.wins}W-{micro.recent.losses}L-{micro.recent.draws}D
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </AnimatedItem>
  );
};

// Delta Badge component for showing +/- changes
const DeltaBadge = ({ delta, suffix = "", invert = false }) => {
  const value = invert ? -delta : delta;
  if (Math.abs(value) < 0.5) return null;
  
  const isPositive = value > 0;
  return (
    <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
      isPositive 
        ? 'bg-emerald-500/10 text-emerald-500' 
        : 'bg-red-500/10 text-red-500'
    }`}>
      {isPositive ? '+' : ''}{value.toFixed(0)}{suffix}
    </span>
  );
};

// ============================================
// Opening Evolution Section - NEW
// ============================================
const OpeningEvolutionSection = ({ openingData, onViewGame }) => {
  if (!openingData || openingData.recent_games_count < 10) {
    return null; // Not enough data yet
  }

  const improving = openingData.improving || [];
  const declining = openingData.declining || [];
  const stable = openingData.stable || [];
  const recommendations = openingData.recommendations || [];

  // Only show if there's meaningful data
  if (improving.length === 0 && declining.length === 0 && stable.length < 2) {
    return null;
  }

  return (
    <AnimatedItem>
      <Card className="surface" data-testid="opening-evolution">
        <CardContent className="py-6">
          <SectionHeader 
            label="Opening Performance" 
            action={
              <span className="text-xs text-muted-foreground">
                Last {openingData.recent_games_count} vs previous {openingData.previous_games_count} games
              </span>
            }
          />
          
          <div className="space-y-4 mt-4">
            {/* Recommendations */}
            {recommendations.length > 0 && (
              <div className="space-y-2">
                {recommendations.slice(0, 2).map((rec, idx) => (
                  <div 
                    key={idx}
                    className={`p-3 rounded-lg border ${
                      rec.priority === "positive" 
                        ? "bg-emerald-500/5 border-emerald-500/20" 
                        : rec.priority === "warning"
                        ? "bg-amber-500/5 border-amber-500/20"
                        : "bg-muted/30 border-border/50"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      {rec.priority === "positive" ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-500 mt-0.5" />
                      ) : rec.priority === "warning" ? (
                        <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5" />
                      ) : (
                        <BookOpen className="w-4 h-4 text-muted-foreground mt-0.5" />
                      )}
                      <div>
                        <p className="text-sm font-medium">{rec.opening}</p>
                        <p className="text-xs text-muted-foreground">{rec.message}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Opening Stats Grid */}
            <div className="grid md:grid-cols-3 gap-3">
              {/* Improving Openings */}
              {improving.length > 0 && (
                <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                  <p className="text-xs font-medium text-emerald-500 mb-2 flex items-center gap-1">
                    <TrendingUp className="w-3 h-3" />
                    Improving
                  </p>
                  <div className="space-y-1">
                    {improving.slice(0, 2).map((o, idx) => (
                      <div key={idx} className="text-sm">
                        <span className="font-medium">{o.opening_name}</span>
                        <span className="text-xs text-emerald-500 ml-1">
                          +{Math.round(o.accuracy_delta || 0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Stable Openings */}
              {stable.length > 0 && (
                <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                  <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                    <Minus className="w-3 h-3" />
                    Stable
                  </p>
                  <div className="space-y-1">
                    {stable.slice(0, 2).map((o, idx) => (
                      <div key={idx} className="text-sm">
                        <span className="font-medium">{o.opening_name}</span>
                        <span className="text-xs text-muted-foreground ml-1">
                          {o.recent?.games_played || 0} games
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Declining Openings */}
              {declining.length > 0 && (
                <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                  <p className="text-xs font-medium text-amber-500 mb-2 flex items-center gap-1">
                    <TrendingDown className="w-3 h-3" />
                    Needs Work
                  </p>
                  <div className="space-y-1">
                    {declining.slice(0, 2).map((o, idx) => (
                      <div key={idx} className="text-sm">
                        <span className="font-medium">{o.opening_name}</span>
                        <span className="text-xs text-amber-500 ml-1">
                          {Math.round(o.accuracy_delta || 0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Detailed opening list - collapsible */}
            {stable.length > 2 && (
              <details className="group">
                <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                  View all {stable.length + improving.length + declining.length} openings
                </summary>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {[...improving, ...stable, ...declining].map((o, idx) => (
                    <div 
                      key={idx} 
                      className="text-xs p-2 rounded bg-muted/20 flex justify-between"
                    >
                      <span className="truncate">{o.opening_name}</span>
                      <span className="text-muted-foreground ml-2">
                        {o.recent?.score_pct || 0}%
                      </span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        </CardContent>
      </Card>
    </AnimatedItem>
  );
};

// ============================================
// Progress Tracker - OLD (keeping as fallback)
// ============================================
const ProgressTrackerSection = ({ baseline, current, progress, hasBaseline, gamesUntilBaseline }) => {
  // If no baseline yet, show progress toward establishing profile
  if (!hasBaseline) {
    return (
      <AnimatedItem>
        <Card className="surface border-2 border-dashed border-primary/30">
          <CardContent className="py-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <Target className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h3 className="font-heading font-semibold">Getting to Know Your Game</h3>
                <p className="text-sm text-muted-foreground">
                  {gamesUntilBaseline > 0 
                    ? `${gamesUntilBaseline} more games to analyze`
                    : 'Almost there...'}
                </p>
              </div>
            </div>
            <Progress value={((10 - gamesUntilBaseline) / 10) * 100} className="h-2" />
            <p className="text-xs text-muted-foreground mt-3">
              We're learning your playing style to give you personalized coaching.
            </p>
          </CardContent>
        </Card>
      </AnimatedItem>
    );
  }

  // Has baseline - show coaching progress
  if (!progress) return null;

  // Determine what's improving and what needs work
  const improvements = [];
  const needsWork = [];

  // Accuracy check
  if (progress.accuracy.improved && progress.accuracy.delta >= 3) {
    improvements.push({
      icon: <Target className="w-4 h-4" />,
      label: "Move Quality",
      detail: "Your moves are getting sharper"
    });
  } else if (progress.accuracy.delta <= -3) {
    needsWork.push({
      icon: <Target className="w-4 h-4" />,
      label: "Move Quality", 
      detail: "Focus on calculating before moving"
    });
  }

  // Blunders check
  if (progress.blunders_per_game.improved && progress.blunders_per_game.delta <= -0.5) {
    improvements.push({
      icon: <Shield className="w-4 h-4" />,
      label: "Blunder Control",
      detail: "Making fewer game-losing mistakes"
    });
  } else if (progress.blunders_per_game.delta >= 0.3) {
    needsWork.push({
      icon: <AlertTriangle className="w-4 h-4" />,
      label: "Blunder Control",
      detail: "Double-check before big moves"
    });
  }

  // Win rate check
  if (progress.win_rate.improved && progress.win_rate.delta >= 5) {
    improvements.push({
      icon: <Crown className="w-4 h-4" />,
      label: "Winning More",
      detail: "Your results are improving"
    });
  } else if (progress.win_rate.delta <= -5) {
    needsWork.push({
      icon: <Swords className="w-4 h-4" />,
      label: "Game Results",
      detail: "Focus on converting advantages"
    });
  }

  // Opening progress
  const improvedOpenings = (progress.openings || []).filter(o => o.improved && o.delta >= 10);
  const strugglingOpenings = (progress.openings || []).filter(o => !o.improved && o.delta <= -10);

  if (improvedOpenings.length > 0) {
    improvements.push({
      icon: <BookOpen className="w-4 h-4" />,
      label: improvedOpenings[0].name,
      detail: "Getting stronger in this opening"
    });
  }

  if (strugglingOpenings.length > 0) {
    needsWork.push({
      icon: <BookOpen className="w-4 h-4" />,
      label: strugglingOpenings[0].name,
      detail: "Review this opening's key ideas"
    });
  }

  const overallImproving = improvements.length >= needsWork.length;

  return (
    <AnimatedItem>
      <Card className="surface overflow-hidden" data-testid="progress-tracker">
        {/* Header */}
        <div className="bg-gradient-to-r from-primary/10 to-transparent px-6 py-4 border-b border-border/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                overallImproving ? 'bg-emerald-500/20' : 'bg-amber-500/20'
              }`}>
                {overallImproving 
                  ? <TrendingUp className="w-5 h-5 text-emerald-500" />
                  : <Target className="w-5 h-5 text-amber-500" />
                }
              </div>
              <div>
                <h3 className="font-heading font-semibold">Since You Started</h3>
                <p className="text-xs text-muted-foreground">
                  {progress.games_since_baseline} games with your coach
                </p>
              </div>
            </div>
            
            <div className={`px-3 py-1.5 rounded-full text-sm font-medium ${
              overallImproving 
                ? 'bg-emerald-500/10 text-emerald-500'
                : 'bg-amber-500/10 text-amber-500'
            }`}>
              {overallImproving ? 'Growing!' : 'Keep Going!'}
            </div>
          </div>
        </div>
        
        <CardContent className="py-5">
          <div className="grid md:grid-cols-2 gap-6">
            {/* What's Improving */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span className="text-sm font-medium text-emerald-500">What's Improving</span>
              </div>
              {improvements.length > 0 ? (
                <div className="space-y-3">
                  {improvements.map((item, idx) => (
                    <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
                      <div className="mt-0.5 text-emerald-500">{item.icon}</div>
                      <div>
                        <p className="font-medium text-sm">{item.label}</p>
                        <p className="text-xs text-muted-foreground">{item.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground p-3 rounded-lg bg-muted/30">
                  Keep playing! We're tracking your progress.
                </p>
              )}
            </div>
            
            {/* What Needs Work */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Target className="w-4 h-4 text-amber-500" />
                <span className="text-sm font-medium text-amber-500">Focus Areas</span>
              </div>
              {needsWork.length > 0 ? (
                <div className="space-y-3">
                  {needsWork.map((item, idx) => (
                    <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-amber-500/5 border border-amber-500/10">
                      <div className="mt-0.5 text-amber-500">{item.icon}</div>
                      <div>
                        <p className="font-medium text-sm">{item.label}</p>
                        <p className="text-xs text-muted-foreground">{item.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground p-3 rounded-lg bg-muted/30">
                  Great job! No major concerns right now.
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </AnimatedItem>
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
