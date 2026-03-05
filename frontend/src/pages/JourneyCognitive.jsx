/**
 * JOURNEY PAGE - Human Coach Style
 * 
 * Not a dashboard. A coaching narrative.
 * Your coach telling you YOUR story, with specific examples and actionable steps.
 * 
 * Tab A (Now): Quick snapshot with coaching context
 * Tab B (Journey): Your progress story with Before → After
 * Tab C (Trend): Recent momentum with specific game evidence
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import Layout from "@/components/Layout";
import { 
  Loader2, ArrowRight, Target, Zap, Award, Clock, Eye,
  TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle2,
  Brain, Flame, Sparkles, ChevronRight, RefreshCw
} from "lucide-react";

const Journey = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("now");
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    fetchJourneyData();
  }, []);

  const fetchJourneyData = async () => {
    try {
      const response = await fetch(`${API}/cognitive/journey`, { credentials: "include" });
      if (response.ok) {
        const result = await response.json();
        setData(result);
      } else {
        setError("Failed to load journey data");
      }
    } catch (e) {
      console.error("Failed to fetch journey data:", e);
      setError("Failed to load journey data");
    } finally {
      setLoading(false);
    }
  };

  const syncNow = async () => {
    setSyncing(true);
    try {
      await fetch(`${API}/journey/sync-now`, { method: "POST", credentials: "include" });
      setTimeout(fetchJourneyData, 3000);
    } catch (e) {
      console.error(e);
    } finally {
      setSyncing(false);
    }
  };

  const handleEvidenceClick = (gameId, moveNumber) => {
    navigate(`/lab/game/${gameId}?move=${moveNumber}&src=journey`);
  };

  // Coaching tone helpers
  const getStabilityCoaching = (band) => {
    if (band === "Volatile") return { 
      icon: AlertTriangle, 
      color: "text-amber-500",
      message: "You're swinging between clean games and blunder-fests. The skill is there - consistency isn't."
    };
    if (band === "Stable") return { 
      icon: CheckCircle2, 
      color: "text-emerald-500",
      message: "Your play is consistent. Focus on raising the ceiling, not plugging leaks."
    };
    return { 
      icon: Minus, 
      color: "text-slate-400",
      message: "Your consistency is average. Some games are clean, some aren't."
    };
  };

  const getPhaseCoaching = (phase) => {
    const phaseAdvice = {
      "Opening": "You're losing the plot in the first 15 moves. Study your openings.",
      "Middlegame": "The chaos of the middlegame gets you. Slow down when pieces are flying.",
      "Endgame": "You're throwing away won positions. Learn basic endgame technique.",
      "Early middlegame": "Right after the opening, you lose your way. Plan before you push.",
    };
    return phaseAdvice[phase] || `Your ${phase?.toLowerCase()} needs work.`;
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

  if (error) {
    return (
      <Layout user={user}>
        <div className="max-w-2xl mx-auto text-center py-12">
          <p className="text-muted-foreground">{error}</p>
          <Button onClick={fetchJourneyData} variant="outline" className="mt-4">
            Try Again
          </Button>
        </div>
      </Layout>
    );
  }

  const snapshot = data?.snapshot;
  const journey = data?.journey;
  const momentum = data?.momentum;
  const gamesAnalyzed = data?.games_analyzed || 0;

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto space-y-6" data-testid="journey-page">
        {/* Header with coaching context */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center py-4"
        >
          <h1 className="text-3xl font-heading font-bold tracking-tight mb-2">Your Journey</h1>
          <p className="text-muted-foreground">
            {gamesAnalyzed} games analyzed
          </p>
        </motion.div>

        {/* Tabs with better labels */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-3 bg-muted/50">
            <TabsTrigger value="now" className="gap-2" data-testid="tab-now">
              <Target className="w-4 h-4" />
              Now
            </TabsTrigger>
            <TabsTrigger value="journey" className="gap-2" data-testid="tab-journey">
              <TrendingUp className="w-4 h-4" />
              Journey
            </TabsTrigger>
            <TabsTrigger value="trend" className="gap-2" data-testid="tab-trend">
              <Zap className="w-4 h-4" />
              Trend
            </TabsTrigger>
          </TabsList>

          {/* ============================================ */}
          {/* TAB A: SNAPSHOT (NOW) - Human Coach Style */}
          {/* ============================================ */}
          <TabsContent value="now" className="space-y-4 mt-6">
            <AnimatePresence>
              {!snapshot?.ready ? (
                <Card>
                  <CardContent className="py-12 text-center">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto mb-4 text-muted-foreground" />
                    <p className="text-muted-foreground">{snapshot?.message || "Loading your analysis..."}</p>
                  </CardContent>
                </Card>
              ) : (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="space-y-4"
                >
                  {/* Main Issue - The ONE thing to fix */}
                  <Card className="border-l-4 border-l-amber-500" data-testid="snapshot-main-issue">
                    <CardContent className="p-5">
                      <div className="flex items-start gap-4">
                        <div className="w-12 h-12 rounded-xl bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                          <AlertTriangle className="w-6 h-6 text-amber-500" />
                        </div>
                        <div className="flex-1">
                          <p className="text-xs text-amber-500 font-medium uppercase tracking-wide mb-1">
                            Your Main Issue
                          </p>
                          <p className="text-xl font-bold mb-2">
                            {snapshot.top_issue?.name || "No clear pattern yet"}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            This is costing you the most games. Fix this first.
                          </p>
                          {snapshot.top_issue?.name && (
                            <Button 
                              variant="outline" 
                              size="sm" 
                              className="mt-3 gap-2"
                              onClick={() => navigate(`/training/prescribed?weakness=${snapshot.top_issue?.name?.toLowerCase().replace(/\s+/g, '_')}`)}
                            >
                              <Target className="w-3 h-3" />
                              Train This
                            </Button>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Consistency Check */}
                  {snapshot.decision_stability && (() => {
                    const coaching = getStabilityCoaching(snapshot.decision_stability.band);
                    const Icon = coaching.icon;
                    return (
                      <Card data-testid="snapshot-stability">
                        <CardContent className="p-5">
                          <div className="flex items-start gap-4">
                            <Icon className={`w-5 h-5 mt-0.5 ${coaching.color}`} />
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <p className="text-sm text-muted-foreground">Consistency</p>
                                <span className={`text-sm font-medium ${coaching.color}`}>
                                  {snapshot.decision_stability.band}
                                </span>
                              </div>
                              <p className="text-sm">{coaching.message}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })()}

                  {/* When Ahead */}
                  {snapshot.advantage_discipline && (
                    <Card data-testid="snapshot-advantage">
                      <CardContent className="p-5">
                        <div className="flex items-start gap-4">
                          <Sparkles className={`w-5 h-5 mt-0.5 ${
                            snapshot.advantage_discipline.band === "High risk" 
                              ? "text-red-500" 
                              : snapshot.advantage_discipline.band === "Low risk"
                              ? "text-emerald-500"
                              : "text-amber-500"
                          }`} />
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <p className="text-sm text-muted-foreground">When you're winning</p>
                              <span className="text-sm font-medium">
                                {snapshot.advantage_discipline.band}
                              </span>
                            </div>
                            <p className="text-sm">
                              {snapshot.advantage_discipline.meaning}
                            </p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Weakest Phase */}
                  {snapshot.unstable_phase && (
                    <Card data-testid="snapshot-phase">
                      <CardContent className="p-5">
                        <div className="flex items-start gap-4">
                          <Clock className="w-5 h-5 mt-0.5 text-red-400" />
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <p className="text-sm text-muted-foreground">Weakest phase</p>
                              <span className="text-sm font-medium text-red-400">
                                {snapshot.unstable_phase}
                              </span>
                            </div>
                            <p className="text-sm">
                              {getPhaseCoaching(snapshot.unstable_phase)}
                            </p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Coach's Directive */}
                  <Card className="border-primary/30 bg-primary/5" data-testid="snapshot-directive">
                    <CardContent className="p-5">
                      <div className="flex items-start gap-3">
                        <Brain className="w-5 h-5 text-primary mt-0.5" />
                        <div>
                          <p className="text-xs text-primary font-medium uppercase tracking-wide mb-2">
                            Coach's Focus
                          </p>
                          <p className="text-sm font-medium leading-relaxed">
                            {snapshot.directive}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>
          </TabsContent>

          {/* ============================================ */}
          {/* TAB B: JOURNEY - Your Story */}
          {/* ============================================ */}
          <TabsContent value="journey" className="space-y-4 mt-6">
            {!journey?.ready ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <Loader2 className="w-6 h-6 animate-spin mx-auto mb-4 text-muted-foreground" />
                  <p className="text-muted-foreground">{journey?.message || "Building your story..."}</p>
                </CardContent>
              </Card>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-4"
              >
                {/* Voice Headline - The Story */}
                {journey.voice && (
                  <Card className={`border-l-4 ${
                    journey.voice.tone_level === "positive" ? "border-l-emerald-500" :
                    journey.voice.tone_level === "concern" ? "border-l-amber-500" :
                    "border-l-slate-500"
                  }`} data-testid="journey-voice">
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className={`text-lg font-semibold mb-2 ${
                            journey.voice.tone_level === "positive" ? "text-emerald-400" :
                            journey.voice.tone_level === "concern" ? "text-amber-400" :
                            "text-foreground"
                          }`}>
                            {journey.voice.headline}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {journey.voice.explanation}
                          </p>
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

                {/* Before vs After Stats */}
                {journey.stat_rows && journey.overall_change !== "stable_hidden" && (
                  <Card data-testid="journey-stats">
                    <CardContent className="p-5">
                      <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-4">
                        Your Progress
                      </p>
                      <div className="space-y-3">
                        {journey.stat_rows.map((row, idx) => (
                          <div 
                            key={idx}
                            className="flex items-center justify-between py-2 border-b border-border/50 last:border-0"
                          >
                            <span className="text-sm text-muted-foreground">{row.label}</span>
                            <div className="flex items-center gap-3">
                              <span className="text-sm text-muted-foreground">{row.then}</span>
                              <ArrowRight className="w-3 h-3 text-muted-foreground" />
                              <span className="text-sm font-medium">{row.now}</span>
                              {row.show_delta && (
                                <span className={`text-xs px-2 py-0.5 rounded ${
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

                {/* Cognitive Growth */}
                {journey.cognitive_rows && (
                  <Card data-testid="journey-cognitive">
                    <CardContent className="p-5">
                      <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-4">
                        How You Think
                      </p>
                      <div className="space-y-3">
                        {journey.cognitive_rows.map((row, idx) => (
                          <div 
                            key={idx}
                            className="flex items-center justify-between py-2 border-b border-border/50 last:border-0"
                          >
                            <span className="text-sm text-muted-foreground">{row.label}</span>
                            <div className="flex items-center gap-3">
                              <span className="text-sm text-muted-foreground">{row.then}</span>
                              <ArrowRight className="w-3 h-3 text-muted-foreground" />
                              <span className={`text-sm ${row.changed ? "font-medium text-emerald-400" : ""}`}>
                                {row.now}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Journey Directive */}
                <Card className="border-primary/30 bg-primary/5" data-testid="journey-directive">
                  <CardContent className="p-5">
                    <div className="flex items-start gap-3">
                      <Target className="w-5 h-5 text-primary mt-0.5" />
                      <div>
                        <p className="text-xs text-primary font-medium uppercase tracking-wide mb-2">
                          Next Milestone
                        </p>
                        <p className="text-sm font-medium leading-relaxed">
                          {journey.directive}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </TabsContent>

          {/* ============================================ */}
          {/* TAB C: TREND - Recent Momentum */}
          {/* ============================================ */}
          <TabsContent value="trend" className="space-y-4 mt-6">
            {!momentum?.ready ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <Loader2 className="w-6 h-6 animate-spin mx-auto mb-4 text-muted-foreground" />
                  <p className="text-muted-foreground">{momentum?.message || "Analyzing recent games..."}</p>
                </CardContent>
              </Card>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-4"
              >
                {/* Momentum Headline */}
                <Card className={`border-l-4 ${
                  momentum.voice?.tone_level === "positive" ? "border-l-emerald-500" :
                  momentum.voice?.tone_level === "concern" ? "border-l-amber-500" :
                  "border-l-slate-500"
                }`} data-testid="momentum-headline">
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        {momentum.voice?.tone_level === "positive" ? (
                          <Flame className="w-5 h-5 text-orange-500 mt-0.5" />
                        ) : momentum.voice?.tone_level === "concern" ? (
                          <TrendingDown className="w-5 h-5 text-amber-500 mt-0.5" />
                        ) : (
                          <Minus className="w-5 h-5 text-slate-400 mt-0.5" />
                        )}
                        <p className={`text-lg font-semibold ${
                          momentum.voice?.tone_level === "positive" ? "text-emerald-400" :
                          momentum.voice?.tone_level === "concern" ? "text-amber-400" :
                          "text-foreground"
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

                {/* Shifts - What's changing */}
                {momentum.shifts && momentum.shifts.length > 0 && (
                  <Card data-testid="momentum-shifts">
                    <CardContent className="p-5">
                      <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-4">
                        What's Changing
                      </p>
                      <div className="space-y-3">
                        {momentum.shifts.map((shift, idx) => (
                          <div key={idx} className="flex items-start gap-3 py-2 border-b border-border/50 last:border-0">
                            {shift.direction === "improving" ? (
                              <TrendingUp className="w-4 h-4 text-emerald-500 mt-0.5" />
                            ) : shift.direction === "declining" ? (
                              <TrendingDown className="w-4 h-4 text-red-400 mt-0.5" />
                            ) : (
                              <Minus className="w-4 h-4 text-slate-400 mt-0.5" />
                            )}
                            <div className="flex-1">
                              <p className="text-sm font-medium">{shift.area}</p>
                              <p className="text-xs text-muted-foreground">{shift.detail}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Evidence - Link to specific games */}
                {momentum.evidence && momentum.evidence.length > 0 && (
                  <Card data-testid="momentum-evidence">
                    <CardContent className="p-5">
                      <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-4">
                        See It In Your Games
                      </p>
                      <div className="space-y-2">
                        {momentum.evidence.slice(0, 3).map((ev, idx) => (
                          <button
                            key={idx}
                            onClick={() => handleEvidenceClick(ev.game_id, ev.move_number)}
                            className="w-full flex items-center justify-between p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors text-left"
                            data-testid={`evidence-${idx}`}
                          >
                            <div className="flex items-center gap-3">
                              <Eye className="w-4 h-4 text-muted-foreground" />
                              <div>
                                <p className="text-sm font-medium">{ev.label}</p>
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
                <Card className="border-primary/30 bg-primary/5" data-testid="momentum-directive">
                  <CardContent className="p-5">
                    <div className="flex items-start gap-3">
                      <Zap className="w-5 h-5 text-primary mt-0.5" />
                      <div>
                        <p className="text-xs text-primary font-medium uppercase tracking-wide mb-2">
                          Keep This Going
                        </p>
                        <p className="text-sm font-medium leading-relaxed">
                          {momentum.directive}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </TabsContent>
        </Tabs>

        {/* Sync footer */}
        <div className="flex justify-center pt-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={syncNow}
            disabled={syncing}
            className="text-muted-foreground"
          >
            {syncing ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            Sync latest games
          </Button>
        </div>
      </div>
    </Layout>
  );
};

export default Journey;
