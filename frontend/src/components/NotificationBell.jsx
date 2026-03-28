import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import {
  Bell,
  X,
  Trophy,
  Target,
  Zap,
  TrendingUp,
  Check,
  ChevronRight
} from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { toast } from "sonner";

// Request browser notification permission
const requestNotificationPermission = async () => {
  if (!("Notification" in window)) {
    return false;
  }
  
  if (Notification.permission === "granted") {
    return true;
  }
  
  if (Notification.permission !== "denied") {
    const permission = await Notification.requestPermission();
    return permission === "granted";
  }
  
  return false;
};

// Show browser notification
const showBrowserNotification = (title, body, onClick) => {
  if (Notification.permission === "granted") {
    const notification = new Notification(title, {
      body,
      icon: "/logo192.png",
      badge: "/badge.png",
      tag: "chess-coach"
    });
    
    notification.onclick = () => {
      window.focus();
      if (onClick) onClick();
      notification.close();
    };
  }
};

// Icon map for notification types
const iconMap = {
  game_analyzed: <Target className="w-4 h-4" />,
  new_milestone: <Trophy className="w-4 h-4" />,
  focus_updated: <TrendingUp className="w-4 h-4" />,
  system: <Zap className="w-4 h-4" />
};

// Color map for notification types
const colorMap = {
  game_analyzed: "text-blue-400",
  new_milestone: "text-yellow-400",
  focus_updated: "text-green-400",
  system: "text-purple-400"
};

// Single notification item
const NotificationItem = ({ notification, onDismiss, onNavigate }) => {
  const navigate = useNavigate();
  
  const handleClick = async () => {
    // Mark as read
    try {
      await fetch(`${API}/notifications/read?notification_id=${notification.id}`, {
        method: "POST",
        credentials: "include"
      });
    } catch (e) {
      console.error("Failed to mark notification read:", e);
    }
    
    // Navigate if action URL exists
    if (notification.action_url) {
      navigate(notification.action_url);
      if (onNavigate) onNavigate();
    }
  };
  
  const handleDismiss = async (e) => {
    e.stopPropagation();
    try {
      await fetch(`${API}/notifications/${notification.id}/dismiss`, {
        method: "POST",
        credentials: "include"
      });
      if (onDismiss) onDismiss(notification.id);
    } catch (e) {
      console.error("Failed to dismiss notification:", e);
    }
  };
  
  const timeAgo = (dateStr) => {
    const date = new Date(dateStr);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };
  
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 10 }}
      className={`p-3 rounded-lg cursor-pointer transition-colors group ${
        notification.read ? 'bg-background/50' : 'bg-muted/50 hover:bg-muted'
      }`}
      onClick={handleClick}
    >
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 ${colorMap[notification.type] || 'text-muted-foreground'}`}>
          {iconMap[notification.type] || <Bell className="w-4 h-4" />}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <p className={`text-sm font-medium truncate ${notification.read ? 'text-muted-foreground' : ''}`}>
              {notification.title}
            </p>
            <button 
              onClick={handleDismiss}
              className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-background rounded"
            >
              <X className="w-3 h-3 text-muted-foreground" />
            </button>
          </div>
          <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
            {notification.message}
          </p>
          <p className="text-[10px] text-muted-foreground/60 mt-1">
            {timeAgo(notification.created_at)}
          </p>
        </div>
        
        {notification.action_url && (
          <ChevronRight className="w-4 h-4 text-muted-foreground/50 mt-0.5" />
        )}
      </div>
    </motion.div>
  );
};

// Main notification bell component
const NotificationBell = () => {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [hasPermission, setHasPermission] = useState(false);
  
  // Fetch notifications
  const fetchNotifications = useCallback(async () => {
    try {
      const res = await fetch(`${API}/notifications?limit=10`, {
        credentials: "include"
      });
      
      if (res.ok) {
        const data = await res.json();
        
        // Check for new notifications to show browser notification
        if (data.unread_count > unreadCount && data.notifications.length > 0) {
          const newest = data.notifications[0];
          if (!newest.read && hasPermission) {
            showBrowserNotification(
              newest.title,
              newest.message,
              () => {
                if (newest.action_url) navigate(newest.action_url);
              }
            );
          }
        }
        
        setNotifications(data.notifications);
        setUnreadCount(data.unread_count);
      }
    } catch (e) {
      console.error("Failed to fetch notifications:", e);
    }
  }, [unreadCount, hasPermission, navigate]);
  
  // Initial fetch and polling
  useEffect(() => {
    fetchNotifications();
    
    // Poll every 30 seconds
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);
  
  // Request permission on mount
  useEffect(() => {
    requestNotificationPermission().then(setHasPermission);
  }, []);
  
  // Mark all as read
  const markAllRead = async () => {
    try {
      await fetch(`${API}/notifications/read`, {
        method: "POST",
        credentials: "include"
      });
      setUnreadCount(0);
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch (e) {
      console.error("Failed to mark all read:", e);
    }
  };
  
  // Handle dismiss
  const handleDismiss = (id) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
    setUnreadCount(prev => Math.max(0, prev - 1));
  };
  
  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button 
          variant="ghost" 
          size="icon" 
          className="relative"
          data-testid="notification-bell"
        >
          <Bell className="w-5 h-5" />
          {unreadCount > 0 && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center font-bold"
            >
              {unreadCount > 9 ? "9+" : unreadCount}
            </motion.span>
          )}
        </Button>
      </PopoverTrigger>
      
      <PopoverContent 
        className="w-80 p-0" 
        align="end"
        data-testid="notification-panel"
      >
        <div className="p-3 border-b flex items-center justify-between">
          <h3 className="font-semibold">Notifications</h3>
          {unreadCount > 0 && (
            <Button 
              variant="ghost" 
              size="sm" 
              className="text-xs h-7"
              onClick={markAllRead}
            >
              <Check className="w-3 h-3 mr-1" />
              Mark all read
            </Button>
          )}
        </div>
        
        <div className="max-h-[400px] overflow-y-auto">
          {notifications.length === 0 ? (
            <div className="p-6 text-center text-muted-foreground">
              <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No notifications yet</p>
            </div>
          ) : (
            <AnimatePresence mode="popLayout">
              <div className="p-2 space-y-1">
                {notifications.map(notification => (
                  <NotificationItem
                    key={notification.id || notification.created_at}
                    notification={notification}
                    onDismiss={handleDismiss}
                    onNavigate={() => setIsOpen(false)}
                  />
                ))}
              </div>
            </AnimatePresence>
          )}
        </div>
        
        {!hasPermission && (
          <div className="p-3 border-t bg-muted/30">
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs"
              onClick={async () => {
                const granted = await requestNotificationPermission();
                setHasPermission(granted);
                if (granted) {
                  toast.success("Browser notifications enabled!");
                }
              }}
            >
              <Bell className="w-3 h-3 mr-1" />
              Enable browser notifications
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
};

export default NotificationBell;
export { requestNotificationPermission, showBrowserNotification };
