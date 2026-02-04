import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// XP Progress Bar Component
export const XPProgressBar = ({ progress, compact = false }) => {
  const { current_level, next_level, progress_percent, xp_to_next } = progress?.level_info || {};
  const xp = progress?.xp || 0;
  
  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-lg">{current_level?.icon}</span>
        <div className="flex-1">
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <motion.div 
              className="h-full bg-gradient-to-r from-amber-500 to-amber-400"
              initial={{ width: 0 }}
              animate={{ width: `${progress_percent}%` }}
              transition={{ duration: 0.8, ease: "easeOut" }}
            />
          </div>
        </div>
        <span className="text-xs text-zinc-400">{Math.round(progress_percent)}%</span>
      </div>
    );
  }
  
  return (
    <div className="bg-zinc-900 rounded-xl p-4 border border-zinc-800">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{current_level?.icon}</span>
          <div>
            <div className="text-white font-semibold">{current_level?.name}</div>
            <div className="text-xs text-zinc-400">Level {current_level?.level}</div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-amber-400 font-bold">{xp.toLocaleString()} XP</div>
          {next_level && (
            <div className="text-xs text-zinc-500">{xp_to_next} to next level</div>
          )}
        </div>
      </div>
      
      <div className="h-3 bg-zinc-800 rounded-full overflow-hidden">
        <motion.div 
          className="h-full bg-gradient-to-r from-amber-500 to-amber-400 rounded-full"
          initial={{ width: 0 }}
          animate={{ width: `${progress_percent}%` }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
      </div>
      
      {next_level && (
        <div className="flex justify-between mt-1 text-xs text-zinc-500">
          <span>{current_level?.name}</span>
          <span>{next_level?.name}</span>
        </div>
      )}
    </div>
  );
};

// Streak Display Component
export const StreakDisplay = ({ streak, compact = false }) => {
  const currentStreak = streak || 0;
  
  if (compact) {
    return (
      <div className="flex items-center gap-1">
        <span className="text-lg">🔥</span>
        <span className="text-white font-bold">{currentStreak}</span>
      </div>
    );
  }
  
  return (
    <div className="bg-gradient-to-br from-orange-500/10 to-red-500/10 rounded-xl p-4 border border-orange-500/20">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <motion.span 
            className="text-4xl"
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 0.5, repeat: currentStreak > 0 ? Infinity : 0, repeatDelay: 2 }}
          >
            🔥
          </motion.span>
          <div>
            <div className="text-3xl font-bold text-white">{currentStreak}</div>
            <div className="text-sm text-orange-400">Day Streak</div>
          </div>
        </div>
        <div className="text-right text-xs text-zinc-400">
          {currentStreak >= 7 && <div>🏆 Week achieved!</div>}
          {currentStreak >= 30 && <div>👑 Month achieved!</div>}
        </div>
      </div>
    </div>
  );
};

// Achievement Badge Component
export const AchievementBadge = ({ achievement, size = 'md' }) => {
  const sizeClasses = {
    sm: 'w-12 h-12 text-lg',
    md: 'w-16 h-16 text-2xl',
    lg: 'w-20 h-20 text-3xl'
  };
  
  return (
    <motion.div
      className={`relative ${sizeClasses[size]} rounded-full flex items-center justify-center ${
        achievement.unlocked 
          ? 'bg-gradient-to-br from-amber-500/20 to-amber-600/20 border-2 border-amber-500/50' 
          : 'bg-zinc-800/50 border-2 border-zinc-700 opacity-50 grayscale'
      }`}
      whileHover={{ scale: 1.05 }}
      title={achievement.unlocked ? achievement.description : `Locked: ${achievement.description}`}
    >
      <span className={achievement.unlocked ? '' : 'opacity-30'}>{achievement.icon}</span>
      {achievement.unlocked && (
        <motion.div 
          className="absolute -bottom-1 -right-1 w-5 h-5 bg-green-500 rounded-full flex items-center justify-center"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
        >
          <span className="text-xs">✓</span>
        </motion.div>
      )}
    </motion.div>
  );
};

