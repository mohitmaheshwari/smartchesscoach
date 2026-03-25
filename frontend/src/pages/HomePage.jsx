/**
 * HOME PAGE → DECISION
 * "What should I do right now?"
 * 
 * One screen = one job
 * - Play button (primary action)
 * - One problem → leads to action
 * - Nothing else
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Loader2, Play, ChevronRight } from "lucide-react";

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${API}/coach/home-intelligence`, { credentials: "include" });
        if (res.ok) setData(await res.json());
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[70vh]">
          <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
        </div>
      </Layout>
    );
  }

  const problem = data?.specific_patterns?.dominant_pattern;
  const problemFormatted = problem?.replace(/_/g, " ");

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-4 py-12 min-h-[70vh] flex flex-col justify-center" data-testid="home-page">
        
        {/* ═══════════════════════════════════════════════════════════════
            PRIMARY: PLAY BUTTON
            The main decision - start playing
        ═══════════════════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <Card 
            className="bg-gradient-to-br from-emerald-600 to-emerald-700 border-0 cursor-pointer hover:from-emerald-500 hover:to-emerald-600 transition-all duration-300 shadow-lg shadow-emerald-900/30"
            onClick={() => navigate("/play-with-coach")}
            data-testid="play-card"
          >
            <CardContent className="p-8 text-center">
              <div className="w-16 h-16 rounded-full bg-white/20 flex items-center justify-center mx-auto mb-4">
                <Play className="w-8 h-8 text-white fill-white" />
              </div>
              <h1 className="text-2xl font-bold text-white mb-2">Play with Coach</h1>
              <p className="text-emerald-100/80 text-sm">Learn while you play</p>
            </CardContent>
          </Card>
        </motion.div>

        {/* ═══════════════════════════════════════════════════════════════
            SECONDARY: ONE PROBLEM → ACTION
            Not just showing problem, but leading to fix
        ═══════════════════════════════════════════════════════════════ */}
        {problem && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card 
              className="bg-zinc-900 border-zinc-800 cursor-pointer hover:border-zinc-700 transition-all"
              onClick={() => navigate(`/training/prescribed?weakness=${problem}`)}
              data-testid="problem-card"
            >
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-zinc-500 uppercase tracking-wide mb-1">Your focus</p>
                    <p className="text-lg text-white font-medium capitalize">{problemFormatted}</p>
                  </div>
                  <div className="flex items-center gap-2 text-zinc-400">
                    <span className="text-sm">Train this</span>
                    <ChevronRight className="w-4 h-4" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════════════════
            TERTIARY: REVIEW LAST GAME (only if exists)
            Quick access, not prominent
        ═══════════════════════════════════════════════════════════════ */}
        {data?.last_game && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="mt-6 text-center"
          >
            <button
              onClick={() => navigate(`/game/${data.last_game.game_id}`)}
              className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
              data-testid="review-link"
            >
              Review last game →
            </button>
          </motion.div>
        )}
      </div>
    </Layout>
  );
};

export default HomePage;
