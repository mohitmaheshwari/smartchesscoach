/**
 * JOURNEY PAGE - Before/After Report
 * 
 * A) MICRO: Now vs Then (Recent 5 vs Previous 5)
 * B) MACRO: Becoming vs Started (Recent 15 vs First 15)  
 * C) EVIDENCE: 2 clickable game links
 * 
 * No tabs. No "no change" spam. Impact-driven headline.
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Card, CardContent } from "@/components/ui/card";
import Layout from "@/components/Layout";
import { Loader2, ChevronDown, ChevronUp, ArrowRight, ExternalLink } from "lucide-react";

const Journey = ({ user }) => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [showMetrics, setShowMetrics] = useState(false);

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
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
              Cognitive Evolution
            </p>
            <h1 className="text-2xl font-semibold text-white">Journey</h1>
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

  const { micro, macro, evidence } = data;

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6" data-testid="journey-page">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
              Cognitive Evolution
            </p>
            <h1 className="text-2xl font-semibold text-white">Journey</h1>
          </div>
          
          <button
            onClick={() => setShowMetrics(!showMetrics)}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
            data-testid="metrics-toggle"
          >
            {showMetrics ? "Hide Metrics" : "View Metrics"}
            {showMetrics ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>

        {/* ============================================ */}
        {/* A) MICRO: Now vs Then (5 vs 5) */}
        {/* ============================================ */}
        
        <div className="space-y-4">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Now vs Then
          </p>

          {/* Headline */}
          <Card className="border-slate-700 bg-slate-900/50">
            <CardContent className="p-6">
              <p className="text-base text-white leading-relaxed">
                {micro.headline}
              </p>
            </CardContent>
          </Card>

          {/* 3 Comparative Rows */}
          <Card className="border-slate-700 bg-slate-900/50">
            <CardContent className="p-6 space-y-4">
              {/* Row 1: Decision Stability */}
              <div className="flex items-center justify-between py-2 border-b border-slate-700/50">
                <span className="text-sm text-muted-foreground">{micro.rows[0].label}</span>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-slate-400">{micro.rows[0].previous}</span>
                  <ArrowRight className="w-3 h-3 text-slate-600" />
                  <span className={micro.rows[0].changed ? "text-white font-medium" : "text-slate-300"}>
                    {micro.rows[0].recent}
                  </span>
                </div>
              </div>

              {/* Row 2: Advantage Discipline */}
              <div className="flex items-center justify-between py-2 border-b border-slate-700/50">
                <span className="text-sm text-muted-foreground">{micro.rows[1].label}</span>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-slate-400">{micro.rows[1].previous}</span>
                  <ArrowRight className="w-3 h-3 text-slate-600" />
                  <span className={micro.rows[1].changed ? "text-white font-medium" : "text-slate-300"}>
                    {micro.rows[1].recent}
                  </span>
                </div>
              </div>

              {/* Row 3: Primary Driver */}
              <div className="flex items-center justify-between py-2">
                <span className="text-sm text-muted-foreground">{micro.rows[2].label}</span>
                <div className="text-sm text-right">
                  <span className="text-white">{micro.rows[2].value}</span>
                  <span className="text-slate-500 ml-1 text-xs">{micro.rows[2].note}</span>
                </div>
              </div>

              {/* Optional metrics */}
              {showMetrics && (
                <div className="pt-3 border-t border-slate-700/50 text-xs text-slate-500">
                  TSI: {micro.metrics.tsi_previous} → {micro.metrics.tsi_recent} (Δ{micro.metrics.tsi_delta >= 0 ? "+" : ""}{micro.metrics.tsi_delta}) | 
                  Blunders when ahead: {micro.metrics.context_previous}% → {micro.metrics.context_recent}%
                </div>
              )}
            </CardContent>
          </Card>

          {/* What Changed (only if meaningful) */}
          {micro.what_changed && micro.what_changed.length > 0 && (
            <Card className="border-slate-700 bg-slate-900/50">
              <CardContent className="p-6">
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
                  What Changed
                </p>
                <ul className="space-y-1">
                  {micro.what_changed.map((change, idx) => (
                    <li key={idx} className="text-sm text-slate-300">• {change}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>

        {/* ============================================ */}
        {/* B) MACRO: Becoming vs Started (15 vs 15) */}
        {/* ============================================ */}
        
        {macro && (
          <div className="space-y-4 pt-6 border-t border-slate-700">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Becoming vs Started
            </p>

            <Card className="border-slate-700 bg-slate-900/50">
              <CardContent className="p-6 space-y-4">
                {/* Row 1: Long-term Stability */}
                <div className="flex items-center justify-between py-2 border-b border-slate-700/50">
                  <span className="text-sm text-muted-foreground">{macro.rows[0].label}</span>
                  <div className="text-sm text-right">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400">{macro.rows[0].first}</span>
                      <ArrowRight className="w-3 h-3 text-slate-600" />
                      <span className="text-white">{macro.rows[0].recent}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1">{macro.rows[0].clause}</p>
                  </div>
                </div>

                {/* Row 2: Weakness Evolution */}
                <div className="flex items-center justify-between py-2 border-b border-slate-700/50">
                  <span className="text-sm text-muted-foreground">{macro.rows[1].label}</span>
                  <div className="text-sm text-right">
                    {macro.rows[1].driver ? (
                      <>
                        <span className="text-white">{macro.rows[1].driver}</span>
                        {macro.rows[1].changed && (
                          <span className="text-slate-400 ml-2">
                            {macro.rows[1].first_band} → {macro.rows[1].recent_band}
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="text-slate-400">{macro.rows[1].text}</span>
                    )}
                  </div>
                </div>

                {/* Row 3: Phase Evolution */}
                <div className="flex items-center justify-between py-2 border-b border-slate-700/50">
                  <span className="text-sm text-muted-foreground">{macro.rows[2].label}</span>
                  <div className="flex items-center gap-2 text-sm">
                    {macro.rows[2].changed ? (
                      <>
                        <span className="text-slate-400">{macro.rows[2].first}</span>
                        <ArrowRight className="w-3 h-3 text-slate-600" />
                        <span className="text-white">{macro.rows[2].recent}</span>
                      </>
                    ) : (
                      <span className="text-slate-300">{macro.rows[2].recent} (unchanged)</span>
                    )}
                  </div>
                </div>

                {/* Row 4: Peer Context */}
                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-muted-foreground">{macro.rows[3].label}</span>
                  <span className={`text-sm ${
                    macro.rows[3].status === "above" ? "text-green-400" :
                    macro.rows[3].status === "below" ? "text-amber-400" :
                    "text-slate-300"
                  }`}>
                    {macro.rows[3].text}
                  </span>
                </div>

                {/* Optional metrics */}
                {showMetrics && (
                  <div className="pt-3 border-t border-slate-700/50 text-xs text-slate-500">
                    TSI: {macro.metrics.tsi_first} (start) → {macro.metrics.tsi_recent} (now) | 
                    Cohort: {macro.metrics.cohort_label}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* ============================================ */}
        {/* C) EVIDENCE */}
        {/* ============================================ */}
        
        {evidence && evidence.length > 0 && (
          <div className="space-y-4 pt-6 border-t border-slate-700">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Evidence
            </p>

            <Card className="border-slate-700 bg-slate-900/50">
              <CardContent className="p-6 space-y-3">
                {evidence.map((item, idx) => (
                  <div 
                    key={idx}
                    className="flex items-center justify-between p-3 rounded-lg bg-slate-800/30 hover:bg-slate-800/50 transition-colors cursor-pointer"
                    data-testid={`evidence-${idx}`}
                  >
                    <div>
                      <p className="text-sm text-white">{item.label}</p>
                      <p className="text-xs text-slate-500">{item.description}</p>
                    </div>
                    <ExternalLink className="w-4 h-4 text-slate-500" />
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Journey;
