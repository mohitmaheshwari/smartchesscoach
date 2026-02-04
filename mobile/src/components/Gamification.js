import React, { useMemo } from 'react';
import { View, Text, StyleSheet, Animated, TouchableOpacity, Dimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';

const { width } = Dimensions.get('window');

// XP Progress Bar Component
export const XPProgressBar = ({ progress, compact = false }) => {
  const { colors } = useTheme();
  
  const levelInfo = progress?.level_info;
  const currentLevel = levelInfo?.current_level;
  const nextLevel = levelInfo?.next_level;
  const progressPercent = levelInfo?.progress_percent || 0;
  const xp = progress?.xp || 0;
  
  if (compact) {
    return (
      <View style={styles.compactContainer}>
        <Text style={styles.levelIcon}>{currentLevel?.icon}</Text>
        <View style={styles.compactBarBg}>
          <View style={[styles.compactBarFill, { width: `${progressPercent}%` }]} />
        </View>
        <Text style={[styles.compactPercent, { color: colors.textSecondary }]}>
          {Math.round(progressPercent)}%
        </Text>
      </View>
    );
  }
  
  return (
    <View style={[styles.progressCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.progressHeader}>
        <View style={styles.levelInfo}>
          <Text style={styles.levelIconLarge}>{currentLevel?.icon}</Text>
          <View>
            <Text style={[styles.levelName, { color: colors.text }]}>{currentLevel?.name}</Text>
            <Text style={[styles.levelNum, { color: colors.textSecondary }]}>Level {currentLevel?.level}</Text>
          </View>
        </View>
        <View style={styles.xpInfo}>
          <Text style={styles.xpValue}>{xp.toLocaleString()} XP</Text>
          {nextLevel && (
            <Text style={[styles.xpToNext, { color: colors.textSecondary }]}>
              {levelInfo?.xp_to_next} to next
            </Text>
          )}
        </View>
      </View>
      
      <View style={[styles.progressBarBg, { backgroundColor: colors.border }]}>
        <View style={[styles.progressBarFill, { width: `${progressPercent}%` }]} />
      </View>
      
      {nextLevel && (
        <View style={styles.levelLabels}>
          <Text style={[styles.levelLabel, { color: colors.textSecondary }]}>{currentLevel?.name}</Text>
          <Text style={[styles.levelLabel, { color: colors.textSecondary }]}>{nextLevel?.name}</Text>
        </View>
      )}
    </View>
  );
};

// Streak Display Component
export const StreakDisplay = ({ streak, compact = false }) => {
  const { colors } = useTheme();
  const currentStreak = streak || 0;
  
  if (compact) {
    return (
      <View style={styles.streakCompact}>
        <Text style={styles.fireEmoji}>🔥</Text>
        <Text style={[styles.streakNumCompact, { color: colors.text }]}>{currentStreak}</Text>
      </View>
    );
  }
  
  return (
    <View style={styles.streakCard}>
      <View style={styles.streakContent}>
        <Text style={styles.fireEmojiLarge}>🔥</Text>
        <View>
          <Text style={styles.streakNum}>{currentStreak}</Text>
          <Text style={styles.streakLabel}>Day Streak</Text>
        </View>
      </View>
      <View style={styles.streakBadges}>
        {currentStreak >= 7 && <Text style={styles.streakBadge}>🏆 Week!</Text>}
        {currentStreak >= 30 && <Text style={styles.streakBadge}>👑 Month!</Text>}
      </View>
    </View>
  );
};

// Achievement Badge Component
export const AchievementBadge = ({ achievement, size = 'md', onPress }) => {
  const sizes = {
    sm: { container: 48, icon: 20 },
    md: { container: 64, icon: 28 },
    lg: { container: 80, icon: 36 },
  };
  const s = sizes[size];
  
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.8}
      style={[
        styles.achievementBadge,
        { 
          width: s.container, 
          height: s.container,
          backgroundColor: achievement.unlocked ? 'rgba(245, 158, 11, 0.15)' : 'rgba(39, 39, 42, 0.5)',
          borderColor: achievement.unlocked ? 'rgba(245, 158, 11, 0.5)' : '#3f3f46',
          opacity: achievement.unlocked ? 1 : 0.5,
        }
      ]}
    >
      <Text style={{ fontSize: s.icon, opacity: achievement.unlocked ? 1 : 0.3 }}>
        {achievement.icon}
      </Text>
      {achievement.unlocked && (
        <View style={styles.unlockedCheck}>
          <Ionicons name="checkmark" size={10} color="#fff" />
        </View>
      )}
    </TouchableOpacity>
  );
};

