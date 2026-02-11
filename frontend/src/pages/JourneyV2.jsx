import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { 
  Loader2, 
  Flame,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  Target,
  Zap,
  Trophy,
  ChevronRight,
  BarChart3,
  Crosshair,
  Shield,
  Brain,
  Eye,
  Dumbbell
} from "lucide-react";
import EvidenceModal from "@/components/EvidenceModal";
import DrillMode from "@/components/DrillMode";

/**
 * JOURNEY PAGE - "How you're evolving"
 * 
 * This is the TREND page for long-term intelligence and reflection.
 * 
 * Structure:
 * - Weakness ranking (not equal badges) with EVIDENCE DRILL-DOWN
 * - Win-state analysis with EVIDENCE DRILL-DOWN
 * - Mistake heatmap
 * - Identity profile
 * - Milestones
 */

// Heatmap component for board visualization
const MistakeHeatmap = ({ data }) => {
  if (!data || !data.hot_squares || data.hot_squares.length === 0) {
    return null;
  }

  const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
  const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];
  
  // Create intensity map
  const maxCount = Math.max(...data.hot_squares.map(s => s.count), 1);
  const squareIntensity = {};
  data.hot_squares.forEach(({ square, count }) => {
    squareIntensity[square] = count / maxCount;
  });

  return (
    <Card className="border-orange-500/20">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Crosshair className="w-5 h-5 text-orange-500" />
          Mistake Heatmap
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-8 gap-0.5 aspect-square max-w-[280px] mx-auto mb-4">
          {ranks.map(rank => 
            files.map(file => {
              const sq = file + rank;
              const intensity = squareIntensity[sq] || 0;
              const isLight = (files.indexOf(file) + ranks.indexOf(rank)) % 2 === 0;
              
              return (
                <div
                  key={sq}
                  className={`aspect-square flex items-center justify-center text-[8px] font-mono
                    ${isLight ? 'bg-amber-100 dark:bg-amber-900/30' : 'bg-amber-800/30 dark:bg-amber-950/50'}
                    ${intensity > 0 ? 'relative' : ''}
                  `}
                  style={{
                    backgroundColor: intensity > 0 
                      ? `rgba(239, 68, 68, ${intensity * 0.7})` 
                      : undefined
                  }}
                >
                  {intensity > 0.5 && (
                    <span className="text-white font-bold text-[10px]">
                      {data.hot_squares.find(s => s.square === sq)?.count}
                    </span>
                  )}
                </div>
              );
            })
          )}
        </div>
        
        <p className="text-sm text-muted-foreground text-center">
          {data.insight}
        </p>
        
        {/* Region breakdown */}
        <div className="flex justify-center gap-4 mt-4 text-xs">
          <div className="text-center">
            <span className="block font-bold">{data.regions?.queenside || 0}</span>
            <span className="text-muted-foreground">Queenside</span>
          </div>
          <div className="text-center">
            <span className="block font-bold">{data.regions?.center || 0}</span>
            <span className="text-muted-foreground">Center</span>
          </div>
          <div className="text-center">
            <span className="block font-bold">{data.regions?.kingside || 0}</span>
            <span className="text-muted-foreground">Kingside</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Win state analysis component - NOW WITH EVIDENCE DRILL-DOWN
const WinStateAnalysis = ({ data, onShowEvidence }) => {
  if (!data || data.total_blunders === 0) {
    return null;
  }

  const getStateEvidence = (state) => {
    if (state === 'winning') return data.when_winning?.evidence || [];
    if (state === 'equal') return data.when_equal?.evidence || [];
    if (state === 'losing') return data.when_losing?.evidence || [];
    return [];
  };

  const StateRow = ({ state, label, icon: Icon, iconColor, percentage, isDanger }) => {
    const evidence = getStateEvidence(state);
    const hasEvidence = evidence.length > 0;
    
    return (
      <div 
        className={`${hasEvidence ? 'cursor-pointer hover:bg-muted/30 rounded-lg p-2 -mx-2 transition-colors' : ''}`}
        onClick={() => hasEvidence && onShowEvidence(state, evidence)}
        data-testid={`win-state-${state}`}
      >
        <div className="flex justify-between text-sm mb-1">
          <span className="flex items-center gap-1">
            <Icon className={`w-3 h-3 ${iconColor}`} />
            {label}
            {hasEvidence && (
              <span className="text-xs text-muted-foreground ml-1">
                ({evidence.length} examples)
              </span>
            )}
          </span>
          <span className={isDanger ? 'text-red-500 font-bold' : ''}>
            {percentage}%
          </span>
        </div>
        <Progress 
          value={percentage} 
          className={`h-2 ${isDanger ? '[&>div]:bg-red-500' : `[&>div]:${iconColor.replace('text-', 'bg-')}`}`}
        />
      </div>
    );
  };

  return (
    <Card className="border-blue-500/20">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-500" />
          When You Blunder
          <span className="text-xs text-muted-foreground font-normal ml-auto">Click to see examples</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Visual bars - now clickable */}
        <div className="space-y-3">
          <StateRow 
            state="winning"
            label="When Winning"
            icon={TrendingUp}
            iconColor="text-green-500"
            percentage={data.when_winning.percentage}
            isDanger={data.danger_zone === 'winning'}
          />
          
          <StateRow 
            state="equal"
            label="When Equal"
            icon={Target}
            iconColor="text-yellow-500"
            percentage={data.when_equal.percentage}
            isDanger={data.danger_zone === 'equal'}
          />
          
          <StateRow 
            state="losing"
            label="When Losing"
            icon={TrendingDown}
            iconColor="text-orange-500"
            percentage={data.when_losing.percentage}
            isDanger={data.danger_zone === 'losing'}
          />
        </div>
        
        {/* Insight */}
        <div className="p-3 rounded-lg bg-muted/50 text-sm">
          {data.insight}
        </div>
      </CardContent>
    </Card>
  );
};

