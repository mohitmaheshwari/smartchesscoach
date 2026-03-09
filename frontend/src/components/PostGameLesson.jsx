/**
 * PostGameLesson.jsx - Post-Game Teaching Summary
 * 
 * Shows a structured lesson summary after the game ends:
 * - Result and congratulations/encouragement
 * - Concepts that were taught
 * - Good moments and learning opportunities
 * - Key takeaways
 * - Opening played
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Trophy,
  Target,
  Lightbulb,
  BookOpen,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
  Star,
  TrendingUp,
  Award
} from "lucide-react";

/**
 * Result Banner - Shows win/loss/draw with appropriate styling
 */
const ResultBanner = ({ result }) => {
  const config = {
    win: {
      icon: Trophy,
      text: "Victory!",
      bgColor: "bg-green-500/20",
      borderColor: "border-green-500/30",
      textColor: "text-green-400"
    },
    loss: {
      icon: Target,
      text: "Good effort!",
      bgColor: "bg-orange-500/20",
      borderColor: "border-orange-500/30",
      textColor: "text-orange-400"
    },
    draw: {
      icon: Award,
      text: "Draw!",
      bgColor: "bg-blue-500/20",
      borderColor: "border-blue-500/30",
      textColor: "text-blue-400"
    }
  };

  const { icon: Icon, text, bgColor, borderColor, textColor } = config[result] || config.draw;

  return (
    <div className={`flex items-center gap-3 p-4 rounded-lg ${bgColor} border ${borderColor}`}>
      <Icon className={`w-8 h-8 ${textColor}`} />
      <div>
        <h3 className={`text-xl font-bold ${textColor}`}>{text}</h3>
        <p className="text-sm text-muted-foreground">
          {result === "win" ? "Great game!" : result === "loss" ? "Every game makes you stronger." : "Well fought!"}
        </p>
      </div>
    </div>
  );
};

/**
 * Takeaway Card - Shows a key lesson from the game
 */
const TakeawayCard = ({ takeaway, index }) => {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-card/50 border border-border">
      <div className="flex items-center justify-center w-6 h-6 rounded-full bg-primary/20 text-primary text-xs font-bold">
        {index + 1}
      </div>
      <p className="text-sm flex-1">{takeaway}</p>
    </div>
  );
};

/**
 * Main PostGameLesson Component
 */
const PostGameLesson = ({ 
  sessionId,
  result,
  studentColor,
  moves,
  onPlayAgain,
  onClose 
}) => {
  const [lesson, setLesson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchLesson();
  }, [sessionId]);

  const fetchLesson = async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch the game summary from the API
      const response = await fetch(`${API}/coach/teaching/game-summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          result: result,
          student_color: studentColor,
          moves: moves || [],
          concepts_taught: [], // Would be populated from session
          mistakes: [],
          good_moves: [],
          user_rating: 1200
        })
      });

      if (response.ok) {
        const data = await response.json();
        setLesson(data);
      } else {
        setError("Failed to load lesson");
      }
    } catch (err) {
      console.error("Lesson fetch error:", err);
      setError("Failed to load lesson");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="w-full max-w-lg mx-auto">
        <CardContent className="p-6 text-center">
          <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-muted-foreground">Preparing your lesson...</p>
        </CardContent>
      </Card>
    );
  }

  if (error || !lesson) {
    return (
      <Card className="w-full max-w-lg mx-auto">
        <CardContent className="p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-orange-400 mx-auto mb-4" />
          <p className="text-muted-foreground">{error || "No lesson available"}</p>
          <Button onClick={onPlayAgain} className="mt-4">
            Play Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-lg mx-auto border-primary/20" data-testid="post-game-lesson">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <BookOpen className="w-5 h-5 text-primary" />
          Game Lesson
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Result Banner */}
        <ResultBanner result={lesson.result_for_student} />

        {/* Summary */}
        <div className="p-4 rounded-lg bg-muted/30">
          <p className="text-sm leading-relaxed">{lesson.summary}</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3">
          {lesson.good_moments > 0 && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
              <Star className="w-4 h-4 text-green-400" />
              <div>
                <div className="text-lg font-bold text-green-400">{lesson.good_moments}</div>
                <div className="text-xs text-muted-foreground">Great moves</div>
              </div>
            </div>
          )}
          {lesson.learning_opportunities > 0 && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-orange-500/10 border border-orange-500/20">
              <TrendingUp className="w-4 h-4 text-orange-400" />
              <div>
                <div className="text-lg font-bold text-orange-400">{lesson.learning_opportunities}</div>
                <div className="text-xs text-muted-foreground">Learning moments</div>
              </div>
            </div>
          )}
        </div>

        {/* Opening */}
        {lesson.opening_played && (
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Opening played:</span>
            <Badge variant="secondary">{lesson.opening_played}</Badge>
          </div>
        )}

        {/* Concepts Covered */}
        {lesson.concepts_covered?.length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-primary" />
              Concepts Covered
            </h4>
            <div className="flex flex-wrap gap-2">
              {lesson.concepts_covered.map((concept, i) => (
                <Badge key={i} variant="outline" className="capitalize">
                  {concept.replace(/_/g, " ")}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Key Takeaways */}
        {lesson.key_takeaways?.length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
              <Lightbulb className="w-4 h-4 text-primary" />
              Key Takeaways
            </h4>
            <div className="space-y-2">
              {lesson.key_takeaways.map((takeaway, i) => (
                <TakeawayCard key={i} takeaway={takeaway} index={i} />
              ))}
            </div>
          </div>
        )}
      </CardContent>

      <CardFooter className="flex gap-2 pt-4">
        <Button onClick={onPlayAgain} className="flex-1" data-testid="play-again-btn">
          Play Again
          <ChevronRight className="w-4 h-4 ml-1" />
        </Button>
        {onClose && (
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        )}
      </CardFooter>
    </Card>
  );
};

export default PostGameLesson;
