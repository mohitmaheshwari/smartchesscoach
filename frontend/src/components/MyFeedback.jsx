/**
 * MyFeedback - Shows user's submitted feedback and corrections
 * 
 * Displays:
 * - Feedback history
 * - Original explanation vs corrected explanation
 * - Status (pending, corrected, applied)
 */

import { useState, useEffect } from "react";
import { 
  ThumbsDown, 
  CheckCircle2, 
  Clock, 
  ChevronDown,
  ChevronUp,
  Lightbulb,
  ArrowRight
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const API = process.env.REACT_APP_BACKEND_URL;

export default function MyFeedback() {
  const [feedback, setFeedback] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    fetchFeedback();
  }, []);

  const fetchFeedback = async () => {
    try {
      const response = await fetch(`${API}/api/coach/pattern-learning/my-feedback`, {
        credentials: "include"
      });
      if (response.ok) {
        const data = await response.json();
        setFeedback(data.feedback || []);
      }
    } catch (error) {
      console.error("Failed to fetch feedback:", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (id) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const getStatusBadge = (status, hasCorrection) => {
    if (hasCorrection) {
      return (
        <span className="flex items-center gap-1 text-xs text-green-400 bg-green-500/10 px-2 py-0.5 rounded">
          <CheckCircle2 className="w-3 h-3" />
          Corrected
        </span>
      );
    }
    if (status === "pending") {
      return (
        <span className="flex items-center gap-1 text-xs text-yellow-400 bg-yellow-500/10 px-2 py-0.5 rounded">
          <Clock className="w-3 h-3" />
          Pending
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-xs text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded">
        Processing
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin h-6 w-6 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (feedback.length === 0) {
    return (
      <Card className="bg-slate-900/50 border-slate-800">
        <CardContent className="p-6 text-center">
          <ThumbsDown className="w-8 h-8 mx-auto mb-3 text-muted-foreground/40" />
          <p className="text-muted-foreground">No feedback submitted yet</p>
          <p className="text-sm text-muted-foreground/60 mt-1">
            When you see an incorrect explanation, click "Not helpful" to help improve the coach
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Your Feedback</h3>
        <span className="text-sm text-muted-foreground">{feedback.length} submissions</span>
      </div>

      {feedback.map((item) => (
        <Card 
          key={item.feedback_id} 
          className="bg-slate-900/50 border-slate-800 overflow-hidden"
        >
          <CardHeader 
            className="p-4 cursor-pointer hover:bg-slate-800/30 transition-colors"
            onClick={() => toggleExpand(item.feedback_id)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <ThumbsDown className="w-4 h-4 text-red-400" />
                <div>
                  <p className="text-sm font-medium">
                    Move {item.move_number}: {item.move_played} → {item.best_move}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {item.section_type?.replace(/_/g, ' ')} • {new Date(item.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {getStatusBadge(item.status, item.correction)}
                {expanded[item.feedback_id] ? (
                  <ChevronUp className="w-4 h-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                )}
              </div>
            </div>
          </CardHeader>

          {expanded[item.feedback_id] && (
            <CardContent className="p-4 pt-0 border-t border-slate-800 space-y-4">
              {/* Original explanation */}
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                <p className="text-xs text-red-400 font-medium mb-1">WRONG EXPLANATION</p>
                <p className="text-sm text-red-300">{item.system_explanation}</p>
              </div>

              {/* User's correction */}
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <p className="text-xs text-amber-400 font-medium mb-1 flex items-center gap-1">
                  <Lightbulb className="w-3 h-3" />
                  YOUR INSIGHT
                </p>
                <p className="text-sm text-amber-300">
                  {item.user_explanation || item.correct_classification || "No explanation provided"}
                </p>
              </div>

              {/* Corrected explanation */}
              {item.correction && (
                <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                  <p className="text-xs text-green-400 font-medium mb-1 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    CORRECTED EXPLANATION
                  </p>
                  <p className="text-sm text-green-300">{item.correction.corrected_explanation}</p>
                  {item.correction.user_insight_used && (
                    <p className="text-xs text-green-400/60 mt-2">
                      ✓ Your insight was incorporated
                    </p>
                  )}
                </div>
              )}

              {/* Position info */}
              <div className="flex items-center gap-4 text-xs text-muted-foreground pt-2 border-t border-slate-800">
                <span>Position: {item.position_fen?.slice(0, 30)}...</span>
                {item.game_id && (
                  <a 
                    href={`/lab/game/${item.game_id}`}
                    className="text-primary hover:underline"
                  >
                    View Game →
                  </a>
                )}
              </div>
            </CardContent>
          )}
        </Card>
      ))}
    </div>
  );
}
