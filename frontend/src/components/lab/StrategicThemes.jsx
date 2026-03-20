/**
 * StrategicThemes (Ideas Tab) - Position-Linked Strategic Concepts
 * 
 * STRICT RULE: Every idea must contain:
 * - concept name
 * - position (fen)
 * - move number
 * - short explanation (RATING-ADAPTIVE)
 * - "View Position" button
 * - "How a stronger player thinks" section
 * 
 * NO textbook fluff. Everything tied to actual game positions.
 * 
 * Rating Adaptation:
 * - Beginner (< 1000): Simple, one-concept explanations
 * - Intermediate (1000-1500): Add "why" and alternatives
 * - Advanced (1500+): Include strategic nuances
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import ThoughtProcessWalkthrough from "./ThoughtProcessWalkthrough";
import {
  Crown,
  Shield,
  Swords,
  Target,
  Zap,
  Clock,
  Grid3X3,
  ArrowUpRight,
  Eye,
  ChevronRight,
  Brain,
  ChevronDown,
  ChevronUp,
  Lightbulb
} from "lucide-react";

// Rating-adaptive explanation templates
const RATING_EXPLANATIONS = {
  beginner: {
    piece_activity: (move, best) => `Your ${move} left a piece doing nothing. ${best} makes it useful.`,
    pawn_structure: (move, best) => `Your pawn move created a weakness. ${best} keeps pawns safe.`,
    king_safety: (move, best) => `Your king was in danger! ${best} keeps it safe.`,
    central_control: (move, best) => `Control the center! ${best} gives you more space.`,
    tactical: (move, best) => `You missed a trick! ${best} wins material.`,
    development: (move, best) => `Get your pieces out! ${best} develops faster.`,
    defense: (move, best) => `Watch out for threats! ${best} defends properly.`
  },
  intermediate: {
    piece_activity: (move, best) => `${move} was passive. ${best} improves piece coordination and creates threats.`,
    pawn_structure: (move, best) => `The pawn structure after ${move} has long-term weaknesses. ${best} maintains flexibility.`,
    king_safety: (move, best) => `${move} left attacking lines open. ${best} prioritizes king safety before attacking.`,
    central_control: (move, best) => `${move} cedes central squares. ${best} fights for key squares e4/d4/e5/d5.`,
    tactical: (move, best) => `${move} missed a forcing sequence. ${best} exploits the tactical opportunity.`,
    development: (move, best) => `${move} delays development. ${best} completes development with tempo.`,
    defense: (move, best) => `${move} ignores the threat. ${best} defends while maintaining counterplay.`
  },
  advanced: {
    piece_activity: (move, best) => `${move} doesn't address piece harmony. ${best} optimizes all piece activity and creates lasting pressure.`,
    pawn_structure: (move, best) => `The structural transformation after ${move} favors the opponent long-term. ${best} preserves dynamic potential.`,
    king_safety: (move, best) => `${move} underestimates positional king safety. ${best} balances attack/defense ratio.`,
    central_control: (move, best) => `${move} allows opponent piece mobility. ${best} restricts their options while expanding yours.`,
    tactical: (move, best) => `${move} overlooks the forcing sequence. ${best} calculates through to a favorable evaluation.`,
    development: (move, best) => `${move} is too committal too early. ${best} maintains flexibility while improving position.`,
    defense: (move, best) => `${move} is purely reactive. ${best} defends dynamically with counter-threats.`
  }
};

// Helper to get player level from rating
const getPlayerLevel = (rating) => {
  if (!rating || rating < 1000) return "beginner";
  if (rating < 1500) return "intermediate";
  return "advanced";
};

// Map theme types to icons and colors

// Map theme types to icons and colors
const THEME_CONFIG = {
  piece_activity: {
    icon: Zap,
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
    borderColor: "border-amber-500/30"
  },
  pawn_structure: {
    icon: Grid3X3,
    color: "text-blue-400",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/30"
  },
  king_safety: {
    icon: Crown,
    color: "text-red-400",
    bgColor: "bg-red-500/10",
    borderColor: "border-red-500/30"
  },
  central_control: {
    icon: Target,
    color: "text-emerald-400",
    bgColor: "bg-emerald-500/10",
    borderColor: "border-emerald-500/30"
  },
  piece_coordination: {
    icon: Swords,
    color: "text-violet-400",
    bgColor: "bg-violet-500/10",
    borderColor: "border-violet-500/30"
  },
  development: {
    icon: ArrowUpRight,
    color: "text-cyan-400",
    bgColor: "bg-cyan-500/10",
    borderColor: "border-cyan-500/30"
  },
  time_management: {
    icon: Clock,
    color: "text-orange-400",
    bgColor: "bg-orange-500/10",
    borderColor: "border-orange-500/30"
  },
  defense: {
    icon: Shield,
    color: "text-slate-400",
    bgColor: "bg-slate-500/10",
    borderColor: "border-slate-500/30"
  },
  tactical: {
    icon: Zap,
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/10",
    borderColor: "border-yellow-500/30"
  }
};

const StrategicThemes = ({ 
  deepStrategy,
  labData,
  game,
  onNavigateToMove,
  playerRating = null  // Add player rating prop
}) => {
  const [expandedIdea, setExpandedIdea] = useState(null);
  const [showThinkingFor, setShowThinkingFor] = useState(null);
  
  // Get player level for adaptive explanations
  const playerLevel = getPlayerLevel(playerRating || labData?.player_rating || 1200);
  
  // Extract position-linked strategic ideas from critical moments
  const extractIdeas = () => {
    const ideas = [];
    const criticalMoments = deepStrategy?.critical_moments || [];
    const seenTypes = new Set();
    
    criticalMoments.forEach(moment => {
      const insight = moment.insight || {};
      const tags = moment.tags || {};
      const moveNum = moment.move_number;
      const fen = moment.fen;
      const yourMove = moment.your_move;
      const bestMove = moment.best_move;
      
      // Skip if no position data
      if (!fen || !moveNum) return;
      
      // Determine strategic concept from this moment
      let ideaType = null;
      let ideaTitle = null;
      let explanation = null;
      
      // Check what the moment reveals
      const whatYouMissed = insight.what_you_missed || "";
      const whatBestMoveAchieves = insight.what_best_move_achieves || "";
      const threatLower = (moment.threat || "").toLowerCase();
      
      // Detect idea type from context
      if (whatYouMissed.toLowerCase().includes("inactive") || 
          whatYouMissed.toLowerCase().includes("passive") ||
          whatBestMoveAchieves.toLowerCase().includes("active")) {
        ideaType = "piece_activity";
        ideaTitle = "Piece Activity";
        explanation = whatYouMissed || `On move ${moveNum}, ${bestMove} would have activated your pieces more effectively.`;
      } else if (whatYouMissed.toLowerCase().includes("pawn") ||
                 whatYouMissed.toLowerCase().includes("weakness") ||
                 tags.positional_concepts?.includes("pawn_structure")) {
        ideaType = "pawn_structure";
        ideaTitle = "Pawn Structure";
        explanation = whatYouMissed || `The pawn move created weaknesses that could have been avoided.`;
      } else if (threatLower.includes("king") || 
                 whatYouMissed.toLowerCase().includes("king") ||
                 threatLower.includes("mate") ||
                 tags.tactical_theme === "king_attack") {
        ideaType = "king_safety";
        ideaTitle = "King Safety";
        explanation = whatYouMissed || `Your king was exposed here. Safety should have been prioritized.`;
      } else if (whatBestMoveAchieves.toLowerCase().includes("center") ||
                 whatBestMoveAchieves.toLowerCase().includes("central") ||
                 tags.positional_concepts?.includes("central_control")) {
        ideaType = "central_control";
        ideaTitle = "Central Control";
        explanation = whatBestMoveAchieves || `Controlling the center would have given you more options.`;
      } else if (threatLower.includes("fork") ||
                 threatLower.includes("pin") ||
                 threatLower.includes("skewer") ||
                 threatLower.includes("loose") ||
                 tags.tactical_theme) {
        ideaType = "tactical";
        ideaTitle = tags.tactical_theme?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || "Tactical Pattern";
        explanation = moment.threat || whatYouMissed || `A tactical opportunity was missed here.`;
      } else if (whatYouMissed.toLowerCase().includes("develop") ||
                 moment.phase === "opening") {
        ideaType = "development";
        ideaTitle = "Development";
        explanation = whatYouMissed || `Faster development would have improved your position.`;
      } else if (whatYouMissed) {
        // Generic idea with actual explanation
        ideaType = "defense";
        ideaTitle = "Defensive Awareness";
        explanation = whatYouMissed;
      }
      
      // Only add if we have a valid idea and haven't seen this type
      if (ideaType && !seenTypes.has(ideaType)) {
        seenTypes.add(ideaType);
        ideas.push({
          type: ideaType,
          title: ideaTitle,
          explanation,
          moveNum,
          fen,
          yourMove,
          bestMove,
          hasPosition: true
        });
      }
    });
    
    return ideas.slice(0, 4); // Max 4 ideas
  };
  
  const ideas = extractIdeas();
  
  if (ideas.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <p className="text-sm">No strategic themes identified in this game.</p>
        <p className="text-xs mt-1">Play more games for deeper analysis.</p>
      </div>
    );
  }
  
  return (
    <div className="space-y-4" data-testid="strategic-themes">
      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        Strategic Ideas From This Game
      </h3>
      
      <div className="space-y-3">
        {ideas.map((idea, idx) => {
          const config = THEME_CONFIG[idea.type] || THEME_CONFIG.defense;
          const Icon = config.icon;
          
          return (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
            >
              <Card className={`border ${config.borderColor} ${config.bgColor}`}>
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <div className={`w-10 h-10 rounded-lg ${config.bgColor} flex items-center justify-center flex-shrink-0`}>
                      <Icon className={`w-5 h-5 ${config.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      {/* Idea header with move number */}
                      <div className="flex items-center justify-between mb-1">
                        <h4 className={`font-medium ${config.color}`}>
                          {idea.title}
                        </h4>
                        <span className="text-xs text-muted-foreground">
                          Move {idea.moveNum}
                        </span>
                      </div>
                      
                      {/* Rating-adaptive explanation */}
                      <p className="text-sm text-muted-foreground leading-relaxed mb-2">
                        {RATING_EXPLANATIONS[playerLevel]?.[idea.type] 
                          ? RATING_EXPLANATIONS[playerLevel][idea.type](idea.yourMove, idea.bestMove)
                          : idea.explanation}
                      </p>
                      
                      {/* Original insight if different */}
                      {idea.explanation && !idea.explanation.includes(idea.yourMove) && (
                        <p className="text-xs text-muted-foreground/70 italic mb-2">
                          "{idea.explanation}"
                        </p>
                      )}
                      
                      {/* Show moves if available */}
                      {idea.yourMove && idea.bestMove && (
                        <div className="flex items-center gap-3 text-xs mb-3">
                          <span className="text-red-300/70">
                            Played: <span className="font-mono">{idea.yourMove}</span>
                          </span>
                          <span className="text-emerald-300/70">
                            Better: <span className="font-mono">{idea.bestMove}</span>
                          </span>
                        </div>
                      )}
                      
                      {/* Action buttons */}
                      <div className="flex items-center gap-2 flex-wrap">
                        {/* View Position button - REQUIRED for every idea */}
                        {onNavigateToMove && idea.hasPosition && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className={`text-xs ${config.color} hover:${config.color} p-0 h-auto`}
                            onClick={() => onNavigateToMove(idea.moveNum, idea.yourMove, idea.bestMove)}
                          >
                            <Eye className="w-3 h-3 mr-1" />
                            View position
                            <ChevronRight className="w-3 h-3 ml-0.5" />
                          </Button>
                        )}
                        
                        {/* How a stronger player thinks */}
                        {idea.fen && idea.bestMove && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs text-blue-400 hover:text-blue-300 p-0 h-auto"
                            onClick={() => setShowThinkingFor(showThinkingFor === idx ? null : idx)}
                          >
                            <Brain className="w-3 h-3 mr-1" />
                            {showThinkingFor === idx ? "Hide thinking" : "How to think here"}
                            {showThinkingFor === idx ? <ChevronUp className="w-3 h-3 ml-0.5" /> : <ChevronDown className="w-3 h-3 ml-0.5" />}
                          </Button>
                        )}
                      </div>
                      
                      {/* Thought Process Walkthrough - Expandable */}
                      {showThinkingFor === idx && idea.fen && idea.bestMove && (
                        <div className="mt-3 pt-3 border-t border-border/30">
                          <ThoughtProcessWalkthrough
                            fen={idea.fen}
                            bestMove={idea.bestMove}
                            playedMove={idea.yourMove}
                            compact={false}
                            autoFetch={true}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>
      
      {/* Rating level indicator */}
      <div className="flex items-center justify-center gap-2 pt-2">
        <Lightbulb className="w-3 h-3 text-muted-foreground" />
        <span className="text-[10px] text-muted-foreground">
          Explanations adapted for {playerLevel} level ({playerRating || labData?.player_rating || "~1200"} rating)
        </span>
      </div>
    </div>
  );
};

export default StrategicThemes;
