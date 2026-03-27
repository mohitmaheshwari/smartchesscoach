/**
 * LAB PAGE - Game Decryption Environment
 * 
 * This is the new Lab page that uses the Game Decryption view by default.
 * Users can switch to Classic view if needed.
 * 
 * Game Decryption: Step-by-step move explanations in plain English
 * Classic: The original 5-tab analysis view
 */

import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Layout from "@/components/Layout";
import GameDecryptionV5 from "@/components/GameDecryptionV5";
import LabClassic from "@/pages/LabClassic";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, BookOpen, Brain, Loader2, RefreshCw, Target } from "lucide-react";
import { toast } from "sonner";
import CoachInsightPanel from "@/components/Lab/CoachInsightPanel";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const Lab = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  
  // View mode: "decryption" (new) or "classic" (old)
  const [viewMode, setViewMode] = useState("decryption");
  
  // Game data
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshingCoaching, setRefreshingCoaching] = useState(false);
  
  // Fetch game and analysis data
  useEffect(() => {
    fetchGameData();
  }, [gameId]);
  
  const fetchGameData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Fetch game
      const gameRes = await fetch(`${API}/games/${gameId}`, {
        credentials: "include"
      });
      
      if (!gameRes.ok) {
        throw new Error("Game not found");
      }
      
      const gameData = await gameRes.json();
      setGame(gameData);
      
      // Fetch analysis
      const analysisRes = await fetch(`${API}/analysis/${gameId}`, {
        credentials: "include"
      });
      
      if (analysisRes.ok) {
        const analysisData = await analysisRes.json();
        setAnalysis(analysisData);
      }
      
    } catch (err) {
      console.error("Error fetching game:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  const handleRefreshCoaching = async () => {
    setRefreshingCoaching(true);
    try {
      const res = await fetch(`${API}/games/${gameId}/regenerate-coaching`, {
        method: "POST",
        credentials: "include"
      });
      if (res.ok) {
        toast.success("Coaching cleared — reloading...");
        await fetchGameData();
      } else {
        const err = await res.json();
        toast.error(err.detail || "Failed to refresh coaching");
      }
    } catch (e) {
      toast.error("Failed to refresh coaching");
    } finally {
      setRefreshingCoaching(false);
    }
  };
  
  // Determine user color
  const userColor = game?.user_plays_as || (game?.white_player === user?.username ? "white" : "black");
  const opponent = userColor === "white" ? game?.black_player : game?.white_player;
  const opponentRating = userColor === "white" ? game?.black_rating : game?.white_rating;
  const result = game?.result || "";
  
  // If classic view, render the old Lab component
  if (viewMode === "classic") {
    return <LabClassic user={user} />;
  }
  
  // Loading state
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[calc(100vh-80px)]" data-testid="lab-loading">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
          <span className="ml-3 text-zinc-400">Loading game...</span>
        </div>
      </Layout>
    );
  }
  
  // Error state
  if (error) {
    return (
      <Layout user={user}>
        <div className="flex flex-col items-center justify-center h-[calc(100vh-80px)]" data-testid="lab-error">
          <p className="text-zinc-400 mb-4">{error}</p>
          <Button onClick={() => navigate(-1)}>Go Back</Button>
        </div>
      </Layout>
    );
  }
  
  return (
    <Layout user={user}>
      <div className="h-[calc(100vh-80px)] flex flex-col" data-testid="lab-page">
        {/* Header */}
        <div className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b border-border/50 px-4 py-3">
          <div className="flex items-center justify-between gap-4">
            {/* Left: Back + Game Info */}
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
                <ArrowLeft className="w-5 h-5" />
              </Button>
              
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-bold">vs {opponent || "Opponent"}</h1>
                  {opponentRating && (
                    <Badge variant="outline" className="text-xs">
                      {opponentRating}
                    </Badge>
                  )}
                  <Badge 
                    variant={result.includes("1-0") ? (userColor === "white" ? "default" : "destructive") : 
                            result.includes("0-1") ? (userColor === "black" ? "default" : "destructive") : 
                            "secondary"}
                    className="text-xs"
                  >
                    {result.includes("1-0") ? (userColor === "white" ? "WIN" : "LOSS") :
                     result.includes("0-1") ? (userColor === "black" ? "WIN" : "LOSS") :
                     "DRAW"}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  You played {userColor}
                </p>
              </div>
            </div>
            
            {/* Right: Refresh + View Toggle */}
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefreshCoaching}
                disabled={refreshingCoaching}
                data-testid="refresh-coaching-btn"
                className="text-xs text-muted-foreground hover:text-primary"
              >
                <RefreshCw className={`w-3.5 h-3.5 mr-1 ${refreshingCoaching ? 'animate-spin' : ''}`} />
                {refreshingCoaching ? "Refreshing..." : "Refresh Coaching"}
              </Button>
              
              <div className="flex items-center gap-2 px-2 py-1 rounded-lg bg-gray-800/50 border border-gray-700">
              <button
                onClick={() => setViewMode("decryption")}
                className={`px-3 py-1.5 text-xs rounded transition-colors ${
                  viewMode === "decryption" 
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
                    : 'text-gray-400 hover:text-gray-300'
                }`}
                data-testid="decryption-view-btn"
              >
                <BookOpen className="w-3 h-3 inline mr-1" />
                Decrypt Game
              </button>
              <button
                onClick={() => setViewMode("classic")}
                className={`px-3 py-1.5 text-xs rounded transition-colors ${
                  viewMode === "classic" 
                    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
                    : 'text-gray-400 hover:text-gray-300'
                }`}
                data-testid="classic-view-btn"
              >
                <Target className="w-3 h-3 inline mr-1" />
                Coach
              </button>
              </div>
            </div>
          </div>
        </div>
        
        {/* Main Content: Toggle between Decrypt and Coach */}
        <div className="flex-1 overflow-auto">
          {viewMode === "decryption" ? (
            <GameDecryptionV5
              gameId={gameId}
              analysis={analysis}
              pgn={game?.pgn}
              userColor={userColor}
              onBack={() => navigate(-1)}
            />
          ) : (
            <div className="max-w-2xl mx-auto py-6 px-4">
              <CoachInsightPanel gameId={gameId} />
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default Lab;
