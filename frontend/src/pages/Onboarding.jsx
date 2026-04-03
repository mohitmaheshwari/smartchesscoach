/**
 * ONBOARDING PAGE — Warm Wine/Gold Theme
 *
 * 2-step wizard:
 *   Step 1: Link Chess.com / Lichess account
 *   Step 2: Calibrate profile (rating, focus intent)
 *   → Analyze games → Show results
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import {
  Loader2, CheckCircle2, AlertCircle, ArrowRight, ArrowLeft,
  Link as LinkIcon, Target, Brain, Zap, BookOpen,
} from "lucide-react";

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

  // Analysis
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisResult, setAnalysisResult] = useState(null);

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
      const url = isChessCom
        ? `https://api.chess.com/pub/player/${username.toLowerCase()}`
        : `https://lichess.org/api/user/${username}`;
      const res = await fetch(url);

      if (res.ok) {
        isChessCom ? setChessComVerified(true) : setLichessVerified(true);
        try {
          const linkRes = await fetch(`${API}/settings/link-account`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ platform, username: username.toLowerCase() }),
          });
          if (linkRes.ok) {
            const d = await linkRes.json();
            if (d.assessed_rating && (!detectedRating || isChessCom)) {
              setDetectedRating(d.assessed_rating);
              setDetectedPlatform(platform);
              setGamesAnalyzed(d.games_analyzed || 0);
            }
          }
        } catch { /* ok */ }
      } else {
        setError(`${isChessCom ? "Chess.com" : "Lichess"} username not found. Please check and try again.`);
        isChessCom ? setChessComVerified(false) : setLichessVerified(false);
      }
    } catch {
      setError(`Failed to verify ${isChessCom ? "Chess.com" : "Lichess"} account.`);
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
      if (chessComVerified) {
        await fetch(`${API}/settings/link-account`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ platform: "chess.com", username: chessComUsername.toLowerCase() }) });
      }
      if (lichessVerified) {
        await fetch(`${API}/settings/link-account`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ platform: "lichess", username: lichessUsername.toLowerCase() }) });
      }
      await fetch(`${API}/settings/profile`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({ fide_rating: fideRating ? parseInt(fideRating) : null, detected_rating: detectedRating, detected_platform: detectedPlatform, focus_intent: focusIntent || null }),
      });

      setAnalyzing(true);
      setAnalysisProgress(10);
      await fetch(`${API}/games/sync`, { method: "POST", credentials: "include" }).catch(() => {});
      setAnalysisProgress(50);

      let attempts = 0;
      while (attempts < 45) {
        await new Promise(r => setTimeout(r, 1000));
        attempts++;
        setAnalysisProgress(50 + (attempts / 45) * 45);
        try {
          const pr = await fetch(`${API}/cognitive/patterns`, { credentials: "include" });
          if (pr.ok) {
            const patterns = await pr.json();
            if (patterns.games_analyzed > 0) {
              setAnalysisProgress(100);
              setAnalysisResult(patterns);
              return;
            }
          }
        } catch { /* keep polling */ }
      }
      setAnalysisProgress(100);
      await new Promise(r => setTimeout(r, 500));
      navigate("/training");
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
  // ANALYSIS COMPLETE SCREEN
  // ──────────────────────────────────────────────────
  if (analysisResult) {
    const tsi = analysisResult.thinking_stability_index;
    const primaryPattern = Object.entries(analysisResult.patterns || {})
      .sort((a, b) => b[1].weighted_score - a[1].weighted_score)[0];
    const tsiLabel = tsi >= 80 ? "Stable" : tsi >= 65 ? "Moderate instability" : tsi >= 50 ? "Frequent lapses" : "High volatility";
    const tsiColor = tsi >= 80 ? "#16a34a" : tsi >= 65 ? GOLD : tsi >= 50 ? "#ea580c" : WINE;

    return (
      <Shell>
        <div className="text-center mb-6">
          <div className="mx-auto w-14 h-14 rounded-full flex items-center justify-center mb-4" style={{ background: "rgba(22,163,74,0.1)" }}>
            <CheckCircle2 className="w-7 h-7 text-emerald-600" />
          </div>
          <h1 className="text-2xl text-foreground tracking-tight font-heading">Analysis Complete</h1>
          <p className="text-sm text-muted-foreground font-light mt-1">
            We analyzed {analysisResult.games_analyzed} of your recent games
          </p>
        </div>

        {/* TSI Score */}
        <div className="text-center p-6 rounded-sm border mb-5" style={{ borderColor: BORDER }}>
          <p className="text-[10px] uppercase tracking-[0.2em] font-mono mb-2" style={{ color: GOLD_TEXT }}>
            Thinking Stability Index
          </p>
          <p className="text-5xl font-light font-heading" style={{ color: tsiColor }}>{tsi}</p>
          <p className="text-xs mt-1 font-mono" style={{ color: tsiColor }}>{tsiLabel}</p>
        </div>

        {/* Primary Weakness */}
        {primaryPattern && (
          <div className="p-4 rounded-sm border mb-6" style={{ borderColor: BORDER, borderLeftWidth: 3, borderLeftColor: WINE }}>
            <div className="flex items-center gap-2 mb-1.5">
              <Target className="w-3.5 h-3.5" style={{ color: WINE }} />
              <p className="text-[10px] uppercase tracking-[0.15em] font-mono" style={{ color: WINE }}>Primary Focus Area</p>
            </div>
            <p className="text-base text-foreground font-heading">
              {primaryPattern[0].replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
            </p>
            <p className="text-xs text-muted-foreground font-light mt-1">
              Found in {primaryPattern[1].frequency} positions across your games
            </p>
          </div>
        )}

        <WineButton onClick={() => { window.sessionStorage.removeItem("demo_mode_bypass"); navigate("/training"); }} testId="start-training-btn">
          Start Fixing This <ArrowRight className="w-4 h-4 ml-1.5" />
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
            Analyzing Your Games
          </h2>
          <p className="text-sm text-muted-foreground font-light mb-6">This usually takes 15–30 seconds...</p>

          <div className="w-full h-1.5 rounded-full mb-2" style={{ background: "rgba(0,0,0,0.05)" }}>
            <div className="h-1.5 rounded-full transition-all duration-500" style={{ width: `${analysisProgress}%`, background: GOLD }} />
          </div>
          <p className="text-[10px] text-muted-foreground font-mono">{analysisProgress}%</p>

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
      {/* Progress */}
      <div className="flex items-center justify-between mb-5">
        <span className="text-[10px] text-muted-foreground font-mono">Step {step} of 2</span>
        <div className="flex gap-1">
          <div className="w-8 h-1 rounded-full" style={{ background: GOLD }} />
          <div className="w-8 h-1 rounded-full" style={{ background: step >= 2 ? GOLD : "rgba(0,0,0,0.06)" }} />
        </div>
      </div>

      <h1 className="text-xl text-foreground tracking-tight mb-1 font-heading">
        {step === 1 ? "Link Your Chess Account" : "Calibrate Your Profile"}
      </h1>
      <p className="text-sm text-muted-foreground font-light mb-6">
        {step === 1 ? "Connect at least one account to analyze your games" : "Help us understand your current level"}
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
              Continue <ArrowRight className="w-4 h-4 ml-1.5" />
            </WineButton>
            <button
              onClick={handleDemoMode}
              className="w-full py-2.5 text-sm text-muted-foreground/60 hover:text-muted-foreground transition-colors font-light"
              data-testid="demo-mode-btn"
            >
              Explore Demo Mode Instead
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 2: Calibrate ── */}
      {step === 2 && (
        <div className="space-y-5">
          {/* Detected Rating */}
          {detectedRating && (
            <div className="p-4 rounded-sm border" style={{ borderColor: BORDER }}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider">
                    {gamesAnalyzed > 0
                      ? `Live ${detectedPlatform} Rating · ${gamesAnalyzed} games available`
                      : `Live ${detectedPlatform} Rating`}
                  </p>
                  <p className="text-2xl text-foreground font-light mt-0.5 font-heading">
                    {detectedRating}
                  </p>
                </div>
                <RatingBadge rating={detectedRating} />
              </div>
            </div>
          )}

          {/* FIDE Rating */}
          <div>
            <label className="text-xs text-muted-foreground font-mono uppercase tracking-wider block mb-1.5" style={{ color: GOLD_TEXT }}>
              FIDE Rating (Optional)
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
              What do you want to improve most?
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
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Analyze My Games <ArrowRight className="w-4 h-4" /></>}
            </button>
          </div>
        </div>
      )}
    </Shell>
  );
};

// ── SHARED COMPONENTS ──

const Shell = ({ children }) => (
  <div className="min-h-screen flex items-center justify-center p-4 bg-background">
    <div className="w-full max-w-lg bg-card border border-border rounded-lg p-8 shadow-sm">
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

const RatingBadge = ({ rating }) => {
  const config = rating >= 2000 ? { label: "Expert", color: WINE }
    : rating >= 1800 ? { label: "Advanced", color: GOLD_TEXT }
    : rating >= 1400 ? { label: "Intermediate", color: GOLD_TEXT }
    : rating >= 1000 ? { label: "Developing", color: "#16a34a" }
    : { label: "Beginner", color: "#888" };
  return (
    <span className="text-[10px] px-2 py-1 rounded-sm font-mono" style={{ color: config.color, background: `${config.color}15` }}>
      {config.label}
    </span>
  );
};

export default Onboarding;
