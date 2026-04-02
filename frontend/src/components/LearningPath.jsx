/**
 * LearningPath - Personalized Learning Dashboard
 * 
 * Shows what the user should work on based on their:
 * - Weaknesses from past games
 * - Recurring patterns/habits
 * - Progress on different skills
 * 
 * This is the "smart coach" recommendation panel.
 */

import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  Target, 
  TrendingUp, 
  AlertTriangle, 
  BookOpen,
  Swords,
  Brain,
  ChevronRight,
  Sparkles,
  Trophy,
  Loader2
} from "lucide-react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";

const LearningPath = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const navigate = useNavigate();
  
  useEffect(() => {
    fetchLearningPath();
  }, []);
  
  const fetchLearningPath = async () => {
    try {
      const res = await fetch(`${API}/coach/learning-path`, {
        credentials: "include"
      });
      
      if (res.ok) {
        const result = await res.json();
        setData(result);
      }
    } catch (err) {
      console.error("Error fetching learning path:", err);
    } finally {
      setLoading(false);
    }
  };
  
  const handleAction = (action) => {
    switch (action) {
      case "play_with_coach":
        navigate("/play-with-coach");
        break;
      case "opening_lab":
        navigate("/opening-repertoire");
        break;
      case "tactics":
        navigate("/play-with-coach");
        break;
      default:
        navigate("/play-with-coach");
    }
  };
  
  const getTypeIcon = (type) => {
    switch (type) {
      case "weakness":
        return <AlertTriangle className="w-4 h-4" />;
      case "opening":
        return <BookOpen className="w-4 h-4" />;
      case "tactics":
        return <Swords className="w-4 h-4" />;
      default:
        return <Target className="w-4 h-4" />;
    }
  };
  
  const getPriorityColor = (priority) => {
    switch (priority) {
      case 1:
        return "bg-red-500/20 text-red-400 border-red-500/30";
      case 2:
        return "bg-amber-500/20 text-amber-400 border-amber-500/30";
      default:
        return "bg-blue-500/20 text-blue-400 border-blue-500/30";
    }
  };
  
  if (loading) {
    return (
      <Card>
        <CardContent className="p-8 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }
  
  if (!data) {
    return null;
  }
  
  return (
    <div className="space-y-4">
      {/* Today's Focus - Main Recommendation */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-primary" />
              <CardTitle className="text-lg">Today's Focus</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <h3 className="font-semibold text-lg mb-1">
              {data.todays_focus?.title}
            </h3>
            <p className="text-sm text-muted-foreground mb-4">
              {data.todays_focus?.description}
            </p>
            <Button 
              onClick={() => handleAction(data.todays_focus?.type)}
              className="w-full"
            >
              Start Working on This
              <ChevronRight className="w-4 h-4 ml-2" />
            </Button>
          </CardContent>
        </Card>
      </motion.div>
      
      {/* Coach's Message */}
      {data.message && (
        <Card className="bg-muted/30">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-full bg-primary/20">
                <Brain className="w-4 h-4 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium">Your Coach Says:</p>
                <p className="text-sm text-muted-foreground mt-1">
                  "{data.message}"
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Improving Areas - Positive Reinforcement */}
      {data.improving_areas?.length > 0 && (
        <Card className="border-green-500/30 bg-green-500/5">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-green-400" />
              <span className="text-sm font-medium text-green-400">You're Improving!</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {data.improving_areas.map((area, i) => (
                <Badge 
                  key={i} 
                  variant="outline" 
                  className="bg-green-500/10 text-green-400 border-green-500/30"
                >
                  <Trophy className="w-3 h-3 mr-1" />
                  {area}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Focus Areas - Weaknesses */}
      {data.focus_areas?.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Target className="w-4 h-4" />
              Areas to Improve
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.focus_areas.map((area, i) => (
              <div 
                key={i}
                className="flex items-center justify-between p-2 rounded-lg bg-muted/30"
              >
                <div className="flex items-center gap-2">
                  <AlertTriangle className={`w-4 h-4 ${
                    area.priority === "high" ? "text-red-400" : "text-amber-400"
                  }`} />
                  <span className="text-sm">{area.area}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge 
                    variant="outline" 
                    className={`text-xs ${
                      area.priority === "high" 
                        ? "border-red-500/30 text-red-400" 
                        : "border-amber-500/30 text-amber-400"
                    }`}
                  >
                    {area.count}x
                  </Badge>
                  {area.improving && (
                    <TrendingUp className="w-3 h-3 text-green-400" />
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
      
      {/* Recommendations List */}
      {data.recommendations?.length > 1 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">More Recommendations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.recommendations.slice(1).map((rec, i) => (
              <div 
                key={i}
                className="flex items-center justify-between p-3 rounded-lg border border-border/50 hover:border-primary/30 cursor-pointer transition-colors"
                onClick={() => handleAction(rec.action)}
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${getPriorityColor(rec.priority)}`}>
                    {getTypeIcon(rec.type)}
                  </div>
                  <div>
                    <p className="text-sm font-medium">{rec.title}</p>
                    <p className="text-xs text-muted-foreground">{rec.description}</p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-muted-foreground" />
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default LearningPath;
