import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, useLocation, useNavigate, Navigate } from "react-router-dom";
import "@/App.css";

// Pages
import Landing from "@/pages/Landing";
import ChessJourney from "@/pages/ChessJourney";
import Dashboard from "@/pages/Dashboard";
import CoachHome from "@/pages/CoachHome";
import HomePage from "@/pages/HomePage";  // NEW focused homepage
import ImportGames from "@/pages/ImportGames";
import Lab from "@/pages/Lab";
import LabV2 from "@/pages/LabV2";
import WeaknessTracker from "@/pages/WeaknessTracker";
import Training from "@/pages/TrainingNew";  // NEW interactive training
import PrescribedTraining from "@/pages/PrescribedTraining";  // Coached puzzles based on weaknesses
import OpeningQuizPage from "@/pages/OpeningQuizPage";  // Opening mastery quiz
import OpeningRepertoire from "@/pages/OpeningRepertoire";  // Opening Training Lab
import OpeningLesson from "@/pages/OpeningLesson";  // Individual opening lessons
import Challenge from "@/pages/Challenge";
import Settings from "@/pages/Settings";
import AuthCallback from "@/pages/AuthCallback";
import UnifiedProgress from "@/pages/UnifiedProgress";  // Merged progress + journey
import JourneyV2 from "@/pages/JourneyV2";
import JourneyIntelligence from "@/pages/JourneyIntelligence";
import ProgressV2 from "@/pages/ProgressV2";
import Reflect from "@/pages/Reflect";
import Onboarding from "@/pages/Onboarding";
import MissionRunner from "@/pages/MissionRunner";
import PostLossRecovery from "@/pages/PostLossRecovery";
import CoachPlay from "@/pages/CoachPlay";

// Components
import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/context/ThemeContext";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
export const API = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';

// Protected Route wrapper with onboarding check
const ProtectedRoute = ({ children, skipOnboardingCheck = false }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(null);
  const [user, setUser] = useState(null);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const checkOnboarding = async () => {
      try {
        const response = await fetch(`${API}/onboarding/status`, {
          credentials: 'include'
        });
        if (response.ok) {
          const data = await response.json();
          if (data.needs_onboarding) {
            setNeedsOnboarding(true);
            navigate('/onboarding');
          }
        }
      } catch (e) {
        console.log("Onboarding check failed:", e);
      }
    };

    const checkAuth = async () => {
      try {
        // If user data passed from AuthCallback, use it directly
        if (location.state?.user) {
          setUser(location.state.user);
          setIsAuthenticated(true);
          if (!skipOnboardingCheck) {
            checkOnboarding();
          }
          return;
        }

        const response = await fetch(`${API}/auth/me`, {
          credentials: 'include'
        });
        if (!response.ok) throw new Error('Not authenticated');
        const userData = await response.json();
        setUser(userData);
        setIsAuthenticated(true);
        
        // Check if user needs onboarding (unless skipping)
        if (!skipOnboardingCheck) {
          checkOnboarding();
        }
      } catch (error) {
        setIsAuthenticated(false);
        navigate('/');
      }
    };
    
    checkAuth();
  }, [navigate, location.state, skipOnboardingCheck]);

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
  
  if (needsOnboarding && !skipOnboardingCheck) {
    return null; // Will redirect to onboarding
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
      <Route path="/onboarding" element={
        <ProtectedRoute skipOnboardingCheck={true}>
          {({ user }) => <Onboarding user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/coach" element={
        <ProtectedRoute>
          {({ user }) => <Training user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/focus" element={
        <ProtectedRoute>
          {({ user }) => <Training user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/progress" element={
        <ProtectedRoute>
          {({ user }) => <UnifiedProgress user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/journey" element={
        <Navigate to="/progress" replace />
      } />
      <Route path="/progress-v2" element={
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
          {({ user }) => <HomePage user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/dashboard-full" element={
        <ProtectedRoute>
          {({ user }) => <Dashboard user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/home" element={
        <ProtectedRoute>
          {({ user }) => <HomePage user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/lab" element={
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
          {({ user }) => <LabV2 user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/lab/game/:gameId" element={
        <ProtectedRoute>
          {({ user }) => <LabV2 user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/game-old/:gameId" element={
        <ProtectedRoute>
          {({ user }) => <Lab user={user} />}
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
      <Route path="/training/prescribed" element={
        <ProtectedRoute>
          {({ user }) => <PrescribedTraining user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/training/quiz/:openingKey" element={
        <ProtectedRoute>
          {({ user }) => <OpeningQuizPage user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/openings" element={
        <ProtectedRoute>
          {({ user }) => <OpeningRepertoire user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/openings/:openingKey" element={
        <ProtectedRoute>
          {({ user }) => <OpeningLesson user={user} />}
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
      <Route path="/reflect" element={
        <ProtectedRoute>
          {({ user }) => <Reflect user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/mission/:missionId" element={
        <ProtectedRoute>
          {({ user }) => <MissionRunner user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/play-with-coach" element={
        <ProtectedRoute>
          {({ user }) => <CoachPlay user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/recover/:gameId" element={
        <ProtectedRoute>
          {({ user }) => <PostLossRecovery user={user} />}
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