// Achievement Card Component  
export const AchievementCard = ({ achievement, onPress }) => {
  const { colors } = useTheme();
  
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.8}
      style={[
        styles.achievementCard,
        { 
          backgroundColor: achievement.unlocked ? colors.card : 'rgba(24, 24, 27, 0.5)',
          borderColor: achievement.unlocked ? 'rgba(245, 158, 11, 0.3)' : colors.border,
          opacity: achievement.unlocked ? 1 : 0.6,
        }
      ]}
    >
      <AchievementBadge achievement={achievement} size="md" />
      <View style={styles.achievementInfo}>
        <View style={styles.achievementHeader}>
          <Text style={[
            styles.achievementName, 
            { color: achievement.unlocked ? colors.text : colors.textSecondary }
          ]}>
            {achievement.name}
          </Text>
          {achievement.unlocked && (
            <View style={styles.unlockedBadge}>
              <Text style={styles.unlockedBadgeText}>Unlocked</Text>
            </View>
          )}
        </View>
        <Text style={[styles.achievementDesc, { color: colors.textSecondary }]}>
          {achievement.description}
        </Text>
        <Text style={styles.achievementXp}>+{achievement.xp_reward} XP</Text>
      </View>
    </TouchableOpacity>
  );
};

// Daily Reward Button
export const DailyRewardButton = ({ onClaim, claimed, loading }) => {
  return (
    <TouchableOpacity
      onPress={onClaim}
      disabled={claimed || loading}
      activeOpacity={0.8}
      style={[
        styles.dailyRewardBtn,
        claimed ? styles.dailyRewardBtnClaimed : styles.dailyRewardBtnActive
      ]}
    >
      <Text style={styles.dailyRewardIcon}>{claimed ? '✓' : '🎁'}</Text>
      <Text style={[
        styles.dailyRewardText,
        { color: claimed ? '#71717a' : '#000' }
      ]}>
        {loading ? 'Claiming...' : claimed ? 'Claimed Today' : 'Claim Daily Reward'}
      </Text>
    </TouchableOpacity>
  );
};

