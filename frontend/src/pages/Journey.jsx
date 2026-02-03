import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import Layout from "@/components/Layout";
import { toast } from "sonner";
import { 
  Loader2, 
  Brain,
  TrendingUp,
  TrendingDown,
  Minus,
  CheckCircle2,
  AlertCircle,
  Link as LinkIcon,
  Sparkles
} from "lucide-react";

const Journey = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [linkedAccounts, setLinkedAccounts] = useState({ chess_com: null, lichess: null });
  const [linkingPlatform, setLinkingPlatform] = useState(null);
  const [linkUsername, setLinkUsername] = useState("");
  const [isLinking, setIsLinking] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch linked accounts
        const accountsRes = await fetch(API + "/journey/linked-accounts", { credentials: "include" });
        if (accountsRes.ok) {
          const accounts = await accountsRes.json();
          setLinkedAccounts(accounts);
        }

        // Fetch journey dashboard
        const dashRes = await fetch(API + "/journey", { credentials: "include" });
        if (dashRes.ok) {
          const data = await dashRes.json();
          setDashboard(data);
        }
      } catch (error) {
        console.error("Error loading journey:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleLinkAccount = async () => {
    if (!linkUsername.trim()) {
      toast.error("Please enter a username");
      return;
    }

    setIsLinking(true);
    try {
      const response = await fetch(API + "/journey/link-account", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          platform: linkingPlatform,
          username: linkUsername.trim()
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to link account");
      }

      const data = await response.json();
      toast.success(data.message);
      
      // Update linked accounts
      if (linkingPlatform === "chess.com") {
        setLinkedAccounts(prev => ({ ...prev, chess_com: linkUsername }));
      } else {
        setLinkedAccounts(prev => ({ ...prev, lichess: linkUsername }));
      }
      
      setLinkingPlatform(null);
      setLinkUsername("");
      
      // Refresh dashboard
      const dashRes = await fetch(API + "/journey", { credentials: "include" });
      if (dashRes.ok) setDashboard(await dashRes.json());
      
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsLinking(false);
    }
  };

  const getTrendIcon = (trend) => {
    if (trend === "improving") return <TrendingDown className="w-4 h-4 text-emerald-500" />;
    if (trend === "worsening") return <TrendingUp className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-muted-foreground" />;
  };

  const getTrendLabel = (trend) => {
    if (trend === "improving") return "Improving";
    if (trend === "worsening") return "Needs work";
    return "Stable";
  };

  const getStatusBadge = (status) => {
    if (status === "improving") {
      return <Badge className="bg-emerald-500/20 text-emerald-600 border-0">Improving</Badge>;
    }
    if (status === "needs_attention") {
      return <Badge className="bg-red-500/20 text-red-600 border-0">Focus here</Badge>;
    }
    return <Badge className="bg-blue-500/20 text-blue-600 border-0">Stable</Badge>;
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

  const hasLinkedAccount = linkedAccounts.chess_com || linkedAccounts.lichess;
  const gamesAnalyzed = dashboard ? dashboard.games_analyzed : 0;

  return (
    <Layout user={user}>
      <div className="space-y-6" data-testid="journey-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Your Journey</h1>
            <p className="text-sm text-muted-foreground">
              Track your learning progress over time
            </p>
          </div>
          {gamesAnalyzed > 0 && (
            <Badge variant="outline" className="text-xs">
              {gamesAnalyzed} games analyzed
            </Badge>
          )}
        </div>

        {/* Link Accounts Section (if none linked) */}
        {!hasLinkedAccount && (
          <Card className="border-dashed border-2">
            <CardContent className="py-8">
              <div className="text-center space-y-4">
                <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                  <LinkIcon className="w-8 h-8 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg">Connect Your Chess Account</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    Link your Chess.com or Lichess account to start automatic coaching
                  </p>
                </div>
                <div className="flex justify-center gap-3">
                  <Button onClick={() => setLinkingPlatform("chess.com")} variant="outline">
                    Chess.com
                  </Button>
                  <Button onClick={() => setLinkingPlatform("lichess")} variant="outline">
                    Lichess
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Link Account Dialog */}
        {linkingPlatform && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Link {linkingPlatform}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input
                placeholder={`Enter your ${linkingPlatform} username`}
                value={linkUsername}
                onChange={(e) => setLinkUsername(e.target.value)}
                disabled={isLinking}
              />
              <div className="flex gap-2">
                <Button onClick={handleLinkAccount} disabled={isLinking}>
                  {isLinking ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                  Link Account
                </Button>
                <Button variant="ghost" onClick={() => setLinkingPlatform(null)}>
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Onboarding Message (0-4 games) */}
        {dashboard && dashboard.mode === "onboarding" && (
          <Card className="bg-primary/5 border-primary/20">
            <CardContent className="py-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                  <Brain className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold">Getting to Know Your Game</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    {dashboard.weekly_assessment}
                  </p>
                  {hasLinkedAccount && (
                    <p className="text-xs text-muted-foreground mt-3">
                      Your games are being analyzed automatically. Check back soon.
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Main Dashboard (5+ games) */}
        {dashboard && dashboard.mode !== "onboarding" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Coach's Weekly Assessment */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Brain className="w-5 h-5 text-primary" />
                  Coach&apos;s Assessment
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground leading-relaxed">
                  {dashboard.weekly_assessment}
                </p>
              </CardContent>
            </Card>

            {/* Current Focus Areas */}
            {dashboard.focus_areas && dashboard.focus_areas.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Focus Areas This Week</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {dashboard.focus_areas.map((area, i) => (
                      <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                        <div>
                          <p className="font-medium capitalize">{area.name}</p>
                          <p className="text-xs text-muted-foreground capitalize">{area.category}</p>
                        </div>
                        {getStatusBadge(area.status)}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Weakness Trends */}
            {dashboard.weakness_trends && dashboard.weakness_trends.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Habit Trends</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {dashboard.weakness_trends.map((trend, i) => (
                      <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                        <div className="flex-1">
                          <p className="font-medium capitalize">{trend.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {trend.occurrences_recent} recent vs {trend.occurrences_previous} before
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {getTrendIcon(trend.trend)}
                          <span className={`text-xs ${
                            trend.trend === "improving" ? "text-emerald-500" :
                            trend.trend === "worsening" ? "text-red-500" : "text-muted-foreground"
                          }`}>
                            {getTrendLabel(trend.trend)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Resolved Habits */}
            {dashboard.resolved_habits && dashboard.resolved_habits.length > 0 && (
              <Card className="bg-emerald-500/5 border-emerald-500/20">
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    Resolved Habits
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {dashboard.resolved_habits.map((habit, i) => (
                      <p key={i} className="text-sm text-muted-foreground">
                        {habit.message}
                      </p>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Strengths */}
            {dashboard.strengths && dashboard.strengths.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-amber-500" />
                    Your Strengths
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {dashboard.strengths.map((strength, i) => (
                      <Badge key={i} variant="outline" className="capitalize">
                        {strength.name}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* Linked Accounts (if any) */}
        {hasLinkedAccount && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground">Linked Accounts</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4 text-sm">
                {linkedAccounts.chess_com && (
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    <span>Chess.com: {linkedAccounts.chess_com}</span>
                  </div>
                )}
                {linkedAccounts.lichess && (
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    <span>Lichess: {linkedAccounts.lichess}</span>
                  </div>
                )}
                {!linkedAccounts.chess_com && (
                  <Button variant="ghost" size="sm" onClick={() => setLinkingPlatform("chess.com")}>
                    + Add Chess.com
                  </Button>
                )}
                {!linkedAccounts.lichess && (
                  <Button variant="ghost" size="sm" onClick={() => setLinkingPlatform("lichess")}>
                    + Add Lichess
                  </Button>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-3">
                Your games are analyzed automatically. No action needed.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default Journey;
