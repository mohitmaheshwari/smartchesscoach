/**
 * TrapAnalysis - Display trap detection results for a game
 * Shows traps executed, fallen into, and missed opportunities
 */

import { motion, AnimatePresence } from "framer-motion";
import { 
  Sparkles, 
  AlertTriangle, 
  Lightbulb,
  Trophy,
  Target,
  ChevronRight,
  Info
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

const TrapAnalysis = ({ trapAnalysis, onLearnTrap }) => {
  const navigate = useNavigate();
  
  if (!trapAnalysis) return null;
  
  const { 
    traps_executed = [], 
    traps_fallen_into = [], 
    trap_opportunities_missed = [],
    summary = {}
  } = trapAnalysis;
  
  const hasData = traps_executed.length > 0 || 
                  traps_fallen_into.length > 0 || 
                  trap_opportunities_missed.length > 0;
  
  if (!hasData) return null;
  
  return (
    <Card className="border-purple-500/30 bg-purple-500/5">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-purple-400" />
          Trap Analysis
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        
        {/* Traps Successfully Executed */}
        {traps_executed.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-green-400">
              <Trophy className="w-4 h-4" />
              <span className="font-medium">Traps You Executed!</span>
            </div>
            {traps_executed.map((trap, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1 }}
                className="p-3 rounded-lg bg-green-500/10 border border-green-500/30"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-green-300">{trap.trap_name}</span>
                    <span className="text-xs text-muted-foreground ml-2">
                      Move {trap.move_number}
                    </span>
                  </div>
                  <Badge variant="outline" className="text-green-400 border-green-400/50">
                    {trap.result}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {trap.description}
                </p>
              </motion.div>
            ))}
          </div>
        )}
        
        {/* Traps Fallen Into */}
        {traps_fallen_into.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-amber-400">
              <AlertTriangle className="w-4 h-4" />
              <span className="font-medium">Traps You Fell Into</span>
            </div>
            {traps_fallen_into.map((trap, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1 }}
                className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-amber-300">{trap.trap_name}</span>
                    <span className="text-xs text-muted-foreground ml-2">
                      Move {trap.move_number}
                    </span>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    className="text-xs text-purple-400 hover:text-purple-300"
                    onClick={() => navigate(`/openings/${trap.opening}`)}
                  >
                    Learn to Avoid
                    <ChevronRight className="w-3 h-3 ml-1" />
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {trap.description}
                </p>
                {trap.how_to_avoid && (
                  <p className="text-xs text-amber-400/80 mt-2 flex items-start gap-1">
                    <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
                    {trap.how_to_avoid}
                  </p>
                )}
              </motion.div>
            ))}
          </div>
        )}
        
        {/* Missed Trap Opportunities */}
        {trap_opportunities_missed.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-blue-400">
              <Target className="w-4 h-4" />
              <span className="font-medium">Trap Opportunities Missed</span>
            </div>
            {trap_opportunities_missed.map((trap, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1 }}
                className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/30"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-blue-300">{trap.trap_name}</span>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    className="text-xs text-purple-400 hover:text-purple-300"
                    onClick={() => navigate(`/openings/${trap.opening}`)}
                  >
                    Learn This Trap
                    <ChevronRight className="w-3 h-3 ml-1" />
                  </Button>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-muted-foreground">Move {trap.move_number}:</span>
                  <span className="text-amber-300">You played {trap.you_played}</span>
                  <span className="text-muted-foreground">→</span>
                  <span className="text-green-300">Trap was {trap.trap_move}</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1 pl-0">
                  <Lightbulb className="w-3 h-3 inline mr-1 text-blue-400" />
                  {trap.explanation}
                </p>
              </motion.div>
            ))}
          </div>
        )}
        
        {/* Summary */}
        {(summary.executed_count > 0 || summary.fallen_into_count > 0 || summary.missed_count > 0) && (
          <div className="pt-2 border-t border-border/50 text-xs text-muted-foreground">
            <span className="text-purple-400">Trap Score: </span>
            {summary.executed_count > 0 && (
              <span className="text-green-400 mr-2">
                {summary.executed_count} executed
              </span>
            )}
            {summary.fallen_into_count > 0 && (
              <span className="text-amber-400 mr-2">
                {summary.fallen_into_count} fallen into
              </span>
            )}
            {summary.missed_count > 0 && (
              <span className="text-blue-400">
                {summary.missed_count} missed
              </span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default TrapAnalysis;