// Achievement Card Component
export const AchievementCard = ({ achievement }) => {
  return (
    <motion.div
      className={`p-4 rounded-xl border ${
        achievement.unlocked 
          ? 'bg-zinc-900 border-amber-500/30' 
          : 'bg-zinc-900/50 border-zinc-800 opacity-60'
      }`}
      whileHover={{ scale: 1.02 }}
    >
      <div className="flex items-start gap-3">
        <AchievementBadge achievement={achievement} size="md" />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className={`font-semibold ${achievement.unlocked ? 'text-white' : 'text-zinc-500'}`}>
              {achievement.name}
            </span>
            {achievement.unlocked && (
              <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded">
                Unlocked
              </span>
            )}
          </div>
          <p className="text-sm text-zinc-400 mt-1">{achievement.description}</p>
          <div className="text-xs text-amber-500 mt-2">+{achievement.xp_reward} XP</div>
        </div>
      </div>
    </motion.div>
  );
};

// Level Up Celebration Modal
export const LevelUpModal = ({ show, levelInfo, onClose }) => {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="bg-zinc-900 rounded-2xl p-8 border border-amber-500/30 text-center max-w-sm"
            initial={{ scale: 0.5, y: 50 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.5, y: 50 }}
            onClick={e => e.stopPropagation()}
          >
            <motion.div 
              className="text-6xl mb-4"
              animate={{ 
                rotate: [0, -10, 10, -10, 10, 0],
                scale: [1, 1.2, 1]
              }}
              transition={{ duration: 0.6 }}
            >
              {levelInfo?.icon}
            </motion.div>
            <div className="text-amber-400 text-sm font-medium mb-1">LEVEL UP!</div>
            <div className="text-2xl font-bold text-white mb-2">{levelInfo?.name}</div>
            <div className="text-zinc-400 text-sm mb-6">
              You&apos;ve reached Level {levelInfo?.level}
            </div>
            <button
              onClick={onClose}
              className="px-6 py-2 bg-amber-500 hover:bg-amber-400 text-black font-semibold rounded-lg transition"
            >
              Continue
            </button>
          </motion.div>
          
          {/* Confetti effect - using pre-calculated positions */}
          {[...Array(20)].map((_, i) => {
            // Pre-calculate positions based on index for deterministic rendering
            const leftPos = ((i * 17) % 100);
            const xOffset = ((i % 5) - 2) * 80;
            const duration = 2 + (i % 3);
            const delay = (i % 5) * 0.1;
            const rotateDir = i % 2 === 0 ? 1 : -1;
            
            return (
              <motion.div
                key={i}
                className="absolute w-3 h-3 rounded-full"
                style={{
                  backgroundColor: ['#f59e0b', '#10b981', '#3b82f6', '#ef4444'][i % 4],
                  left: `${leftPos}%`,
                  top: '-20px'
                }}
                animate={{
                  y: [0, 800],
                  x: [0, xOffset],
                  rotate: [0, 360 * rotateDir]
                }}
                transition={{
                  duration: duration,
                  ease: "easeIn",
                  delay: delay
                }}
              />
            );
          })}
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// XP Earned Toast
export const XPToast = ({ show, xp, action }) => {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50"
          initial={{ y: 50, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -20, opacity: 0 }}
        >
          <div className="bg-amber-500 text-black px-4 py-2 rounded-full font-semibold flex items-center gap-2 shadow-lg shadow-amber-500/30">
            <span>+{xp} XP</span>
            {action && <span className="text-amber-800 text-sm">• {action}</span>}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// Daily Reward Button
export const DailyRewardButton = ({ onClaim, claimed }) => {
  return (
    <motion.button
      onClick={onClaim}
      disabled={claimed}
      className={`px-4 py-2 rounded-lg font-semibold flex items-center gap-2 ${
        claimed 
          ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed' 
          : 'bg-gradient-to-r from-amber-500 to-orange-500 text-black hover:from-amber-400 hover:to-orange-400'
      }`}
      whileHover={!claimed ? { scale: 1.05 } : {}}
      whileTap={!claimed ? { scale: 0.95 } : {}}
    >
      <span>{claimed ? '✓' : '🎁'}</span>
      <span>{claimed ? 'Claimed Today' : 'Claim Daily Reward'}</span>
    </motion.button>
  );
};

// Stats Grid Component
export const StatsGrid = ({ progress }) => {
  const stats = [
    { label: 'Games Analyzed', value: progress?.games_analyzed || 0, icon: '📊' },
    { label: 'Puzzles Solved', value: progress?.puzzles_solved || 0, icon: '🧩' },
    { label: 'Best Accuracy', value: `${progress?.best_accuracy || 0}%`, icon: '🎯' },
    { label: 'Longest Streak', value: progress?.longest_streak || 0, icon: '🏆' },
  ];
  
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {stats.map((stat, i) => (
        <div key={i} className="bg-zinc-900 rounded-lg p-3 border border-zinc-800">
          <div className="text-lg mb-1">{stat.icon}</div>
          <div className="text-xl font-bold text-white">{stat.value}</div>
          <div className="text-xs text-zinc-500">{stat.label}</div>
        </div>
      ))}
    </div>
  );
};

// Main Gamification Dashboard Component
export const GamificationDashboard = () => {
  const [progress, setProgress] = useState(null);
  const [achievements, setAchievements] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showLevelUp, setShowLevelUp] = useState(false);
  const [showXPToast, setShowXPToast] = useState(false);
  const [xpToastData, setXpToastData] = useState({ xp: 0, action: '' });
  
  useEffect(() => {
    fetchData();
  }, []);
  
  const fetchData = async () => {
    try {
      const [progressRes, achievementsRes] = await Promise.all([
        fetch(`${API_URL}/api/gamification/progress`, { credentials: 'include' }),
        fetch(`${API_URL}/api/gamification/achievements`, { credentials: 'include' })
      ]);
      
      if (progressRes.ok) setProgress(await progressRes.json());
      if (achievementsRes.ok) setAchievements(await achievementsRes.json());
    } catch (err) {
      console.error('Failed to fetch gamification data:', err);
    } finally {
      setLoading(false);
    }
  };
  
  const claimDailyReward = async () => {
    try {
      const res = await fetch(`${API_URL}/api/gamification/daily-reward`, {
        method: 'POST',
        credentials: 'include'
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.claimed) {
          setXpToastData({ xp: data.xp_earned, action: 'Daily Reward' });
          setShowXPToast(true);
          setTimeout(() => setShowXPToast(false), 2000);
          fetchData(); // Refresh data
        }
      }
    } catch (err) {
      console.error('Failed to claim daily reward:', err);
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full" />
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      {/* XP and Streak Row */}
      <div className="grid md:grid-cols-2 gap-4">
        <XPProgressBar progress={progress} />
        <StreakDisplay streak={progress?.current_streak} />
      </div>
      
      {/* Daily Reward */}
      <div className="flex justify-center">
        <DailyRewardButton onClaim={claimDailyReward} claimed={false} />
      </div>
      
      {/* Stats */}
      <StatsGrid progress={progress} />
      
      {/* Achievements */}
      {achievements && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Achievements</h3>
            <span className="text-sm text-zinc-400">
              {achievements.unlocked_count} / {achievements.total_count} unlocked
            </span>
          </div>
          
          <div className="grid md:grid-cols-2 gap-3">
            {achievements.achievements?.slice(0, 8).map(ach => (
              <AchievementCard key={ach.id} achievement={ach} />
            ))}
          </div>
        </div>
      )}
      
      {/* Modals */}
      <LevelUpModal 
        show={showLevelUp} 
        levelInfo={progress?.level_info?.current_level}
        onClose={() => setShowLevelUp(false)} 
      />
      <XPToast show={showXPToast} xp={xpToastData.xp} action={xpToastData.action} />
    </div>
  );
};

export default GamificationDashboard;
