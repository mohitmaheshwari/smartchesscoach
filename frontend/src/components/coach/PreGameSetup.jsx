/**
 * PreGameSetup — Setup screen before Play with Coach starts
 * Shows: color selector, opening suggestions, start button
 */

import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";
import { Crown, Swords, RotateCcw } from "lucide-react";
import { API } from "@/App";

const OpeningSuggestions = () => {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetch(`${API}/coach/play/opening-suggestions`, { credentials: "include" })
      .then(r => r.ok ? r.json() : null)
      .then(d => setData(d))
      .catch(() => {});
  }, []);

  if (!data || data.total_games === 0) return null;

  const statusColors = {
    strong: "text-emerald-600 bg-emerald-500/10 border-emerald-500/20",
    learning: "text-amber-600 bg-amber-500/10 border-amber-500/20",
    weak: "text-red-500 bg-red-500/10 border-red-500/20",
    new: "text-blue-500 bg-blue-500/10 border-blue-500/20",
  };

  const renderOpenings = (openings, label) => {
    if (!openings?.length) return null;
    return (
      <div>
        <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1.5">{label}</p>
        <div className="space-y-1">
          {openings.slice(0, 3).map((o, i) => (
            <div key={i} className="flex items-center justify-between text-xs p-1.5 rounded border border-border">
              <span className="text-foreground font-medium truncate max-w-[140px]">{o.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">{o.games}g</span>
                <span className="text-muted-foreground">{o.win_rate}%</span>
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] border ${statusColors[o.status]}`}>
                  {o.status_label}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-3 p-3 rounded-lg bg-muted/30 border border-border" data-testid="opening-suggestions">
      <p className="text-xs font-medium text-foreground">Your Openings</p>
      {renderOpenings(data.white, "As White")}
      {renderOpenings(data.black, "As Black")}
      {data.suggestion && (
        <div className="pt-2 border-t border-border">
          <p className="text-xs text-primary">{data.suggestion.message}</p>
        </div>
      )}
    </div>
  );
};

const PreGameSetup = ({ selectedColor, setSelectedColor, onStart, loading }) => {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6" data-testid="pregame-setup">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md space-y-6"
      >
        <div className="text-center">
          <h1 className="text-3xl font-bold text-foreground mb-2" style={{ fontFamily: "'Cormorant Garamond', serif" }}>
            Play with Coach
          </h1>
          <p className="text-sm text-muted-foreground">Learn chess by playing guided games</p>
        </div>

        {/* Color Selection */}
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground text-center">Choose your color</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => setSelectedColor("white")}
              className={`flex items-center gap-2 px-6 py-3 rounded-lg border-2 transition-all ${
                selectedColor === "white"
                  ? "border-primary bg-primary/10"
                  : "border-border hover:border-primary/30"
              }`}
              data-testid="color-white"
            >
              <Crown className="w-5 h-5" />
              <span className="font-medium">White</span>
            </button>
            <button
              onClick={() => setSelectedColor("black")}
              className={`flex items-center gap-2 px-6 py-3 rounded-lg border-2 transition-all ${
                selectedColor === "black"
                  ? "border-primary bg-primary/10"
                  : "border-border hover:border-primary/30"
              }`}
              data-testid="color-black"
            >
              <Swords className="w-5 h-5" />
              <span className="font-medium">Black</span>
            </button>
          </div>
        </div>

        {/* Opening Suggestions */}
        <OpeningSuggestions />

        {/* Start Button */}
        <Button
          onClick={onStart}
          disabled={loading}
          className="w-full py-6 text-lg"
          data-testid="start-game-btn"
        >
          {loading ? "Starting..." : "Start Game"}
        </Button>
      </motion.div>
    </div>
  );
};

export default PreGameSetup;
