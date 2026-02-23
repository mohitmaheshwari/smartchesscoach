/**
 * JOURNEY PAGE - 3-Tab Cognitive Progress Tracker
 * 
 * Tab A (Now): Snapshot - Current identity (5 items)
 * Tab B (Journey): Overall Journey - Then vs Now (4 rows)
 * Tab C (Trend): Recent Momentum - 5 vs 5 rolling tracker
 * 
 * + Collapsible Stats Drawer
 * 
 * Rules:
 * - No raw severity numbers (bands only)
 * - No empty section spam
 * - One directive per tab
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
  Target, Zap, Clock
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
    navigate(`/game/${gameId}?move=${moveNumber}&src=journey`);
  };

  const getTrendIcon = (direction) => {
    if (direction === "improving" || direction === "Improving") {
      return <TrendingUp className="w-4 h-4 text-green-400" />;
    }
    if (direction === "declining" || direction === "Declining") {
      return <TrendingDown className="w-4 h-4 text-amber-400" />;
    }
    return <Minus className="w-4 h-4 text-slate-400" />;
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

  // Not activated
  if (!data.activated) {
    return (
      <Layout user={user}>
        <div className="max-w-4xl mx-auto px-4 py-8 space-y-8" data-testid="journey-page">
          <div>
            <h1 className="text-2xl font-semibold text-white">Journey</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Track your chess improvement over time
            </p>
          </div>

          <Card className="border-slate-700 bg-slate-900/50">
            <CardContent className="p-8 text-center">
              <p className="text-sm text-slate-300 mb-2">
                Journey unlocks after 10 analyzed games.
              </p>
              <p className="text-lg text-white">
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

        {/* Stats Drawer (Collapsible) */}
        {showStats && stats?.ready && (
          <Card className="border-slate-700 bg-slate-800/30" data-testid="stats-drawer">
            <CardContent className="p-4">
              <div className="grid grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-2xl font-semibold text-white">{stats.accuracy}%</p>
                  <p className="text-xs text-slate-400">Accuracy</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold text-white">{stats.win_rate}%</p>
                  <p className="text-xs text-slate-400">Win Rate</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold text-white">{stats.blunders_per_game}</p>
                  <p className="text-xs text-slate-400">Blunders/Game</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold text-white">{stats.mistakes_per_game}</p>
                  <p className="text-xs text-slate-400">Mistakes/Game</p>
                </div>
              </div>
              <p className="text-xs text-slate-500 text-center mt-3">
                Based on last {stats.games_count} games • W{stats.record?.wins} L{stats.record?.losses} D{stats.record?.draws}
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
          {/* TAB A: SNAPSHOT (NOW) */}
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
                        {snapshot.decision_stability.band}
                      </span>
                    </div>
                    <p className="text-sm text-slate-400 mt-2">
                      {snapshot.decision_stability.meaning}
                    </p>
                  </CardContent>
                </Card>

                {/* Item 2: Top Issue (Primary Driver) */}
                <Card className="border-slate-700 bg-slate-900/50" data-testid="snapshot-driver">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Main reason you slip</span>
                      <span className="text-base font-medium text-white">
                        {snapshot.top_issue?.name || "No clear pattern"}
                      </span>
                    </div>
                    {snapshot.top_issue?.impact && (
                      <p className="text-xs text-slate-500 mt-1">
                        Impact: {snapshot.top_issue.impact}
                      </p>
                    )}
                  </CardContent>
                </Card>

                {/* Item 3: Advantage Discipline */}
                <Card className="border-slate-700 bg-slate-900/50" data-testid="snapshot-advantage">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">When ahead</span>
                      <span className="text-base font-medium text-white">
                        {snapshot.advantage_discipline.band}
                      </span>
                    </div>
                    <p className="text-sm text-slate-400 mt-2">
                      {snapshot.advantage_discipline.meaning}
                    </p>
                  </CardContent>
                </Card>

                {/* Item 4: Most Unstable Phase */}
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
          {/* TAB B: OVERALL JOURNEY (THEN VS NOW) */}
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
                <Card className="border-slate-700 bg-slate-900/50" data-testid="journey-rows">
                  <CardContent className="p-5 space-y-4">
                    {journey.rows.map((row, idx) => (
                      <div 
                        key={idx}
                        className={`flex items-center justify-between py-3 ${
                          idx < journey.rows.length - 1 ? "border-b border-slate-700/50" : ""
                        }`}
                        data-testid={`journey-row-${idx}`}
                      >
                        <span className="text-sm text-muted-foreground">{row.label}</span>
                        
                        {row.label === "Primary Driver" ? (
                          <div className="text-sm text-right">
                            <span className="text-white">{row.driver}</span>
                            {row.then_band && row.now_band && (
                              <div className="flex items-center gap-2 mt-1 justify-end">
                                <span className="text-slate-400 text-xs">{row.then_band}</span>
                                <ArrowRight className="w-3 h-3 text-slate-600" />
                                <span className={`text-xs ${row.changed ? "text-white font-medium" : "text-slate-300"}`}>
                                  {row.now_band}
                                </span>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 text-sm">
                            <span className="text-slate-400">{row.then}</span>
                            <ArrowRight className="w-3 h-3 text-slate-600" />
                            <span className={row.changed ? "text-white font-medium" : "text-slate-300"}>
                              {row.now}
                            </span>
                            {row.trend && (
                              <span className={`text-xs ml-2 ${
                                row.trend === "Improving" ? "text-green-400" : 
                                row.trend === "Declining" ? "text-amber-400" : 
                                "text-slate-500"
                              }`}>
                                ({row.trend})
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </CardContent>
                </Card>

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
          {/* TAB C: RECENT MOMENTUM (5 VS 5) */}
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
                {/* Headline */}
                <Card className="border-slate-700 bg-slate-900/50" data-testid="momentum-headline">
                  <CardContent className="p-5">
                    <p className="text-base text-white leading-relaxed">
                      {momentum.headline}
                    </p>
                  </CardContent>
                </Card>

                {/* Top 2 Shifts (if any) */}
                {momentum.shifts && momentum.shifts.length > 0 && (
                  <Card className="border-slate-700 bg-slate-900/50" data-testid="momentum-shifts">
                    <CardContent className="p-5 space-y-3">
                      <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                        What Changed
                      </p>
                      {momentum.shifts.map((shift, idx) => (
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
                            <span className="text-slate-400">{shift.previous}</span>
                            <ArrowRight className="w-3 h-3 text-slate-600" />
                            <span className="text-white">{shift.recent}</span>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {/* Evidence */}
                {momentum.evidence_ready && momentum.evidence.length > 0 ? (
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
