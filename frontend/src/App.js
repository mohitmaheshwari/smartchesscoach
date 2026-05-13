import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, useLocation, useNavigate, Navigate } from "react-router-dom";
import "@/App.css";

// Pages
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Pricing from "@/pages/Pricing";
import TermsOfService from "@/pages/TermsOfService";
import PrivacyPolicy from "@/pages/PrivacyPolicy";
import RefundPolicy from "@/pages/RefundPolicy";
import ContactUs from "@/pages/ContactUs";
import ChessJourney from "@/pages/ChessJourney";
import Dashboard from "@/pages/Dashboard";
import HomePage from "@/pages/HomePage";  // NEW focused homepage
import ImportGames from "@/pages/ImportGames";
import Lab from "@/pages/Lab";
import AllGames from "@/pages/AllGames";
import ReviewQueue from "@/pages/ReviewQueue";
import LabV2 from "@/pages/LabV2";
import WeaknessTracker from "@/pages/WeaknessTracker";
import TrainingNew from "@/pages/TrainingNew";  // Used by /coach and /focus routes (renamed from aliased `Training` for clarity)
import PrescribedTraining from "@/pages/PrescribedTraining";  // Canonical training page (all /training/* routes)
import OpeningQuizPage from "@/pages/OpeningQuizPage";  // Opening mastery quiz
import OpeningRepertoire from "@/pages/OpeningRepertoire";  // Opening Training Lab
import OpeningLesson from "@/pages/OpeningLesson";  // Individual opening lessons
import OpeningWalkthrough from "@/pages/OpeningWalkthrough";  // Guided opening lesson from your games
import Challenge from "@/pages/Challenge";
import Settings from "@/pages/Settings";
import AuthCallback from "@/pages/AuthCallback";
import UnifiedProgress from "@/pages/UnifiedProgress";  // Merged progress + journey
import JourneyIntelligence from "@/pages/JourneyIntelligence";
import Reflect from "@/pages/Reflect";
import Onboarding from "@/pages/Onboarding";
import MissionRunner from "@/pages/MissionRunner";
import PostLossRecovery from "@/pages/PostLossRecovery";
import CoachPlay from "@/pages/CoachPlay";
import AdminOpenings from "@/pages/AdminOpenings";
import AdminDashboard from "@/pages/AdminDashboard";
import AdminAuthoring from "@/pages/AdminAuthoring";
import OpeningsOverview from "@/pages/OpeningsOverview";
import EndgameLesson from "@/pages/EndgameLesson";
import CoachReplay from "@/pages/CoachReplay";  // Guided behavioral game review

// V1 Plateau Breaker Mode (Enforced Learning)
import PlateauBreakerDashboard from "@/pages/PlateauBreakerDashboard";
import PlateauBreakerReview from "@/pages/PlateauBreakerReview";
import ApplyMode from "@/pages/ApplyMode";

// Public SEO pages — no auth, served to crawlers + cold visitors
import OpeningsIndex from "@/pages/OpeningsIndex";
import OpeningGuide from "@/pages/OpeningGuide";

// Prototype/demo pages — for design review, not feature surfaces
import PrototypeInteractiveMoment from "@/pages/PrototypeInteractiveMoment";

// Components
import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/context/ThemeContext";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
export const API = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';

const getStoredRedirectPath = () => {
  const savedPath = window.sessionStorage.getItem('post_auth_redirect');
  return savedPath || '/dashboard';
};

const consumeStoredRedirectPath = () => {
  const savedPath = getStoredRedirectPath();
  window.sessionStorage.removeItem('post_auth_redirect');
  return savedPath;
};

