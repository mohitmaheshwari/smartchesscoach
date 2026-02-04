import React, { useState, useEffect, useCallback } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  RefreshControl,
  ActivityIndicator,
  Dimensions
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../../src/context/ThemeContext';
import { getSessionToken } from '../../src/services/api';
import { API_URL } from '../../src/constants/config';
import {
  XPProgressBar,
  StreakDisplay,
  AchievementCard,
  AchievementBadge,
} from '../../src/components/Gamification';

const { width } = Dimensions.get('window');

export default function AchievementsScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [progress, setProgress] = useState(null);
  const [achievements, setAchievements] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('all');

  const fetchData = async () => {
    try {
      const token = await getSessionToken();
      const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      };
      
      const [progressRes, achievementsRes] = await Promise.all([
        fetch(`${API_URL}/gamification/progress`, { headers }),
        fetch(`${API_URL}/gamification/achievements`, { headers }),
      ]);
      
      if (progressRes.ok) setProgress(await progressRes.json());
      if (achievementsRes.ok) setAchievements(await achievementsRes.json());
    } catch (error) {
      console.error('Failed to fetch achievements:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, []);

  const categories = [
    { id: 'all', label: 'All', icon: '🏆' },
    { id: 'beginner', label: 'Start', icon: '🎯' },
    { id: 'streak', label: 'Streaks', icon: '🔥' },
    { id: 'analysis', label: 'Analysis', icon: '📊' },
    { id: 'accuracy', label: 'Accuracy', icon: '💎' },
    { id: 'puzzles', label: 'Puzzles', icon: '🧩' },
    { id: 'level', label: 'Levels', icon: '⭐' },
  ];

  const filteredAchievements = selectedCategory === 'all'
    ? achievements?.achievements || []
    : (achievements?.by_category?.[selectedCategory] || []);

  const styles = createStyles(colors);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.text} />
        }
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>ACHIEVEMENTS</Text>
            <Text style={styles.title}>Your Badges</Text>
          </View>
          <View style={styles.completionBadge}>
            <Text style={styles.completionNum}>
              {achievements?.unlocked_count || 0}/{achievements?.total_count || 0}
            </Text>
            <Text style={styles.completionLabel}>Unlocked</Text>
          </View>
        </View>

        {/* XP Progress */}
        {progress && (
          <View style={styles.section}>
            <XPProgressBar progress={progress} />
          </View>
        )}

        {/* Streak */}
        {progress?.current_streak > 0 && (
          <View style={styles.section}>
            <StreakDisplay streak={progress.current_streak} />
          </View>
        )}

        {/* Progress Bar */}
        <View style={styles.progressSection}>
          <View style={styles.progressHeader}>
            <Text style={[styles.progressLabel, { color: colors.text }]}>
              Achievement Progress
            </Text>
            <Text style={[styles.progressPercent, { color: colors.accent }]}>
              {achievements?.completion_percent || 0}%
            </Text>
          </View>
          <View style={[styles.progressBarBg, { backgroundColor: colors.border }]}>
            <View 
              style={[
                styles.progressBarFill, 
                { width: `${achievements?.completion_percent || 0}%` }
              ]} 
            />
          </View>
        </View>

        {/* Category Filter */}
        <ScrollView 
          horizontal 
          showsHorizontalScrollIndicator={false}
          style={styles.categoryScroll}
          contentContainerStyle={styles.categoryContent}
        >
          {categories.map(cat => (
            <View
              key={cat.id}
              style={[
                styles.categoryChip,
                selectedCategory === cat.id && styles.categoryChipActive,
                { borderColor: selectedCategory === cat.id ? colors.accent : colors.border }
              ]}
              onTouchEnd={() => setSelectedCategory(cat.id)}
            >
              <Text style={styles.categoryIcon}>{cat.icon}</Text>
              <Text style={[
                styles.categoryLabel,
                { color: selectedCategory === cat.id ? colors.text : colors.textSecondary }
              ]}>
                {cat.label}
              </Text>
            </View>
          ))}
        </ScrollView>

        {/* Achievements Grid */}
        <View style={styles.achievementsList}>
          {filteredAchievements.map(achievement => (
            <AchievementCard key={achievement.id} achievement={achievement} />
          ))}
        </View>

        {filteredAchievements.length === 0 && (
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>🏆</Text>
            <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
              No achievements in this category yet
            </Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const createStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollView: {
    flex: 1,
  },
  content: {
    padding: 20,
    paddingBottom: 40,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    marginBottom: 20,
  },
  greeting: {
    fontSize: 11,
    color: colors.textSecondary,
    letterSpacing: 1,
    marginBottom: 4,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    letterSpacing: -0.5,
  },
  completionBadge: {
    alignItems: 'center',
    backgroundColor: colors.accent + '15',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
  },
  completionNum: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.accent,
  },
  completionLabel: {
    fontSize: 10,
    color: colors.accent,
    opacity: 0.8,
  },
  section: {
    marginBottom: 16,
  },
  progressSection: {
    marginBottom: 20,
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  progressLabel: {
    fontSize: 14,
    fontWeight: '600',
  },
  progressPercent: {
    fontSize: 14,
    fontWeight: '700',
  },
  progressBarBg: {
    height: 8,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: colors.accent,
    borderRadius: 4,
  },
  categoryScroll: {
    marginBottom: 20,
    marginHorizontal: -20,
  },
  categoryContent: {
    paddingHorizontal: 20,
    gap: 8,
  },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    backgroundColor: colors.card,
    gap: 6,
  },
  categoryChipActive: {
    backgroundColor: colors.accent + '15',
  },
  categoryIcon: {
    fontSize: 14,
  },
  categoryLabel: {
    fontSize: 12,
    fontWeight: '500',
  },
  achievementsList: {
    gap: 0,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 12,
    opacity: 0.5,
  },
  emptyText: {
    fontSize: 14,
  },
});
