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
  TrendingUp,
  Settings,
  Sun,
  Moon,
  LogOut,
  Menu,
  X,
  Bell,
  CheckCheck,
  Swords,
  ChevronLeft,
  ChevronRight,
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
  const [coachPulse, setCoachPulse] = useState(null);
  const [lossStreak, setLossStreak] = useState({ show: false, count: 0 });

  useEffect(() => {
    const fetchCoachPulse = async () => {
      try {
        const streakRes = await fetch(`${API}/loss-streak-status`, { credentials: 'include' });
        if (streakRes.ok) {
          const streakData = await streakRes.json();
          setLossStreak({ show: streakData.show_plateau_breaker, count: streakData.consecutive_losses, message: streakData.message });
          if (streakData.show_plateau_breaker) {
            setCoachPulse({ type: "losing_streak", count: streakData.consecutive_losses, label: `${streakData.consecutive_losses} losses in a row` });
            return;
          }
        }
        const reflectRes = await fetch(`${API}/reflect/pending/count`, { credentials: 'include' });
        if (reflectRes.ok) {
          const data = await reflectRes.json();
          if (data.count > 0) { setCoachPulse({ type: "reflect", count: data.count, label: "Reflect on recent games" }); return; }
        }
        const lossRes = await fetch(`${API}/coach/fresh-loss`, { credentials: 'include' });
        if (lossRes.ok) {
          const data = await lossRes.json();
          if (data.has_fresh_loss) { setCoachPulse({ type: "loss", count: 1, label: "Fix your last loss", game_id: data.game_id }); return; }
        }
        setCoachPulse(null);
      } catch (e) {}
    };
    fetchCoachPulse();
    const interval = setInterval(fetchCoachPulse, 60000);
    return () => clearInterval(interval);
  }, []);

  const handleCoachPulseClick = () => {
    if (coachPulse?.type === "losing_streak") navigate("/plateau-breaker");
    else if (coachPulse?.type === "loss" && coachPulse?.game_id) navigate(`/recover/${coachPulse.game_id}`);
    else navigate("/lab");
  };

  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {}
  }, []);

  const showBrowserNotification = (notif) => {
    if (Notification.permission === "granted") {
      const notification = new Notification(notif.title || "ChessGuru", { body: notif.message, icon: "/logo192.png", tag: "chessguru-" + (notif.id || Date.now()) });
      notification.onclick = () => { window.focus(); if (notif.action_url) navigate(notif.action_url); notification.close(); };
    }
  };

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
            if (newest) showBrowserNotification(newest);
          }
          setNotifications(newNotifications);
          setUnreadCount(newUnread);
          setPrevUnreadCount(newUnread);
        }
      } catch (e) {}
    };
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [prevUnreadCount]);

  const markAllRead = async () => {
    try {
      await fetch(`${API}/notifications/read`, { method: 'POST', credentials: 'include' });
      setUnreadCount(0); setPrevUnreadCount(0);
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch (e) {}
  };

  const navigation = [
    { name: 'Home', href: '/home', icon: Home },
    { name: 'Lab', href: '/lab', icon: FlaskConical },
    { name: 'Progress', href: '/progress', icon: TrendingUp },
  ];

  // Admin nav is locked to the owner email on top of the role check.
  // Server enforces the same rule.
  const ADMIN_EMAILS = new Set(['bhutramohit@gmail.com']);
  const isAdmin =
    (user?.role === 'super_admin' || user?.role === 'admin')
    && ADMIN_EMAILS.has((user?.email || '').trim().toLowerCase());
  const isActive = (href) => location.pathname === href ||
    (href === '/lab' && location.pathname.startsWith('/game/')) ||
    (href === '/lab' && location.pathname.startsWith('/lab/')) ||
    (href === '/admin' && location.pathname.startsWith('/admin'));

  const handleLogout = async () => {
    try { await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'include' }); navigate('/'); } catch (e) {}
  };

  const userName = user?.name || "User";
  const userEmail = user?.email || "";
  const userPicture = user?.picture || "";
  const userInitial = userName.charAt(0);

  return (
    <div className="min-h-screen flex bg-background">
      {/* ═══ Desktop Sidebar ═══ */}
      <aside
        className={`hidden md:flex flex-col fixed left-0 top-0 h-full z-40 transition-all duration-300 sidebar-gradient ${
          sidebarCollapsed ? 'w-[68px]' : 'w-[240px]'
        }`}
      >
        {/* Logo */}
        <div className={`flex items-center h-16 px-4 ${sidebarCollapsed ? 'justify-center' : 'justify-between'}`}>
          <Link to="/home" className="flex items-center gap-3 group">
            <div className="w-8 h-8 rounded-lg gradient-gold flex items-center justify-center shadow-md shadow-amber-500/20">
              <span className="text-sm font-bold text-black">CG</span>
            </div>
            {!sidebarCollapsed && (
              <span className="text-foreground font-heading font-bold text-[15px] tracking-tight">
                ChessGuru
              </span>
            )}
          </Link>
          {!sidebarCollapsed && (
            <button
              className="w-7 h-7 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors rounded-lg hover:bg-white/5"
              onClick={() => setSidebarCollapsed(true)}
            >
              <ChevronLeft className="w-4 h-4" strokeWidth={1.5} />
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {navigation.map((item) => {
            const IconComponent = item.icon;
            const active = isActive(item.href);
            return (
              <Link key={item.href} to={item.href}>
                <div
                  className={`relative w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                    sidebarCollapsed ? 'justify-center px-2' : 'justify-start'
                  } ${active
                    ? 'bg-primary/15 text-primary font-medium'
                    : 'text-muted-foreground hover:text-foreground hover:bg-white/5 dark:hover:bg-white/5'
                  }`}
                  data-testid={`nav-${item.name.toLowerCase()}`}
                  title={sidebarCollapsed ? item.name : undefined}
                >
                  {active && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-primary" />
                  )}
                  <IconComponent className={`w-[18px] h-[18px] flex-shrink-0 ${active ? 'text-primary' : ''}`} strokeWidth={active ? 2 : 1.5} />
                  {!sidebarCollapsed && <span className="text-[13px]">{item.name}</span>}
                </div>
              </Link>
            );
          })}

          {/* Play with Coach — Golden CTA */}
          <div className={`pt-5 ${sidebarCollapsed ? 'px-0' : 'px-0'}`}>
            <Link to="/play-with-coach">
              <div
                className={`relative w-full flex items-center gap-2.5 px-3 py-3 rounded-lg transition-all duration-200 gradient-gold text-black font-semibold shadow-lg shadow-amber-500/25 hover:shadow-amber-500/40 hover:scale-[1.02] active:scale-[0.98] ${
                  sidebarCollapsed ? 'justify-center px-2' : 'justify-start'
                }`}
                data-testid="nav-play-coach"
                title={sidebarCollapsed ? "Play with Coach" : undefined}
              >
                <Swords className="w-[18px] h-[18px] flex-shrink-0" strokeWidth={2} />
                {!sidebarCollapsed && <span className="text-[13px]">Play with Coach</span>}
              </div>
            </Link>
          </div>

          {isAdmin && (
            <div className="pt-2">
              <Link to="/admin">
                <div
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] transition-all duration-200 ${
                    sidebarCollapsed ? 'justify-center px-2' : 'justify-start'
                  } ${isActive('/admin') ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-white/5'}`}
                  data-testid="nav-admin"
                >
                  <Settings className="w-[18px] h-[18px] flex-shrink-0" strokeWidth={1.5} />
                  {!sidebarCollapsed && <span>Admin</span>}
                </div>
              </Link>
            </div>
          )}
        </nav>

        {/* Collapse toggle */}
        {sidebarCollapsed && (
          <div className="px-3 pb-2">
            <button className="w-full h-8 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors rounded-lg hover:bg-white/5"
              onClick={() => setSidebarCollapsed(false)}>
              <ChevronRight className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </div>
        )}

        {/* Bottom */}
        <div className="p-3 space-y-1 border-t border-border/50">
          <button
            onClick={toggleTheme}
            className={`w-full flex items-center gap-3 px-3 py-2 text-muted-foreground hover:text-foreground hover:bg-white/5 transition-all rounded-lg ${sidebarCollapsed ? 'justify-center px-2' : 'justify-start'}`}
            data-testid="sidebar-theme-toggle"
          >
            {theme === "dark" ? <Sun className="w-[18px] h-[18px]" strokeWidth={1.5} /> : <Moon className="w-[18px] h-[18px]" strokeWidth={1.5} />}
            {!sidebarCollapsed && <span className="text-[13px]">{theme === "dark" ? "Light" : "Dark"}</span>}
          </button>

          <Link to="/settings">
            <div className={`w-full flex items-center gap-3 px-3 py-2 text-muted-foreground hover:text-foreground hover:bg-white/5 transition-all rounded-lg ${sidebarCollapsed ? 'justify-center px-2' : 'justify-start'}`} data-testid="nav-settings">
              <Settings className="w-[18px] h-[18px]" strokeWidth={1.5} />
              {!sidebarCollapsed && <span className="text-[13px]">Settings</span>}
            </div>
          </Link>

          {/* User */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className={`w-full gap-3 hover:bg-white/5 h-auto py-2 ${sidebarCollapsed ? 'justify-center px-2' : 'justify-start'}`} data-testid="user-menu-trigger">
                <div className="relative">
                  <Avatar className="h-8 w-8 ring-2 ring-primary/20">
                    <AvatarImage src={userPicture} alt={userName} />
                    <AvatarFallback className="text-xs font-bold bg-primary/20 text-primary">{userInitial}</AvatarFallback>
                  </Avatar>
                  <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-background" />
                </div>
                {!sidebarCollapsed && (
                  <div className="flex flex-col items-start min-w-0">
                    <span className="text-[13px] font-medium truncate max-w-[130px] text-foreground">{userName}</span>
                    <span className="text-[11px] text-muted-foreground truncate max-w-[130px]">{userEmail}</span>
                  </div>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" side="top" className="w-52">
              <div className="flex items-center gap-2 p-2">
                <Avatar className="h-8 w-8"><AvatarImage src={userPicture} alt={userName} /><AvatarFallback className="text-xs bg-primary/20 text-primary">{userInitial}</AvatarFallback></Avatar>
                <div className="flex flex-col min-w-0">
                  <span className="text-sm font-medium truncate">{userName}</span>
                  <span className="text-xs text-muted-foreground truncate">{userEmail}</span>
                </div>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout} className="text-destructive cursor-pointer focus:text-destructive" data-testid="menu-logout">
                <LogOut className="w-4 h-4 mr-2" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* ═══ Mobile Header ═══ */}
      <header className="md:hidden fixed top-0 left-0 right-0 z-50 border-b border-border/50 bg-background/90 backdrop-blur-xl">
        <div className="flex items-center justify-between h-14 px-4">
          <Link to="/home" className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md gradient-gold flex items-center justify-center">
              <span className="text-xs font-bold text-black">CG</span>
            </div>
            <span className="font-heading font-bold text-sm text-foreground">ChessGuru</span>
          </Link>
          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="w-8 h-8 relative" data-testid="notifications-bell">
                  <Bell className="w-4 h-4" />
                  {unreadCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 w-4 h-4 gradient-gold text-[10px] font-bold text-black rounded-full flex items-center justify-center">
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
                      <CheckCheck className="w-3 h-3" /> Mark all read
                    </button>
                  )}
                </div>
                {notifications.length === 0 ? (
                  <div className="py-6 text-center text-muted-foreground text-sm">No notifications yet</div>
                ) : (
                  <div className="max-h-60 overflow-y-auto">
                    {notifications.slice(0, 5).map((notif, idx) => (
                      <div key={notif.id || idx} className={`px-3 py-2 border-b border-border last:border-0 cursor-pointer hover:bg-muted/50 transition-colors ${!notif.read ? 'bg-primary/5' : ''}`}
                        onClick={() => notif.action_url && navigate(notif.action_url)}>
                        <p className="text-sm font-medium">{notif.title}</p>
                        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{notif.message}</p>
                      </div>
                    ))}
                  </div>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button variant="ghost" size="icon" className="w-8 h-8" onClick={() => setMobileMenuOpen(!mobileMenuOpen)} data-testid="mobile-menu-toggle">
              {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </Button>
          </div>
        </div>
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }} className="border-t border-border bg-card overflow-hidden">
              <nav className="flex flex-col p-3 gap-1">
                {navigation.map((item) => { const IconComponent = item.icon; const active = isActive(item.href); return (
                  <Link key={item.href} to={item.href} onClick={() => setMobileMenuOpen(false)}>
                    <Button variant={active ? "secondary" : "ghost"} className={`w-full justify-start gap-3 ${active ? 'bg-primary/10 text-primary' : ''}`} data-testid={`mobile-nav-${item.name.toLowerCase()}`}>
                      <IconComponent className="w-4 h-4" /> {item.name}
                    </Button>
                  </Link>
                ); })}
                <div className="border-t border-border my-2" />
                <Link to="/play-with-coach" onClick={() => setMobileMenuOpen(false)}>
                  <Button className="w-full justify-start gap-3 gradient-gold text-black font-semibold hover:opacity-90 border-0">
                    <Swords className="w-4 h-4" /> Play with Coach
                  </Button>
                </Link>
                <div className="border-t border-border my-2" />
                <Button variant="ghost" onClick={toggleTheme} className="w-full justify-start gap-3">
                  {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />} {theme === "dark" ? "Light mode" : "Dark mode"}
                </Button>
                <Link to="/settings" onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="ghost" className="w-full justify-start gap-3"><Settings className="w-4 h-4" /> Settings</Button>
                </Link>
                <Button variant="ghost" onClick={handleLogout} className="w-full justify-start gap-3 text-destructive"><LogOut className="w-4 h-4" /> Sign out</Button>
              </nav>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* ═══ Main Content ═══ */}
      <main className={`flex-1 transition-all duration-300 ${sidebarCollapsed ? 'md:ml-[68px]' : 'md:ml-[240px]'} pt-14 md:pt-0 bg-background`}>
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 md:py-8">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
            {children}
          </motion.div>
        </div>
      </main>
    </div>
  );
};

export default Layout;
