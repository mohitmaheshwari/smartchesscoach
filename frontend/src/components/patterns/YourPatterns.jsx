/**
 * YourPatterns.jsx - Dashboard Component for Pattern Memory
 * 
 * Shows user's top 3 recurring blind spots in a sharp, confrontational format.
 * 
 * Design Philosophy (from user):
 * - No progress bars, no graphs, no analytics-style UI
 * - Everything is a problem to fix
 * - Minimal, sharp, uncomfortable
 * - Every card has "Fix This" CTA
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, Target, ChevronRight, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { API } from "@/App";

const YourPatterns = ({ user }) => {
  const navigate = useNavigate();
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchPatterns();
  }, []);

  const fetchPatterns = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const res = await fetch(`${API}/coach/patterns/top?limit=3`, {
        credentials: "include"
      });
      
      if (res.ok) {
        const data = await res.json();
        setPatterns(data.patterns || []);
      } else {
        setError("Could not load patterns");
      }
    } catch (err) {
      console.error("Error fetching patterns:", err);
      setError("Could not load patterns");
    } finally {
      setLoading(false);
    }
  };

  const handleFixThis = (pattern) => {
    // Navigate to plateau breaker with focus on this pattern
    navigate("/plateau-breaker", {
      state: { focusPattern: pattern.pattern_type }
    });
  };

  if (loading) {
    return (
      <Card className="bg-card border-border" data-testid="your-patterns-loading">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold text-foreground flex items-center gap-2">
            <Target className="w-4 h-4 text-red-400" />
            Your Patterns
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-6">
            <RefreshCw className="w-5 h-5 text-muted-foreground animate-spin" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || patterns.length === 0) {
    return (
      <Card className="bg-card border-border" data-testid="your-patterns-empty">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold text-foreground flex items-center gap-2">
            <Target className="w-4 h-4 text-red-400" />
            Your Patterns
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground py-4">
            {error || "Not enough data yet. Play and analyze more games to reveal your patterns."}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card border-border" data-testid="your-patterns">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold text-foreground flex items-center gap-2">
          <Target className="w-4 h-4 text-red-400" />
          Your Patterns
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-1">
          These keep happening. Fix them.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {patterns.map((pattern, idx) => (
          <PatternCard 
            key={pattern.pattern_type} 
            pattern={pattern} 
            rank={idx + 1}
            onFixThis={() => handleFixThis(pattern)}
          />
        ))}
      </CardContent>
    </Card>
  );
};

/**
 * Individual pattern card - sharp, minimal, confrontational
 */
const PatternCard = ({ pattern, rank, onFixThis }) => {
  const { label, total_count, recent_count, recent_games, severity } = pattern;
  
  // Severity color mapping - all red-ish tones, nothing "green good"
  const severityColors = {
    critical: "border-red-500/50 bg-red-950/20",
    high: "border-orange-500/50 bg-orange-950/20",
    medium: "border-yellow-500/50 bg-yellow-950/20",
    low: "border-border bg-card"
  };
  
  const iconColors = {
    critical: "text-red-400",
    high: "text-orange-400",
    medium: "text-yellow-400",
    low: "text-muted-foreground"
  };

  return (
    <div 
      className={`rounded-lg border p-3 ${severityColors[severity] || severityColors.medium}`}
      data-testid={`pattern-card-${pattern.pattern_type}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <AlertCircle className={`w-4 h-4 flex-shrink-0 ${iconColors[severity]}`} />
            <span className="font-medium text-white text-sm truncate">
              {label}
            </span>
          </div>
          
          {/* Stats - sharp, direct */}
          <div className="space-y-0.5 ml-6">
            <p className="text-sm text-foreground">
              <span className="font-bold text-white">{recent_count}</span>
              <span className="text-muted-foreground"> times in last </span>
              <span className="text-foreground">{recent_games}</span>
              <span className="text-muted-foreground"> games</span>
            </p>
            {total_count > recent_count && (
              <p className="text-xs text-muted-foreground">
                {total_count} times overall
              </p>
            )}
          </div>
        </div>
        
        {/* CTA - always actionable */}
        <Button
          size="sm"
          variant="ghost"
          onClick={onFixThis}
          className="text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10 px-2 py-1 h-auto whitespace-nowrap"
          data-testid={`fix-this-btn-${pattern.pattern_type}`}
        >
          Fix This
          <ChevronRight className="w-3 h-3 ml-1" />
        </Button>
      </div>
    </div>
  );
};

export default YourPatterns;
