import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTheme } from "@/context/ThemeContext";
import { 
  Home,
  FlaskConical,
  Target, 
  TrendingUp,
  Settings,
  Sun,
  Moon,
  LogOut,
  Menu,
  X,
  Bell,
  CheckCheck,
  Brain,
  Swords,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Zap,
  BookOpen
} from "lucide-react";
import { useState, useEffect } from "react";
import { API } from "@/App";

const Layout = ({ children, user }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [prevUnreadCount, setPrevUnreadCount] = useState(0);
  
  // Coach Pulse state
  const [coachPulse, setCoachPulse] = useState(null);
  
  // Loss streak state for Plateau Breaker
  const [lossStreak, setLossStreak] = useState({ show: false, count: 0 });

  // Fetch coach pulse status and loss streak
  useEffect(() => {
    const fetchCoachPulse = async () => {
      try {
        // Check loss streak first (highest priority)
        const streakRes = await fetch(`${API}/loss-streak-status`, { credentials: 'include' });
        if (streakRes.ok) {
          const streakData = await streakRes.json();
          setLossStreak({ 
            show: streakData.show_plateau_breaker, 
            count: streakData.consecutive_losses,
            message: streakData.message
          });
          
          // If on losing streak, that becomes the coach pulse
          if (streakData.show_plateau_breaker) {
            setCoachPulse({ 
              type: "losing_streak", 
              count: streakData.consecutive_losses, 
              label: `${streakData.consecutive_losses} losses in a row` 
            });
            return;
          }
        }
        
        const reflectRes = await fetch(`${API}/reflect/pending/count`, { credentials: 'include' });
        if (reflectRes.ok) {
          const data = await reflectRes.json();
          if (data.count > 0) {
            setCoachPulse({ type: "reflect", count: data.count, label: "Reflect on recent games" });
            return;
          }
        }
        
        const lossRes = await fetch(`${API}/coach/fresh-loss`, { credentials: 'include' });
        if (lossRes.ok) {
          const data = await lossRes.json();
          if (data.has_fresh_loss) {
            setCoachPulse({ type: "loss", count: 1, label: "Fix your last loss", game_id: data.game_id });
            return;
          }
        }
        
        setCoachPulse(null);
      } catch (e) {
        // Silently fail
      }
    };
    
    fetchCoachPulse();
    const interval = setInterval(fetchCoachPulse, 60000);
    return () => clearInterval(interval);
  }, []);

  const handleCoachPulseClick = () => {
    if (coachPulse?.type === "losing_streak") {
      navigate("/plateau-breaker");
    } else if (coachPulse?.type === "loss" && coachPulse?.game_id) {
      navigate(`/recover/${coachPulse.game_id}`);
    } else {
      // Navigate to Lab (game review list) instead of Reflect
      navigate("/lab");
    }
  };

  // Request browser notification permission
  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      // Will request on first interaction
    }
  }, []);

  // Show browser notification
  const showBrowserNotification = (notif) => {
    if (Notification.permission === "granted") {
      const notification = new Notification(notif.title || "Chess Coach", {
        body: notif.message,
        icon: "/logo192.png",
        tag: "chess-coach-" + (notif.id || Date.now())
      });
      
      notification.onclick = () => {
        window.focus();
        if (notif.action_url) {
          navigate(notif.action_url);
        }
        notification.close();
      };
    }
  };

  // Fetch notifications
  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        const res = await fetch(`${API}/notifications?limit=10`, { credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          const newNotifications = data.notifications || [];
          const newUnread = data.unread_count || 0;
          
          if (newUnread > prevUnreadCount && newNotifications.length > 0) {
            const newest = newNotifications.find(n => !n.read);
            if (newest) {
              showBrowserNotification(newest);
            }
          }
          
          setNotifications(newNotifications);
          setUnreadCount(newUnread);
          setPrevUnreadCount(newUnread);
        }
      } catch (e) {
        console.error('Failed to fetch notifications:', e);
      }
    };
    
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [prevUnreadCount]);

  const markAllRead = async () => {
    try {
      await fetch(`${API}/notifications/read`, { 
        method: 'POST', 
        credentials: 'include' 
      });
      setUnreadCount(0);
      setPrevUnreadCount(0);
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch (e) {
      console.error('Failed to mark notifications read:', e);
    }
  };

  const navigation = [
    { name: 'Home', href: '/home', icon: Home },
    { name: 'Lab', href: '/lab', icon: FlaskConical },
    { name: 'Openings', href: '/openings-overview', icon: BookOpen },
    { name: 'Progress', href: '/progress', icon: TrendingUp },
  ];

  const isAdmin = user?.role === 'super_admin' || user?.role === 'admin';

  const isActive = (href) => location.pathname === href || 
    (href === '/lab' && location.pathname.startsWith('/game/')) ||
    (href === '/lab' && location.pathname.startsWith('/lab/')) ||
    (href === '/admin' && location.pathname.startsWith('/admin'));

  const handleLogout = async () => {
    try {
      await fetch(`${API}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
      navigate('/');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const userName = user?.name || "User";
  const userEmail = user?.email || "";
  const userPicture = user?.picture || "";
  const userInitial = userName.charAt(0);

  return (
    <div className="min-h-screen bg-background flex">
      {/* Desktop Sidebar */}
      <aside 
        className={`hidden md:flex flex-col fixed left-0 top-0 h-full bg-card border-r border-border z-40 transition-all duration-300 ${
          sidebarCollapsed ? 'w-16' : 'w-56'
        }`}
      >
        {/* Logo */}
        <div className={`flex items-center h-14 border-b border-border px-3 ${sidebarCollapsed ? 'justify-center' : 'justify-between'}`}>
          <Link to="/home" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center transition-transform group-hover:scale-105">
              <span className="text-primary-foreground font-heading font-bold text-sm">CC</span>
            </div>
            {!sidebarCollapsed && (
              <span className="font-heading font-semibold text-sm tracking-tight">
                Chess Coach
              </span>
            )}
          </Link>
          {!sidebarCollapsed && (
            <Button
              variant="ghost"
              size="icon"
              className="w-7 h-7 text-muted-foreground hover:text-foreground"
              onClick={() => setSidebarCollapsed(true)}
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-2 space-y-1">
          {navigation.map((item) => {
            const IconComponent = item.icon;
            const active = isActive(item.href);
            return (
              <Link key={item.href} to={item.href}>
                <Button
                  variant={active ? "secondary" : "ghost"}
                  className={`w-full gap-3 transition-colors ${
                    sidebarCollapsed ? 'justify-center px-2' : 'justify-start'
                  } ${active ? 'bg-primary/10 text-primary hover:bg-primary/15' : 'text-muted-foreground hover:text-foreground'}`}
                  data-testid={`nav-${item.name.toLowerCase()}`}
                  title={sidebarCollapsed ? item.name : undefined}
                >
                  <IconComponent className="w-4 h-4 flex-shrink-0" />
                  {!sidebarCollapsed && <span className="text-sm">{item.name}</span>}
                </Button>
              </Link>
            );
          })}
          
          {/* Play with Coach - Featured */}
          <div className={`pt-4 ${sidebarCollapsed ? 'px-0' : 'px-1'}`}>
            <Link to="/play-with-coach">
              <Button
                variant="default"
                className={`w-full gap-2 bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70 ${
                  sidebarCollapsed ? 'justify-center px-2' : 'justify-start'
                }`}
                data-testid="nav-play-coach"
                title={sidebarCollapsed ? "Play with Coach" : undefined}
              >
                <Swords className="w-4 h-4 flex-shrink-0" />
                {!sidebarCollapsed && <span className="text-sm">Play with Coach</span>}
              </Button>
            </Link>
          </div>

          {/* Plateau Breaker - Only show when on losing streak (3+ losses) */}
          {lossStreak.show && (
            <div className={`pt-2 ${sidebarCollapsed ? 'px-0' : 'px-1'}`}>
              <Link to="/plateau-breaker">
                <Button
                  variant="outline"
                  className={`w-full gap-2 border-red-500/50 text-red-500 hover:bg-red-500/10 hover:text-red-400 animate-pulse ${
                    sidebarCollapsed ? 'justify-center px-2' : 'justify-start'
                  }`}
                  data-testid="nav-plateau-breaker"
                  title={sidebarCollapsed ? `${lossStreak.count} losses - Fix this now` : undefined}
                >
                  <Zap className="w-4 h-4 flex-shrink-0" />
                  {!sidebarCollapsed && (
                    <span className="text-sm">{lossStreak.count} losses - Fix Now</span>
                  )}
                </Button>
              </Link>
            </div>
          )}

          {/* Admin Dashboard - Only for admin/super_admin */}
          {isAdmin && (
            <div className={`pt-2 ${sidebarCollapsed ? 'px-0' : 'px-1'}`}>
              <Link to="/admin">
                <Button
                  variant={isActive('/admin') ? "secondary" : "ghost"}
                  className={`w-full gap-2 ${
                    sidebarCollapsed ? 'justify-center px-2' : 'justify-start'
                  } ${isActive('/admin') ? 'bg-amber-500/10 text-amber-400' : 'text-muted-foreground hover:text-foreground'}`}
                  data-testid="nav-admin"
                  title={sidebarCollapsed ? "Admin Dashboard" : undefined}
                >
                  <Settings className="w-4 h-4 flex-shrink-0" />
                  {!sidebarCollapsed && <span className="text-sm">Admin</span>}
                </Button>
              </Link>
            </div>
          )}
        </nav>

        {/* Collapse toggle (when collapsed) */}
        {sidebarCollapsed && (
          <div className="px-2 pb-2">
            <Button
              variant="ghost"
              size="icon"
              className="w-full h-8 text-muted-foreground hover:text-foreground"
              onClick={() => setSidebarCollapsed(false)}
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        )}

        {/* Bottom section */}
        <div className={`border-t border-border p-2 space-y-1`}>
          {/* Theme toggle */}
          <Button
            variant="ghost"
            onClick={toggleTheme}
            className={`w-full gap-3 text-muted-foreground hover:text-foreground ${
              sidebarCollapsed ? 'justify-center px-2' : 'justify-start'
            }`}
            data-testid="sidebar-theme-toggle"
            title={sidebarCollapsed ? (theme === "dark" ? "Light mode" : "Dark mode") : undefined}
          >
            {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            {!sidebarCollapsed && <span className="text-sm">{theme === "dark" ? "Light mode" : "Dark mode"}</span>}
          </Button>

          {/* Settings */}
          <Link to="/settings">
            <Button
              variant="ghost"
              className={`w-full gap-3 text-muted-foreground hover:text-foreground ${
                sidebarCollapsed ? 'justify-center px-2' : 'justify-start'
              }`}
              data-testid="nav-settings"
              title={sidebarCollapsed ? "Settings" : undefined}
            >
              <Settings className="w-4 h-4" />
              {!sidebarCollapsed && <span className="text-sm">Settings</span>}
            </Button>
          </Link>

          {/* User Profile */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className={`w-full gap-3 ${sidebarCollapsed ? 'justify-center px-2' : 'justify-start'}`}
                data-testid="user-menu-trigger"
              >
                <Avatar className="h-7 w-7">
                  <AvatarImage src={userPicture} alt={userName} />
                  <AvatarFallback className="text-xs font-medium bg-muted">
                    {userInitial}
                  </AvatarFallback>
                </Avatar>
                {!sidebarCollapsed && (
                  <div className="flex flex-col items-start min-w-0">
                    <span className="text-sm font-medium truncate max-w-[120px]">{userName}</span>
                  </div>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" side="top" className="w-52">
              <div className="flex items-center gap-2 p-2">
                <Avatar className="h-8 w-8">
                  <AvatarImage src={userPicture} alt={userName} />
                  <AvatarFallback className="text-xs">{userInitial}</AvatarFallback>
                </Avatar>
                <div className="flex flex-col min-w-0">
                  <span className="text-sm font-medium truncate">{userName}</span>
                  <span className="text-xs text-muted-foreground truncate">{userEmail}</span>
                </div>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem 
                onClick={handleLogout} 
                className="text-destructive cursor-pointer focus:text-destructive" 
                data-testid="menu-logout"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Mobile Header */}
      <header className="md:hidden fixed top-0 left-0 right-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center justify-between h-14 px-4">
          <Link to="/home" className="flex items-center gap-2 group">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-heading font-bold text-sm">CC</span>
            </div>
            <span className="font-heading font-semibold text-sm">Chess Coach</span>
          </Link>

          <div className="flex items-center gap-2">
            {/* Notifications */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="w-8 h-8 relative" data-testid="notifications-bell">
                  <Bell className="w-4 h-4" />
                  {unreadCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-amber-500 text-[10px] font-bold text-black rounded-full flex items-center justify-center">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-72">
                <div className="flex items-center justify-between px-3 py-2 border-b border-border">
                  <span className="text-sm font-semibold">Notifications</span>
                  {unreadCount > 0 && (
                    <button onClick={markAllRead} className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
                      <CheckCheck className="w-3 h-3" />
                      Mark all read
                    </button>
                  )}
                </div>
                {notifications.length === 0 ? (
                  <div className="py-6 text-center text-muted-foreground text-sm">
                    No notifications yet
                  </div>
                ) : (
                  <div className="max-h-60 overflow-y-auto">
                    {notifications.slice(0, 5).map((notif, idx) => (
                      <div 
                        key={notif.id || idx}
                        className={`px-3 py-2 border-b border-border last:border-0 ${!notif.read ? 'bg-amber-500/5' : ''}`}
                        onClick={() => notif.action_url && navigate(notif.action_url)}
                      >
                        <p className="text-sm font-medium">{notif.title}</p>
                        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{notif.message}</p>
                      </div>
                    ))}
                  </div>
                )}
              </DropdownMenuContent>
            </DropdownMenu>

            <Button
              variant="ghost"
              size="icon"
              className="w-8 h-8"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              data-testid="mobile-menu-toggle"
            >
              {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </Button>
          </div>
        </div>

        {/* Mobile Navigation Dropdown */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="border-t border-border bg-background overflow-hidden"
            >
              <nav className="flex flex-col p-3 gap-1">
                {navigation.map((item) => {
                  const IconComponent = item.icon;
                  const active = isActive(item.href);
                  return (
                    <Link key={item.href} to={item.href} onClick={() => setMobileMenuOpen(false)}>
                      <Button
                        variant={active ? "secondary" : "ghost"}
                        className={`w-full justify-start gap-3 ${active ? 'bg-primary/10 text-primary' : ''}`}
                        data-testid={`mobile-nav-${item.name.toLowerCase()}`}
                      >
                        <IconComponent className="w-4 h-4" />
                        {item.name}
                      </Button>
                    </Link>
                  );
                })}
                
                <div className="border-t border-border my-2" />
                
                <Link to="/play-with-coach" onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="default" className="w-full justify-start gap-3">
                    <Swords className="w-4 h-4" />
                    Play with Coach
                  </Button>
                </Link>

                {lossStreak.show && (
                  <Link to="/plateau-breaker" onClick={() => setMobileMenuOpen(false)}>
                    <Button variant="outline" className="w-full justify-start gap-3 border-red-500/50 text-red-500 animate-pulse">
                      <Zap className="w-4 h-4" />
                      {lossStreak.count} losses - Fix Now
                    </Button>
                  </Link>
                )}

                <div className="border-t border-border my-2" />

                <Button variant="ghost" onClick={toggleTheme} className="w-full justify-start gap-3">
                  {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                  {theme === "dark" ? "Light mode" : "Dark mode"}
                </Button>

                <Link to="/settings" onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="ghost" className="w-full justify-start gap-3">
                    <Settings className="w-4 h-4" />
                    Settings
                  </Button>
                </Link>

                <Button variant="ghost" onClick={handleLogout} className="w-full justify-start gap-3 text-destructive">
                  <LogOut className="w-4 h-4" />
                  Sign out
                </Button>
              </nav>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* Main Content */}
      <main className={`flex-1 transition-all duration-300 ${sidebarCollapsed ? 'md:ml-16' : 'md:ml-56'} pt-14 md:pt-0`}>
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 md:py-8">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            {children}
          </motion.div>
        </div>
      </main>
    </div>
  );
};

export default Layout;
