/**
 * ONBOARDING PAGE
 * 
 * 2-step wizard for new users:
 * Step 1: Link at least one account (Chess.com / Lichess / PGN)
 * Step 2: Skill calibration + Focus intent
 * 
 * After completion: Analyze games and show first results
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { RadioGroup, RadioGroupItem } from "../components/ui/radio-group";
import { Label } from "../components/ui/label";
import { 
  Loader2, 
  CheckCircle2, 
  AlertCircle,
  ArrowRight,
  Upload,
  Link as LinkIcon,
  Target,
  Brain,
  Zap,
  BookOpen
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const Onboarding = () => {
  const navigate = useNavigate();
  
  // Wizard state
  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  
  // Step 1: Account linking
  const [chessComUsername, setChessComUsername] = useState("");
  const [lichessUsername, setLichessUsername] = useState("");
  const [chessComVerified, setChessComVerified] = useState(false);
  const [lichessVerified, setLichessVerified] = useState(false);
  const [verifyingChessCom, setVerifyingChessCom] = useState(false);
  const [verifyingLichess, setVerifyingLichess] = useState(false);
  
  // Step 2: Skill + Focus
  const [fideRating, setFideRating] = useState("");
  const [selfRating, setSelfRating] = useState("intermediate");
  const [focusIntent, setFocusIntent] = useState("");
  
  // Analysis state
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisResult, setAnalysisResult] = useState(null);

  // Check if user needs onboarding
  useEffect(() => {
    checkOnboardingStatus();
  }, []);

  const checkOnboardingStatus = async () => {
    try {
      const response = await fetch(`${API}/auth/me`, { credentials: "include" });
      if (response.ok) {
        const user = await response.json();
        // If user already has linked accounts, skip onboarding
        if (user.chess_com_username || user.lichess_username) {
          navigate("/training");
        }
      }
    } catch (e) {
      console.error("Failed to check onboarding status:", e);
    }
  };

  const verifyChessComAccount = async () => {
    if (!chessComUsername.trim()) return;
    
    setVerifyingChessCom(true);
    setError("");
    
    try {
      const response = await fetch(
        `https://api.chess.com/pub/player/${chessComUsername.toLowerCase()}`
      );
      
      if (response.ok) {
        setChessComVerified(true);
      } else {
        setError("Chess.com username not found. Please check and try again.");
        setChessComVerified(false);
      }
    } catch (e) {
      setError("Failed to verify Chess.com account. Please try again.");
      setChessComVerified(false);
    } finally {
      setVerifyingChessCom(false);
    }
  };

  const verifyLichessAccount = async () => {
    if (!lichessUsername.trim()) return;
    
    setVerifyingLichess(true);
    setError("");
    
    try {
      const response = await fetch(
        `https://lichess.org/api/user/${lichessUsername}`
      );
      
      if (response.ok) {
        setLichessVerified(true);
      } else {
        setError("Lichess username not found. Please check and try again.");
        setLichessVerified(false);
      }
    } catch (e) {
      setError("Failed to verify Lichess account. Please try again.");
      setLichessVerified(false);
    } finally {
      setVerifyingLichess(false);
    }
  };

  const hasLinkedAccount = chessComVerified || lichessVerified;

  const handleStep1Continue = () => {
    if (!hasLinkedAccount) {
      setError("Please link at least one account to continue.");
      return;
    }
    setError("");
    setStep(2);
  };

  const handleStep2Complete = async () => {
    setIsLoading(true);
    setError("");
    
    try {
      // Save linked accounts
      if (chessComVerified) {
        await fetch(`${API}/settings/link-account`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            platform: "chess.com",
            username: chessComUsername.toLowerCase()
          })
        });
      }
      
      if (lichessVerified) {
        await fetch(`${API}/settings/link-account`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            platform: "lichess",
            username: lichessUsername.toLowerCase()
          })
        });
      }
      
      // Save skill calibration
      await fetch(`${API}/settings/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fide_rating: fideRating ? parseInt(fideRating) : null,
          self_rating: selfRating,
          focus_intent: focusIntent || null
        })
      });
      
      // Start game analysis
      setAnalyzing(true);
      setAnalysisProgress(10);
      
      // Trigger game sync
      const syncResponse = await fetch(`${API}/games/sync`, {
        method: "POST",
        credentials: "include"
      });
      
      if (!syncResponse.ok) {
        throw new Error("Failed to sync games");
      }
      
      setAnalysisProgress(50);
      
      // Poll for analysis completion
      let attempts = 0;
      const maxAttempts = 30; // 30 seconds max
      
      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
        setAnalysisProgress(50 + (attempts / maxAttempts) * 40);
        
        // Check if we have analyzed games
        const patternsResponse = await fetch(`${API}/cognitive/patterns`, {
          credentials: "include"
        });
        
        if (patternsResponse.ok) {
          const patterns = await patternsResponse.json();
          if (patterns.games_analyzed > 0) {
            setAnalysisProgress(100);
            setAnalysisResult(patterns);
            break;
          }
        }
      }
      
      if (!analysisResult && attempts >= maxAttempts) {
        // Even if analysis isn't complete, proceed
        setAnalysisProgress(100);
      }
      
    } catch (e) {
      console.error("Onboarding error:", e);
      setError("Something went wrong. Please try again.");
      setAnalyzing(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartTraining = () => {
    navigate("/training");
  };

  const handleDemoMode = () => {
    navigate("/training?demo=true");
  };

  // Analysis complete screen
  if (analysisResult) {
    const tsi = analysisResult.thinking_stability_index;
    const primaryPattern = Object.entries(analysisResult.patterns || {})
      .sort((a, b) => b[1].weighted_score - a[1].weighted_score)[0];
    
    const tsiLabel = tsi >= 80 ? "Stable" : 
                     tsi >= 65 ? "Moderate instability" :
                     tsi >= 50 ? "Frequent lapses" : "High volatility";
    
    const tsiColor = tsi >= 80 ? "text-green-400" :
                     tsi >= 65 ? "text-yellow-400" :
                     tsi >= 50 ? "text-orange-400" : "text-red-400";

    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-lg border-slate-700 bg-slate-900/50">
          <CardHeader className="text-center">
            <div className="mx-auto w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mb-4">
              <CheckCircle2 className="w-8 h-8 text-green-500" />
            </div>
            <CardTitle className="text-2xl">Analysis Complete</CardTitle>
            <CardDescription>
              We analyzed {analysisResult.games_analyzed} of your recent games
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* TSI Score */}
            <div className="text-center p-6 rounded-lg bg-slate-800/50 border border-slate-700">
              <p className="text-sm text-muted-foreground mb-2">Thinking Stability Index</p>
              <p className={`text-5xl font-bold ${tsiColor}`}>{tsi}</p>
              <p className={`text-sm mt-1 ${tsiColor}`}>{tsiLabel}</p>
            </div>
            
            {/* Primary Weakness */}
            {primaryPattern && (
              <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
                <div className="flex items-center gap-2 mb-2">
                  <Target className="w-4 h-4 text-amber-400" />
                  <p className="text-sm font-medium text-amber-400">Primary Focus Area</p>
                </div>
                <p className="text-lg font-semibold text-white">
                  {primaryPattern[0].replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  Found in {primaryPattern[1].frequency} positions across your games
                </p>
              </div>
            )}
            
            <Button 
              onClick={handleStartTraining} 
              className="w-full"
              size="lg"
              data-testid="start-training-btn"
            >
              Start Fixing This
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Analyzing screen
  if (analyzing) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-lg border-slate-700 bg-slate-900/50">
          <CardContent className="py-12 text-center">
            <Loader2 className="w-12 h-12 animate-spin mx-auto mb-6 text-primary" />
            <h2 className="text-xl font-semibold mb-2">Analyzing Your Games</h2>
            <p className="text-muted-foreground mb-6">
              This usually takes 15-30 seconds...
            </p>
            <div className="w-full bg-slate-800 rounded-full h-2 mb-2">
              <div 
                className="bg-primary h-2 rounded-full transition-all duration-500"
                style={{ width: `${analysisProgress}%` }}
              />
            </div>
            <p className="text-sm text-muted-foreground">{analysisProgress}%</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-lg border-slate-700 bg-slate-900/50">
        <CardHeader>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted-foreground">Step {step} of 2</span>
            <div className="flex gap-1">
              <div className={`w-8 h-1 rounded ${step >= 1 ? 'bg-primary' : 'bg-slate-700'}`} />
              <div className={`w-8 h-1 rounded ${step >= 2 ? 'bg-primary' : 'bg-slate-700'}`} />
            </div>
          </div>
          <CardTitle className="text-xl">
            {step === 1 ? "Link Your Chess Account" : "Calibrate Your Profile"}
          </CardTitle>
          <CardDescription>
            {step === 1 
              ? "Connect at least one account to analyze your games"
              : "Help us understand your current level"
            }
          </CardDescription>
        </CardHeader>
        
        <CardContent className="space-y-6">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}
          
          {step === 1 && (
            <>
              {/* Chess.com */}
              <div className="space-y-2">
                <Label htmlFor="chesscom">Chess.com Username</Label>
                <div className="flex gap-2">
                  <Input
                    id="chesscom"
                    placeholder="Enter your Chess.com username"
                    value={chessComUsername}
                    onChange={(e) => {
                      setChessComUsername(e.target.value);
                      setChessComVerified(false);
                    }}
                    disabled={verifyingChessCom}
                    data-testid="chesscom-input"
                  />
                  <Button
                    variant={chessComVerified ? "secondary" : "outline"}
                    onClick={verifyChessComAccount}
                    disabled={!chessComUsername.trim() || verifyingChessCom}
                    data-testid="verify-chesscom-btn"
                  >
                    {verifyingChessCom ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : chessComVerified ? (
                      <CheckCircle2 className="w-4 h-4 text-green-500" />
                    ) : (
                      <LinkIcon className="w-4 h-4" />
                    )}
                  </Button>
                </div>
                {chessComVerified && (
                  <p className="text-xs text-green-500 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Account verified
                  </p>
                )}
              </div>
              
              <div className="flex items-center gap-4">
                <div className="h-px flex-1 bg-slate-700" />
                <span className="text-xs text-muted-foreground">OR</span>
                <div className="h-px flex-1 bg-slate-700" />
              </div>
              
              {/* Lichess */}
              <div className="space-y-2">
                <Label htmlFor="lichess">Lichess Username</Label>
                <div className="flex gap-2">
                  <Input
                    id="lichess"
                    placeholder="Enter your Lichess username"
                    value={lichessUsername}
                    onChange={(e) => {
                      setLichessUsername(e.target.value);
                      setLichessVerified(false);
                    }}
                    disabled={verifyingLichess}
                    data-testid="lichess-input"
                  />
                  <Button
                    variant={lichessVerified ? "secondary" : "outline"}
                    onClick={verifyLichessAccount}
                    disabled={!lichessUsername.trim() || verifyingLichess}
                    data-testid="verify-lichess-btn"
                  >
                    {verifyingLichess ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : lichessVerified ? (
                      <CheckCircle2 className="w-4 h-4 text-green-500" />
                    ) : (
                      <LinkIcon className="w-4 h-4" />
                    )}
                  </Button>
                </div>
                {lichessVerified && (
                  <p className="text-xs text-green-500 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Account verified
                  </p>
                )}
              </div>
              
              <div className="pt-4 space-y-3">
                <Button 
                  onClick={handleStep1Continue}
                  disabled={!hasLinkedAccount}
                  className="w-full"
                  data-testid="step1-continue-btn"
                >
                  Continue
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
                
                <Button
                  variant="ghost"
                  onClick={handleDemoMode}
                  className="w-full text-muted-foreground"
                  data-testid="demo-mode-btn"
                >
                  Explore Demo Mode Instead
                </Button>
              </div>
            </>
          )}
          
          {step === 2 && (
            <>
              {/* FIDE Rating */}
              <div className="space-y-2">
                <Label htmlFor="fide">FIDE Rating (Optional)</Label>
                <Input
                  id="fide"
                  type="number"
                  placeholder="e.g., 1500"
                  value={fideRating}
                  onChange={(e) => setFideRating(e.target.value)}
                  data-testid="fide-input"
                />
                <p className="text-xs text-muted-foreground">
                  Used to calibrate puzzle difficulty
                </p>
              </div>
              
              {/* Self Rating */}
              <div className="space-y-3">
                <Label>How would you rate yourself?</Label>
                <RadioGroup
                  value={selfRating}
                  onValueChange={setSelfRating}
                  className="grid grid-cols-3 gap-2"
                >
                  <Label
                    htmlFor="beginner"
                    className={`flex flex-col items-center p-3 rounded-lg border cursor-pointer transition-colors ${
                      selfRating === "beginner" 
                        ? "border-primary bg-primary/10" 
                        : "border-slate-700 hover:border-slate-600"
                    }`}
                  >
                    <RadioGroupItem value="beginner" id="beginner" className="sr-only" />
                    <span className="text-sm font-medium">Beginner</span>
                    <span className="text-xs text-muted-foreground">&lt; 1200</span>
                  </Label>
                  <Label
                    htmlFor="intermediate"
                    className={`flex flex-col items-center p-3 rounded-lg border cursor-pointer transition-colors ${
                      selfRating === "intermediate" 
                        ? "border-primary bg-primary/10" 
                        : "border-slate-700 hover:border-slate-600"
                    }`}
                  >
                    <RadioGroupItem value="intermediate" id="intermediate" className="sr-only" />
                    <span className="text-sm font-medium">Intermediate</span>
                    <span className="text-xs text-muted-foreground">1200-1800</span>
                  </Label>
                  <Label
                    htmlFor="advanced"
                    className={`flex flex-col items-center p-3 rounded-lg border cursor-pointer transition-colors ${
                      selfRating === "advanced" 
                        ? "border-primary bg-primary/10" 
                        : "border-slate-700 hover:border-slate-600"
                    }`}
                  >
                    <RadioGroupItem value="advanced" id="advanced" className="sr-only" />
                    <span className="text-sm font-medium">Advanced</span>
                    <span className="text-xs text-muted-foreground">1800+</span>
                  </Label>
                </RadioGroup>
              </div>
              
              {/* Focus Intent */}
              <div className="space-y-3">
                <Label>What do you want to improve most? (Optional)</Label>
                <RadioGroup
                  value={focusIntent}
                  onValueChange={setFocusIntent}
                  className="grid grid-cols-2 gap-2"
                >
                  <Label
                    htmlFor="tactics"
                    className={`flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-colors ${
                      focusIntent === "tactics" 
                        ? "border-primary bg-primary/10" 
                        : "border-slate-700 hover:border-slate-600"
                    }`}
                  >
                    <RadioGroupItem value="tactics" id="tactics" className="sr-only" />
                    <Zap className="w-4 h-4 text-amber-400" />
                    <span className="text-sm">Tactical awareness</span>
                  </Label>
                  <Label
                    htmlFor="openings"
                    className={`flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-colors ${
                      focusIntent === "openings" 
                        ? "border-primary bg-primary/10" 
                        : "border-slate-700 hover:border-slate-600"
                    }`}
                  >
                    <RadioGroupItem value="openings" id="openings" className="sr-only" />
                    <BookOpen className="w-4 h-4 text-blue-400" />
                    <span className="text-sm">Opening discipline</span>
                  </Label>
                  <Label
                    htmlFor="endgames"
                    className={`flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-colors ${
                      focusIntent === "endgames" 
                        ? "border-primary bg-primary/10" 
                        : "border-slate-700 hover:border-slate-600"
                    }`}
                  >
                    <RadioGroupItem value="endgames" id="endgames" className="sr-only" />
                    <Target className="w-4 h-4 text-green-400" />
                    <span className="text-sm">Endgame precision</span>
                  </Label>
                  <Label
                    htmlFor="stability"
                    className={`flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-colors ${
                      focusIntent === "stability" 
                        ? "border-primary bg-primary/10" 
                        : "border-slate-700 hover:border-slate-600"
                    }`}
                  >
                    <RadioGroupItem value="stability" id="stability" className="sr-only" />
                    <Brain className="w-4 h-4 text-purple-400" />
                    <span className="text-sm">Decision stability</span>
                  </Label>
                </RadioGroup>
              </div>
              
              <div className="pt-4 flex gap-2">
                <Button 
                  variant="outline"
                  onClick={() => setStep(1)}
                  className="flex-1"
                >
                  Back
                </Button>
                <Button 
                  onClick={handleStep2Complete}
                  disabled={isLoading}
                  className="flex-1"
                  data-testid="complete-onboarding-btn"
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      Analyze My Games
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </>
                  )}
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Onboarding;
