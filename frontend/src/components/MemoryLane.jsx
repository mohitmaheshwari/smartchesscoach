/**
 * MemoryLane - Coach's memories of past games
 * 
 * Makes the coach feel human by referencing specific past games.
 * "Remember that game last Tuesday where you fell for the same tactic?"
 */

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  Brain,
  History,
  Trophy,
  AlertTriangle,
  ChevronRight,
  Loader2,
  Sparkles
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const MemoryLane = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const navigate = useNavigate();
  
  useEffect(() => {
    fetchMemories();
  }, []);
  
  const fetchMemories = async () => {
    try {
      const res = await fetch(`${API}/coach/memory-lane`, {
        credentials: "include"
      });
      
      if (res.ok) {
        const result = await res.json();
        setData(result);
      }
    } catch (err) {
      console.error("Error fetching memory lane:", err);
    } finally {
      setLoading(false);
    }
  };
  
  const getMemoryIcon = (type) => {
    switch (type) {
      case "mistake_pattern":
        return <AlertTriangle className="w-4 h-4 text-amber-400" />;
      case "good_game":
        return <Trophy className="w-4 h-4 text-green-400" />;
      case "recurring_pattern":
        return <History className="w-4 h-4 text-red-400" />;
      default:
        return <Brain className="w-4 h-4 text-primary" />;
    }
  };
  
  const getMemoryStyle = (type) => {
    switch (type) {
      case "mistake_pattern":
        return "border-amber-500/30 bg-amber-500/5";
      case "good_game":
        return "border-green-500/30 bg-green-500/5";
      case "recurring_pattern":
        return "border-red-500/30 bg-red-500/5";
      default:
        return "border-primary/30 bg-primary/5";
    }
  };
  
  if (loading) {
    return (
      <Card className="bg-muted/30">
        <CardContent className="p-4 flex items-center justify-center">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }
  
  if (!data || !data.has_memories) {
    return null; // Don't show if no memories
  }
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <Card className="bg-gradient-to-r from-purple-500/5 to-indigo-500/5 border-purple-500/20">
        <CardContent className="p-4">
          {/* Header */}
          <div className="flex items-center gap-2 mb-3">
            <div className="p-1.5 rounded-full bg-purple-500/20">
              <Brain className="w-4 h-4 text-purple-400" />
            </div>
            <span className="text-sm font-semibold text-purple-400">
              Coach Remembers...
            </span>
            <Sparkles className="w-3 h-3 text-purple-400/60" />
          </div>
          
          {/* Memories */}
          <div className="space-y-2">
            <AnimatePresence>
              {data.memories.map((memory, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className={`p-3 rounded-lg border ${getMemoryStyle(memory.type)} cursor-pointer hover:border-primary/50 transition-all`}
                  onClick={() => memory.game_id && navigate(`/game/${memory.game_id}`)}
                  data-testid={`memory-item-${index}`}
                >
                  <div className="flex items-start gap-2">
                    <div className="mt-0.5">
                      {getMemoryIcon(memory.type)}
                    </div>
                    <p className="text-sm flex-1">
                      {memory.message}
                    </p>
                    {memory.game_id && (
                      <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    )}
                  </div>
                  
                  {/* Memory tags */}
                  <div className="flex gap-2 mt-2 ml-6">
                    {memory.pattern && (
                      <Badge variant="outline" className="text-xs">
                        {memory.pattern.replace(/_/g, ' ')}
                      </Badge>
                    )}
                    {memory.accuracy && (
                      <Badge variant="outline" className="text-xs text-green-400 border-green-500/30">
                        {memory.accuracy}% accuracy
                      </Badge>
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
          
          {/* Action hint */}
          {data.coach_knows_you && (
            <p className="text-xs text-muted-foreground mt-3 text-center">
              The more you play, the better I know you!
            </p>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default MemoryLane;
