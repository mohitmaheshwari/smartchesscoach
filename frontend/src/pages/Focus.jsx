import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { 
  Loader2, 
  Target,
  AlertTriangle,
  Lightbulb,
  Flame,
  Trophy,
  ChevronRight,
  Zap,
  Brain,
  Eye,
  Dumbbell
} from "lucide-react";
import MistakeMastery from "@/components/MistakeMastery";
import EvidenceModal from "@/components/EvidenceModal";
import DrillMode from "@/components/DrillMode";

/**
 * FOCUS PAGE - "What should I focus on in my next game?"
 * 
 * This page answers ONE question only.
 * 
 * Structure:
 * - ONE dominant weakness (CLICKABLE - see evidence)
 * - ONE mission
 * - ONE behavioral rule
 * - ONE interactive puzzle
 * 
 * No badge grid. No phase breakdown. No heavy stats.
 * This page = ACTIONABLE.
 */

const FocusPage = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [focusData, setFocusData] = useState(null);
  const [coachData, setCoachData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch focus data from new endpoint
        const [focusRes, coachRes] = await Promise.all([
          fetch(`${API}/focus`, { credentials: "include" }),
          fetch(`${API}/coach`, { credentials: "include" })
        ]);
        
        if (focusRes.ok) {
          const data = await focusRes.json();
          setFocusData(data);
        }
        
        if (coachRes.ok) {
          const data = await coachRes.json();
          setCoachData(data);
        }
      } catch (err) {
        console.error("Failed to load focus data:", err);
        toast.error("Failed to load focus data");
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

  const gamesAnalyzed = focusData?.games_analyzed || 0;
  const needsMoreGames = gamesAnalyzed < 5;

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        
        {/* Header */}
        <motion.div 
          initial={{ opacity: 0, y: -10 }} 
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <h1 className="text-3xl font-bold mb-2">Today's Focus</h1>
          <p className="text-muted-foreground">
            One thing to remember in your next game
          </p>
        </motion.div>

        {needsMoreGames ? (
          /* Not enough data state */
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="border-2 border-dashed border-muted-foreground/20">
              <CardContent className="py-12 text-center">
                <Brain className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                <h3 className="text-lg font-medium mb-2">Building Your Profile</h3>
                <p className="text-muted-foreground mb-6">
                  Analyze {5 - gamesAnalyzed} more games to unlock personalized coaching
                </p>
                <Progress value={(gamesAnalyzed / 5) * 100} className="w-48 mx-auto mb-4" />
                <p className="text-sm text-muted-foreground">
                  {gamesAnalyzed}/5 games analyzed
                </p>
                <Button 
                  className="mt-6" 
                  onClick={() => navigate("/import")}
                >
                  Import Games
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        ) : (
          <>
            {/* MAIN FOCUS - The ONE thing */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <Card className="border-2 border-red-500/30 bg-gradient-to-br from-red-500/5 to-orange-500/5">
                <CardContent className="py-8">
                  <div className="flex items-start gap-4">
                    <div className="p-3 rounded-full bg-red-500/10">
                      <Flame className="w-8 h-8 text-red-500" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-red-500">
                          #1 Rating Killer
                        </span>
                      </div>
                      <h2 className="text-xl font-bold mb-3">
                        {focusData?.focus?.main_message || "Loading..."}
                      </h2>
                      {focusData?.focus?.impact && (
                        <p className="text-sm text-muted-foreground mb-4">
                          Cost you {focusData.focus.impact} in recent games
                        </p>
                      )}
                      
                      {/* The FIX */}
                      <div className="p-4 rounded-lg bg-background/50 border border-border/50">
                        <div className="flex items-center gap-2 mb-2">
                          <Lightbulb className="w-4 h-4 text-yellow-500" />
                          <span className="text-sm font-semibold">Before your next move:</span>
                        </div>
                        <p className="text-base">
                          {focusData?.focus?.fix || "Focus on piece safety."}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>

            {/* MISSION */}
            {focusData?.mission && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                <Card className="border-amber-500/20 bg-gradient-to-br from-amber-500/5 to-yellow-500/5">
                  <CardContent className="py-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-full bg-amber-500/10">
                          <Target className="w-5 h-5 text-amber-500" />
                        </div>
                        <div>
                          <span className="text-xs font-bold uppercase tracking-wider text-amber-500">
                            Active Mission
                          </span>
                          <h3 className="font-bold">{focusData.mission.name}</h3>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-2xl font-bold text-amber-500">
                          {focusData.mission.games_completed || 0}
                        </span>
                        <span className="text-muted-foreground">/{focusData.mission.games_required || 10}</span>
                      </div>
                    </div>
                    
                    <p className="text-sm text-muted-foreground mb-3">
                      {focusData.mission.description || focusData.mission.goal}
                    </p>
                    
                    <Progress 
                      value={((focusData.mission.games_completed || 0) / (focusData.mission.games_required || 10)) * 100} 
                      className="h-2"
                    />
                    
                    {focusData.mission.reward && (
                      <div className="flex items-center gap-2 mt-3 text-sm">
                        <Trophy className="w-4 h-4 text-amber-500" />
                        <span className="text-muted-foreground">Reward: {focusData.mission.reward}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* IDENTITY BADGE */}
            {focusData?.identity && focusData.identity.profile !== "unknown" && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
              >
                <Card className="border-purple-500/20 bg-gradient-to-br from-purple-500/5 to-indigo-500/5">
                  <CardContent className="py-5">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-full bg-purple-500/10">
                        <Zap className="w-5 h-5 text-purple-500" />
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground">Your Chess Identity</span>
                        <h3 className="font-bold text-purple-400">{focusData.identity.label}</h3>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground mt-2 ml-12">
                      {focusData.identity.description}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* RATING IMPACT - Motivational */}
            {focusData?.rating_impact?.potential_gain > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
              >
                <Card className="border-green-500/20 bg-gradient-to-br from-green-500/5 to-emerald-500/5">
                  <CardContent className="py-5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-full bg-green-500/10">
                          <AlertTriangle className="w-5 h-5 text-green-500" />
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground">Potential Rating Gain</span>
                          <p className="text-sm">{focusData.rating_impact.message}</p>
                        </div>
                      </div>
                      <span className="text-2xl font-bold text-green-500">
                        +{focusData.rating_impact.potential_gain}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* PRACTICE PUZZLE - ONE interactive element */}
            {coachData?.mistake_mastery && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
              >
                <MistakeMastery 
                  data={coachData.mistake_mastery}
                  compact={true}
                />
              </motion.div>
            )}

            {/* CTA to see full analysis */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="text-center pt-4"
            >
              <Button 
                variant="outline" 
                onClick={() => navigate("/progress")}
                className="group"
              >
                View Full Journey
                <ChevronRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
              </Button>
            </motion.div>
          </>
        )}
      </div>
    </Layout>
  );
};

export default FocusPage;