// Protected Route wrapper with onboarding check
const ProtectedRoute = ({ children, skipOnboardingCheck = false }) => {
  const [isResolved, setIsResolved] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [redirectTarget, setRedirectTarget] = useState(null);
  const location = useLocation();
  const demoBypass = location.search.includes('demo=true') || window.sessionStorage.getItem('demo_mode_bypass') === 'true';

  useEffect(() => {
    let cancelled = false;

    const resolveRouteAccess = async () => {
      try {
        setIsResolved(false);
        setRedirectTarget(null);

        let userData = location.state?.user || null;

        // If user data passed from AuthCallback, use it directly
        if (!userData) {
          const response = await fetch(`${API}/auth/me`, {
            credentials: 'include'
          });
          if (!response.ok) throw new Error('Not authenticated');
          userData = await response.json();
        }

        if (cancelled) return;

        setUser(userData);
        setIsAuthenticated(true);

        if (!skipOnboardingCheck && !demoBypass) {
          const onboardingResponse = await fetch(`${API}/onboarding/status`, {
            credentials: 'include'
          });

          if (!cancelled && onboardingResponse.ok) {
            const onboardingData = await onboardingResponse.json();
            if (onboardingData.needs_onboarding) {
              setRedirectTarget('/onboarding');
            }
          }
        } else if (demoBypass) {
          window.sessionStorage.setItem('demo_mode_bypass', 'true');
        }
      } catch (error) {
        if (cancelled) return;
        const intendedPath = `${location.pathname}${location.search}`;
        if (intendedPath && intendedPath !== '/') {
          window.sessionStorage.setItem('post_auth_redirect', intendedPath);
        }
        setIsAuthenticated(false);
        setRedirectTarget('/');
      } finally {
        if (!cancelled) {
          setIsResolved(true);
        }
      }
    };
    
    resolveRouteAccess();

    return () => {
      cancelled = true;
    };
  }, [location.pathname, location.search, location.state, skipOnboardingCheck, demoBypass]);

  if (!isResolved) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center" data-testid="protected-route-loading-state">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated || redirectTarget === '/') {
    return <Navigate to="/" replace />;
  }
  
  if (redirectTarget === '/onboarding' && !skipOnboardingCheck && !demoBypass) {
    return <Navigate to="/onboarding" replace state={{ from: `${location.pathname}${location.search}` }} />;
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
      navigate(consumeStoredRedirectPath(), { replace: true });
    }
  }, [location.search, navigate]);

  // Legacy: Check URL fragment for session_id (OAuth callback)
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/pricing" element={<Pricing />} />
      {/* Public policy pages — required for Razorpay compliance. */}
      <Route path="/terms" element={<TermsOfService />} />
      <Route path="/privacy" element={<PrivacyPolicy />} />
      <Route path="/refund" element={<RefundPolicy />} />
      <Route path="/contact" element={<ContactUs />} />
      <Route path="/prototype/interactive-moment" element={<PrototypeInteractiveMoment />} />

      {/* Public SEO routes — no auth required. Indexed by crawlers,
          served to cold visitors as marketing/teaching content. */}
      <Route path="/learn/openings" element={<OpeningsIndex />} />
      <Route path="/learn/openings/:slug" element={<OpeningGuide />} />

      <Route path="/onboarding" element={
        <ProtectedRoute skipOnboardingCheck={true}>
          {({ user }) => <Onboarding user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/coach" element={
        <ProtectedRoute>
          {({ user }) => <TrainingNew user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/focus" element={
        <ProtectedRoute>
          {({ user }) => <TrainingNew user={user} />}
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
      <Route path="/dashboard" element={
        <ProtectedRoute>
          {({ user }) => <HomePage user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/home" element={
        <ProtectedRoute>
          {({ user }) => <HomePage user={user} />}
        </ProtectedRoute>
      } />
      {/* /today is now an alias for /home — one landing page */}
      <Route path="/today" element={<Navigate to="/home" replace />} />
      <Route path="/lab" element={
        <ProtectedRoute>
          {({ user }) => <Dashboard user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/games" element={
        <ProtectedRoute>
          {({ user }) => <AllGames user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/review" element={
        <ProtectedRoute>
          {({ user }) => <ReviewQueue user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/import" element={
        <ProtectedRoute>
          {({ user }) => <ImportGames user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/replay/:gameId" element={
        <ProtectedRoute>
          {({ user }) => <CoachReplay user={user} />}
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
      {/* Training — consolidated to one page. All three URLs below render
          the same PrescribedTraining component; weakness is taken from
          ?weakness=X query param OR :pattern URL segment.
          `/training/legacy` has been removed (zero incoming references
          per audit; it pointed to a superseded Training component). */}
      <Route path="/training" element={
        <ProtectedRoute>
          {({ user }) => <PrescribedTraining user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/training/prescribed" element={
        <ProtectedRoute>
          {({ user }) => <PrescribedTraining user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/training/pattern/:pattern" element={
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
      <Route path="/opening-walkthrough" element={
        <ProtectedRoute>
          {({ user }) => <OpeningWalkthrough user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/admin/openings" element={
        <ProtectedRoute skipOnboardingCheck={true}>
          {({ user }) => <AdminOpenings user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/review/authoring" element={
        <ProtectedRoute skipOnboardingCheck={true}>
          {({ user }) => <AdminAuthoring user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/admin" element={
        <ProtectedRoute skipOnboardingCheck={true}>
          {({ user }) => <AdminDashboard user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/openings-overview" element={
        <ProtectedRoute skipOnboardingCheck={true}>
          {({ user }) => <OpeningsOverview user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/endgames/:categoryKey/:lessonKey" element={
        <ProtectedRoute>
          {({ user }) => <EndgameLesson user={user} />}
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
      
      {/* V1 Plateau Breaker Mode (Enforced Learning) */}
      <Route path="/plateau-breaker" element={
        <ProtectedRoute>
          {({ user }) => <PlateauBreakerDashboard user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/plateau-breaker/review/:gameId" element={
        <ProtectedRoute>
          {({ user }) => <PlateauBreakerReview user={user} />}
        </ProtectedRoute>
      } />
      <Route path="/plateau-breaker/apply" element={
        <ProtectedRoute>
          {({ user }) => <ApplyMode user={user} />}
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
