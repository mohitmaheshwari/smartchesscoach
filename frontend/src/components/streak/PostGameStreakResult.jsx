/**
 * PostGameStreakResult.jsx - Show streak result after game
 * 
 * Displays whether the user:
 * - Continued their streak (celebration)
 * - Achieved a new best (big celebration)
 * - Broke their streak (emotional hit)
 * 
 * EMOTIONAL COPY IS THE RETENTION ENGINE
 */

import { motion } from "framer-motion";
import {
  Flame,
  Trophy,
  XCircle,
  CheckCircle,
  ArrowRight,
  AlertTriangle,
  Target
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const PostGameStreakResult = ({ 
  result,  // { result, headline, message, streak, best, tone, previous_streak, critical_hint, improvement, improvement_message }
  onContinue,
  onGoToTraining
}) => {
  if (!result) return null;

  const isNewBest = result.result === "new_best";
  const isContinued = result.result === "continued";
  const isBroken = result.result === "broken";
  
  // Improvement data
  const improvement = result.improvement;
  const improvementMessage = result.improvement_message;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
    >
      <Card className={`max-w-md w-full ${
        isBroken 
          ? "bg-red-950/50 border-red-500/50" 
          : isNewBest
            ? "bg-amber-950/30 border-amber-500/50"
            : "bg-green-950/30 border-green-500/50"
      }`}>
        <CardContent className="p-8 text-center">
          {/* Icon */}
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: "spring" }}
            className={`w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 ${
              isNewBest 
                ? "bg-gradient-to-br from-amber-500/30 to-orange-500/30"
                : isContinued
                  ? "bg-green-500/20"
                  : "bg-red-500/20"
            }`}
          >
            {isNewBest ? (
              <Trophy className="w-10 h-10 text-amber-400" />
            ) : isContinued ? (
              <CheckCircle className="w-10 h-10 text-green-400" />
            ) : (
              <XCircle className="w-10 h-10 text-red-400" />
            )}
          </motion.div>

          {/* Headline */}
          <h2 className={`text-2xl font-bold mb-2 ${
            isBroken ? "text-red-400" : 
            isNewBest ? "text-amber-400" : "text-green-400"
          }`}>
            {result.headline}
          </h2>

          {/* Message - EMOTIONAL COPY */}
          <p className={`mb-4 ${isBroken ? "text-zinc-200" : "text-zinc-300"}`}>
            {result.message}
          </p>
          
          {/* Critical moment hint for broken streak */}
          {isBroken && result.critical_hint && (
            <div className="bg-red-900/30 rounded-lg p-3 mb-4 border border-red-500/20">
              <div className="flex items-center gap-2 justify-center text-sm text-red-300">
                <Target className="w-4 h-4" />
                <span>{result.critical_hint}</span>
              </div>
            </div>
          )}
          
          {/* IMPROVEMENT PROOF - Compare to last game */}
          {improvement && improvement.text && (
            <div className={`rounded-lg p-3 mb-4 border ${
              improvement.verdict === "improving" 
                ? "bg-green-900/20 border-green-500/20" 
                : improvement.verdict === "slipping"
                  ? "bg-red-900/20 border-red-500/20"
                  : "bg-zinc-900/30 border-zinc-700"
            }`}>
              <p className={`text-sm font-medium ${
                improvement.verdict === "improving" ? "text-green-400" :
                improvement.verdict === "slipping" ? "text-red-400" : "text-zinc-300"
              }`}>
                {improvement.text}
              </p>
              {improvementMessage && (
                <p className={`text-xs mt-1 ${
                  improvement.verdict === "improving" ? "text-green-400/70" :
                  improvement.verdict === "slipping" ? "text-red-400/70" : "text-zinc-500"
                }`}>
                  {improvementMessage}
                </p>
              )}
            </div>
          )}

          {/* Streak Display */}
          {!isBroken ? (
            <div className="flex items-center justify-center gap-8 mb-6">
              <div className="text-center">
                <div className="flex items-center gap-2 justify-center">
                  <Flame className="w-5 h-5 text-amber-400" />
                  <span className="text-3xl font-bold text-white">{result.streak}</span>
                </div>
                <p className="text-xs text-zinc-500">Current Streak</p>
              </div>
              <div className="text-center">
                <div className="flex items-center gap-2 justify-center">
                  <Trophy className="w-5 h-5 text-amber-400" />
                  <span className="text-3xl font-bold text-amber-400">{result.best}</span>
                </div>
                <p className="text-xs text-zinc-500">Best Streak</p>
              </div>
            </div>
          ) : (
            <div className="bg-red-900/30 rounded-lg p-4 mb-6">
              <p className="text-sm text-zinc-300">
                Previous streak: <span className="font-bold text-white">{result.previous_streak || 0}</span> games
              </p>
              <p className="text-xs text-zinc-500 mt-1">
                Your best ({result.best}) is still saved.
              </p>
            </div>
          )}
          
          {/* Accountability message for broken streaks */}
          {isBroken && (
            <p className="text-xs text-zinc-500 mb-4 italic">
              "Players don't improve by making the same mistakes. Break the pattern."
            </p>
          )}
          
          {/* Success reinforcement */}
          {isNewBest && (
            <p className="text-xs text-amber-400/80 mb-4">
              This is real progress. Keep building.
            </p>
          )}

          {/* CTAs */}
          <div className="flex gap-3">
            {isBroken && onGoToTraining && (
              <Button
                onClick={onGoToTraining}
                className="flex-1 bg-red-600 hover:bg-red-700"
                data-testid="fix-this-now-btn"
              >
                <AlertTriangle className="w-4 h-4 mr-2" />
                Fix This Now
              </Button>
            )}
            <Button
              onClick={onContinue}
              variant={isBroken ? "outline" : "default"}
              className={`flex-1 ${
                isNewBest ? "bg-amber-600 hover:bg-amber-700" :
                !isBroken ? "bg-green-600 hover:bg-green-700" : "border-zinc-700"
              }`}
              data-testid="continue-btn"
            >
              {isBroken ? "Continue" : "Keep Going"}
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default PostGameStreakResult;
