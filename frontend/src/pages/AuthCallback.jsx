import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";

const AuthCallback = () => {
  const navigate = useNavigate();
  const hasProcessed = useRef(false);

  useEffect(() => {
    // Prevent double processing in StrictMode
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processAuth = async () => {
      const hash = window.location.hash;
      const sessionId = hash.split('session_id=')[1]?.split('&')[0];

      if (!sessionId) {
        navigate('/');
        return;
      }

      try {
        const response = await fetch(`${API}/auth/session`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ session_id: sessionId })
        });

        if (!response.ok) {
          throw new Error('Auth failed');
        }

        const user = await response.json();
        
        // Clear the hash and navigate to dashboard with user data
        window.history.replaceState(null, '', '/dashboard');
        navigate('/dashboard', { replace: true, state: { user } });
      } catch (error) {
        console.error('Auth error:', error);
        navigate('/');
      }
    };

    processAuth();
  }, [navigate]);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="text-center space-y-4">
        <div className="w-12 h-12 rounded-full border-4 border-primary border-t-transparent animate-spin mx-auto" />
        <p className="text-muted-foreground">Signing you in...</p>
      </div>
    </div>
  );
};

export default AuthCallback;
