/**
 * TeachingPanel.jsx - Teaching Insights Panel for Play with Coach
 * 
 * Shows real-time teaching insights:
 * - Current pawn structure analysis
 * - Strategic plans for both sides
 * - Teaching concepts from the coach's moves
 * - Position phase and priorities
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  BookOpen,
  Target,
  Lightbulb,
  ChevronDown,
  ChevronUp,
  Loader2,
  Swords,
  Shield,
  Crown,
  Puzzle,
  Clock,
  TrendingUp
} from "lucide-react";

/**
 * Phase indicator with visual styling
 */
const PhaseIndicator = ({ phase, phasePercent }) => {
  const phaseColors = {
    opening: "bg-green-500/20 text-green-400 border-green-500/30",
    early_middlegame: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    middlegame: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    late_middlegame: "bg-orange-500/20 text-orange-400 border-orange-500/30",
    early_endgame: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    endgame: "bg-red-500/20 text-red-400 border-red-500/30",
    deep_endgame: "bg-red-600/20 text-red-500 border-red-600/30"
  };

  const phaseIcons = {
    opening: Crown,
    early_middlegame: Swords,
    middlegame: Swords,
    late_middlegame: Puzzle,
    early_endgame: Target,
    endgame: Target,
    deep_endgame: Target
  };

  const Icon = phaseIcons[phase] || Clock;
  const colorClass = phaseColors[phase] || "bg-gray-500/20 text-gray-400 border-gray-500/30";

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border ${colorClass}`}>
      <Icon className="w-4 h-4" />
      <span className="text-sm font-medium capitalize">{phase?.replace(/_/g, " ")}</span>
      <span className="text-xs opacity-70">({phasePercent}%)</span>
    </div>
  );
};

/**
 * Strategic Plan Card
 */
const PlanCard = ({ plan, color, isExpanded, onToggle }) => {
  if (!plan) return null;

  return (
    <div 
      className={`rounded-lg border transition-all ${
        color === "white" 
          ? "bg-slate-100/10 border-slate-300/30" 
          : "bg-slate-800/30 border-slate-600/30"
      }`}
    >
      <button 
        onClick={onToggle}
        className="w-full p-3 flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-2">
          {color === "white" ? (
            <div className="w-4 h-4 rounded-full bg-white border border-gray-300" />
          ) : (
            <div className="w-4 h-4 rounded-full bg-gray-800" />
          )}
          <span className="font-medium text-sm">{plan.name}</span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>
      
      {isExpanded && (
        <div className="px-3 pb-3 space-y-2 text-sm">
          <p className="text-muted-foreground">{plan.description}</p>
          
          {plan.key_moves?.length > 0 && (
            <div>
              <span className="text-xs font-medium text-muted-foreground">Key moves: </span>
              <span className="font-mono text-primary">{plan.key_moves.join(", ")}</span>
            </div>
          )}
          
          {plan.teaching && (
            <div className="p-2 rounded bg-primary/5 border border-primary/20">
              <Lightbulb className="w-3 h-3 inline mr-1 text-primary" />
              <span className="text-xs">{plan.teaching}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * Main Teaching Panel Component
 */
const TeachingPanel = ({ fen, userColor, sessionId }) => {
  const [loading, setLoading] = useState(false);
  const [phaseData, setPhaseData] = useState(null);
  const [structureData, setStructureData] = useState(null);
  const [expandedPlans, setExpandedPlans] = useState({ white: true, black: false });
  const [showPanel, setShowPanel] = useState(true);

  // Fetch position analysis when FEN changes
  useEffect(() => {
    if (fen) {
      analyzePosition(fen);
    }
  }, [fen]);

  const analyzePosition = async (currentFen) => {
    setLoading(true);
    try {
      // Fetch phase and structure analysis in parallel
      const [phaseRes, structureRes] = await Promise.all([
        fetch(`${API}/coach/analyze/phase`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ fen: currentFen })
        }),
        fetch(`${API}/coach/analyze/structure`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ fen: currentFen })
        })
      ]);

      if (phaseRes.ok) {
        const phase = await phaseRes.json();
        setPhaseData(phase);
      }

      if (structureRes.ok) {
        const structure = await structureRes.json();
        // If we got a structure, fetch the detailed plans
        if (structure.structure_type) {
          const [whitePlans, blackPlans] = await Promise.all([
            fetch(`${API}/coach/teaching/structure-plans`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              credentials: "include",
              body: JSON.stringify({ 
                structure_type: structure.structure_type, 
                color: "white" 
              })
            }),
            fetch(`${API}/coach/teaching/structure-plans`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              credentials: "include",
              body: JSON.stringify({ 
                structure_type: structure.structure_type, 
                color: "black" 
              })
            })
          ]);

          const whiteData = whitePlans.ok ? await whitePlans.json() : null;
          const blackData = blackPlans.ok ? await blackPlans.json() : null;

          setStructureData({
            ...structure,
            whitePlans: whiteData?.plans || [],
            blackPlans: blackData?.plans || [],
            teachingPoints: whiteData?.teaching_points || [],
            commonMistakes: whiteData?.common_mistakes || []
          });
        } else {
          setStructureData(structure);
        }
      }
    } catch (error) {
      console.error("Position analysis error:", error);
    } finally {
      setLoading(false);
    }
  };

  const togglePlan = (color) => {
    setExpandedPlans(prev => ({
      ...prev,
      [color]: !prev[color]
    }));
  };

  if (!showPanel) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => setShowPanel(true)}
        className="w-full"
      >
        <BookOpen className="w-4 h-4 mr-2" />
        Show Teaching Insights
      </Button>
    );
  }

  return (
    <Card className="border-primary/20 bg-card/50">
      <CardHeader className="py-3 px-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-primary" />
            Teaching Insights
          </CardTitle>
          <div className="flex items-center gap-2">
            {loading && <Loader2 className="w-4 h-4 animate-spin text-primary" />}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowPanel(false)}
              className="h-6 w-6 p-0"
            >
              <ChevronDown className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="pt-0 px-4 pb-4 space-y-4">
        {/* Game Phase */}
        {phaseData && (
          <div className="space-y-2">
            <PhaseIndicator 
              phase={phaseData.phase_label} 
              phasePercent={phaseData.phase_percent} 
            />
            
            {/* Coaching Priorities */}
            {phaseData.coaching?.priorities?.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {phaseData.coaching.priorities.slice(0, 3).map((priority, i) => (
                  <Badge 
                    key={i} 
                    variant="secondary" 
                    className="text-xs capitalize"
                  >
                    {priority.replace(/_/g, " ")}
                  </Badge>
                ))}
              </div>
            )}
            
            {/* Endgame Type if applicable */}
            {phaseData.endgame_type && (
              <div className="p-2 rounded bg-amber-500/10 border border-amber-500/20">
                <div className="flex items-center gap-2 text-sm">
                  <Target className="w-4 h-4 text-amber-400" />
                  <span className="font-medium text-amber-400">
                    {phaseData.endgame_type.name}
                  </span>
                </div>
                {phaseData.endgame_teaching?.key_concepts?.[0] && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {phaseData.endgame_teaching.key_concepts[0]}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Pawn Structure */}
        {structureData?.structure_name && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Puzzle className="w-4 h-4 text-primary" />
              <span className="font-medium text-sm">{structureData.structure_name}</span>
              {structureData.confidence && (
                <Badge variant="outline" className="text-xs">
                  {Math.round(structureData.confidence * 100)}%
                </Badge>
              )}
            </div>
            
            {structureData.main_idea && (
              <p className="text-xs text-muted-foreground">
                {structureData.main_idea}
              </p>
            )}

            {/* Plans for your color first */}
            {userColor === "white" ? (
              <>
                {structureData.whitePlans?.[0] && (
                  <PlanCard 
                    plan={structureData.whitePlans[0]} 
                    color="white"
                    isExpanded={expandedPlans.white}
                    onToggle={() => togglePlan("white")}
                  />
                )}
                {structureData.blackPlans?.[0] && (
                  <PlanCard 
                    plan={structureData.blackPlans[0]} 
                    color="black"
                    isExpanded={expandedPlans.black}
                    onToggle={() => togglePlan("black")}
                  />
                )}
              </>
            ) : (
              <>
                {structureData.blackPlans?.[0] && (
                  <PlanCard 
                    plan={structureData.blackPlans[0]} 
                    color="black"
                    isExpanded={expandedPlans.black}
                    onToggle={() => togglePlan("black")}
                  />
                )}
                {structureData.whitePlans?.[0] && (
                  <PlanCard 
                    plan={structureData.whitePlans[0]} 
                    color="white"
                    isExpanded={expandedPlans.white}
                    onToggle={() => togglePlan("white")}
                  />
                )}
              </>
            )}

            {/* Teaching Points */}
            {structureData.teachingPoints?.length > 0 && (
              <div className="space-y-1">
                <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
                  <Lightbulb className="w-3 h-3" />
                  Key Concepts
                </div>
                <ul className="text-xs text-muted-foreground space-y-0.5">
                  {structureData.teachingPoints.slice(0, 2).map((point, i) => (
                    <li key={i} className="flex items-start gap-1">
                      <span className="text-primary">•</span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Loading state */}
        {loading && !phaseData && !structureData && (
          <div className="text-center py-4 text-muted-foreground text-sm">
            <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
            Analyzing position...
          </div>
        )}

        {/* No structure found */}
        {!loading && !structureData?.structure_name && phaseData && (
          <div className="text-center py-2 text-muted-foreground text-xs">
            Structure analysis will appear as the game develops
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default TeachingPanel;
