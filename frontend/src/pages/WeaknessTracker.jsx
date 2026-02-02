import { useState, useEffect } from "react";
import { API } from "@/App";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import Layout from "@/components/Layout";
import { 
  Target, 
  TrendingUp, 
  AlertTriangle,
  Loader2,
  Calendar,
  Gamepad2
} from "lucide-react";

const WeaknessTracker = ({ user }) => {
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPatterns = async () => {
      try {
        const response = await fetch(`${API}/patterns`, {
          credentials: 'include'
        });
        if (response.ok) {
          const data = await response.json();
          setPatterns(data);
        }
      } catch (error) {
        console.error('Error fetching patterns:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchPatterns();
  }, []);

  const getCategoryColor = (category) => {
    const colors = {
      tactical: 'bg-red-500/10 text-red-500 border-red-500/20',
      positional: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
      endgame: 'bg-purple-500/10 text-purple-500 border-purple-500/20',
      opening: 'bg-green-500/10 text-green-500 border-green-500/20',
      time_management: 'bg-orange-500/10 text-orange-500 border-orange-500/20'
    };
    return colors[category] || 'bg-muted text-muted-foreground';
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    return `${Math.floor(diffDays / 30)} months ago`;
  };

  // Group patterns by category
  const groupedPatterns = patterns.reduce((acc, pattern) => {
    const cat = pattern.category || 'other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(pattern);
    return acc;
  }, {});

  const totalOccurrences = patterns.reduce((sum, p) => sum + p.occurrences, 0);

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
      <div className="space-y-8" data-testid="weakness-tracker-page">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">Weakness Tracker</h1>
          <p className="text-muted-foreground">
            Recurring patterns identified across your games
          </p>
        </div>

        {patterns.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-16 space-y-4">
              <Target className="w-12 h-12 text-muted-foreground" />
              <div className="text-center">
                <p className="font-medium">No patterns detected yet</p>
                <p className="text-sm text-muted-foreground">
                  Analyze more games to discover your recurring weaknesses
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Overview Stats */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Card data-testid="stat-total-patterns">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">Patterns Found</p>
                      <p className="text-3xl font-bold">{patterns.length}</p>
                    </div>
                    <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Target className="w-6 h-6 text-primary" />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card data-testid="stat-total-occurrences">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">Total Occurrences</p>
                      <p className="text-3xl font-bold text-red-500">{totalOccurrences}</p>
                    </div>
                    <div className="w-12 h-12 rounded-lg bg-red-500/10 flex items-center justify-center">
                      <AlertTriangle className="w-6 h-6 text-red-500" />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card data-testid="stat-categories">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">Categories</p>
                      <p className="text-3xl font-bold">{Object.keys(groupedPatterns).length}</p>
                    </div>
                    <div className="w-12 h-12 rounded-lg bg-blue-500/10 flex items-center justify-center">
                      <TrendingUp className="w-6 h-6 text-blue-500" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Patterns by Category */}
            <div className="space-y-6">
              {Object.entries(groupedPatterns).map(([category, categoryPatterns]) => (
                <div key={category} className="space-y-4">
                  <div className="flex items-center gap-2">
                    <Badge 
                      variant="outline" 
                      className={`${getCategoryColor(category)} capitalize`}
                    >
                      {category.replace(/_/g, ' ')}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      {categoryPatterns.length} pattern{categoryPatterns.length > 1 ? 's' : ''}
                    </span>
                  </div>

                  <div className="grid gap-4">
                    {categoryPatterns.sort((a, b) => b.occurrences - a.occurrences).map((pattern) => (
                      <Card 
                        key={pattern.pattern_id}
                        data-testid={`pattern-card-${pattern.pattern_id}`}
                      >
                        <CardContent className="pt-6">
                          <div className="space-y-4">
                            <div className="flex items-start justify-between">
                              <div>
                                <h3 className="font-semibold capitalize">
                                  {pattern.subcategory.replace(/_/g, ' ')}
                                </h3>
                                <p className="text-sm text-muted-foreground mt-1">
                                  {pattern.description}
                                </p>
                              </div>
                              <div className="text-right">
                                <p className="text-2xl font-bold text-red-500">
                                  {pattern.occurrences}
                                </p>
                                <p className="text-xs text-muted-foreground">occurrences</p>
                              </div>
                            </div>

                            <div className="flex items-center justify-between text-sm">
                              <div className="flex items-center gap-4">
                                <div className="flex items-center gap-1 text-muted-foreground">
                                  <Calendar className="w-4 h-4" />
                                  <span>First seen: {formatDate(pattern.first_seen)}</span>
                                </div>
                                <div className="flex items-center gap-1 text-muted-foreground">
                                  <Gamepad2 className="w-4 h-4" />
                                  <span>{pattern.game_ids?.length || 0} games</span>
                                </div>
                              </div>
                              <span className="text-xs text-muted-foreground">
                                Last: {formatDate(pattern.last_seen)}
                              </span>
                            </div>

                            <Progress 
                              value={Math.min(pattern.occurrences * 10, 100)} 
                              className="h-2"
                            />
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </Layout>
  );
};

export default WeaknessTracker;
