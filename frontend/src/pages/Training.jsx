import { useState, useEffect } from "react";
import { API } from "@/App";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Layout from "@/components/Layout";
import { 
  Target, 
  Clock,
  Loader2,
  RefreshCw,
  CheckCircle2,
  Circle
} from "lucide-react";

const Training = ({ user }) => {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [completed, setCompleted] = useState(new Set());

  const fetchRecommendations = async () => {
    try {
      const response = await fetch(`${API}/training-recommendations`, {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setRecommendations(data.recommendations || []);
      }
    } catch (error) {
      console.error('Error fetching recommendations:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchRecommendations();
  };

  const toggleComplete = (index) => {
    setCompleted(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const getPriorityColor = (priority) => {
    switch (priority?.toLowerCase()) {
      case 'high': return 'bg-red-500/10 text-red-500 border-red-500/20';
      case 'medium': return 'bg-orange-500/10 text-orange-500 border-orange-500/20';
      case 'low': return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
      default: return 'bg-muted text-muted-foreground';
    }
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="space-y-8" data-testid="training-page">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-tight">Training Plan</h1>
            <p className="text-muted-foreground">
              AI-generated exercises based on your weaknesses
            </p>
          </div>
          <Button 
            variant="outline" 
            onClick={handleRefresh}
            disabled={refreshing}
            data-testid="refresh-button"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {/* Progress Overview */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                  <Target className="w-8 h-8 text-primary" />
                </div>
                <div>
                  <p className="text-2xl font-bold">
                    {completed.size} / {recommendations.length}
                  </p>
                  <p className="text-sm text-muted-foreground">exercises completed today</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Total time</p>
                <p className="text-lg font-semibold">
                  {recommendations.reduce((acc, r) => {
                    const time = parseInt(r.estimated_time) || 15;
                    return acc + time;
                  }, 0)} mins
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Recommendations List */}
        <div className="space-y-4">
          {recommendations.map((rec, index) => (
            <Card 
              key={index}
              className={`transition-all ${completed.has(index) ? 'opacity-60' : ''}`}
              data-testid={`training-card-${index}`}
            >
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <button
                    onClick={() => toggleComplete(index)}
                    className="mt-1 flex-shrink-0"
                    data-testid={`complete-btn-${index}`}
                  >
                    {completed.has(index) ? (
                      <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                    ) : (
                      <Circle className="w-6 h-6 text-muted-foreground hover:text-primary transition-colors" />
                    )}
                  </button>
                  
                  <div className="flex-1 space-y-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className={`font-semibold ${completed.has(index) ? 'line-through' : ''}`}>
                          {rec.title}
                        </h3>
                        <p className="text-sm text-muted-foreground mt-1">
                          {rec.description}
                        </p>
                      </div>
                      <Badge 
                        variant="outline" 
                        className={`${getPriorityColor(rec.priority)} capitalize ml-4`}
                      >
                        {rec.priority || 'medium'}
                      </Badge>
                    </div>
                    
                    {rec.estimated_time && (
                      <div className="flex items-center gap-1 text-sm text-muted-foreground">
                        <Clock className="w-4 h-4" />
                        <span>{rec.estimated_time}</span>
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {recommendations.length === 0 && (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-16 space-y-4">
              <Target className="w-12 h-12 text-muted-foreground" />
              <div className="text-center">
                <p className="font-medium">No training recommendations yet</p>
                <p className="text-sm text-muted-foreground">
                  Import and analyze more games to get personalized training
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default Training;
