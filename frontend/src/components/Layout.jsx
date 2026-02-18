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
  LayoutDashboard, 
  Import, 
  Target, 
  Swords,
  Settings,
  Sun,
  Moon,
  LogOut,
  Menu,
  X,
  TrendingUp,
  Bell,
  CheckCheck,
  Brain
} from "lucide-react";
import { useState, useEffect } from "react";
import { API } from "@/App";

const Layout = ({ children, user }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [prevUnreadCount, setPrevUnreadCount] = useState(0);
  const [pendingReflections, setPendingReflections] = useState(0);

  // Request browser notification permission
  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      // Will request on first interaction
    }
  }, []);

  // Show browser notification for new items
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
          
          // Show browser notification if there are new unread notifications
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
    // Poll every 30 seconds for faster notification delivery
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [prevUnreadCount]);

  // Fetch pending reflections count
  useEffect(() => {
    const fetchPendingReflections = async () => {
      try {
        const res = await fetch(`${API}/reflect/pending/count`, { credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          setPendingReflections(data.count || 0);
        }
      } catch (e) {
        // Silently fail - non-critical
      }
    };
    
    fetchPendingReflections();
    // Poll every 60 seconds for reflection count
    const interval = setInterval(fetchPendingReflections, 60000);
    return () => clearInterval(interval);
  }, []);

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
    { name: 'Reflect', href: '/reflect', icon: Brain, badge: pendingReflections },
    { name: 'Training', href: '/training', icon: Target },
    { name: 'Journey', href: '/progress', icon: TrendingUp },
    { name: 'Lab', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Import', href: '/import', icon: Import },
  ];

  const isActive = (href) => location.pathname === href;

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
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            {/* Logo */}
            <Link to="/focus" className="flex items-center gap-2.5 group">
              <div className="w-7 h-7 rounded-md bg-foreground flex items-center justify-center transition-transform group-hover:scale-105">
                <span className="text-background font-heading font-bold text-xs">E1</span>
              </div>
              <span className="font-heading font-semibold text-sm tracking-tight hidden sm:block">
                Chess Coach
              </span>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center gap-1">
              {navigation.map((item) => {
                const IconComponent = item.icon;
                const active = isActive(item.href);
                return (
                  <Link key={item.href} to={item.href}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className={`gap-2 text-sm font-medium transition-colors ${
                        active 
                          ? 'bg-muted text-foreground' 
                          : 'text-muted-foreground hover:text-foreground hover:bg-transparent'
                      }`}
                      data-testid={`nav-${item.name.toLowerCase()}`}
                    >
                      <IconComponent className="w-4 h-4" />
                      {item.name}
                    </Button>
                  </Link>
                );
              })}
            </nav>

            {/* Right side */}
            <div className="flex items-center gap-1">
              {/* Notifications Bell */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="w-8 h-8 text-muted-foreground hover:text-foreground relative"
                    data-testid="notifications-bell"
                  >
                    <Bell className="w-4 h-4" />
                    {unreadCount > 0 && (
                      <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-amber-500 text-[10px] font-bold text-black rounded-full flex items-center justify-center">
                        {unreadCount > 9 ? '9+' : unreadCount}
                      </span>
                    )}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-80">
                  <div className="flex items-center justify-between px-3 py-2 border-b border-border">
                    <span className="text-sm font-semibold">Notifications</span>
                    {unreadCount > 0 && (
                      <button 
                        onClick={markAllRead}
                        className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                      >
                        <CheckCheck className="w-3 h-3" />
                        Mark all read
                      </button>
                    )}
                  </div>
                  
                  {notifications.length === 0 ? (
                    <div className="py-8 text-center text-muted-foreground text-sm">
                      <Bell className="w-8 h-8 mx-auto mb-2 opacity-30" />
                      No notifications yet
                    </div>
                  ) : (
                    <div className="max-h-80 overflow-y-auto">
                      {notifications.map((notif, idx) => (
                        <div 
                          key={notif.id || idx}
                          className={`px-3 py-2.5 border-b border-border last:border-0 hover:bg-muted/50 cursor-pointer transition-colors ${
                            !notif.read ? 'bg-amber-500/5' : ''
                          }`}
                          onClick={() => {
                            // Navigate to action URL if available
                            if (notif.action_url) {
                              navigate(notif.action_url);
                            } else if (notif.type === 'game_analyzed' && notif.data?.game_id) {
                              navigate(`/game/${notif.data.game_id}`);
                            } else if (notif.type === 'focus_updated') {
                              navigate('/focus');
                            } else {
                              navigate('/dashboard');
                            }
                          }}
                        >
                          <div className="flex items-start gap-2">
                            {!notif.read && (
                              <span className="w-2 h-2 mt-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                            )}
                            <div className={!notif.read ? '' : 'ml-4'}>
                              <p className="text-sm font-medium">{notif.title}</p>
                              <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{notif.message}</p>
                              <p className="text-[10px] text-muted-foreground/60 mt-1">
                                {new Date(notif.created_at).toLocaleDateString()}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>

              <Button
                variant="ghost"
                size="icon"
                onClick={toggleTheme}
                className="w-8 h-8 text-muted-foreground hover:text-foreground"
                data-testid="header-theme-toggle"
              >
                <motion.div
                  initial={false}
                  animate={{ rotate: theme === "dark" ? 0 : 180 }}
                  transition={{ duration: 0.3 }}
                >
                  {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                </motion.div>
              </Button>

              {/* User Menu */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button 
                    variant="ghost" 
                    className="relative h-8 w-8 rounded-full" 
                    data-testid="user-menu-trigger"
                  >
                    <Avatar className="h-8 w-8">
                      <AvatarImage src={userPicture} alt={userName} />
                      <AvatarFallback className="text-xs font-medium bg-muted">
                        {userInitial}
                      </AvatarFallback>
                    </Avatar>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-52">
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
                    onClick={() => navigate('/settings')} 
                    data-testid="menu-settings"
                    className="cursor-pointer"
                  >
                    <Settings className="w-4 h-4 mr-2" />
                    Settings
                  </DropdownMenuItem>
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

              {/* Mobile menu button */}
              <Button
                variant="ghost"
                size="icon"
                className="md:hidden w-8 h-8"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                data-testid="mobile-menu-toggle"
              >
                {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
              </Button>
            </div>
          </div>
        </div>

        {/* Mobile Navigation */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="md:hidden border-t border-border bg-background overflow-hidden"
            >
              <nav className="flex flex-col p-4 gap-1">
                {navigation.map((item) => {
                  const IconComponent = item.icon;
                  const active = isActive(item.href);
                  return (
                    <Link 
                      key={item.href} 
                      to={item.href}
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      <Button
                        variant={active ? "secondary" : "ghost"}
                        className="w-full justify-start gap-2"
                        data-testid={`mobile-nav-${item.name.toLowerCase()}`}
                      >
                        <IconComponent className="w-4 h-4" />
                        {item.name}
                      </Button>
                    </Link>
                  );
                })}
              </nav>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {children}
        </motion.div>
      </main>
    </div>
  );
};

export default Layout;
