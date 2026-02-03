import React, { useState, useEffect, useCallback } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TouchableOpacity, 
  RefreshControl,
  ActivityIndicator 
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../../src/context/ThemeContext';
import { useAuth } from '../../src/context/AuthContext';
import { dashboardAPI } from '../../src/services/api';
import { StatusColors } from '../../src/constants/config';

export default function DashboardScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchStats = async () => {
    try {
      const data = await dashboardAPI.getStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchStats();
    setRefreshing(false);
  }, []);

  const styles = createStyles(colors);
  const firstName = user?.name?.split(' ')[0] || 'Player';
  const hasGames = stats && stats.total_games > 0;

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.text} />
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
            <Text style={styles.greeting}>Dashboard</Text>
            <Text style={styles.title}>Welcome, {firstName}</Text>
          </View>
        </View>

        {!hasGames ? (
          /* Empty State */
          <View style={styles.emptyState}>
            <View style={styles.emptyIcon}>
              <Ionicons name="cloud-download-outline" size={48} color={colors.textSecondary} />
            </View>
            <Text style={styles.emptyTitle}>No games imported yet</Text>
            <Text style={styles.emptyText}>
              Connect your Chess.com or Lichess account to start receiving personalized coaching.
            </Text>
            <TouchableOpacity 
              style={styles.primaryButton}
              onPress={() => router.push('/(tabs)/games')}
            >
              <Ionicons name="add" size={20} color={colors.background} />
              <Text style={styles.primaryButtonText}>Import Games</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            {/* Stats Grid */}
            <View style={styles.statsGrid}>
              <StatCard 
                label="Games" 
                value={stats.total_games} 
                icon="game-controller-outline"
                colors={colors}
              />
              <StatCard 
                label="Analyzed" 
                value={stats.analyzed_games} 
                icon="checkmark-circle-outline"
                colors={colors}
              />
              <StatCard 
                label="Blunders" 
                value={stats.stats?.total_blunders || 0} 
                icon="alert-circle-outline"
                colors={colors}
                valueColor={StatusColors.blunder}
              />
              <StatCard 
                label="Best Moves" 
                value={stats.stats?.total_best_moves || 0} 
                icon="star-outline"
                colors={colors}
                valueColor={StatusColors.excellent}
              />
            </View>

            {/* Recent Games */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Text style={styles.sectionTitle}>RECENT GAMES</Text>
                <TouchableOpacity onPress={() => router.push('/(tabs)/games')}>
                  <Text style={styles.seeAll}>See all</Text>
                </TouchableOpacity>
              </View>
              
              {stats.recent_games?.slice(0, 4).map((game) => (
                <TouchableOpacity 
                  key={game.game_id}
                  style={styles.gameItem}
                  onPress={() => router.push(`/game/${game.game_id}`)}
                >
                  <View style={styles.gameInfo}>
                    <View style={[
                      styles.colorIndicator, 
                      { backgroundColor: game.user_color === 'white' ? '#fff' : '#333' }
                    ]} />
                    <View>
                      <Text style={styles.gamePlayers} numberOfLines={1}>
                        {game.white_player} vs {game.black_player}
                      </Text>
                      <Text style={styles.gameMeta}>
                        {game.platform} • {game.result}
                      </Text>
                    </View>
                  </View>
                  <View style={styles.gameStatus}>
                    {game.is_analyzed ? (
                      <Ionicons name="checkmark-circle" size={20} color={StatusColors.excellent} />
                    ) : (
                      <Ionicons name="ellipse-outline" size={20} color={colors.textSecondary} />
                    )}
                  </View>
                </TouchableOpacity>
              ))}
            </View>

            {/* Focus Areas */}
            {stats.top_weaknesses?.length > 0 && (
              <View style={styles.section}>
                <View style={styles.sectionHeader}>
                  <Text style={styles.sectionTitle}>FOCUS AREAS</Text>
                  <TouchableOpacity onPress={() => router.push('/(tabs)/journey')}>
                    <Text style={styles.seeAll}>Journey</Text>
                  </TouchableOpacity>
                </View>
                
                {stats.top_weaknesses.slice(0, 3).map((weakness, index) => (
                  <View key={index} style={styles.weaknessItem}>
                    <View>
                      <Text style={styles.weaknessName}>
                        {(weakness.subcategory || weakness.name || '').replace(/_/g, ' ')}
                      </Text>
                      <Text style={styles.weaknessCategory}>{weakness.category}</Text>
                    </View>
                    <View style={styles.weaknessBar}>
                      <View style={[
                        styles.weaknessProgress, 
                        { width: `${Math.min((weakness.occurrences || 1) * 20, 100)}%` }
                      ]} />
                    </View>
                  </View>
                ))}
              </View>
            )}

            {/* Quick Actions */}
            <View style={styles.quickActions}>
              <TouchableOpacity 
                style={styles.actionButton}
                onPress={() => router.push('/(tabs)/games')}
              >
                <Ionicons name="cloud-download-outline" size={24} color={colors.text} />
                <Text style={styles.actionText}>Import</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.actionButton}
                onPress={() => router.push('/(tabs)/journey')}
              >
                <Ionicons name="trending-up-outline" size={24} color={colors.text} />
                <Text style={styles.actionText}>Journey</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.actionButton}
                onPress={() => router.push('/(tabs)/settings')}
              >
                <Ionicons name="settings-outline" size={24} color={colors.text} />
                <Text style={styles.actionText}>Settings</Text>
              </TouchableOpacity>
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const StatCard = ({ label, value, icon, colors, valueColor }) => (
  <View style={{
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
  }}>
    <Ionicons name={icon} size={20} color={colors.textSecondary} style={{ marginBottom: 8 }} />
    <Text style={{ 
      fontSize: 24, 
      fontWeight: '700', 
      color: valueColor || colors.text,
      letterSpacing: -0.5,
    }}>{value}</Text>
    <Text style={{ 
      fontSize: 11, 
      color: colors.textSecondary, 
      textTransform: 'uppercase',
      letterSpacing: 0.5,
      marginTop: 4,
    }}>{label}</Text>
  </View>
);

const createStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loadingContainer: {
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
    marginBottom: 24,
  },
  greeting: {
    fontSize: 12,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 4,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    letterSpacing: -0.5,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 24,
  },
  section: {
    marginBottom: 24,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 11,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1,
    fontWeight: '600',
  },
  seeAll: {
    fontSize: 13,
    color: colors.accent,
  },
  gameItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  gameInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  colorIndicator: {
    width: 24,
    height: 24,
    borderRadius: 6,
    marginRight: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  gamePlayers: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 2,
  },
  gameMeta: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  gameStatus: {
    marginLeft: 12,
  },
  weaknessItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  weaknessName: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.text,
    textTransform: 'capitalize',
    marginBottom: 2,
  },
  weaknessCategory: {
    fontSize: 12,
    color: colors.textSecondary,
    textTransform: 'capitalize',
  },
  weaknessBar: {
    width: 60,
    height: 6,
    backgroundColor: colors.muted,
    borderRadius: 3,
    overflow: 'hidden',
  },
  weaknessProgress: {
    height: '100%',
    backgroundColor: colors.warning,
    borderRadius: 3,
  },
  quickActions: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  actionButton: {
    alignItems: 'center',
    padding: 12,
  },
  actionText: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 8,
  },
  emptyState: {
    alignItems: 'center',
    padding: 40,
    marginTop: 40,
  },
  emptyIcon: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: colors.card,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
    borderWidth: 2,
    borderColor: colors.border,
    borderStyle: 'dashed',
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 8,
  },
  emptyText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 22,
  },
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.text,
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 12,
    gap: 8,
  },
  primaryButtonText: {
    color: colors.background,
    fontSize: 16,
    fontWeight: '600',
  },
});
