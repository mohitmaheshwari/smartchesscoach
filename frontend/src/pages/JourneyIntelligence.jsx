/**
 * Journey Intelligence Page
 * 
 * A single, intelligent page that feels like a personal coach.
 * Data-driven, calm, precise, and actionable.
 * 
 * Answers in 5 seconds:
 * - Who am I?
 * - What is my main problem?
 * - What should I do next?
 * - How far can I go?
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import PlayerIdentityCard from "@/components/Journey/PlayerIdentityCard";
import { CoachFocusCard } from "@/components/Home";
import {
  Brain,
  Target,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronRight,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  BarChart3,
  Crosshair,
  Layers,
  BookOpen,
  Activity,
  HelpCircle,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const JourneyIntelligence = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState("snapshot"); // snapshot | trend

  useEffect(() => {
    fetchIntelligence();
  }, []);

  const fetchIntelligence = async () => {
    try {
      const res = await fetch(`${API}/journey/intelligence`, { credentials: "include" });
      if (res.ok) {
        setData(await res.json());
      }
    } catch (err) {
      console.error("Error fetching journey intelligence:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  if (!data?.has_data) {
    return (
      <Layout>
        <div className="max-w-2xl mx-auto py-12 text-center">
          <Brain className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Building Your Profile</h2>
          <p className="text-muted-foreground mb-6">
            {data?.message || "Analyze more games to unlock deeper insights."}
          </p>
          <p className="text-sm text-muted-foreground">
            {data?.games_analyzed || 0} / {data?.minimum_required || 5} games analyzed
          </p>
          <Button onClick={() => navigate("/home")} className="mt-6">
            Go to Coach Home
          </Button>
        </div>
      </Layout>
    );
  }

  const { identity, growth_delta, rating_ceiling, pattern_engine, phase_discipline, fundamentals, openings, momentum } = data;

  return (
    <Layout>
      <div className="max-w-3xl mx-auto py-6 space-y-6">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold mb-1">Your Chess Journey</h1>
          <p className="text-sm text-muted-foreground">
            Based on last {data.games_analyzed} analyzed games
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="flex justify-center gap-2 mb-6">
          <Button
            variant={activeTab === "snapshot" ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveTab("snapshot")}
          >
            Snapshot
          </Button>
          <Button
            variant={activeTab === "trend" ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveTab("trend")}
          >
            Trend
          </Button>
        </div>

        {activeTab === "snapshot" ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6"
          >
            {/* SECTION 0: Coach Focus This Week - FROM CoachState */}
            <CoachFocusCard />

            {/* SECTION 1: Player Identity (New Rich Component) */}
            <PlayerIdentityCard identity={identity} />

            {/* SECTION 1b: Immediate Focus (THE KEY CARD) */}
            {data.immediate_focus && (
              <Card className="border-primary/50 bg-primary/5" data-testid="immediate-focus">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2 text-primary">
                    <Target className="w-5 h-5" />
                    Do This Next
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-lg font-medium mb-2">{data.immediate_focus.text}</p>
                  <p className="text-sm text-muted-foreground">{data.immediate_focus.reason}</p>
                </CardContent>
              </Card>
            )}

            {/* SECTION 2: Growth Delta */}
            {growth_delta.has_delta && (
              <Card data-testid="growth-delta">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-primary" />
                    Your Progress
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">
                    Last {growth_delta.recent_games} games vs Previous {growth_delta.previous_games} games
                  </p>
                </CardHeader>
                <CardContent>
                  {growth_delta.is_stable ? (
                    <p className="text-sm text-muted-foreground">{growth_delta.message}</p>
                  ) : (
                    <div className="space-y-3">
                      {growth_delta.metrics
                        .filter(metric => {
                          // Filter out metrics where both values are 0 or empty
                          const prevNum = parseFloat(String(metric.previous).replace(/[^0-9.-]/g, '')) || 0;
                          const recentNum = parseFloat(String(metric.recent).replace(/[^0-9.-]/g, '')) || 0;
                          return prevNum !== 0 || recentNum !== 0 || metric.delta !== 0;
                        })
                        .map((metric, idx) => (
                        <div key={idx} className="flex items-center justify-between">
                          <span className="text-sm">{metric.name}</span>
                          <div className="flex items-center gap-3">
                            <span className="text-sm text-muted-foreground">
                              {metric.previous} → {metric.recent}
                            </span>
                            {metric.delta !== 0 && (
                              <span className={`text-sm font-medium flex items-center gap-1 ${
                                metric.improved ? "text-emerald-500" : "text-red-500"
                              }`}>
                                {metric.improved ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
                                {metric.improved ? "-" : "+"}{Math.abs(metric.delta)}{metric.unit}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* SECTION 3: Rating Ceiling Model */}
            {rating_ceiling.has_ceiling && (
              <Card data-testid="rating-ceiling">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Crosshair className="w-5 h-5 text-primary" />
                    Your Rating Potential
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <TooltipProvider>
                    <div className="grid grid-cols-3 gap-3 text-center">
                      <div className="p-3 rounded-lg bg-muted/30">
                        <p className="text-2xl font-bold">{rating_ceiling.stable_rating}</p>
                        <Tooltip>
                          <TooltipTrigger className="text-xs text-muted-foreground flex items-center justify-center gap-1 cursor-help">
                            Stable Level <HelpCircle className="w-3 h-3" />
                          </TooltipTrigger>
                          <TooltipContent side="bottom" className="max-w-[200px]">
                            <p className="text-xs">Your average performance rating across all analyzed games. Updates after each game analysis.</p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                        <p className="text-2xl font-bold text-emerald-500">{rating_ceiling.peak_rating}</p>
                        <Tooltip>
                          <TooltipTrigger className="text-xs text-muted-foreground flex items-center justify-center gap-1 cursor-help">
                            Demonstrated Peak <HelpCircle className="w-3 h-3" />
                          </TooltipTrigger>
                          <TooltipContent side="bottom" className="max-w-[200px]">
                            <p className="text-xs">Your highest estimated performance based on your best games. Shows what you're capable of on a good day.</p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
                        <p className="text-2xl font-bold text-amber-500">+{rating_ceiling.performance_gap}</p>
                        <Tooltip>
                          <TooltipTrigger className="text-xs text-muted-foreground flex items-center justify-center gap-1 cursor-help">
                            Performance Gap <HelpCircle className="w-3 h-3" />
                          </TooltipTrigger>
                          <TooltipContent side="bottom" className="max-w-[200px]">
                            <p className="text-xs">The difference between your peak and stable level. A smaller gap means more consistent play.</p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                    </div>
                  </TooltipProvider>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {rating_ceiling.explanation}
                  </p>
                </CardContent>
              </Card>
            )}

            {/* SECTION 4: Pattern Engine */}
            {pattern_engine.has_pattern && (
              <Card data-testid="pattern-engine">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <BarChart3 className="w-5 h-5 text-primary" />
                    Where You Lose Control
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-3">
                    {pattern_engine.states.map((state, idx) => (
                      <div key={idx} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className={state.state === pattern_engine.highest_state ? "font-medium" : "text-muted-foreground"}>
                            {state.label}
                          </span>
                          <span className={state.state === pattern_engine.highest_state ? "font-medium" : "text-muted-foreground"}>
                            {state.percentage}%
                          </span>
                        </div>
                        <Progress 
                          value={state.percentage} 
                          className={`h-2 ${state.state === pattern_engine.highest_state ? "" : "opacity-50"}`}
                        />
                      </div>
                    ))}
                  </div>
                  <p className="text-sm text-muted-foreground">{pattern_engine.interpretation}</p>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={() => navigate("/lab")}
                    className="w-full"
                  >
                    View Critical Moments <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* SECTION 5: Phase Discipline */}
            <Card data-testid="phase-discipline">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Layers className="w-5 h-5 text-primary" />
                  Game Discipline
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-3">
                  {phase_discipline.phases.map((phase, idx) => (
                    <div 
                      key={idx} 
                      className={`p-3 rounded-lg text-center ${
                        phase.is_stable 
                          ? "bg-emerald-500/10 border border-emerald-500/30" 
                          : "bg-red-500/10 border border-red-500/30"
                      }`}
                    >
                      <p className="font-medium">{phase.label}</p>
                      <p className={`text-sm ${phase.is_stable ? "text-emerald-500" : "text-red-500"}`}>
                        {phase.status}
                      </p>
                      {phase.phase === phase_discipline.most_errors_phase && (
                        <p className="text-xs text-muted-foreground mt-1">Most errors</p>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* SECTION 6: Fundamentals Snapshot */}
            {fundamentals.has_fundamentals && (
              <Card data-testid="fundamentals">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-primary" />
                    Fundamentals Snapshot
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    {fundamentals.strongest && (
                      <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                        <p className="text-xs text-emerald-500 mb-1">Strongest</p>
                        <p className="font-medium">{fundamentals.strongest.label}</p>
                      </div>
                    )}
                    {fundamentals.focus && fundamentals.focus.percentage > 0 && (
                      <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
                        <p className="text-xs text-amber-500 mb-1">Focus Area</p>
                        <p className="font-medium">{fundamentals.focus.label}</p>
                      </div>
                    )}
                  </div>
                  {fundamentals.focus_action && (
                    <p className="text-sm text-muted-foreground">{fundamentals.focus_action}</p>
                  )}
                </CardContent>
              </Card>
            )}

            {/* SECTION 7: Opening Snapshot */}
            {openings.has_openings && (
              <Card data-testid="openings">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <BookOpen className="w-5 h-5 text-primary" />
                    Opening Snapshot
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {openings.openings.map((opening, idx) => (
                      <div key={idx} className="flex items-center justify-between p-2 rounded-lg hover:bg-muted/30">
                        <div>
                          <p className="font-medium text-sm">{opening.name}</p>
                          <p className="text-xs text-muted-foreground">{opening.games} games</p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm">{opening.win_rate}% win</p>
                          <p className={`text-xs ${opening.status === "Stable" ? "text-emerald-500" : "text-amber-500"}`}>
                            {opening.status}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </motion.div>
        ) : (
          /* TREND TAB */
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6"
          >
            {/* SECTION 8: Momentum Trend */}
            <Card data-testid="momentum">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Activity className="w-5 h-5 text-primary" />
                  Recent Momentum
                </CardTitle>
                <p className="text-xs text-muted-foreground">Last 5 vs Previous 5 games</p>
              </CardHeader>
              <CardContent>
                {momentum.has_momentum ? (
                  momentum.is_stable ? (
                    <p className="text-sm text-muted-foreground">{momentum.message}</p>
                  ) : (
                    <div className="space-y-4">
                      <div className={`p-4 rounded-lg ${
                        momentum.biggest_change.direction === "improved" 
                          ? "bg-emerald-500/10 border border-emerald-500/30"
                          : "bg-red-500/10 border border-red-500/30"
                      }`}>
                        <div className="flex items-center gap-2 mb-2">
                          {momentum.biggest_change.direction === "improved" 
                            ? <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                            : <AlertTriangle className="w-5 h-5 text-red-500" />
                          }
                          <span className="font-medium">{momentum.message}</span>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {momentum.biggest_change.metric}: {momentum.biggest_change.direction === "improved" ? "getting better" : "needs attention"}
                        </p>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 rounded-lg bg-muted/30">
                          <p className="text-xs text-muted-foreground mb-1">Recent (5 games)</p>
                          <p className="text-sm">Blunders: {momentum.recent.blunders}/game</p>
                          <p className="text-sm">Win Rate: {momentum.recent.win_rate}%</p>
                        </div>
                        <div className="p-3 rounded-lg bg-muted/30">
                          <p className="text-xs text-muted-foreground mb-1">Previous (5 games)</p>
                          <p className="text-sm">Blunders: {momentum.previous.blunders}/game</p>
                          <p className="text-sm">Win Rate: {momentum.previous.win_rate}%</p>
                        </div>
                      </div>
                    </div>
                  )
                ) : (
                  <p className="text-sm text-muted-foreground">{momentum.message || "Need more games."}</p>
                )}
              </CardContent>
            </Card>

            {/* Growth Delta in Trend Tab too */}
            {growth_delta.has_delta && !growth_delta.is_stable && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-primary" />
                    Long-term Progress
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">
                    Last {growth_delta.recent_games} games vs Previous {growth_delta.previous_games} games
                  </p>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {growth_delta.metrics.map((metric, idx) => (
                      <div key={idx} className="flex items-center justify-between">
                        <span className="text-sm">{metric.name}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-sm text-muted-foreground">
                            {metric.previous} → {metric.recent}
                          </span>
                          {metric.delta !== 0 && (
                            <span className={`text-sm font-medium flex items-center gap-1 ${
                              metric.improved ? "text-emerald-500" : "text-red-500"
                            }`}>
                              {metric.improved ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
                              {metric.improved ? "-" : "+"}{Math.abs(metric.delta)}{metric.unit}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </motion.div>
        )}
      </div>
    </Layout>
  );
};

export default JourneyIntelligence;
