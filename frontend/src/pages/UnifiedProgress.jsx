/**
 * UNIFIED PROGRESS PAGE - Human Coach Style
 * 
 * Combines /progress and /journey into one cohesive view.
 * Your coach giving you a complete picture: where you are, how far you've come, what to do next.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress as ProgressBar } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  Loader2, Target, Zap, TrendingUp, TrendingDown, Minus,
  AlertTriangle, CheckCircle2, Brain, Flame, Sparkles,
  ChevronRight, RefreshCw, Clock, Eye, ArrowRight,
  Award, ChevronDown, ChevronUp
} from "lucide-react";

const UnifiedProgress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [progressData, setProgressData] = useState(null);
  const [journeyData, setJourneyData] = useState(null);
  const [journeyV2Data, setJourneyV2Data] = useState(null);  // For rating ceiling, baseline
  const [homeData, setHomeData] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [activeTab, setActiveTab] = useState("now");
  const [showIdentity, setShowIdentity] = useState(false);

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    try {
      const [progressRes, journeyRes, journeyV2Res, homeRes] = await Promise.all([
        fetch(`${API}/progress`, { credentials: "include" }),
        fetch(`${API}/cognitive/journey`, { credentials: "include" }),
        fetch(`${API}/journey/v2`, { credentials: "include" }),
        fetch(`${API}/coach/home-intelligence`, { credentials: "include" })
      ]);
      
      if (progressRes.ok) setProgressData(await progressRes.json());
      if (journeyRes.ok) setJourneyData(await journeyRes.json());
      if (journeyV2Res.ok) setJourneyV2Data(await journeyV2Res.json());
      if (homeRes.ok) setHomeData(await homeRes.json());
    } catch (e) {
      console.error("Failed to fetch:", e);
    } finally {
      setLoading(false);
    }
  };

  const syncNow = async () => {
    setSyncing(true);
    try {
      await fetch(`${API}/journey/sync-now`, { method: "POST", credentials: "include" });
      setTimeout(fetchAll, 3000);
    } catch (e) {
      console.error(e);
    } finally {
      setSyncing(false);
    }
  };

  // Coaching helpers
  const getStabilityCoaching = (band) => {
    if (band === "Volatile") return { 
      icon: AlertTriangle, 
      color: "text-amber-500",
      bg: "bg-amber-500/10",
      message: "You swing between clean games and blunder-fests. The skill is there - consistency isn't."
    };
    if (band === "Stable") return { 
      icon: CheckCircle2, 
      color: "text-emerald-500",
      bg: "bg-emerald-500/10",
      message: "Your play is consistent. Focus on raising the ceiling."
    };
    return { 
      icon: Minus, 
      color: "text-slate-400",
      bg: "bg-slate-500/10",
      message: "Your consistency is average."
    };
  };

  const getPhaseCoaching = (phase) => {
    const advice = {
      "Opening": "You lose the plot in the first 15 moves.",
      "Middlegame": "The chaos of the middlegame gets you.",
      "Endgame": "You throw away won positions.",
      "Early middlegame": "Right after the opening, you lose your way.",
    };
    return advice[phase] || `Your ${phase?.toLowerCase()} needs work.`;
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

  const patterns = homeData?.specific_patterns;
  const dominantPattern = patterns?.dominant_pattern;
  const patternCount = patterns?.pattern_count || 0;
  const accuracy = progressData?.accuracy || {};
  const blunders = progressData?.blunders || {};
  const habits = progressData?.habits || [];
  const gamesAnalyzed = progressData?.valid_analysis_count || 0;
  
  const snapshot = journeyData?.snapshot;
  const journey = journeyData?.journey;
  const momentum = journeyData?.momentum;

  // Calculate improvement
  const accuracyDelta = (accuracy.current || 0) - (accuracy.previous || accuracy.current || 0);
  const isImproving = accuracyDelta > 0;

  // Get greeting based on performance
  const getGreeting = () => {
    if (accuracyDelta >= 5) return { text: "You're on fire!", icon: Flame, color: "text-orange-500" };
    if (accuracyDelta >= 2) return { text: "Nice progress", icon: TrendingUp, color: "text-emerald-500" };
    if (accuracyDelta <= -3) return { text: "Let's refocus", icon: Target, color: "text-amber-500" };
    return { text: "Steady progress", icon: Sparkles, color: "text-primary" };
  };

  const greeting = getGreeting();
  const GreetingIcon = greeting.icon;

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto space-y-6" data-testid="unified-progress-page">
        
        {/* Header with coaching vibe */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center py-4"
        >
          <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full bg-muted/50 mb-3`}>
            <GreetingIcon className={`w-5 h-5 ${greeting.color}`} />
            <span className="font-medium">{greeting.text}</span>
          </div>
          <h1 className="text-3xl font-heading font-bold mb-1">Your Progress</h1>
          <p className="text-muted-foreground text-sm">{gamesAnalyzed} games analyzed</p>
        </motion.div>

        {/* Quick Stats Row */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-2 gap-3"
        >
          {/* Accuracy */}
          <Card>
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground mb-1">Accuracy</p>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold">{accuracy.current?.toFixed(1) || '--'}%</span>
                {accuracyDelta !== 0 && (
                  <span className={`flex items-center text-xs ${isImproving ? 'text-emerald-500' : 'text-red-400'}`}>
                    {isImproving ? <TrendingUp className="w-3 h-3 mr-0.5" /> : <TrendingDown className="w-3 h-3 mr-0.5" />}
                    {accuracyDelta > 0 ? '+' : ''}{accuracyDelta.toFixed(1)}%
                  </span>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Blunders */}
          <Card>
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground mb-1">Blunders/Game</p>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold">{blunders.avg_per_game?.toFixed(1) || '--'}</span>
                <span className={`text-xs ${
                  blunders.trend === 'improving' ? 'text-emerald-500' : 
                  blunders.trend === 'worsening' ? 'text-red-400' : 'text-muted-foreground'
                }`}>
                  {blunders.trend === 'improving' ? 'improving' : 
                   blunders.trend === 'worsening' ? 'needs work' : 'stable'}
                </span>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Main Weakness - THE thing to fix */}
        {(dominantPattern || snapshot?.top_issue?.name) && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
          >
            <Card className="border-l-4 border-l-amber-500" data-testid="main-weakness">
              <CardContent className="p-5">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                    <AlertTriangle className="w-6 h-6 text-amber-500" />
                  </div>
                  <div className="flex-1">
                    <p className="text-xs text-amber-500 font-medium uppercase tracking-wide mb-1">
                      Your Main Leak
                    </p>
                    <p className="text-xl font-bold mb-1">
                      {patternCount > 0 ? `${patternCount}x ` : ''}{dominantPattern?.replace(/_/g, " ") || snapshot?.top_issue?.name}
                    </p>
                    <p className="text-sm text-muted-foreground mb-3">
                      This is costing you the most games. Fix this first.
                    </p>
                    <Button 
                      onClick={() => navigate(`/training/prescribed?weakness=${dominantPattern || snapshot?.top_issue?.name?.toLowerCase().replace(/\s+/g, '_')}`)}
                      className="bg-amber-500 hover:bg-amber-600 text-black"
                      data-testid="train-weakness-btn"
                    >
                      <Target className="w-4 h-4 mr-2" />
                      Train This Now
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Tabs: Now / Journey / Trend */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-3 bg-muted/50">
              <TabsTrigger value="now" className="gap-2 text-xs" data-testid="tab-now">
                <Target className="w-3.5 h-3.5" />
                Now
              </TabsTrigger>
              <TabsTrigger value="journey" className="gap-2 text-xs" data-testid="tab-journey">
                <TrendingUp className="w-3.5 h-3.5" />
                Journey
              </TabsTrigger>
              <TabsTrigger value="trend" className="gap-2 text-xs" data-testid="tab-trend">
                <Zap className="w-3.5 h-3.5" />
                Trend
              </TabsTrigger>
            </TabsList>

            {/* NOW TAB */}
            <TabsContent value="now" className="space-y-3 mt-4">
              {/* Consistency */}
              {snapshot?.decision_stability && (() => {
                const coaching = getStabilityCoaching(snapshot.decision_stability.band);
                const Icon = coaching.icon;
                return (
                  <Card data-testid="consistency-card">
                    <CardContent className="p-4">
                      <div className="flex items-start gap-3">
                        <div className={`w-8 h-8 rounded-lg ${coaching.bg} flex items-center justify-center flex-shrink-0`}>
                          <Icon className={`w-4 h-4 ${coaching.color}`} />
                        </div>
                        <div>
                          <div className="flex items-center gap-2 mb-0.5">
                            <p className="text-sm font-medium">Consistency</p>
                            <span className={`text-xs ${coaching.color}`}>{snapshot.decision_stability.band}</span>
                          </div>
                          <p className="text-xs text-muted-foreground">{coaching.message}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })()}

              {/* When Ahead */}
              {snapshot?.advantage_discipline && (
                <Card data-testid="when-ahead-card">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        snapshot.advantage_discipline.band === "High risk" ? "bg-red-500/10" :
                        snapshot.advantage_discipline.band === "Low risk" ? "bg-emerald-500/10" : "bg-amber-500/10"
                      }`}>
                        <Sparkles className={`w-4 h-4 ${
                          snapshot.advantage_discipline.band === "High risk" ? "text-red-500" :
                          snapshot.advantage_discipline.band === "Low risk" ? "text-emerald-500" : "text-amber-500"
                        }`} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2 mb-0.5">
                          <p className="text-sm font-medium">When winning</p>
                          <span className="text-xs text-muted-foreground">{snapshot.advantage_discipline.band}</span>
                        </div>
                        <p className="text-xs text-muted-foreground">{snapshot.advantage_discipline.meaning}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Weakest Phase */}
              {snapshot?.unstable_phase && (
                <Card data-testid="weakest-phase-card">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center flex-shrink-0">
                        <Clock className="w-4 h-4 text-red-400" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2 mb-0.5">
                          <p className="text-sm font-medium">Weakest phase</p>
                          <span className="text-xs text-red-400">{snapshot.unstable_phase}</span>
                        </div>
                        <p className="text-xs text-muted-foreground">{getPhaseCoaching(snapshot.unstable_phase)}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Active Habits */}
              {habits.filter(h => h.is_active).length > 0 && (
                <Card data-testid="habits-card">
                  <CardContent className="p-4">
                    <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">
                      Habits You're Building
                    </p>
                    <div className="space-y-2">
                      {habits.filter(h => h.is_active).slice(0, 3).map((habit, idx) => (
                        <div key={idx} className="flex items-center justify-between py-1.5">
                          <div className="flex items-center gap-2">
                            {habit.trend === 'improving' 
                              ? <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
                              : <Target className="w-3.5 h-3.5 text-muted-foreground" />
                            }
                            <span className="text-sm">{habit.name}</span>
                          </div>
                          <span className="text-xs text-muted-foreground">{habit.occurrences_recent} this week</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Coach's Focus */}
              {snapshot?.directive && (
                <Card className="border-primary/30 bg-primary/5" data-testid="coach-focus-card">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <Brain className="w-5 h-5 text-primary mt-0.5" />
                      <div>
                        <p className="text-xs text-primary font-medium uppercase tracking-wide mb-1">Coach's Focus</p>
                        <p className="text-sm font-medium">{snapshot.directive}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* JOURNEY TAB */}
            <TabsContent value="journey" className="space-y-3 mt-4">
              {!journey?.ready ? (
                <Card>
                  <CardContent className="py-8 text-center">
                    <p className="text-sm text-muted-foreground">{journey?.message || "Building your story..."}</p>
                  </CardContent>
                </Card>
              ) : (
                <>
                  {/* Voice Headline */}
                  {journey.voice && (
                    <Card className={`border-l-4 ${
                      journey.voice.tone_level === "positive" ? "border-l-emerald-500" :
                      journey.voice.tone_level === "concern" ? "border-l-amber-500" : "border-l-slate-500"
                    }`}>
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between">
                          <div>
                            <p className={`text-base font-semibold mb-1 ${
                              journey.voice.tone_level === "positive" ? "text-emerald-400" :
                              journey.voice.tone_level === "concern" ? "text-amber-400" : ""
                            }`}>
                              {journey.voice.headline}
                            </p>
                            <p className="text-xs text-muted-foreground">{journey.voice.explanation}</p>
                          </div>
                          {journey.badge && (
                            <span className="flex items-center gap-1 text-xs bg-emerald-500/10 text-emerald-400 px-2 py-1 rounded">
                              <Award className="w-3 h-3" />
                              {journey.badge}
                            </span>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Before vs After */}
                  {journey.stat_rows && journey.overall_change !== "stable_hidden" && (
                    <Card>
                      <CardContent className="p-4">
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">
                          Your Progress
                        </p>
                        <div className="space-y-2">
                          {journey.stat_rows.map((row, idx) => (
                            <div key={idx} className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
                              <span className="text-xs text-muted-foreground">{row.label}</span>
                              <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground">{row.then}</span>
                                <ArrowRight className="w-3 h-3 text-muted-foreground" />
                                <span className="text-xs font-medium">{row.now}</span>
                                {row.show_delta && (
                                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                                    (row.lower_is_better ? parseFloat(row.delta) < 0 : parseFloat(row.delta) > 0)
                                      ? "bg-emerald-500/10 text-emerald-400"
                                      : "bg-red-500/10 text-red-400"
                                  }`}>
                                    {row.delta}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Rating Ceiling - Your True Level */}
                  {journeyV2Data?.rating_ceiling?.has_data && (
                    <Card className={`border-l-4 ${
                      journeyV2Data.rating_ceiling.urgency === "high" ? "border-l-red-500" :
                      journeyV2Data.rating_ceiling.urgency === "medium" ? "border-l-amber-500" : "border-l-emerald-500"
                    }`} data-testid="rating-ceiling-card">
                      <CardContent className="p-4">
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">
                          Your True Level
                        </p>
                        <div className="grid grid-cols-2 gap-4 mb-4">
                          <div className="text-center p-3 rounded-lg bg-muted/50">
                            <p className="text-xs text-muted-foreground mb-1">Stable Level</p>
                            <p className="text-2xl font-bold">{journeyV2Data.rating_ceiling.stable_level}</p>
                            <p className="text-xs text-muted-foreground">
                              {journeyV2Data.rating_ceiling.stable_games_count} clean games
                            </p>
                          </div>
                          <div className="text-center p-3 rounded-lg bg-primary/10">
                            <p className="text-xs text-muted-foreground mb-1">Peak Level</p>
                            <p className="text-2xl font-bold text-primary">{journeyV2Data.rating_ceiling.peak_level}</p>
                            <p className="text-xs text-muted-foreground">
                              {journeyV2Data.rating_ceiling.peak_accuracy}% accuracy
                            </p>
                          </div>
                        </div>
                        
                        {/* Gap visualization */}
                        <div className="space-y-2 mb-3">
                          <div className="flex justify-between text-xs">
                            <span className="text-muted-foreground">Stability Gap</span>
                            <span className="font-medium">{journeyV2Data.rating_ceiling.gap} points</span>
                          </div>
                          <div className="h-2 rounded-full bg-muted overflow-hidden">
                            <div 
                              className="h-full bg-primary rounded-full transition-all"
                              style={{ width: `${Math.min(100, (journeyV2Data.rating_ceiling.stable_level / journeyV2Data.rating_ceiling.peak_level) * 100)}%` }}
                            />
                          </div>
                        </div>
                        
                        <p className="text-sm text-muted-foreground">
                          {journeyV2Data.rating_ceiling.message}
                        </p>
                        
                        {journeyV2Data.rating_ceiling.gap_driver && (
                          <div className="mt-3 p-2 rounded bg-amber-500/10 border border-amber-500/20">
                            <p className="text-xs font-medium text-amber-500">Gap Driver: {journeyV2Data.rating_ceiling.gap_driver}</p>
                            <p className="text-xs text-muted-foreground mt-1">{journeyV2Data.rating_ceiling.fix_suggestion}</p>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  )}

                  {/* Baseline Comparison - First 10 vs Now */}
                  {journeyV2Data?.has_baseline && journeyV2Data?.baseline && journeyV2Data?.current_stats && (
                    <Card data-testid="baseline-comparison-card">
                      <CardContent className="p-4">
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">
                          Long-term: First {journeyV2Data.baseline.games_analyzed} vs Last {journeyV2Data.current_stats.games_analyzed} Games
                        </p>
                        <div className="space-y-2">
                          {/* Accuracy */}
                          <div className="flex items-center justify-between py-1.5 border-b border-border/30">
                            <span className="text-xs text-muted-foreground">Accuracy</span>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">{journeyV2Data.baseline.avg_accuracy?.toFixed(1)}%</span>
                              <ArrowRight className="w-3 h-3 text-muted-foreground" />
                              <span className="text-xs font-medium">{journeyV2Data.current_stats.avg_accuracy?.toFixed(1)}%</span>
                              {(() => {
                                const delta = journeyV2Data.current_stats.avg_accuracy - journeyV2Data.baseline.avg_accuracy;
                                return delta !== 0 && (
                                  <span className={`text-xs px-1.5 py-0.5 rounded ${delta > 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                                    {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
                                  </span>
                                );
                              })()}
                            </div>
                          </div>
                          {/* Blunders/Game */}
                          <div className="flex items-center justify-between py-1.5 border-b border-border/30">
                            <span className="text-xs text-muted-foreground">Blunders/Game</span>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">{journeyV2Data.baseline.blunders_per_game?.toFixed(1)}</span>
                              <ArrowRight className="w-3 h-3 text-muted-foreground" />
                              <span className="text-xs font-medium">{journeyV2Data.current_stats.blunders_per_game?.toFixed(1)}</span>
                              {(() => {
                                const delta = journeyV2Data.current_stats.blunders_per_game - journeyV2Data.baseline.blunders_per_game;
                                return delta !== 0 && (
                                  <span className={`text-xs px-1.5 py-0.5 rounded ${delta < 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                                    {delta > 0 ? '+' : ''}{delta.toFixed(1)}
                                  </span>
                                );
                              })()}
                            </div>
                          </div>
                          {/* Best Moves/Game */}
                          <div className="flex items-center justify-between py-1.5">
                            <span className="text-xs text-muted-foreground">Best Moves/Game</span>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">{journeyV2Data.baseline.best_moves_per_game?.toFixed(1)}</span>
                              <ArrowRight className="w-3 h-3 text-muted-foreground" />
                              <span className="text-xs font-medium">{journeyV2Data.current_stats.best_moves_per_game?.toFixed(1)}</span>
                              {(() => {
                                const delta = journeyV2Data.current_stats.best_moves_per_game - journeyV2Data.baseline.best_moves_per_game;
                                return delta !== 0 && (
                                  <span className={`text-xs px-1.5 py-0.5 rounded ${delta > 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                                    {delta > 0 ? '+' : ''}{delta.toFixed(1)}
                                  </span>
                                );
                              })()}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Short-term Pattern Trends - Last 7 vs Previous 7 */}
                  {journeyV2Data?.pattern_trends?.has_enough_data && (
                    <Card data-testid="short-term-trends-card">
                      <CardContent className="p-4">
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">
                          Short-term: Last {journeyV2Data.pattern_trends.recent_games} vs Previous {journeyV2Data.pattern_trends.previous_games} Games
                        </p>
                        <div className="space-y-2">
                          {Object.entries(journeyV2Data.pattern_trends.patterns || {}).map(([key, pattern]) => (
                            <div key={key} className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
                              <span className="text-xs text-muted-foreground">{pattern.label}</span>
                              <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground">{pattern.previous}</span>
                                <ArrowRight className="w-3 h-3 text-muted-foreground" />
                                <span className="text-xs font-medium">{pattern.recent}</span>
                                <span className={`text-xs px-1.5 py-0.5 rounded flex items-center gap-1 ${
                                  pattern.trend === "improving" ? "bg-emerald-500/10 text-emerald-400" :
                                  pattern.trend === "worsening" ? "bg-red-500/10 text-red-400" :
                                  "bg-slate-500/10 text-slate-400"
                                }`}>
                                  {pattern.trend === "improving" ? <TrendingDown className="w-3 h-3" /> :
                                   pattern.trend === "worsening" ? <TrendingUp className="w-3 h-3" /> :
                                   <Minus className="w-3 h-3" />}
                                  {pattern.change > 0 ? '+' : ''}{pattern.change}%
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Behavioral Changes - Long term */}
                  {journeyV2Data?.pattern_comparison?.weaknesses?.length > 0 && (
                    <Card data-testid="behavioral-changes-card">
                      <CardContent className="p-4">
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">
                          Behavioral Changes (Overall Journey)
                        </p>
                        <div className="space-y-3">
                          {journeyV2Data.pattern_comparison.weaknesses.map((weakness) => (
                            <div key={weakness.id} className="p-3 rounded-lg bg-muted/30">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium">{weakness.label}</span>
                                <span className={`text-xs px-2 py-0.5 rounded ${
                                  weakness.trend === "fixed" ? "bg-emerald-500/20 text-emerald-400" :
                                  weakness.trend === "improved" ? "bg-blue-500/20 text-blue-400" :
                                  weakness.trend === "regressed" ? "bg-red-500/20 text-red-400" :
                                  "bg-slate-500/10 text-slate-400"
                                }`}>
                                  {weakness.trend === "fixed" ? "Fixed!" :
                                   weakness.trend === "improved" ? "Improving" :
                                   weakness.trend === "regressed" ? "Needs work" : "Stable"}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <span>Occurrence: {weakness.baseline_pct}%</span>
                                <ArrowRight className="w-3 h-3" />
                                <span className="font-medium text-foreground">{weakness.current_pct}%</span>
                                {weakness.delta !== 0 && (
                                  <span className={weakness.delta < 0 ? "text-emerald-400" : "text-red-400"}>
                                    ({weakness.delta > 0 ? '+' : ''}{weakness.delta}%)
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                        
                        {/* Overall improvement indicator */}
                        {journeyV2Data.pattern_comparison.overall_improvement && (
                          <div className={`mt-3 p-2 rounded text-center text-xs font-medium ${
                            journeyV2Data.pattern_comparison.overall_improvement === "improving" 
                              ? "bg-emerald-500/10 text-emerald-400" 
                              : journeyV2Data.pattern_comparison.overall_improvement === "regressing"
                              ? "bg-red-500/10 text-red-400"
                              : "bg-slate-500/10 text-slate-400"
                          }`}>
                            Overall: {journeyV2Data.pattern_comparison.overall_improvement === "improving" 
                              ? "Your behaviors are improving!" 
                              : journeyV2Data.pattern_comparison.overall_improvement === "regressing"
                              ? "Some patterns need attention"
                              : "Behaviors are stable"}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  )}

                  {/* Cognitive Journey - Decision making evolution */}
                  {journey?.cognitive_rows && journey.cognitive_rows.length > 0 && (
                    <Card data-testid="cognitive-journey-card">
                      <CardContent className="p-4">
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">
                          Decision Making Evolution
                        </p>
                        <div className="space-y-2">
                          {journey.cognitive_rows.map((row, idx) => (
                            <div key={idx} className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
                              <span className="text-xs text-muted-foreground">{row.label}</span>
                              <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground">{row.then}</span>
                                <ArrowRight className="w-3 h-3 text-muted-foreground" />
                                <span className={`text-xs font-medium ${row.changed ? "text-emerald-400" : ""}`}>
                                  {row.now}
                                </span>
                                {row.changed && (
                                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Journey Directive */}
                  {journey.directive && (
                    <Card className="border-primary/30 bg-primary/5">
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <Target className="w-5 h-5 text-primary mt-0.5" />
                          <div>
                            <p className="text-xs text-primary font-medium uppercase tracking-wide mb-1">Next Milestone</p>
                            <p className="text-sm font-medium">{journey.directive}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </>
              )}
            </TabsContent>

            {/* TREND TAB */}
            <TabsContent value="trend" className="space-y-3 mt-4">
              {!momentum?.ready ? (
                <Card>
                  <CardContent className="py-8 text-center">
                    <p className="text-sm text-muted-foreground">{momentum?.message || "Analyzing recent games..."}</p>
                  </CardContent>
                </Card>
              ) : (
                <>
                  {/* Momentum Headline */}
                  <Card className={`border-l-4 ${
                    momentum.voice?.tone_level === "positive" ? "border-l-emerald-500" :
                    momentum.voice?.tone_level === "concern" ? "border-l-amber-500" : "border-l-slate-500"
                  }`}>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-2">
                          {momentum.voice?.tone_level === "positive" ? (
                            <Flame className="w-5 h-5 text-orange-500" />
                          ) : momentum.voice?.tone_level === "concern" ? (
                            <TrendingDown className="w-5 h-5 text-amber-500" />
                          ) : (
                            <Minus className="w-5 h-5 text-slate-400" />
                          )}
                          <p className={`text-base font-semibold ${
                            momentum.voice?.tone_level === "positive" ? "text-emerald-400" :
                            momentum.voice?.tone_level === "concern" ? "text-amber-400" : ""
                          }`}>
                            {momentum.headline}
                          </p>
                        </div>
                        {momentum.badge && (
                          <span className="flex items-center gap-1 text-xs bg-orange-500/10 text-orange-400 px-2 py-1 rounded">
                            <Flame className="w-3 h-3" />
                            {momentum.badge}
                          </span>
                        )}
                      </div>
                    </CardContent>
                  </Card>

                  {/* What's Changing */}
                  {momentum.shifts && momentum.shifts.length > 0 && (
                    <Card>
                      <CardContent className="p-4">
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">
                          What's Changing
                        </p>
                        <div className="space-y-2">
                          {momentum.shifts.map((shift, idx) => (
                            <div key={idx} className="flex items-start gap-2 py-1.5">
                              {shift.direction === "improving" ? (
                                <TrendingUp className="w-3.5 h-3.5 text-emerald-500 mt-0.5" />
                              ) : shift.direction === "declining" ? (
                                <TrendingDown className="w-3.5 h-3.5 text-red-400 mt-0.5" />
                              ) : (
                                <Minus className="w-3.5 h-3.5 text-slate-400 mt-0.5" />
                              )}
                              <div>
                                <p className="text-sm font-medium">{shift.area}</p>
                                <p className="text-xs text-muted-foreground">{shift.detail}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Evidence */}
                  {momentum.evidence && momentum.evidence.length > 0 && (
                    <Card>
                      <CardContent className="p-4">
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">
                          See It In Your Games
                        </p>
                        <div className="space-y-1.5">
                          {momentum.evidence.slice(0, 3).map((ev, idx) => (
                            <button
                              key={idx}
                              onClick={() => navigate(`/lab/game/${ev.game_id}?move=${ev.move_number}`)}
                              className="w-full flex items-center justify-between p-2.5 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors text-left"
                            >
                              <div className="flex items-center gap-2">
                                <Eye className="w-3.5 h-3.5 text-muted-foreground" />
                                <div>
                                  <p className="text-sm">{ev.label}</p>
                                  <p className="text-xs text-muted-foreground">vs {ev.opponent}</p>
                                </div>
                              </div>
                              <ChevronRight className="w-4 h-4 text-muted-foreground" />
                            </button>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Trend Directive */}
                  {momentum.directive && (
                    <Card className="border-primary/30 bg-primary/5">
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <Zap className="w-5 h-5 text-primary mt-0.5" />
                          <div>
                            <p className="text-xs text-primary font-medium uppercase tracking-wide mb-1">Keep This Going</p>
                            <p className="text-sm font-medium">{momentum.directive}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </>
              )}
            </TabsContent>
          </Tabs>
        </motion.div>

        {/* Playing Identity - Expandable */}
        {progressData?.playing_identity && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
          >
            <Card>
              <CardContent className="p-4">
                <button 
                  onClick={() => setShowIdentity(!showIdentity)}
                  className="w-full flex items-center justify-between"
                  data-testid="identity-toggle"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Brain className="w-4 h-4 text-primary" />
                    </div>
                    <div className="text-left">
                      <p className="text-sm font-medium">Your Playing Identity</p>
                      <p className="text-xs text-muted-foreground">Based on {progressData.total_analysis_count} games</p>
                    </div>
                  </div>
                  {showIdentity ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
                
                <AnimatePresence>
                  {showIdentity && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <p className="text-sm text-muted-foreground mt-4 pt-4 border-t border-border/50">
                        {progressData.playing_identity}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="grid grid-cols-2 gap-3"
        >
          <Button 
            variant="outline" 
            className="h-auto py-3 flex-col gap-1"
            onClick={() => navigate('/reflect')}
          >
            <Eye className="w-4 h-4" />
            <span className="text-xs">Reflect</span>
          </Button>
          <Button 
            variant="outline" 
            className="h-auto py-3 flex-col gap-1"
            onClick={() => navigate('/home')}
          >
            <Target className="w-4 h-4" />
            <span className="text-xs">Today's Focus</span>
          </Button>
        </motion.div>

        {/* Sync footer */}
        <div className="flex justify-center pt-2 pb-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={syncNow}
            disabled={syncing}
            className="text-muted-foreground text-xs"
          >
            {syncing ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
            Sync latest games
          </Button>
        </div>
      </div>
    </Layout>
  );
};

export default UnifiedProgress;
