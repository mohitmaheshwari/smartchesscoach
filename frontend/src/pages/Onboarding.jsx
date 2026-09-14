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

const BRAND = "#0F5B47";
const BRAND_TEXT = "#28745D";
const LIME = "#B6FF3D";
const INK = "#071B14";
const MUTED_INK = "#596861";
const BORDER = "#DDD8CC";
const ERROR = "#9B2C35";

// Onboarding is intentionally theme-independent. Mixing dark-mode text tokens
// with hard-coded white inputs produced an almost-black page with washed-out
// labels and an unreadable primary action. Local variables keep every state in
// the same warm, high-contrast visual system as the Activation Hub.
const ONBOARDING_THEME = {
  "--background": "40 33% 94%",
  "--foreground": "158 48% 7%",
  "--card": "40 60% 99%",
  "--muted-foreground": "157 8% 38%",
  "--border": "38 18% 80%",
  "--primary": "158 72% 21%",
  "--accent": "82 100% 62%",
  "--experience-shadow": "158 48% 8%",
  color: INK,
  background: "radial-gradient(circle at 78% 8%, rgba(182,255,61,0.16), transparent 27rem), radial-gradient(circle at 10% 82%, rgba(15,91,71,0.08), transparent 30rem), #F4EFE4",
};

const Onboarding = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  // Asked only when there is no account to read a rating from. Not a rating
  // box: someone who has never played online cannot answer "what is your
  // rating?", and they are exactly who this is for.
  const [selfAssessedLevel, setSelfAssessedLevel] = useState("");
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
          // A stored account link is verified server-side, but it is not proof
          // that its games were imported. Keep this explicit page available as
          // the retry surface after an interrupted import.
          if (user.chess_com_username) {
            setChessComUsername(user.chess_com_username);
            setChessComVerified(true);
          }
          if (user.lichess_username) {
            setLichessUsername(user.lichess_username);
            setLichessVerified(true);
          }
        }
      } catch (e) { /* ignore */ }
    })();
  }, []);

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
      setAnalyzing(true);
      setAnalysisProgress(20);

      // Import through the registered server authority. Account verification
      // alone only proves the username exists; it does not persist any games.
      const linkedAccounts = [];
      if (chessComVerified) {
        linkedAccounts.push({ platform: "chess.com", username: chessComUsername.trim().toLowerCase() });
      }
      if (lichessVerified) {
        linkedAccounts.push({ platform: "lichess", username: lichessUsername.trim().toLowerCase() });
      }
      let importedGames = 0;
      for (const account of linkedAccounts) {
        const importRes = await fetch(`${API}/import-games`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(account),
        });
        const importData = await importRes.json().catch(() => ({}));
        if (!importRes.ok) {
          throw new Error(importData.detail || `Could not import your ${account.platform} games.`);
        }
        importedGames += Number(importData.imported) || 0;
      }
      track(ANALYTICS_EVENTS.FUNNEL_IMPORT_DONE, {
        source: "onboarding",
        status: importedGames > 0 ? "new_games" : "already_current",
        total_items: importedGames,
      });

      // This endpoint marks onboarding complete. Call it only after every
      // selected account has passed the import boundary, otherwise a failed
      // import becomes impossible to retry after a reload.
      const profileRes = await fetch(`${API}/settings/profile`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({ fide_rating: fideRating ? parseInt(fideRating) : null, detected_rating: detectedRating, detected_platform: detectedPlatform, focus_intent: focusIntent || null, player_motivation: playerMotivation || null, self_assessed_level: selfAssessedLevel || null }),
      });
      const profileData = await profileRes.json().catch(() => ({}));
      if (!profileRes.ok) {
        throw new Error(profileData.detail || "Your games were imported, but your coaching preferences could not be saved. Please try again.");
      }
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
    } catch (err) {
      setError(err?.message || "Something went wrong. Please try again.");
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
      <div
        className="experience-page experience-onboarding-page min-h-screen flex items-center justify-center p-4 bg-[#F4EFE4]"
        style={ONBOARDING_THEME}
      >
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
          <div className="p-4 rounded-xl border mb-6 bg-white" style={{ borderColor: BORDER, borderLeftWidth: 3, borderLeftColor: BRAND }}>
            <div className="flex items-center gap-2 mb-1.5">
              <Target className="w-3.5 h-3.5" style={{ color: BRAND }} />
              <p className="text-[10px] uppercase tracking-[0.15em] font-mono" style={{ color: BRAND }}>Where we’ll start</p>
            </div>
            <p className="text-base text-foreground font-heading">
              {primaryPattern[0].replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
            </p>
            <p className="text-xs text-muted-foreground font-light mt-1">I’ve seen this decision more than once, so it is worth making natural.</p>
          </div>
        )}

        <PrimaryButton onClick={() => {
          window.sessionStorage.removeItem("demo_mode_bypass");
          const pattern = primaryPattern ? primaryPattern[0] : "";
          navigate(pattern ? `/training?focus=${pattern}` : "/training");
        }} testId="start-training-btn">
          Start with your coach <ArrowRight className="w-4 h-4 ml-1.5" />
        </PrimaryButton>
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
          <Loader2 className="w-10 h-10 animate-spin mx-auto mb-5" style={{ color: BRAND }} />
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

      <h1 className="cg-title !mt-2 !text-[clamp(1.9rem,5vw,2.65rem)] !leading-[1.05]" style={{ color: INK }}>
        {step === 1 ? "Show me where you play." : "What do you want from your chess?"}
      </h1>
      <p className="mt-3 text-[15px] leading-relaxed mb-7" style={{ color: MUTED_INK }}>
        {step === 1 ? "Your real games are the best way for me to understand you." : "Your rating is context, not your curriculum. Tell me what matters to you."}
      </p>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-xl border text-sm mb-4" style={{ background: "#FFF1F2", borderColor: "#F3C3C7", color: ERROR }}>
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
            <span className="text-[10px] font-semibold tracking-[0.12em]" style={{ color: MUTED_INK }}>OR</span>
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
            <PrimaryButton onClick={handleStep1Continue} disabled={!hasLinkedAccount} testId="step1-continue-btn">
              Tell me what you want next <ArrowRight className="w-4 h-4 ml-1.5" />
            </PrimaryButton>
            <button
              onClick={handleDemoMode}
              className="w-full rounded-xl py-3 text-sm font-medium transition-colors hover:bg-black/[0.035] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
              style={{ color: BRAND_TEXT, "--tw-ring-color": BRAND }}
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

          {/* No account to read: ask, rather than guessing. Selection used no
              rating at all before this, so a first-time player met the same
              ladder as a club player and got 12% of the first position right. */}
          {!detectedRating && (
            <div>
              <label className="text-xs font-mono uppercase tracking-wider block mb-1.5" style={{ color: BRAND_TEXT }}>
                Where are you with chess right now?
              </label>
              <p className="text-[11px] text-muted-foreground/70 mb-2.5 font-light">
                No wrong answer. It only decides where I start.
              </p>
              <div className="grid grid-cols-1 gap-2">
                {[
                  { value: "learning_moves", label: "I’m still learning how the pieces move" },
                  { value: "know_rules", label: "I know the rules and play with friends" },
                  { value: "plays_regularly", label: "I play regularly and know some openings" },
                  { value: "experienced", label: "I’m experienced — I know my theory" },
                ].map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setSelfAssessedLevel(option.value)}
                    className="text-[13px] font-light px-3 py-2.5 rounded-sm border text-left transition-colors"
                    style={{
                      borderColor: selfAssessedLevel === option.value ? BRAND : BORDER,
                      background: selfAssessedLevel === option.value ? "#EAF6F0" : "white",
                    }}
                    data-testid={`self-level-${option.value}`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* FIDE Rating */}
          <div>
            <label className="text-xs text-muted-foreground font-mono uppercase tracking-wider block mb-1.5" style={{ color: BRAND_TEXT }}>
              Official FIDE rating (only if you want to share it)
            </label>
            <input
              type="number"
              placeholder="Leave blank if you don't have one"
              className="w-full h-12 px-3.5 text-sm bg-white border rounded-lg focus:outline-none focus:ring-2 text-[#071B14] placeholder:text-[#7A8580]"
              style={{ borderColor: BORDER, "--tw-ring-color": BRAND }}
              value={fideRating}
              onChange={(e) => setFideRating(e.target.value)}
              data-testid="fide-input"
            />
            <p className="text-[10px] text-muted-foreground/60 mt-1 font-light">Only if you have an official FIDE rating</p>
          </div>

          {/* Focus Intent */}
          <div>
            <label className="text-xs font-mono uppercase tracking-wider block mb-2.5" style={{ color: BRAND_TEXT }}>
              What would you most like to understand better?
            </label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { value: "tactics", label: "Tactical awareness", icon: <Zap className="w-4 h-4" style={{ color: BRAND }} /> },
                { value: "openings", label: "Opening discipline", icon: <BookOpen className="w-4 h-4" style={{ color: BRAND_TEXT }} /> },
                { value: "endgames", label: "Endgame precision", icon: <Target className="w-4 h-4 text-emerald-600" /> },
                { value: "stability", label: "Decision stability", icon: <Brain className="w-4 h-4" style={{ color: BRAND }} /> },
              ].map((opt) => (
                <button
                  key={opt.value}
                  className="flex items-center gap-2.5 p-3 rounded-sm border text-left transition-all text-sm font-light"
                  style={{
                    borderColor: focusIntent === opt.value ? BRAND : BORDER,
                    background: focusIntent === opt.value ? "#EAF6F0" : "white",
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
            <label className="text-xs font-mono uppercase tracking-wider block mb-2.5" style={{ color: BRAND_TEXT }}>
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
                    borderColor: playerMotivation === opt.value ? BRAND : BORDER,
                    background: playerMotivation === opt.value ? "#EAF6F0" : "white",
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
              className="flex-1 min-h-12 text-sm border rounded-xl font-semibold flex items-center justify-center gap-1.5 transition-colors hover:bg-black/[0.03]"
              style={{ borderColor: BORDER, color: INK, background: "white" }}
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back
            </button>
            <button
              onClick={handleStep2Complete}
              disabled={isLoading}
              className="flex-1 min-h-12 text-sm rounded-xl font-semibold flex items-center justify-center gap-1.5 transition-all hover:-translate-y-px disabled:hover:translate-y-0"
              style={{
                background: isLoading ? "#E4E5E0" : LIME,
                color: isLoading ? "#66716C" : INK,
                boxShadow: isLoading ? "none" : "0 12px 28px rgba(127,181,32,0.22)",
              }}
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
  <div
    className="experience-page experience-onboarding-page min-h-screen flex items-center justify-center px-4 py-8 md:py-12 bg-[#F4EFE4]"
    style={ONBOARDING_THEME}
    data-testid="onboarding-page"
  >
    <div
      className="experience-onboarding-shell cg-panel w-full max-w-[560px] !p-6 sm:!p-8 md:!p-10"
      style={{ background: "#FFFCF7", borderColor: "rgba(7,27,20,0.12)", boxShadow: "0 28px 80px rgba(7,27,20,0.10)" }}
      data-testid="onboarding-panel"
    >
      {children}
    </div>
  </div>
);

const AccountInput = ({ label, placeholder, value, onChange, verified, verifying, onVerify, testId }) => (
  <div className="rounded-xl border bg-white p-4" style={{ borderColor: verified ? "#7CC7AA" : BORDER }}>
    <label className="text-[11px] font-semibold uppercase tracking-[0.14em] block mb-2" style={{ color: BRAND_TEXT }}>
      {label} Username
    </label>
    <div className="flex flex-col gap-2 sm:flex-row">
      <input
        placeholder={placeholder}
        className="min-w-0 flex-1 h-12 px-3.5 text-sm bg-white border rounded-lg focus:outline-none focus:ring-2 text-[#071B14] placeholder:text-[#7A8580] disabled:bg-[#F2F2EE]"
        style={{ borderColor: BORDER, "--tw-ring-color": BRAND }}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={verifying}
        data-testid={`${testId}-input`}
      />
      <button
        className="min-h-12 shrink-0 px-4 border rounded-lg transition-all flex items-center justify-center gap-2 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
        style={{
          borderColor: verified ? "#159267" : BRAND,
          background: verified ? "#EAF8F2" : (!value.trim() || verifying ? "#ECEDE8" : BRAND),
          color: verified ? "#0B6A49" : (!value.trim() || verifying ? "#69746F" : "white"),
          "--tw-ring-color": BRAND,
        }}
        onClick={onVerify}
        disabled={!value.trim() || verifying}
        data-testid={`verify-${testId}-btn`}
      >
        {verifying ? <Loader2 className="w-4 h-4 animate-spin" /> : verified ? <CheckCircle2 className="w-4 h-4" /> : <LinkIcon className="w-4 h-4" />}
        <span>{verifying ? "Checking…" : verified ? "Connected" : "Connect"}</span>
      </button>
    </div>
    {verified && (
      <p className="text-[10px] text-emerald-600 flex items-center gap-1 mt-1 font-mono">
        <CheckCircle2 className="w-3 h-3" /> Account verified
      </p>
    )}
  </div>
);

const PrimaryButton = ({ children, onClick, disabled, testId }) => (
  <button
    className="w-full min-h-12 px-4 text-sm rounded-xl font-semibold flex items-center justify-center transition-all hover:-translate-y-px disabled:cursor-not-allowed disabled:hover:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
    style={{
      background: disabled ? "#E4E5E0" : LIME,
      color: disabled ? "#66716C" : INK,
      boxShadow: disabled ? "none" : "0 12px 28px rgba(127,181,32,0.22)",
      "--tw-ring-color": BRAND,
    }}
    onClick={onClick}
    disabled={disabled}
    data-testid={testId}
  >
    {children}
  </button>
);

export default Onboarding;
