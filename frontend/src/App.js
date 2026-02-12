import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, useLocation, useNavigate } from "react-router-dom";
import "@/App.css";

// Pages
import Landing from "@/pages/Landing";
import Coach from "@/pages/Coach";
import Focus from "@/pages/Focus";
import ChessJourney from "@/pages/ChessJourney";
import Dashboard from "@/pages/Dashboard";
import ImportGames from "@/pages/ImportGames";
import Lab from "@/pages/Lab";
import WeaknessTracker from "@/pages/WeaknessTracker";
import Training from "@/pages/Training";
import Challenge from "@/pages/Challenge";
import Settings from "@/pages/Settings";
import AuthCallback from "@/pages/AuthCallback";
import Journey from "@/pages/Journey";
import JourneyV2 from "@/pages/JourneyV2";
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
    // If user data passed from AuthCallback, use it directly
    if (location.state?.user) {
      setUser(location.state.user);
      setIsAuthenticated(true);
      return;
    }

    const checkAuth = async () => {
      try {
        const response = await fetch(`${API}/auth/me`, {
          credentials: 'include'
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

// App Router with auth detection
function AppRouter() {
  const location = useLocation();
  const navigate = useNavigate();

  // Check for auth=success in URL (from Google OAuth callback)
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get('auth') === 'success') {
      // Remove the query param and stay on dashboard
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
          {({ user }) => <Focus user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/progress" element={
        <ProtectedRoute>
          {({ user }) => <JourneyV2 user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/progress-old" element={
        <ProtectedRoute>
          {({ user }) => <ProgressV2 user={user} />}
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
