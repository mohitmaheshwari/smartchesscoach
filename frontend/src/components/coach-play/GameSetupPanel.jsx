/**
 * GameSetupPanel - Pre-game settings panel for Play With Coach
 * 
 * Allows users to select color and start a new game.
 */

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  Play, 
  Loader2, 
  Brain,
  Swords
} from "lucide-react";
import { motion } from "framer-motion";

const GameSetupPanel = ({ 
  selectedColor, 
  setSelectedColor, 
  onStartGame, 
  loading,
  recentResults = []
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center min-h-[60vh]"
    >
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-primary/20 flex items-center justify-center">
            <Brain className="w-8 h-8 text-primary" />
          </div>
          <CardTitle className="text-2xl">Play With Coach</CardTitle>
          <p className="text-muted-foreground text-sm mt-2">
            Learn by playing against a teaching opponent
          </p>
        </CardHeader>
        
        <CardContent className="space-y-6">
          {/* Color Selection */}
          <div className="space-y-3">
            <label className="text-sm font-medium">Choose your color</label>
            <div className="grid grid-cols-2 gap-3">
              <Button
                variant={selectedColor === "white" ? "default" : "outline"}
                className="h-16 flex flex-col gap-1"
                onClick={() => setSelectedColor("white")}
                data-testid="select-white"
              >
                <div className="w-8 h-8 rounded-full bg-white border-2 border-gray-300" />
                <span className="text-xs">White</span>
              </Button>
              <Button
                variant={selectedColor === "black" ? "default" : "outline"}
                className="h-16 flex flex-col gap-1"
                onClick={() => setSelectedColor("black")}
                data-testid="select-black"
              >
                <div className="w-8 h-8 rounded-full bg-gray-800 border-2 border-gray-600" />
                <span className="text-xs">Black</span>
              </Button>
            </div>
          </div>
          
          {/* Recent Results */}
          {recentResults.length > 0 && (
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">
                Recent games
              </label>
              <div className="flex gap-1 justify-center">
                {recentResults.slice(0, 5).map((result, idx) => (
                  <Badge
                    key={idx}
                    variant="outline"
                    className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      result === "win" 
                        ? "bg-green-500/20 text-green-400 border-green-500/30"
                        : result === "loss"
                        ? "bg-red-500/20 text-red-400 border-red-500/30"
                        : "bg-gray-500/20 text-gray-400 border-gray-500/30"
                    }`}
                  >
                    {result === "win" ? "W" : result === "loss" ? "L" : "D"}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          
          {/* Start Button */}
          <Button
            className="w-full h-12 text-lg"
            onClick={onStartGame}
            disabled={loading}
            data-testid="start-game-btn"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <Swords className="w-5 h-5 mr-2" />
                Start Game
              </>
            )}
          </Button>
          
          {/* Tips */}
          <div className="text-center text-xs text-muted-foreground">
            <p>The coach will help you learn from every move!</p>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default GameSetupPanel;