// Weakness ranking component
const WeaknessRanking = ({ data }) => {
  if (!data || !data.ranking || data.ranking.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      {/* #1 Rating Killer */}
      {data.rating_killer && (
        <motion.div
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <Card className="border-2 border-red-500/30 bg-gradient-to-r from-red-500/10 to-transparent">
            <CardContent className="py-5">
              <div className="flex items-start gap-4">
                <div className="p-3 rounded-full bg-red-500/20">
                  <Flame className="w-6 h-6 text-red-500" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold uppercase tracking-wider text-red-500">
                      #1 Rating Killer
                    </span>
                    <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full">
                      {data.rating_killer.frequency_pct}% of games
                    </span>
                  </div>
                  <h3 className="text-lg font-bold mb-1">{data.rating_killer.label}</h3>
                  <p className="text-sm text-muted-foreground mb-2">
                    {data.rating_killer.message}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span>~{data.rating_killer.total_cp_loss} cp lost</span>
                    <span>{data.rating_killer.occurrences} occurrences</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Secondary Weakness */}
      {data.secondary_weakness && (
        <motion.div
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="border-amber-500/20">
            <CardContent className="py-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-full bg-amber-500/10">
                  <AlertTriangle className="w-5 h-5 text-amber-500" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold uppercase tracking-wider text-amber-500">
                      Secondary Weakness
                    </span>
                  </div>
                  <h3 className="font-semibold">{data.secondary_weakness.label}</h3>
                  <p className="text-xs text-muted-foreground">
                    {data.secondary_weakness.occurrences} occurrences • ~{data.secondary_weakness.total_cp_loss} cp
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Stable Strength */}
      {data.stable_strength && (
        <motion.div
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="border-green-500/20">
            <CardContent className="py-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-full bg-green-500/10">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold uppercase tracking-wider text-green-500">
                      Stable Strength
                    </span>
                  </div>
                  <h3 className="font-semibold">{data.stable_strength.label}</h3>
                  <p className="text-xs text-muted-foreground">
                    {data.stable_strength.message}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
};

// Milestones component
const Milestones = ({ milestones }) => {
  if (!milestones || milestones.length === 0) {
    return null;
  }

  const iconMap = {
    trophy: Trophy,
    fire: Flame,
    star: Zap,
    chart: BarChart3
  };

  return (
    <Card className="border-purple-500/20">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Trophy className="w-5 h-5 text-purple-500" />
          Recent Achievements
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {milestones.map((milestone, idx) => {
            const Icon = iconMap[milestone.icon] || Trophy;
            return (
              <motion.div
                key={milestone.id}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: idx * 0.1 }}
                className="flex items-center gap-3 p-3 rounded-lg bg-purple-500/10"
              >
                <Icon className="w-5 h-5 text-purple-400" />
                <div>
                  <h4 className="font-semibold text-purple-300">{milestone.name}</h4>
                  <p className="text-xs text-muted-foreground">{milestone.description}</p>
                </div>
              </motion.div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};

const JourneyPage = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [journeyData, setJourneyData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${API}/journey/v2`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setJourneyData(data);
        }
      } catch (err) {
        console.error("Failed to load journey data:", err);
        toast.error("Failed to load journey data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }

  const gamesAnalyzed = journeyData?.games_analyzed || 0;

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto px-4 py-8">
        
        {/* Header */}
        <motion.div 
          initial={{ opacity: 0, y: -10 }} 
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-3xl font-bold mb-2">Your Chess Journey</h1>
          <p className="text-muted-foreground">
            Based on your last {gamesAnalyzed} analyzed games
          </p>
        </motion.div>

        {gamesAnalyzed < 5 ? (
          /* Not enough data */
          <Card className="border-2 border-dashed border-muted-foreground/20">
            <CardContent className="py-12 text-center">
              <Brain className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
              <h3 className="text-lg font-medium mb-2">Building Your Story</h3>
              <p className="text-muted-foreground mb-6">
                Analyze at least 5 games to see your chess journey
              </p>
              <Button onClick={() => navigate("/import")}>
                Import Games
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            
            {/* LEFT COLUMN - Weakness Hierarchy */}
            <div className="space-y-6">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <Target className="w-5 h-5" />
                Your Weaknesses (Prioritized)
              </h2>
              
              <WeaknessRanking data={journeyData?.weakness_ranking} />

              {/* Identity */}
              {journeyData?.identity && journeyData.identity.profile !== "unknown" && (
                <Card className="border-indigo-500/20">
                  <CardContent className="py-5">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-full bg-indigo-500/10">
                        <Zap className="w-5 h-5 text-indigo-500" />
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground">Chess Identity</span>
                        <h3 className="font-bold text-indigo-400">{journeyData.identity.label}</h3>
                        <p className="text-sm text-muted-foreground">{journeyData.identity.description}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>

            {/* RIGHT COLUMN - Analytics */}
            <div className="space-y-6">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Pattern Analysis
              </h2>
              
              <WinStateAnalysis data={journeyData?.win_state} />
              
              <MistakeHeatmap data={journeyData?.heatmap} />
              
              <Milestones milestones={journeyData?.milestones} />
            </div>
          </div>
        )}

        {/* Navigation */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="flex justify-center gap-4 mt-8"
        >
          <Button 
            variant="outline" 
            onClick={() => navigate("/coach")}
          >
            ← Today's Focus
          </Button>
          <Button 
            onClick={() => navigate("/dashboard")}
            className="group"
          >
            Analyze Games
            <ChevronRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
          </Button>
        </motion.div>
      </div>
    </Layout>
  );
};

export default JourneyPage;
