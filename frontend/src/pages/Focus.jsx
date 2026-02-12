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
  
  // Evidence modal state
  const [showEvidence, setShowEvidence] = useState(false);
  
  // Drill mode state
  const [showDrill, setShowDrill] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch focus data from new endpoint
        const [focusRes, coachRes] = await Promise.all([
          fetch(`${API}/focus`, { credentials: "include" }),
          fetch(`${API}/coach/today`, { credentials: "include" })  // Fixed: use /coach/today
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
  
  // Extract evidence for the main focus
  const focusEvidence = focusData?.focus?.evidence || [];
  const focusOccurrences = focusData?.focus?.occurrences || 0;

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
        ) : showDrill ? (
          /* DRILL MODE */
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <DrillMode
              pattern={focusData?.focus?.pattern}
              patternLabel={focusData?.focus?.label || "this pattern"}
              onComplete={() => setShowDrill(false)}
              onClose={() => setShowDrill(false)}
            />
          </motion.div>
        ) : (
          <>
            {/* MAIN FOCUS - The ONE thing - NOW CLICKABLE */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <Card 
                className="border-2 border-red-500/30 bg-gradient-to-br from-red-500/5 to-orange-500/5 cursor-pointer hover:border-red-500/50 transition-colors"
                onClick={() => focusEvidence.length > 0 && setShowEvidence(true)}
                data-testid="rating-killer-card"
              >
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
                        {focusOccurrences > 0 && (
                          <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full flex items-center gap-1">
                            <Eye className="w-3 h-3" />
                            See {focusOccurrences} times this happened
                          </span>
                        )}
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
                      <div className="p-4 rounded-lg bg-background/50 border border-border/50 mb-4">
                        <div className="flex items-center gap-2 mb-2">
                          <Lightbulb className="w-4 h-4 text-yellow-500" />
                          <span className="text-sm font-semibold">Before your next move:</span>
                        </div>
                        <p className="text-base">
                          {focusData?.focus?.fix || "Focus on piece safety."}
                        </p>
                      </div>
                      
                      {/* ACTION BUTTONS */}
                      {focusData?.focus?.pattern && (
                        <div className="flex gap-2" onClick={e => e.stopPropagation()}>
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="gap-1"
                            onClick={() => setShowEvidence(true)}
                            disabled={focusEvidence.length === 0}
                            data-testid="see-examples-btn"
                          >
                            <Eye className="w-4 h-4" />
                            See Examples
                          </Button>
                          <Button 
                            size="sm" 
                            className="gap-1 bg-red-500 hover:bg-red-600"
                            onClick={() => setShowDrill(true)}
                            data-testid="train-pattern-btn"
                          >
                            <Dumbbell className="w-4 h-4" />
                            Train This
                          </Button>
                        </div>
                      )}
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
                <Card className="border-amber-500/30 bg-gradient-to-br from-amber-500/5 to-transparent">
                  <CardContent className="py-5">
                    {/* Header */}
                    <div className="flex items-center gap-2 mb-3">
                      <Target className="w-4 h-4 text-amber-500" />
                      <span className="text-xs font-bold uppercase tracking-wider text-amber-500">
                        Current Discipline Focus
                      </span>
                    </div>
                    
                    {/* Mission Name & Progress */}
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-lg font-bold">{focusData.mission.name}</h3>
                      <div className="flex items-baseline gap-1">
                        <span className="text-2xl font-bold text-amber-500">
                          {focusData.mission.progress || 0}
                        </span>
                        <span className="text-muted-foreground text-sm">/ {focusData.mission.target || 3}</span>
                      </div>
                    </div>
                    
                    {/* Goal */}
                    <p className="text-sm font-medium mb-3">
                      {focusData.mission.goal}
                    </p>
                    
                    {/* Progress Bar */}
                    <Progress 
                      value={((focusData.mission.progress || 0) / (focusData.mission.target || 3)) * 100} 
                      className="h-1.5 mb-4"
                    />
                    
                    {/* Instruction Box */}
                    {focusData.mission.instruction && (
                      <div className="bg-muted/50 rounded-lg p-3 border border-border/50">
                        <p className="text-xs uppercase font-semibold text-muted-foreground mb-1">How to do it</p>
                        <p className="text-sm">{focusData.mission.instruction}</p>
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
      
      {/* Evidence Modal */}
      <EvidenceModal
        isOpen={showEvidence}
        onClose={() => setShowEvidence(false)}
        title={focusData?.focus?.label || "Rating Killer"}
        subtitle={focusData?.focus?.main_message}
        evidence={focusEvidence}
        type="pattern"
      />
    </Layout>
  );
};

export default FocusPage;
