/**
 * JOURNEY PAGE - Master Spec Implementation
 * 
 * Tab A (Now): Snapshot - 5 items + directive
 * Tab B (Journey): 4 stat rows + 4 cognitive rows + directive
 * Tab C (Trend): Headline + shifts + evidence + directive
 * 
 * Rules:
 * - No raw numbers on surface (bands only)
 * - Hide deltas when stable_hidden
 * - One instruction per tab
 * - Plain Indian-English tone
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Layout from "@/components/Layout";
import { 
  Loader2, ChevronDown, ChevronUp, ArrowRight, 
  ExternalLink, TrendingUp, TrendingDown, Minus,
  Target, Zap, Award
} from "lucide-react";

const Journey = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("now");
  const [showStats, setShowStats] = useState(false);

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

  const handleEvidenceClick = (gameId, moveNumber) => {
    // Route format: /lab/game/{id}?move={n}&src=journey
    navigate(`/game/${gameId}?move=${moveNumber}&src=journey`);
  };

  const getTrendIcon = (direction) => {
    if (direction === "improving") {
      return <TrendingUp className="w-4 h-4 text-green-400" />;
    }
    if (direction === "declining") {
      return <TrendingDown className="w-4 h-4 text-amber-400" />;
    }
    return <Minus className="w-4 h-4 text-slate-400" />;
  };

  const getToneColor = (tone) => {
    if (tone === "positive") return "text-green-400";
    if (tone === "concern") return "text-amber-400";
    return "text-slate-300";
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout user={user}>
        <div className="max-w-4xl mx-auto px-4 py-8">
          <p className="text-red-400">{error}</p>
        </div>
      </Layout>
    );
  }

  // Not activated (Section 2: Lock until 10 games)
  if (!data.activated) {
    return (
      <Layout user={user}>
        <div className="max-w-4xl mx-auto px-4 py-8 space-y-8" data-testid="journey-page">
          <div>
            <h1 className="text-2xl font-semibold text-white">Journey</h1>
          </div>

          <Card className="border-slate-700 bg-slate-900/50">
            <CardContent className="p-8 text-center">
              <p className="text-lg text-white mb-2">
                Journey unlocks after 10 analyzed games.
              </p>
              <p className="text-sm text-slate-400">
                You have {data.games_analyzed}/{data.games_required}.
              </p>
            </CardContent>
          </Card>
        </div>
      </Layout>
    );
  }

  const { snapshot, journey, momentum, stats } = data;

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6" data-testid="journey-page">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white">Journey</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {data.games_analyzed} games analyzed
            </p>
          </div>
          
          <button
            onClick={() => setShowStats(!showStats)}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
            data-testid="stats-toggle"
          >
            {showStats ? "Hide Stats" : "View Match Stats"}
            {showStats ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>

        {/* Stats Drawer (Section 10) */}
        {showStats && stats?.ready && (
          <Card className="border-slate-700 bg-slate-800/30" data-testid="stats-drawer">
            <CardContent className="p-4">
              <div className="grid grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-2xl font-semibold text-white">{stats.now?.accuracy}%</p>
                  <p className="text-xs text-slate-400">Accuracy</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold text-white">{stats.now?.blunders_per_game}</p>
                  <p className="text-xs text-slate-400">Blunders/Game</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold text-white">{stats.now?.mistakes_per_game}</p>
                  <p className="text-xs text-slate-400">Mistakes/Game</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold text-white">{stats.now?.winrate}%</p>
                  <p className="text-xs text-slate-400">Win Rate</p>
                </div>
              </div>
              <p className="text-xs text-slate-500 text-center mt-3">
                Based on last {stats.games_count} games
              </p>
            </CardContent>
          </Card>
        )}

        {/* 3-Tab Navigation */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-3 bg-slate-800/50">
            <TabsTrigger 
              value="now" 
              className="data-[state=active]:bg-slate-700"
              data-testid="tab-now"
            >
              <Target className="w-4 h-4 mr-2" />
              Now
            </TabsTrigger>
            <TabsTrigger 
              value="journey" 
              className="data-[state=active]:bg-slate-700"
              data-testid="tab-journey"
            >
              <TrendingUp className="w-4 h-4 mr-2" />
              Journey
            </TabsTrigger>
            <TabsTrigger 
              value="trend" 
              className="data-[state=active]:bg-slate-700"
              data-testid="tab-trend"
            >
              <Zap className="w-4 h-4 mr-2" />
              Trend
            </TabsTrigger>
          </TabsList>

          {/* ============================================ */}
          {/* TAB A: SNAPSHOT (NOW) - Section 8 */}
          {/* ============================================ */}
          <TabsContent value="now" className="space-y-4 mt-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Snapshot (Current)
            </p>

            {!snapshot?.ready ? (
              <Card className="border-slate-700 bg-slate-900/50">
                <CardContent className="p-6 text-center">
                  <p className="text-sm text-slate-400">{snapshot?.message || "Loading..."}</p>
                </CardContent>
              </Card>
            ) : (
              <>
                {/* Item 1: Decision Stability */}
                <Card className="border-slate-700 bg-slate-900/50" data-testid="snapshot-stability">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Decision Stability</span>
                      <span className="text-base font-medium text-white">
                        {snapshot.decision_stability?.band}
                      </span>
                    </div>
                    <p className="text-sm text-slate-400 mt-2">
                      {snapshot.decision_stability?.meaning}
                    </p>
                  </CardContent>
                </Card>

                {/* Item 2: Top Issue (Primary Driver) */}
                <Card className="border-slate-700 bg-slate-900/50" data-testid="snapshot-driver">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Main issue</span>
                      <span className="text-base font-medium text-white">
                        {snapshot.top_issue?.name || "No clear pattern"}
                      </span>
                    </div>
                  </CardContent>
                </Card>

                {/* Item 3: Advantage Discipline */}
                <Card className="border-slate-700 bg-slate-900/50" data-testid="snapshot-advantage">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">When ahead</span>
                      <span className="text-base font-medium text-white">
                        {snapshot.advantage_discipline?.band}
                      </span>
                    </div>
                    <p className="text-sm text-slate-400 mt-2">
                      {snapshot.advantage_discipline?.meaning}
                    </p>
                  </CardContent>
                </Card>

                {/* Item 4: Weakest Phase */}
                <Card className="border-slate-700 bg-slate-900/50" data-testid="snapshot-phase">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Weakest phase</span>
                      <span className="text-base font-medium text-white">
                        {snapshot.unstable_phase}
                      </span>
                    </div>
                  </CardContent>
                </Card>

                {/* Item 5: Directive */}
                <Card className="border-amber-800/50 bg-amber-900/10" data-testid="snapshot-directive">
                  <CardContent className="p-5">
                    <p className="text-xs uppercase tracking-wider text-amber-400/80 mb-2">
                      Do this next
                    </p>
                    <p className="text-sm text-white leading-relaxed">
                      {snapshot.directive}
                    </p>
                  </CardContent>
                </Card>
              </>
            )}
          </TabsContent>

          {/* ============================================ */}
          {/* TAB B: JOURNEY (THEN VS NOW) - Section 8 */}
          {/* ============================================ */}
          <TabsContent value="journey" className="space-y-4 mt-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Overall Journey (Then vs Now)
            </p>

            {!journey?.ready ? (
              <Card className="border-slate-700 bg-slate-900/50">
                <CardContent className="p-6 text-center">
                  <p className="text-sm text-slate-400">{journey?.message || "Loading..."}</p>
                </CardContent>
              </Card>
            ) : (
              <>
                {/* Voice Headline + Badge */}
                {journey.voice && (
                  <Card className="border-slate-700 bg-slate-900/50" data-testid="journey-voice">
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className={`text-base font-medium ${getToneColor(journey.voice.tone_level)}`}>
                            {journey.voice.headline}
                          </p>
                          <p className="text-sm text-slate-400 mt-1">
                            {journey.voice.explanation}
                          </p>
                        </div>
                        {journey.badge && (
                          <span className="flex items-center gap-1 text-xs bg-green-900/30 text-green-400 px-2 py-1 rounded">
                            <Award className="w-3 h-3" />
                            {journey.badge}
                          </span>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Stat Comparison Rows (show deltas only if visible) */}
                {journey.stat_rows && journey.overall_change !== "stable_hidden" && (
                  <Card className="border-slate-700 bg-slate-900/50" data-testid="journey-stat-rows">
                    <CardContent className="p-5 space-y-3">
                      <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                        Before → Now
                      </p>
                      {journey.stat_rows.map((row, idx) => (
                        <div 
                          key={idx}
                          className={`flex items-center justify-between py-2 ${
                            idx < journey.stat_rows.length - 1 ? "border-b border-slate-700/50" : ""
                          }`}
                          data-testid={`stat-row-${idx}`}
                        >
                          <span className="text-sm text-slate-400">{row.label}</span>
                          <div className="flex items-center gap-3 text-sm">
                            <span className="text-slate-500">{row.then}</span>
                            <ArrowRight className="w-3 h-3 text-slate-600" />
                            <span className="text-white">{row.now}</span>
                            {row.show_delta && (
                              <span className={`text-xs px-1.5 py-0.5 rounded ${
                                (row.lower_is_better ? parseFloat(row.delta) < 0 : parseFloat(row.delta) > 0)
                                  ? "bg-green-900/30 text-green-400"
                                  : "bg-amber-900/30 text-amber-400"
                              }`}>
                                {row.delta}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {/* Stable Hidden Message */}
                {journey.overall_change === "stable_hidden" && (
                  <Card className="border-slate-700 bg-slate-900/50">
                    <CardContent className="p-5 text-center">
                      <p className="text-sm text-slate-400">Overall stable. No significant changes.</p>
                    </CardContent>
                  </Card>
                )}

                {/* Cognitive Growth Rows */}
                {journey.cognitive_rows && (
                  <Card className="border-slate-700 bg-slate-900/50" data-testid="journey-cognitive-rows">
                    <CardContent className="p-5 space-y-3">
                      <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                        Cognitive Growth
                      </p>
                      {journey.cognitive_rows.map((row, idx) => (
                        <div 
                          key={idx}
                          className={`flex items-center justify-between py-2 ${
                            idx < journey.cognitive_rows.length - 1 ? "border-b border-slate-700/50" : ""
                          }`}
                          data-testid={`cognitive-row-${idx}`}
                        >
                          <span className="text-sm text-slate-400">{row.label}</span>
                          <div className="flex items-center gap-2 text-sm">
                            <span className="text-slate-500">{row.then}</span>
                            <ArrowRight className="w-3 h-3 text-slate-600" />
                            <span className={row.changed ? "text-white font-medium" : "text-slate-300"}>
                              {row.now}
                            </span>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {/* Directive */}
                <Card className="border-blue-800/50 bg-blue-900/10" data-testid="journey-directive">
                  <CardContent className="p-5">
                    <p className="text-xs uppercase tracking-wider text-blue-400/80 mb-2">
                      Do this next
                    </p>
                    <p className="text-sm text-white leading-relaxed">
                      {journey.directive}
                    </p>
                  </CardContent>
                </Card>
              </>
            )}
          </TabsContent>

          {/* ============================================ */}
          {/* TAB C: TREND (5 VS 5) - Section 8 */}
          {/* ============================================ */}
          <TabsContent value="trend" className="space-y-4 mt-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Recent Momentum (5 vs 5)
            </p>

            {!momentum?.ready ? (
              <Card className="border-slate-700 bg-slate-900/50">
                <CardContent className="p-6 text-center">
                  <p className="text-sm text-slate-400">{momentum?.message || "Loading..."}</p>
                </CardContent>
              </Card>
            ) : (
              <>
                {/* Headline + Badge */}
                <Card className="border-slate-700 bg-slate-900/50" data-testid="momentum-headline">
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between">
                      <p className={`text-base font-medium ${
                        momentum.voice ? getToneColor(momentum.voice.tone_level) : "text-white"
                      }`}>
                        {momentum.headline}
                      </p>
                      {momentum.badge && (
                        <span className="flex items-center gap-1 text-xs bg-green-900/30 text-green-400 px-2 py-1 rounded">
                          <Award className="w-3 h-3" />
                          {momentum.badge}
                        </span>
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* Meaningful Shifts (max 2) OR "No meaningful change" */}
                {momentum.has_meaningful_change && momentum.meaningful_shifts?.length > 0 ? (
                  <Card className="border-slate-700 bg-slate-900/50" data-testid="momentum-shifts">
                    <CardContent className="p-5 space-y-3">
                      <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                        What Changed
                      </p>
                      {momentum.meaningful_shifts.map((shift, idx) => (
                        <div 
                          key={idx}
                          className="flex items-center justify-between py-2"
                          data-testid={`shift-${idx}`}
                        >
                          <div className="flex items-center gap-2">
                            {getTrendIcon(shift.direction)}
                            <span className="text-sm text-slate-300">{shift.label}</span>
                          </div>
                          <div className="flex items-center gap-2 text-sm">
                            <span className="text-slate-500">{shift.previous}</span>
                            <ArrowRight className="w-3 h-3 text-slate-600" />
                            <span className="text-white">{shift.recent}</span>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ) : (
                  !momentum.has_meaningful_change && (
                    <Card className="border-slate-700 bg-slate-900/50">
                      <CardContent className="p-5 text-center">
                        <p className="text-sm text-slate-400">No meaningful change in last 10 games.</p>
                      </CardContent>
                    </Card>
                  )
                )}

                {/* Top 3 Issues (if meaningful) */}
                {momentum.top_issues && momentum.top_issues.length > 0 && (
                  <Card className="border-slate-700 bg-slate-900/50" data-testid="momentum-top-issues">
                    <CardContent className="p-5 space-y-3">
                      <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                        Top Issues Right Now
                      </p>
                      {momentum.top_issues.map((issue, idx) => (
                        <div 
                          key={idx}
                          className="flex items-center justify-between py-2"
                          data-testid={`top-issue-${idx}`}
                        >
                          <span className="text-sm text-slate-300">{idx + 1}. {issue.name}</span>
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            issue.impact === "High" ? "bg-red-900/30 text-red-400" :
                            issue.impact === "Moderate" ? "bg-amber-900/30 text-amber-400" :
                            "bg-slate-800 text-slate-400"
                          }`}>
                            {issue.impact}
                          </span>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {/* Evidence */}
                {momentum.evidence_ready && momentum.evidence?.length > 0 ? (
                  <Card className="border-slate-700 bg-slate-900/50" data-testid="momentum-evidence">
                    <CardContent className="p-5 space-y-3">
                      <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                        Evidence
                      </p>
                      {momentum.evidence.map((item, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleEvidenceClick(item.game_id, item.move_number)}
                          className="w-full flex items-center justify-between p-3 rounded-lg bg-slate-800/30 hover:bg-slate-800/50 transition-colors text-left"
                          data-testid={`evidence-${idx}`}
                        >
                          <div>
                            <p className="text-sm text-white">{item.label}</p>
                            <p className="text-xs text-slate-500">{item.description}</p>
                          </div>
                          <div className="flex items-center gap-2 text-slate-400">
                            <span className="text-xs">Open in Lab</span>
                            <ExternalLink className="w-4 h-4" />
                          </div>
                        </button>
                      ))}
                    </CardContent>
                  </Card>
                ) : (
                  <Card className="border-slate-700 bg-slate-900/50">
                    <CardContent className="p-5 text-center">
                      <p className="text-sm text-slate-400">
                        Evidence will appear after 10 more analyzed games.
                      </p>
                    </CardContent>
                  </Card>
                )}

                {/* Directive */}
                <Card className="border-green-800/50 bg-green-900/10" data-testid="momentum-directive">
                  <CardContent className="p-5">
                    <p className="text-xs uppercase tracking-wider text-green-400/80 mb-2">
                      Do this next
                    </p>
                    <p className="text-sm text-white leading-relaxed">
                      {momentum.directive}
                    </p>
                  </CardContent>
                </Card>
              </>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
};

export default Journey;
