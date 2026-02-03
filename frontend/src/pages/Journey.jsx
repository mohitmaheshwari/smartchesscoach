import { useState, useEffect } from "react";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import Layout from "@/components/Layout";
import { toast } from "sonner";
import { Loader2, Brain, TrendingUp, TrendingDown, Minus, CheckCircle2, Sparkles, RefreshCw } from "lucide-react";

const Journey = ({ user }) => {
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [accounts, setAccounts] = useState({ chess_com: null, lichess: null });
  const [platform, setPlatform] = useState(null);
  const [username, setUsername] = useState("");
  const [linking, setLinking] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const res1 = await fetch(API + "/journey/linked-accounts", { credentials: "include" });
      if (res1.ok) setAccounts(await res1.json());
      
      const res2 = await fetch(API + "/journey", { credentials: "include" });
      if (res2.ok) setDashboard(await res2.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const linkAccount = async () => {
    if (!username.trim()) return toast.error("Enter username");
    setLinking(true);
    try {
      const res = await fetch(API + "/journey/link-account", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ platform: platform, username: username.trim() })
      });
      if (!res.ok) throw new Error((await res.json()).detail);
      toast.success("Account linked!");
      setPlatform(null);
      setUsername("");
      fetchDashboard();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLinking(false);
    }
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
      </Layout>
    );
  }

  const hasAccount = accounts.chess_com || accounts.lichess;
  const games = dashboard ? dashboard.games_analyzed : 0;
  const mode = dashboard ? dashboard.mode : "onboarding";

  return (
    <Layout user={user}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Your Journey</h1>
            <p className="text-sm text-muted-foreground">Track learning progress</p>
          </div>
          {games > 0 && <Badge variant="outline">{games} games</Badge>}
        </div>

        {!hasAccount && (
          <Card className="border-dashed border-2">
            <CardContent className="py-8 text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                <Brain className="w-8 h-8 text-primary" />
              </div>
              <h3 className="font-semibold text-lg">Connect Chess Account</h3>
              <p className="text-sm text-muted-foreground">Link to start automatic coaching</p>
              <div className="flex justify-center gap-3">
                <Button onClick={() => setPlatform("chess.com")} variant="outline">Chess.com</Button>
                <Button onClick={() => setPlatform("lichess")} variant="outline">Lichess</Button>
              </div>
            </CardContent>
          </Card>
        )}

        {platform && (
          <Card>
            <CardHeader><CardTitle>Link {platform}</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <Input
                placeholder={"Enter " + platform + " username"}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={linking}
              />
              <div className="flex gap-2">
                <Button onClick={linkAccount} disabled={linking}>
                  {linking && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                  Link
                </Button>
                <Button variant="ghost" onClick={() => setPlatform(null)}>Cancel</Button>
              </div>
            </CardContent>
          </Card>
        )}

        {mode === "onboarding" && (
          <Card className="bg-primary/5 border-primary/20">
            <CardContent className="py-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center">
                  <Brain className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold">Getting to Know Your Game</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    {dashboard ? dashboard.weekly_assessment : "Play some games to get started."}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {mode !== "onboarding" && dashboard && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Brain className="w-5 h-5 text-primary" />
                  Coach Assessment
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">{dashboard.weekly_assessment}</p>
              </CardContent>
            </Card>

            {dashboard.focus_areas && dashboard.focus_areas.length > 0 && (
              <Card>
                <CardHeader><CardTitle>Focus Areas</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {dashboard.focus_areas.map((area, i) => (
                      <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                        <div>
                          <p className="font-medium capitalize">{area.name}</p>
                          <p className="text-xs text-muted-foreground capitalize">{area.category}</p>
                        </div>
                        <Badge className={
                          area.status === "improving" ? "bg-emerald-500/20 text-emerald-600 border-0" :
                          area.status === "needs_attention" ? "bg-red-500/20 text-red-600 border-0" :
                          "bg-blue-500/20 text-blue-600 border-0"
                        }>
                          {area.status === "improving" ? "Improving" : area.status === "needs_attention" ? "Focus" : "Stable"}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {dashboard.weakness_trends && dashboard.weakness_trends.length > 0 && (
              <Card>
                <CardHeader><CardTitle>Habit Trends</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {dashboard.weakness_trends.map((t, i) => (
                      <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                        <div>
                          <p className="font-medium capitalize">{t.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {t.occurrences_recent} recent vs {t.occurrences_previous} before
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {t.trend === "improving" && <TrendingDown className="w-4 h-4 text-emerald-500" />}
                          {t.trend === "worsening" && <TrendingUp className="w-4 h-4 text-red-500" />}
                          {t.trend === "stable" && <Minus className="w-4 h-4 text-muted-foreground" />}
                          <span className={
                            t.trend === "improving" ? "text-xs text-emerald-500" :
                            t.trend === "worsening" ? "text-xs text-red-500" :
                            "text-xs text-muted-foreground"
                          }>
                            {t.trend === "improving" ? "Better" : t.trend === "worsening" ? "Work on" : "Steady"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {dashboard.resolved_habits && dashboard.resolved_habits.length > 0 && (
              <Card className="bg-emerald-500/5 border-emerald-500/20">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    Resolved
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {dashboard.resolved_habits.map((h, i) => (
                    <p key={i} className="text-sm text-muted-foreground">{h.message}</p>
                  ))}
                </CardContent>
              </Card>
            )}

            {dashboard.strengths && dashboard.strengths.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-amber-500" />
                    Strengths
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {dashboard.strengths.map((s, i) => (
                      <Badge key={i} variant="outline" className="capitalize">{s.name}</Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {hasAccount && (
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex gap-4 text-sm flex-wrap">
                    {accounts.chess_com && (
                      <span className="flex items-center gap-1">
                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                        Chess.com: {accounts.chess_com}
                      </span>
                    )}
                    {accounts.lichess && (
                      <span className="flex items-center gap-1">
                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                        Lichess: {accounts.lichess}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">Games sync automatically every 6 hours</p>
                </div>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={syncNow}
                  disabled={syncing}
                  data-testid="sync-now-btn"
                >
                  {syncing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <RefreshCw className="w-4 h-4 mr-2" />}
                  Sync Now
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default Journey;
