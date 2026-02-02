import { useState } from "react";
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
  Palette
} from "lucide-react";

const Settings = ({ user }) => {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [loggingOut, setLoggingOut] = useState(false);

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
