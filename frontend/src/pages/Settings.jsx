import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import Layout from "@/components/Layout";
import { useTheme } from "@/context/ThemeContext";
import { toast } from "sonner";
import { 
  Sun, 
  Moon, 
  LogOut,
  User,
  Palette,
  Mail,
  Loader2,
  Send
} from "lucide-react";

const Settings = ({ user }) => {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [loggingOut, setLoggingOut] = useState(false);
  const [emailSettings, setEmailSettings] = useState({
    game_analyzed: true,
    weekly_summary: true,
    weakness_alert: true
  });
  const [loadingEmail, setLoadingEmail] = useState(true);
  const [savingEmail, setSavingEmail] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);

  useEffect(() => {
    fetchEmailSettings();
  }, []);

  const fetchEmailSettings = async () => {
    try {
      const res = await fetch(API + "/settings/email-notifications", {
        credentials: "include"
      });
      if (res.ok) {
        const data = await res.json();
        setEmailSettings(data.notifications);
      }
    } catch (e) {
      console.error("Failed to fetch email settings:", e);
    } finally {
      setLoadingEmail(false);
    }
  };

  const updateEmailSetting = async (key, value) => {
    const newSettings = { ...emailSettings, [key]: value };
    setEmailSettings(newSettings);
    setSavingEmail(true);
    
    try {
      const res = await fetch(API + "/settings/email-notifications", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(newSettings)
      });
      if (res.ok) {
        toast.success("Email preferences saved");
      } else {
        throw new Error("Failed to save");
      }
    } catch (e) {
      toast.error("Failed to save email preferences");
      setEmailSettings(prev => ({ ...prev, [key]: !value }));
    } finally {
      setSavingEmail(false);
    }
  };

  const sendTestEmail = async () => {
    setSendingTest(true);
    try {
      const res = await fetch(API + "/settings/test-email", {
        method: "POST",
        credentials: "include"
      });
      if (res.ok) {
        toast.success("Test email sent! Check your inbox.");
      } else {
        const data = await res.json();
        toast.error(data.detail || "Failed to send test email");
      }
    } catch (e) {
      toast.error("Failed to send test email");
    } finally {
      setSendingTest(false);
    }
  };

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await fetch(`${API}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
      toast.success('Logged out successfully');
      navigate('/');
    } catch (error) {
      toast.error('Failed to logout');
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <Layout user={user}>
      <div className="space-y-8 max-w-2xl" data-testid="settings-page">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">
            Manage your account and preferences
          </p>
        </div>

        {/* Profile Card */}
        <Card data-testid="profile-card">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <User className="w-5 h-5" />
              Profile
            </CardTitle>
            <CardDescription>Your account information</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <Avatar className="w-16 h-16">
                <AvatarImage src={user?.picture} alt={user?.name} />
                <AvatarFallback className="text-lg">
                  {user?.name?.charAt(0) || 'U'}
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="font-semibold text-lg">{user?.name}</p>
                <p className="text-sm text-muted-foreground">{user?.email}</p>
              </div>
            </div>

            <Separator className="my-6" />

            <div className="space-y-4">
              {user?.chess_com_username && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Chess.com</span>
                  <span className="font-medium">{user.chess_com_username}</span>
                </div>
              )}
              {user?.lichess_username && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Lichess</span>
                  <span className="font-medium">{user.lichess_username}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Email Notifications Card */}
        <Card data-testid="email-notifications-card">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Mail className="w-5 h-5" />
              Email Notifications
            </CardTitle>
            <CardDescription>Choose what emails you receive</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {loadingEmail ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-5 h-5 animate-spin" />
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="email-game-analyzed">Game Analyzed</Label>
                    <p className="text-sm text-muted-foreground">
                      Get notified when new games are analyzed
                    </p>
                  </div>
                  <Switch
                    id="email-game-analyzed"
                    checked={emailSettings.game_analyzed}
                    onCheckedChange={(v) => updateEmailSetting("game_analyzed", v)}
                    disabled={savingEmail}
                    data-testid="email-game-analyzed-switch"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="email-weekly-summary">Weekly Summary</Label>
                    <p className="text-sm text-muted-foreground">
                      Receive a weekly progress report
                    </p>
                  </div>
                  <Switch
                    id="email-weekly-summary"
                    checked={emailSettings.weekly_summary}
                    onCheckedChange={(v) => updateEmailSetting("weekly_summary", v)}
                    disabled={savingEmail}
                    data-testid="email-weekly-summary-switch"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="email-weakness-alert">Weakness Alerts</Label>
                    <p className="text-sm text-muted-foreground">
                      Get alerted when recurring patterns are detected
                    </p>
                  </div>
                  <Switch
                    id="email-weakness-alert"
                    checked={emailSettings.weakness_alert}
                    onCheckedChange={(v) => updateEmailSetting("weakness_alert", v)}
                    disabled={savingEmail}
                    data-testid="email-weakness-alert-switch"
                  />
                </div>

                <Separator />

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Test Email</p>
                    <p className="text-sm text-muted-foreground">
                      Send a test email to verify your settings
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={sendTestEmail}
                    disabled={sendingTest}
                    data-testid="send-test-email-btn"
                  >
                    {sendingTest ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Send className="w-4 h-4 mr-2" />
                    )}
                    Send Test
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Appearance Card */}
        <Card data-testid="appearance-card">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Palette className="w-5 h-5" />
              Appearance
            </CardTitle>
            <CardDescription>Customize how the app looks</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {theme === 'dark' ? (
                  <Moon className="w-5 h-5" />
                ) : (
                  <Sun className="w-5 h-5" />
                )}
                <div>
                  <Label htmlFor="theme-toggle">Dark Mode</Label>
                  <p className="text-sm text-muted-foreground">
                    Switch between light and dark themes
                  </p>
                </div>
              </div>
              <Switch
                id="theme-toggle"
                checked={theme === 'dark'}
                onCheckedChange={toggleTheme}
                data-testid="theme-switch"
              />
            </div>
          </CardContent>
        </Card>

        {/* Logout Card */}
        <Card className="border-destructive/50" data-testid="logout-card">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2 text-destructive">
              <LogOut className="w-5 h-5" />
              Sign Out
            </CardTitle>
            <CardDescription>End your current session</CardDescription>
          </CardHeader>
          <CardContent>
            <Button 
              variant="destructive" 
              onClick={handleLogout}
              disabled={loggingOut}
              data-testid="logout-button"
            >
              {loggingOut ? 'Signing out...' : 'Sign Out'}
            </Button>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default Settings;
