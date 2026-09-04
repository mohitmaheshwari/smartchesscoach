import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, useLocation, useNavigate } from "react-router-dom";
import { Capacitor } from "@capacitor/core";
import { App as CapApp } from "@capacitor/app";
import { Browser } from "@capacitor/browser";
import "@/App.css";

// Pages
import Landing from "@/pages/Landing";
import Coach from "@/pages/Coach";
import ChessJourney from "@/pages/ChessJourney";
import Dashboard from "@/pages/Dashboard";
import ImportGames from "@/pages/ImportGames";
import GameAnalysis from "@/pages/GameAnalysis";
import WeaknessTracker from "@/pages/WeaknessTracker";
import Training from "@/pages/Training";
import Challenge from "@/pages/Challenge";
import Settings from "@/pages/Settings";
import AuthCallback from "@/pages/AuthCallback";
import Journey from "@/pages/Journey";
import ProgressV2 from "@/pages/ProgressV2";

// Components
import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/context/ThemeContext";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
export const API = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';

// Protected Route wrapper
const ProtectedRoute = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(null);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // If user data passed from AuthCallback or deep link, use it directly
    if (location.state?.user) {
      setUser(location.state.user);
      setIsAuthenticated(true);
      return;
    }

    const checkAuth = async () => {
      try {
        const token = localStorage.getItem('session_token');
        const headers = {};
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(`${API}/auth/me`, {
          credentials: 'include',
          headers
        });
        if (!response.ok) throw new Error('Not authenticated');
        const userData = await response.json();
        setUser(userData);
        setIsAuthenticated(true);
      } catch (error) {
        setIsAuthenticated(false);
        navigate('/');
      }
    };
    checkAuth();
  }, [navigate, location.state]);

  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return children({ user });
};

// App Router with auth detection & deep link listener
function AppRouter() {
  const location = useLocation();
  const navigate = useNavigate();

  // Listen for deep links when opened via custom scheme (e.g. chessguru://auth?token=...)
  useEffect(() => {
    let appUrlListener = null;

    if (Capacitor.isNativePlatform()) {
      const initAppListener = async () => {
        appUrlListener = await CapApp.addListener('appUrlOpen', async (data) => {
          console.log('App opened with deep link URL:', data.url);

          // Close browser if it was opened
          try {
            await Browser.close();
          } catch (e) {}

          // Handle chessguru://auth?token=...
          if (data.url && data.url.includes('auth')) {
            try {
              const url = new URL(data.url.replace(/^[a-zA-Z0-9_-]+:\/\//, 'https://dummy/'));
              const token = url.searchParams.get('token') || url.searchParams.get('session_token');
              if (token) {
                localStorage.setItem('session_token', token);
                const res = await fetch(`${API}/auth/me`, {
                  headers: { Authorization: `Bearer ${token}` }
                });
                if (res.ok) {
                  const userData = await res.json();
                  navigate('/dashboard', { state: { user: userData } });
                } else {
                  navigate('/');
                }
              }
            } catch (err) {
              console.error('Error handling deep link:', err);
            }
          }
        });
      };
      initAppListener();
    }

    return () => {
      if (appUrlListener && appUrlListener.remove) {
        appUrlListener.remove();
      }
    };
  }, [navigate]);

  // Check for auth=success or token in URL (from Google OAuth callback)
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const token = params.get('token');
    if (token) {
      localStorage.setItem('session_token', token);
      navigate('/dashboard', { replace: true });
    } else if (params.get('auth') === 'success') {
      navigate('/dashboard', { replace: true });
    }
  }, [location.search, navigate]);

  // Legacy: Check URL fragment for session_id (Emergent auth)
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/coach" element={
        <ProtectedRoute>
          {({ user }) => <Coach user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/progress" element={
        <ProtectedRoute>
          {({ user }) => <ProgressV2 user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/progress-old" element={
        <ProtectedRoute>
          {({ user }) => <ChessJourney user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/dashboard" element={
        <ProtectedRoute>
          {({ user }) => <Dashboard user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/import" element={
        <ProtectedRoute>
          {({ user }) => <ImportGames user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/game/:gameId" element={
        <ProtectedRoute>
          {({ user }) => <GameAnalysis user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/weaknesses" element={
        <ProtectedRoute>
          {({ user }) => <WeaknessTracker user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/training" element={
        <ProtectedRoute>
          {({ user }) => <Training user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/challenge" element={
        <ProtectedRoute>
          {({ user }) => <Challenge user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/settings" element={
        <ProtectedRoute>
          {({ user }) => <Settings user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/journey" element={
        <ProtectedRoute>
          {({ user }) => <Journey user={user} />}
        </ProtectedRoute>
      } />
    </Routes>
  );
}

function App() {
  return (
    <ThemeProvider>
      <div className="App min-h-screen bg-background">
        <BrowserRouter>
          <AppRouter />
        </BrowserRouter>
        <Toaster position="bottom-right" />
      </div>
    </ThemeProvider>
  );
}

export default App;
