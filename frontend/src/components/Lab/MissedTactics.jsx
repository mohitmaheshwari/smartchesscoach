/**
 * MissedTactics - Pattern Recognition Section
 * 
 * Players love this section.
 * Shows tactical opportunities that were missed.
 * Helps build pattern recognition.
 * 
 * NO cp values. Just "Fork", "Pin", "Loose piece".
 */

import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Chess } from "chess.js";
import {
  Zap,
  Play,
  Eye
} from "lucide-react";

// Helper function to convert SAN move to UCI format
const sanToUci = (fen, sanMove) => {
  if (!fen || !sanMove) return null;
  try {
    const chess = new Chess(fen);
    const move = chess.move(sanMove, { sloppy: true });
    if (move) {
      return move.from + move.to + (move.promotion || '');
    }
  } catch (e) {
    console.log("Could not convert SAN to UCI:", sanMove, e);
  }
  return null;
};

// Tactic type descriptions
const TACTIC_LABELS = {
  fork: { label: "Fork", description: "Attack two pieces at once" },
  pin: { label: "Pin", description: "A piece can't move without exposing a more valuable one" },
  skewer: { label: "Skewer", description: "Attack through a piece to one behind it" },
  discovered_attack: { label: "Discovered Attack", description: "Moving one piece reveals an attack by another" },
  loose_piece: { label: "Loose Piece", description: "Undefended piece can be captured" },
  hanging_piece: { label: "Hanging Piece", description: "Piece left undefended" },
  back_rank: { label: "Back Rank", description: "Checkmate threat on the back rank" },
  removal_of_defender: { label: "Removing the Defender", description: "Capture the piece defending a target" },
  overloaded_piece: { label: "Overloaded Piece", description: "One piece doing too many jobs" },
  trapped_piece: { label: "Trapped Piece", description: "Piece has no safe squares" },
  zwischenzug: { label: "In-Between Move", description: "Surprise move before the expected one" },
  deflection: { label: "Deflection", description: "Force a defender away from its duty" },
  attraction: { label: "Attraction", description: "Lure a piece to a bad square" },
  mate_threat: { label: "Checkmate Threat", description: "Immediate mating threat" },
  winning_exchange: { label: "Winning Exchange", description: "Trade that wins material" }
};

const MissedTactics = ({ 
  deepStrategy,
  labData,
  onNavigateToMove
}) => {
  // Extract missed tactics from critical moments
  const extractTactics = () => {
    const tactics = [];
    const criticalMoments = deepStrategy?.critical_moments || [];
    
    criticalMoments.forEach(moment => {
      const tags = moment.tags || {};
      const insight = moment.insight || {};
      const threat = moment.threat || "";
      
      // Determine tactic type from tags or insight
      let tacticType = null;
      let tacticDescription = "";
      
      // Check tags first
      if (tags.tactical_theme) {
        tacticType = tags.tactical_theme;
      }
      
      // Check threat description
      const threatLower = threat.toLowerCase();
      const insightLower = (insight.what_you_missed || "").toLowerCase();
      
      if (threatLower.includes("fork") || insightLower.includes("fork")) {
        tacticType = "fork";
      } else if (threatLower.includes("pin") || insightLower.includes("pin")) {
        tacticType = "pin";
      } else if (threatLower.includes("skewer") || insightLower.includes("skewer")) {
        tacticType = "skewer";
      } else if (threatLower.includes("discovered") || insightLower.includes("discovered")) {
        tacticType = "discovered_attack";
      } else if (threatLower.includes("loose") || insightLower.includes("loose") ||
                 threatLower.includes("undefended") || insightLower.includes("undefended") ||
                 threatLower.includes("hanging") || insightLower.includes("hanging")) {
        tacticType = "loose_piece";
      } else if (threatLower.includes("back rank") || insightLower.includes("back rank")) {
        tacticType = "back_rank";
      } else if (threatLower.includes("mate") || insightLower.includes("checkmate")) {
        tacticType = "mate_threat";
      } else if (threatLower.includes("deflect") || insightLower.includes("deflect")) {
        tacticType = "deflection";
      } else if (threatLower.includes("trap") || insightLower.includes("trapped")) {
        tacticType = "trapped_piece";
      }
      
      // Only add if we identified a tactic
      if (tacticType || insight.what_you_missed) {
        // Build description
        if (insight.what_best_move_achieves) {
          tacticDescription = insight.what_best_move_achieves;
        } else if (threat) {
          tacticDescription = threat;
        } else if (insight.what_you_missed) {
          tacticDescription = insight.what_you_missed;
        }
        
        tactics.push({
          moveNumber: moment.move_number,
          bestMove: moment.best_move,
          yourMove: moment.your_move,
          tacticType: tacticType || "winning_exchange",
          description: tacticDescription,
          fen: moment.fen
        });
      }
    });
    
    return tactics.slice(0, 5); // Max 5 tactics
  };
  
  const tactics = extractTactics();
  
  if (tactics.length === 0) {
    return null;
  }
  
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Zap className="w-5 h-5 text-amber-500" />
        <h3 className="font-semibold">Missed Tactics</h3>
        <Badge variant="outline" className="text-xs">
          {tactics.length} found
        </Badge>
      </div>
      
      <div className="space-y-3">
        {tactics.map((tactic, idx) => {
          const tacticInfo = TACTIC_LABELS[tactic.tacticType] || {
            label: "Tactical Shot",
            description: "A forcing move that wins"
          };
          
          return (
            <motion.div
              key={idx}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.1 }}
            >
              <Card className="border-amber-500/20 bg-amber-500/5">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      {/* Move number and tactic type */}
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant="outline" className="text-xs">
                          Move {tactic.moveNumber}
                        </Badge>
                        <span className="text-sm font-medium text-amber-400">
                          {tacticInfo.label}
                        </span>
                      </div>
                      
                      {/* Best move */}
                      <p className="text-sm mb-1">
                        <span className="text-emerald-400 font-mono font-bold">
                          {tactic.bestMove}
                        </span>
                        {" "}{tactic.description}
                      </p>
                      
                      {/* What it was */}
                      <p className="text-xs text-muted-foreground">
                        {tacticInfo.description}
                      </p>
                    </div>
                    
                    {/* See on board button */}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        // Convert SAN moves to UCI for arrow display
                        const bestMoveUci = sanToUci(tactic.fen, tactic.bestMove);
                        const yourMoveUci = sanToUci(tactic.fen, tactic.yourMove);
                        onNavigateToMove?.(tactic.moveNumber, yourMoveUci, bestMoveUci);
                      }}
                      className="h-8 text-xs"
                    >
                      <Eye className="w-3 h-3 mr-1" />
                      View
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>
      
      {/* Pattern recognition tip */}
      <Card className="border-0 bg-slate-800/30">
        <CardContent className="p-3">
          <p className="text-xs text-muted-foreground text-center">
            <span className="text-primary">Tip:</span> Practice these patterns with puzzles to spot them faster in games.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default MissedTactics;