// Stats Grid Component
export const StatsGrid = ({ progress }) => {
  const { colors } = useTheme();
  
  const stats = useMemo(() => [
    { label: 'Games', value: progress?.games_analyzed || 0, icon: '📊' },
    { label: 'Puzzles', value: progress?.puzzles_solved || 0, icon: '🧩' },
    { label: 'Accuracy', value: `${progress?.best_accuracy || 0}%`, icon: '🎯' },
    { label: 'Best Streak', value: progress?.longest_streak || 0, icon: '🏆' },
  ], [progress]);
  
  return (
    <View style={styles.statsGrid}>
      {stats.map((stat, i) => (
        <View key={i} style={[styles.statBox, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Text style={styles.statIcon}>{stat.icon}</Text>
          <Text style={[styles.statValue, { color: colors.text }]}>{stat.value}</Text>
          <Text style={[styles.statLabel, { color: colors.textSecondary }]}>{stat.label}</Text>
        </View>
      ))}
    </View>
  );
};

// XP Toast Component (simplified - no animations to avoid ref issues)
export const XPToast = ({ visible, xp, action }) => {
  if (!visible) return null;
  
  return (
    <View style={styles.xpToast}>
      <Text style={styles.xpToastText}>+{xp} XP</Text>
      {action && <Text style={styles.xpToastAction}>• {action}</Text>}
    </View>
  );
};

const styles = StyleSheet.create({
  // Compact XP bar
  compactContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  levelIcon: {
    fontSize: 18,
  },
  compactBarBg: {
    flex: 1,
    height: 8,
    backgroundColor: '#27272a',
    borderRadius: 4,
    overflow: 'hidden',
  },
  compactBarFill: {
    height: '100%',
    backgroundColor: '#f59e0b',
    borderRadius: 4,
  },
  compactPercent: {
    fontSize: 11,
    fontWeight: '500',
  },
  
  // Full XP Progress Card
  progressCard: {
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  levelInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  levelIconLarge: {
    fontSize: 28,
  },
  levelName: {
    fontSize: 16,
    fontWeight: '600',
  },
  levelNum: {
    fontSize: 12,
  },
  xpInfo: {
    alignItems: 'flex-end',
  },
  xpValue: {
    fontSize: 16,
    fontWeight: '700',
    color: '#f59e0b',
  },
  xpToNext: {
    fontSize: 11,
  },
  progressBarBg: {
    height: 12,
    borderRadius: 6,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#f59e0b',
    borderRadius: 6,
  },
  levelLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 6,
  },
  levelLabel: {
    fontSize: 10,
  },
  
  // Streak
  streakCompact: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  fireEmoji: {
    fontSize: 18,
  },
  streakNumCompact: {
    fontSize: 16,
    fontWeight: '700',
  },
  streakCard: {
    backgroundColor: 'rgba(249, 115, 22, 0.1)',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: 'rgba(249, 115, 22, 0.2)',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  streakContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  fireEmojiLarge: {
    fontSize: 36,
  },
  streakNum: {
    fontSize: 28,
    fontWeight: '700',
    color: '#fff',
  },
  streakLabel: {
    fontSize: 13,
    color: '#f97316',
  },
  streakBadges: {
    alignItems: 'flex-end',
  },
  streakBadge: {
    fontSize: 11,
    color: '#a1a1aa',
  },
  
  // Achievement Badge
  achievementBadge: {
    borderRadius: 32,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
  },
  unlockedCheck: {
    position: 'absolute',
    bottom: -2,
    right: -2,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: '#10b981',
    justifyContent: 'center',
    alignItems: 'center',
  },
  
  // Achievement Card
  achievementCard: {
    flexDirection: 'row',
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    gap: 12,
    marginBottom: 8,
  },
  achievementInfo: {
    flex: 1,
  },
  achievementHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  achievementName: {
    fontSize: 14,
    fontWeight: '600',
  },
  unlockedBadge: {
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  unlockedBadgeText: {
    fontSize: 10,
    color: '#10b981',
    fontWeight: '500',
  },
  achievementDesc: {
    fontSize: 12,
    marginTop: 4,
    lineHeight: 16,
  },
  achievementXp: {
    fontSize: 11,
    color: '#f59e0b',
    marginTop: 6,
    fontWeight: '500',
  },
  
  // Daily Reward Button
  dailyRewardBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 10,
    gap: 8,
  },
  dailyRewardBtnActive: {
    backgroundColor: '#f59e0b',
  },
  dailyRewardBtnClaimed: {
    backgroundColor: '#27272a',
  },
  dailyRewardIcon: {
    fontSize: 18,
  },
  dailyRewardText: {
    fontSize: 14,
    fontWeight: '600',
  },
  
  // Stats Grid
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  statBox: {
    width: (width - 48 - 8) / 2,
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: 'center',
  },
  statIcon: {
    fontSize: 20,
    marginBottom: 4,
  },
  statValue: {
    fontSize: 18,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: 10,
    marginTop: 2,
  },
  
  // XP Toast
  xpToast: {
    position: 'absolute',
    bottom: 100,
    alignSelf: 'center',
    backgroundColor: '#f59e0b',
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 24,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    shadowColor: '#f59e0b',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  xpToastText: {
    color: '#000',
    fontSize: 15,
    fontWeight: '700',
  },
  xpToastAction: {
    color: '#78350f',
    fontSize: 12,
  },
});

export default {
  XPProgressBar,
  StreakDisplay,
  AchievementBadge,
  AchievementCard,
  DailyRewardButton,
  StatsGrid,
  XPToast,
};
