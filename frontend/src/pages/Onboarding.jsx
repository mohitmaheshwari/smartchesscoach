/**
 * ONBOARDING PAGE — Warm Wine/Gold Theme
 *
 * 2-step wizard:
 *   Step 1: Link Chess.com / Lichess account
 *   Step 2: Calibrate profile (rating, focus intent)
 *   → Analyze games → Show results
 */

import { useState, useEffect } from "react";
import { ANALYTICS_EVENTS, track } from "@/lib/analytics";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import {
  Loader2, CheckCircle2, AlertCircle, ArrowRight, ArrowLeft,
  Link as LinkIcon, Target, Brain, Zap, BookOpen,
} from "lucide-react";
import InstantDNA from "@/components/InstantDNA";

const WINE = "#722F37";
const GOLD_TEXT = "#8B6F1F";
const GOLD = "#CBA135";
const BORDER = "hsl(35 10% 87%)";

const Onboarding = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  // Step 1
  const [chessComUsername, setChessComUsername] = useState("");
  const [lichessUsername, setLichessUsername] = useState("");
  const [chessComVerified, setChessComVerified] = useState(false);
  const [lichessVerified, setLichessVerified] = useState(false);
  const [verifyingChessCom, setVerifyingChessCom] = useState(false);
  const [verifyingLichess, setVerifyingLichess] = useState(false);

  // Auto-detected
  const [detectedRating, setDetectedRating] = useState(null);
  const [detectedPlatform, setDetectedPlatform] = useState("");
  const [gamesAnalyzed, setGamesAnalyzed] = useState(0);

  // Step 2
  const [fideRating, setFideRating] = useState("");
  const [focusIntent, setFocusIntent] = useState("");
  const [playerMotivation, setPlayerMotivation] = useState("");

  // Analysis
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisResult, setAnalysisResult] = useState(null);

  // Instant DNA
  const [instantDNA, setInstantDNA] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/auth/me`, { credentials: "include" });
        if (res.ok) {
          const user = await res.json();
          if (user.chess_com_username || user.lichess_username) navigate("/training");
        }
      } catch (e) { /* ignore */ }
    })();
  }, [navigate]);

  const verifyAccount = async (platform) => {
    const isChessCom = platform === "chess.com";
    const username = isChessCom ? chessComUsername : lichessUsername;
    if (!username.trim()) return;

    isChessCom ? setVerifyingChessCom(true) : setVerifyingLichess(true);
    setError("");

    try {
      // Verification must happen server-side. Calling Chess.com/Lichess
      // directly from the browser depends on third-party CORS behavior and can
      // fail before ChessGuru receives the username. The existing backend
      // endpoint validates, fetches games and persists the link atomically.
      const linkRes = await fetch(`${API}/settings/link-account`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ platform, username: username.toLowerCase() }),
      });
      const data = await linkRes.json().catch(() => ({}));

      if (!linkRes.ok) {
        throw new Error(
          data.detail
          || `${isChessCom ? "Chess.com" : "Lichess"} username not found. Please check and try again.`
        );
      }

      isChessCom ? setChessComVerified(true) : setLichessVerified(true);
      if (data.assessed_rating && (!detectedRating || isChessCom)) {
        setDetectedRating(data.assessed_rating);
        setDetectedPlatform(platform);
        setGamesAnalyzed(data.games_analyzed || 0);
      }
    } catch (err) {
      isChessCom ? setChessComVerified(false) : setLichessVerified(false);
      setError(
        err?.message
        || `Failed to verify ${isChessCom ? "Chess.com" : "Lichess"} account.`
      );
    } finally {
      isChessCom ? setVerifyingChessCom(false) : setVerifyingLichess(false);
    }
  };

  const hasLinkedAccount = chessComVerified || lichessVerified;

  const handleStep1Continue = () => {
    if (!hasLinkedAccount) { setError("Please link at least one account."); return; }
    setError("");
    setStep(2);
  };

  const handleStep2Complete = async () => {
    setIsLoading(true);
    setError("");
    try {
      const profileRes = await fetch(`${API}/settings/profile`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({ fide_rating: fideRating ? parseInt(fideRating) : null, detected_rating: detectedRating, detected_platform: detectedPlatform, focus_intent: focusIntent || null, player_motivation: playerMotivation || null }),
      });
      const profileData = await profileRes.json().catch(() => ({}));
      if (!profileRes.ok) {
        throw new Error(profileData.detail || "Could not save your profile.");
      }

      setAnalyzing(true);
      setAnalysisProgress(20);

      // Step 1: Sync games from Chess.com/Lichess (fast — just fetches PGNs)
      await fetch(`${API}/games/sync`, { method: "POST", credentials: "include" }).catch(() => {});
      setAnalysisProgress(60);

      // FIRST-AHA fast path (docs/activation_scope.md): jump the user's most
      // recent loss to the front of the analysis queue and take them straight
      // to that decoded game. /game/:id already shows analyze-in-progress and
      // renders the moment analysis lands — their first session opens on
      // THEIR game, not an empty dashboard.
      try {
        const ahaRes = await fetch(`${API}/journey/first-aha`, {
          method: "POST", credentials: "include",
        });
        if (ahaRes.ok) {
          const aha = await ahaRes.json();
          if (aha.game_id) {
            track(ANALYTICS_EVENTS.FUNNEL_FIRST_AHA, { was_loss: aha.was_loss });
            setAnalysisProgress(100);
            navigate(`/game/${aha.game_id}`);
            return;
          }
        }
      } catch { /* fall through to instant DNA / diagnostic */ }

      // Step 2: Get Instant Chess DNA (computed from PGN alone — no Stockfish)
      try {
        const dnaRes = await fetch(`${API}/journey/instant-dna`, { credentials: "include" });
        if (dnaRes.ok) {
          const dna = await dnaRes.json();
          if (dna.has_data && dna.games_analyzed > 0) {
            setAnalysisProgress(100);
            setInstantDNA(dna);
            setAnalyzing(false);
            return;
          }
        }
      } catch { /* fall through */ }

      // No instant DNA yet — games are still in the analysis queue (or
      // there were none). Send the user to the 20-puzzle diagnostic
      // instead of staring at a spinner. The diagnostic IS the
      // productive use of waiting time, and it produces a real
      // rating-band + per-area readout to seed dashboard recommendations
      // until real-game data takes over.
      setAnalysisProgress(100);
      navigate("/diagnostic");
    } catch {
      setError("Something went wrong. Please try again.");
      setAnalyzing(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoMode = () => {
    window.sessionStorage.setItem("demo_mode_bypass", "true");
    navigate("/training?demo=true");
  };

  // ──────────────────────────────────────────────────
  // INSTANT DNA SCREEN (shown before Stockfish completes)
  // ──────────────────────────────────────────────────
  if (instantDNA && instantDNA.has_data) {
    // After DNA reveal, send user directly to training with their top weakness
    // This is the "value in 2 minutes" moment
    const topWeakness = instantDNA.top_weakness || instantDNA.primary_pattern;
    const trainingUrl = topWeakness ? `/training?focus=${topWeakness}` : "/training";

    return (
      <div className="experience-page experience-onboarding-page min-h-screen flex items-center justify-center p-4 bg-background">
        <div className="experience-onboarding-shell w-full max-w-lg py-8">
          <InstantDNA
            data={instantDNA}
            onContinue={() => navigate(trainingUrl)}
            ctaLabel="Start Training Your Weakness"
          />
        </div>
      </div>
    );
  }

  // ──────────────────────────────────────────────────
  // ANALYSIS COMPLETE SCREEN (legacy fallback)
  // ──────────────────────────────────────────────────
  if (analysisResult) {
    const primaryPattern = Object.entries(analysisResult.patterns || {})
      .sort((a, b) => b[1].weighted_score - a[1].weighted_score)[0];

    return (
      <Shell>
        <div className="text-center mb-6">
          <div className="mx-auto w-14 h-14 rounded-full flex items-center justify-center mb-4" style={{ background: "rgba(22,163,74,0.1)" }}>
            <CheckCircle2 className="w-7 h-7 text-emerald-600" />
          </div>
          <h1 className="text-2xl text-foreground tracking-tight font-heading">I found where we should begin.</h1>
          <p className="text-sm text-muted-foreground font-light mt-1">
            Your games already tell a useful story. We’ll keep refining it as we work together.
          </p>
        </div>

        {/* Primary Weakness */}
        {primaryPattern && (
          <div className="p-4 rounded-sm border mb-6" style={{ borderColor: BORDER, borderLeftWidth: 3, borderLeftColor: WINE }}>
            <div className="flex items-center gap-2 mb-1.5">
              <Target className="w-3.5 h-3.5" style={{ color: WINE }} />
              <p className="text-[10px] uppercase tracking-[0.15em] font-mono" style={{ color: WINE }}>Where we’ll start</p>
            </div>
            <p className="text-base text-foreground font-heading">
              {primaryPattern[0].replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
            </p>
            <p className="text-xs text-muted-foreground font-light mt-1">I’ve seen this decision more than once, so it is worth making natural.</p>
          </div>
        )}

        <WineButton onClick={() => {
          window.sessionStorage.removeItem("demo_mode_bypass");
          const pattern = primaryPattern ? primaryPattern[0] : "";
          navigate(pattern ? `/training?focus=${pattern}` : "/training");
        }} testId="start-training-btn">
          Start with your coach <ArrowRight className="w-4 h-4 ml-1.5" />
        </WineButton>
      </Shell>
    );
  }

  // ──────────────────────────────────────────────────
  // ANALYZING SCREEN
  // ──────────────────────────────────────────────────
  if (analyzing) {
    return (
      <Shell>
        <div className="text-center py-6">
          <Loader2 className="w-10 h-10 animate-spin mx-auto mb-5" style={{ color: GOLD }} />
          <h2 className="text-xl text-foreground tracking-tight mb-1 font-heading">
            I’m reading your games
          </h2>
          <p className="text-sm text-muted-foreground font-light mb-6">I’m looking for decisions that repeat, not judging a single result.</p>

          {analysisProgress > 60 && (
            <button
              onClick={() => navigate("/training")}
              className="mt-6 text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors font-light"
              data-testid="skip-analysis-btn"
            >
              Skip and go to Training →
            </button>
          )}
        </div>
      </Shell>
    );
  }

  // ──────────────────────────────────────────────────
  // MAIN WIZARD
  // ──────────────────────────────────────────────────
  return (
    <Shell>
      <p className="cg-eyebrow">A short conversation before we begin</p>

      <h1 className="text-xl text-foreground tracking-tight mb-1 font-heading">
        {step === 1 ? "Show me where you play." : "What do you want from your chess?"}
      </h1>
      <p className="text-sm text-muted-foreground font-light mb-6">
        {step === 1 ? "Your real games are the best way for me to understand you." : "Your rating is context, not your curriculum. Tell me what matters to you."}
      </p>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-sm text-sm mb-4 font-light" style={{ background: "rgba(114,47,55,0.06)", color: WINE }}>
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {/* ── STEP 1: Link Accounts ── */}
      {step === 1 && (
        <div className="space-y-5">
          <AccountInput
            label="Chess.com"
            placeholder="Enter your Chess.com username"
            value={chessComUsername}
            onChange={(v) => { setChessComUsername(v); setChessComVerified(false); }}
            verified={chessComVerified}
            verifying={verifyingChessCom}
            onVerify={() => verifyAccount("chess.com")}
            testId="chesscom"
          />

          <div className="flex items-center gap-4">
            <div className="h-px flex-1" style={{ background: BORDER }} />
            <span className="text-[10px] text-muted-foreground font-mono">OR</span>
            <div className="h-px flex-1" style={{ background: BORDER }} />
          </div>

          <AccountInput
            label="Lichess"
            placeholder="Enter your Lichess username"
            value={lichessUsername}
            onChange={(v) => { setLichessUsername(v); setLichessVerified(false); }}
            verified={lichessVerified}
            verifying={verifyingLichess}
            onVerify={() => verifyAccount("lichess")}
            testId="lichess"
          />

          <div className="pt-3 space-y-2.5">
            <WineButton onClick={handleStep1Continue} disabled={!hasLinkedAccount} testId="step1-continue-btn">
              Tell me what you want next <ArrowRight className="w-4 h-4 ml-1.5" />
            </WineButton>
            <button
              onClick={handleDemoMode}
              className="w-full py-2.5 text-sm text-muted-foreground/60 hover:text-muted-foreground transition-colors font-light"
              data-testid="demo-mode-btn"
            >
              Start without connecting a game account
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 2: Calibrate ── */}
      {step === 2 && (
        <div className="space-y-5">
          {/* Account context: acknowledge it without turning onboarding into a rating report. */}
          {detectedRating && (
            <div className="p-4 rounded-sm border" style={{ borderColor: BORDER }}>
              <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider">Your {detectedPlatform} games are connected</p>
              <p className="text-sm text-foreground mt-1">I’ll build your plan from the decisions inside those games—not from the number beside your name.</p>
            </div>
          )}

          {/* FIDE Rating */}
          <div>
            <label className="text-xs text-muted-foreground font-mono uppercase tracking-wider block mb-1.5" style={{ color: GOLD_TEXT }}>
              Official FIDE rating (only if you want to share it)
            </label>
            <input
              type="number"
              placeholder="Leave blank if you don't have one"
              className="w-full px-3 py-2.5 text-sm bg-white border rounded-sm font-light focus:outline-none focus:ring-1"
              style={{ borderColor: BORDER, "--tw-ring-color": WINE }}
              value={fideRating}
              onChange={(e) => setFideRating(e.target.value)}
              data-testid="fide-input"
            />
            <p className="text-[10px] text-muted-foreground/60 mt-1 font-light">Only if you have an official FIDE rating</p>
          </div>

          {/* Focus Intent */}
          <div>
            <label className="text-xs font-mono uppercase tracking-wider block mb-2.5" style={{ color: GOLD_TEXT }}>
              What would you most like to understand better?
            </label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { value: "tactics", label: "Tactical awareness", icon: <Zap className="w-4 h-4" style={{ color: GOLD }} /> },
                { value: "openings", label: "Opening discipline", icon: <BookOpen className="w-4 h-4" style={{ color: GOLD_TEXT }} /> },
                { value: "endgames", label: "Endgame precision", icon: <Target className="w-4 h-4 text-emerald-600" /> },
                { value: "stability", label: "Decision stability", icon: <Brain className="w-4 h-4" style={{ color: WINE }} /> },
              ].map((opt) => (
                <button
                  key={opt.value}
                  className="flex items-center gap-2.5 p-3 rounded-sm border text-left transition-all text-sm font-light"
                  style={{
                    borderColor: focusIntent === opt.value ? WINE : BORDER,
                    background: focusIntent === opt.value ? "rgba(114,47,55,0.04)" : "white",
                  }}
                  onClick={() => setFocusIntent(opt.value)}
                  data-testid={`focus-${opt.value}`}
                >
                  {opt.icon}
                  <span className="text-foreground">{opt.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Player Motivation — self-declared "why are you here" (segments the user base) */}
          <div>
            <label className="text-xs font-mono uppercase tracking-wider block mb-2.5" style={{ color: GOLD_TEXT }}>
              What brings you to ChessGuru?
            </label>
            <div className="grid grid-cols-1 gap-2">
              {[
                { value: "compete", label: "Prepare for serious games" },
                { value: "improve", label: "Get steadily better" },
                { value: "learn", label: "Learn and enjoy the game" },
                { value: "fun", label: "Just play for fun" },
              ].map((opt) => (
                <button
                  key={opt.value}
                  className="flex items-center gap-2.5 p-3 rounded-sm border text-left transition-all text-sm font-light"
                  style={{
                    borderColor: playerMotivation === opt.value ? WINE : BORDER,
                    background: playerMotivation === opt.value ? "rgba(114,47,55,0.04)" : "white",
                  }}
                  onClick={() => setPlayerMotivation(opt.value)}
                  data-testid={`motivation-${opt.value}`}
                >
                  <span className="text-foreground">{opt.label}</span>
                </button>
              ))}
            </div>
            <p className="text-[10px] text-muted-foreground/60 mt-1 font-light">Optional — helps your coach meet you where you are.</p>
          </div>

          {/* Actions */}
          <div className="pt-2 flex gap-2">
            <button
              onClick={() => setStep(1)}
              className="flex-1 py-2.5 text-sm text-foreground border rounded-sm font-light flex items-center justify-center gap-1.5 transition-colors hover:bg-black/[0.02]"
              style={{ borderColor: BORDER }}
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back
            </button>
            <button
              onClick={handleStep2Complete}
              disabled={isLoading}
              className="flex-1 py-2.5 text-sm text-white rounded-sm font-light flex items-center justify-center gap-1.5 transition-opacity"
              style={{ background: WINE, opacity: isLoading ? 0.6 : 1 }}
              data-testid="complete-onboarding-btn"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Build my first plan <ArrowRight className="w-4 h-4" /></>}
            </button>
          </div>
        </div>
      )}
    </Shell>
  );
};

// ── SHARED COMPONENTS ──

const Shell = ({ children }) => (
  <div className="experience-page experience-onboarding-page min-h-screen flex items-center justify-center p-4 bg-background">
    <div className="experience-onboarding-shell cg-panel w-full max-w-lg !p-8">
      {children}
    </div>
  </div>
);

const AccountInput = ({ label, placeholder, value, onChange, verified, verifying, onVerify, testId }) => (
  <div>
    <label className="text-xs font-mono uppercase tracking-wider block mb-1.5" style={{ color: GOLD_TEXT }}>
      {label} Username
    </label>
    <div className="flex gap-2">
      <input
        placeholder={placeholder}
        className="flex-1 px-3 py-2.5 text-sm bg-white border rounded-sm font-light focus:outline-none focus:ring-1"
        style={{ borderColor: BORDER, "--tw-ring-color": WINE }}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={verifying}
        data-testid={`${testId}-input`}
      />
      <button
        className="px-3 py-2.5 border rounded-sm transition-colors flex items-center justify-center"
        style={{
          borderColor: verified ? "#16a34a" : BORDER,
          background: verified ? "rgba(22,163,74,0.06)" : "white",
          opacity: !value.trim() || verifying ? 0.4 : 1,
        }}
        onClick={onVerify}
        disabled={!value.trim() || verifying}
        data-testid={`verify-${testId}-btn`}
      >
        {verifying ? <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" /> : verified ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : <LinkIcon className="w-4 h-4 text-muted-foreground" />}
      </button>
    </div>
    {verified && (
      <p className="text-[10px] text-emerald-600 flex items-center gap-1 mt-1 font-mono">
        <CheckCircle2 className="w-3 h-3" /> Account verified
      </p>
    )}
  </div>
);

const WineButton = ({ children, onClick, disabled, testId }) => (
  <button
    className="w-full py-2.5 text-sm text-white rounded-sm font-light flex items-center justify-center transition-opacity"
    style={{ background: WINE, opacity: disabled ? 0.4 : 1 }}
    onClick={onClick}
    disabled={disabled}
    data-testid={testId}
  >
    {children}
  </button>
);

export default Onboarding;
