import React, { useState, useEffect, useCallback } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TouchableOpacity, 
  RefreshControl,
  ActivityIndicator,
  TextInput,
  Alert
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../../src/context/ThemeContext';
import { journeyAPI, getSessionToken } from '../../src/services/api';
import { StatusColors, TrendIcons, API_URL } from '../../src/constants/config';
import { 
  RatingTrajectoryCard, 
  TimeManagementCard, 
  FastThinkingCard, 
  PuzzleTrainerCard 
} from '../../src/components/RatingTrajectory';

// Fetch helper
const fetchWithAuth = async (endpoint) => {
  const token = await getSessionToken();
  const response = await fetch(`${API_URL}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
  });
  if (!response.ok) return null;
  return response.json();
};

export default function JourneyScreen() {
  const { colors } = useTheme();
  const [dashboard, setDashboard] = useState(null);
  const [accounts, setAccounts] = useState({ chess_com: null, lichess: null });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [linking, setLinking] = useState(false);
  const [platform, setPlatform] = useState(null);
  const [username, setUsername] = useState('');
  
  // Rating & Training data
  const [trajectoryData, setTrajectoryData] = useState(null);
  const [timeData, setTimeData] = useState(null);
  const [thinkingData, setThinkingData] = useState(null);
  const [puzzleData, setPuzzleData] = useState(null);

  const fetchData = async () => {
    try {
      const [accountsData, dashboardData] = await Promise.all([
        journeyAPI.getLinkedAccounts(),
        journeyAPI.getDashboard()
      ]);
      setAccounts(accountsData);
      setDashboard(dashboardData);
      
      // Fetch rating data
      const [trajectory, time, thinking, puzzles] = await Promise.all([
        fetchWithAuth('/rating/trajectory'),
        fetchWithAuth('/training/time-management'),
        fetchWithAuth('/training/fast-thinking'),
        fetchWithAuth('/training/puzzles?count=5'),
      ]);
      setTrajectoryData(trajectory);
      setTimeData(time);
      setThinkingData(thinking);
      setPuzzleData(puzzles);
    } catch (error) {
      console.error('Failed to fetch journey data:', error);
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

  const handleSync = async () => {
    setSyncing(true);
    try {
      await journeyAPI.syncNow();
      Alert.alert('Success', 'Sync started! New games will appear shortly.');
      setTimeout(fetchData, 5000);
    } catch (error) {
      Alert.alert('Error', error.message);
    } finally {
      setSyncing(false);
    }
  };

  const handleLinkAccount = async () => {
    if (!username.trim()) {
      Alert.alert('Error', 'Please enter a username');
      return;
    }
    setLinking(true);
    try {
      await journeyAPI.linkAccount(platform, username.trim());
      Alert.alert('Success', 'Account linked!');
      setPlatform(null);
      setUsername('');
      fetchData();
    } catch (error) {
      Alert.alert('Error', error.message);
    } finally {
      setLinking(false);
    }
  };

  const styles = createStyles(colors);
  const hasAccount = accounts.chess_com || accounts.lichess;
  const gamesAnalyzed = dashboard?.games_analyzed || 0;
  const mode = dashboard?.mode || 'onboarding';

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
            <Text style={styles.greeting}>YOUR PROGRESS</Text>
            <Text style={styles.title}>Journey</Text>
          </View>
          {gamesAnalyzed > 0 && (
            <View style={styles.gamesCount}>
              <Text style={styles.gamesNumber}>{gamesAnalyzed}</Text>
              <Text style={styles.gamesLabel}>games analyzed</Text>
            </View>
          )}
        </View>

        {/* Connect Account CTA */}
        {!hasAccount && (
          <View style={styles.connectCard}>
            <View style={styles.connectIcon}>
              <Ionicons name="link-outline" size={32} color={colors.textSecondary} />
            </View>
            <Text style={styles.connectTitle}>Connect Your Chess Account</Text>
            <Text style={styles.connectText}>
              Link your account to start tracking progress and receive personalized coaching.
            </Text>
            <View style={styles.platformButtons}>
              <TouchableOpacity 
                style={styles.platformButton}
                onPress={() => setPlatform('chess.com')}
              >
                <Text style={styles.platformButtonText}>Chess.com</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.platformButton}
                onPress={() => setPlatform('lichess')}
              >
                <Text style={styles.platformButtonText}>Lichess</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* Link Account Form */}
        {platform && (
          <View style={styles.linkForm}>
            <Text style={styles.linkFormTitle}>Link {platform}</Text>
            <TextInput
              style={styles.input}
              placeholder={`Enter ${platform} username`}
              placeholderTextColor={colors.textSecondary}
              value={username}
              onChangeText={setUsername}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <View style={styles.linkFormButtons}>
              <TouchableOpacity 
                style={styles.cancelButton}
                onPress={() => { setPlatform(null); setUsername(''); }}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.connectButton}
                onPress={handleLinkAccount}
                disabled={linking}
              >
                {linking ? (
                  <ActivityIndicator color={colors.background} size="small" />
                ) : (
                  <Text style={styles.connectButtonText}>Connect</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* Onboarding State */}
        {mode === 'onboarding' && hasAccount && (
          <View style={styles.onboardingCard}>
            <View style={styles.progressRing}>
              <Text style={styles.progressText}>{Math.min(gamesAnalyzed * 20, 100)}%</Text>
            </View>
            <View style={styles.onboardingContent}>
              <Text style={styles.onboardingLabel}>GETTING STARTED</Text>
              <Text style={styles.onboardingText}>
                {dashboard?.weekly_assessment || "Play a few more games and I'll start identifying patterns in your play."}
              </Text>
            </View>
          </View>
        )}

        {/* Main Dashboard Content */}
        {mode !== 'onboarding' && dashboard && (
          <>
            {/* Coach Assessment */}
            <View style={styles.assessmentCard}>
              <Text style={styles.sectionLabel}>COACH'S ASSESSMENT</Text>
              <View style={styles.coachMessage}>
                <Text style={styles.coachText}>{dashboard.weekly_assessment}</Text>
              </View>
            </View>

            {/* Focus Areas */}
            {dashboard.focus_areas?.length > 0 && (
              <View style={styles.section}>
                <Text style={styles.sectionLabel}>FOCUS AREAS</Text>
                {dashboard.focus_areas.map((area, i) => (
                  <View key={i} style={styles.focusItem}>
                    <View>
                      <Text style={styles.focusName}>{area.name}</Text>
                      <Text style={styles.focusCategory}>{area.category}</Text>
                    </View>
                    <StatusBadge status={area.status} colors={colors} />
                  </View>
                ))}
              </View>
            )}

            {/* Habit Trends */}
            {dashboard.weakness_trends?.length > 0 && (
              <View style={styles.section}>
                <Text style={styles.sectionLabel}>HABIT TRENDS</Text>
                {dashboard.weakness_trends.map((trend, i) => (
                  <View key={i} style={styles.trendItem}>
                    <View>
                      <Text style={styles.trendName}>{trend.name}</Text>
                      <Text style={styles.trendMeta}>
                        {trend.occurrences_recent} recent · {trend.occurrences_previous} before
                      </Text>
                    </View>
                    <TrendIndicator trend={trend.trend} colors={colors} />
                  </View>
                ))}
              </View>
            )}

            {/* Strengths */}
            {dashboard.strengths?.length > 0 && (
              <View style={styles.section}>
                <View style={styles.sectionHeader}>
                  <Text style={styles.sectionLabel}>YOUR STRENGTHS</Text>
                  <Ionicons name="sparkles" size={16} color={colors.accent} />
                </View>
                <View style={styles.strengthsContainer}>
                  {dashboard.strengths.map((s, i) => (
                    <View key={i} style={styles.strengthBadge}>
                      <Text style={styles.strengthText}>{s.name}</Text>
                    </View>
                  ))}
                </View>
              </View>
            )}
          </>
        )}

        {/* Linked Accounts Footer */}
        {hasAccount && (
          <View style={styles.linkedAccounts}>
            <View style={styles.accountsList}>
              {accounts.chess_com && (
                <View style={styles.accountItem}>
                  <View style={styles.accountDot} />
                  <Text style={styles.accountText}>Chess.com: {accounts.chess_com}</Text>
                </View>
              )}
              {accounts.lichess && (
                <View style={styles.accountItem}>
                  <View style={styles.accountDot} />
                  <Text style={styles.accountText}>Lichess: {accounts.lichess}</Text>
                </View>
              )}
            </View>
            <TouchableOpacity 
              style={styles.syncButton}
              onPress={handleSync}
              disabled={syncing}
            >
              {syncing ? (
                <ActivityIndicator color={colors.textSecondary} size="small" />
              ) : (
                <>
                  <Ionicons name="refresh" size={16} color={colors.textSecondary} />
                  <Text style={styles.syncText}>Sync</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const StatusBadge = ({ status, colors }) => {
  const configs = {
    improving: { bg: 'rgba(16, 185, 129, 0.15)', text: StatusColors.improving, icon: '↑' },
    stable: { bg: 'rgba(113, 113, 122, 0.15)', text: StatusColors.stable, icon: '→' },
    needs_attention: { bg: 'rgba(245, 158, 11, 0.15)', text: StatusColors.attention, icon: '↓' },
  };
  const config = configs[status] || configs.stable;
  
  return (
    <View style={{ 
      flexDirection: 'row', 
      alignItems: 'center', 
      backgroundColor: config.bg,
      paddingHorizontal: 10,
      paddingVertical: 6,
      borderRadius: 6,
      gap: 4,
    }}>
      <Text style={{ color: config.text, fontFamily: 'monospace' }}>{config.icon}</Text>
      <Text style={{ color: config.text, fontSize: 12, fontWeight: '500' }}>
        {status === 'needs_attention' ? 'Focus' : status.charAt(0).toUpperCase() + status.slice(1)}
      </Text>
    </View>
  );
};

const TrendIndicator = ({ trend, colors }) => {
  const configs = {
    improving: { icon: '↓', color: StatusColors.improving },
    worsening: { icon: '↑', color: StatusColors.attention },
    stable: { icon: '→', color: colors.textSecondary },
  };
  const config = configs[trend] || configs.stable;
  
  return (
    <Text style={{ fontSize: 20, color: config.color, fontFamily: 'monospace' }}>
      {config.icon}
    </Text>
  );
};

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
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    marginBottom: 24,
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
  gamesCount: {
    alignItems: 'flex-end',
  },
  gamesNumber: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
  },
  gamesLabel: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  connectCard: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 32,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: colors.border,
    borderStyle: 'dashed',
  },
  connectIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.muted,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  connectTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 8,
  },
  connectText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 22,
  },
  platformButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  platformButton: {
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.muted,
  },
  platformButtonText: {
    color: colors.text,
    fontWeight: '500',
  },
  linkForm: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  linkFormTitle: {
    fontSize: 11,
    color: colors.textSecondary,
    letterSpacing: 1,
    marginBottom: 12,
    textTransform: 'uppercase',
  },
  input: {
    backgroundColor: colors.muted,
    borderRadius: 10,
    padding: 14,
    color: colors.text,
    fontSize: 15,
    marginBottom: 12,
  },
  linkFormButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  cancelButton: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cancelButtonText: {
    color: colors.textSecondary,
    fontWeight: '500',
  },
  connectButton: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderRadius: 10,
    backgroundColor: colors.text,
  },
  connectButtonText: {
    color: colors.background,
    fontWeight: '600',
  },
  onboardingCard: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    borderLeftColor: colors.accent,
  },
  progressRing: {
    width: 56,
    height: 56,
    borderRadius: 28,
    borderWidth: 4,
    borderColor: colors.muted,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 16,
  },
  progressText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
  },
  onboardingContent: {
    flex: 1,
  },
  onboardingLabel: {
    fontSize: 11,
    color: colors.textSecondary,
    letterSpacing: 1,
    marginBottom: 6,
  },
  onboardingText: {
    fontSize: 14,
    color: colors.text,
    lineHeight: 22,
  },
  assessmentCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  sectionLabel: {
    fontSize: 11,
    color: colors.textSecondary,
    letterSpacing: 1,
    marginBottom: 12,
    fontWeight: '600',
  },
  coachMessage: {
    borderLeftWidth: 2,
    borderLeftColor: colors.accent,
    paddingLeft: 16,
  },
  coachText: {
    fontSize: 15,
    color: colors.text,
    lineHeight: 24,
  },
  section: {
    marginBottom: 20,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  focusItem: {
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
  focusName: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.text,
    textTransform: 'capitalize',
    marginBottom: 2,
  },
  focusCategory: {
    fontSize: 12,
    color: colors.textSecondary,
    textTransform: 'capitalize',
  },
  trendItem: {
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
  trendName: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.text,
    textTransform: 'capitalize',
    marginBottom: 2,
  },
  trendMeta: {
    fontSize: 12,
    color: colors.textSecondary,
    fontFamily: 'monospace',
  },
  strengthsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  strengthBadge: {
    backgroundColor: colors.muted,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  strengthText: {
    fontSize: 13,
    color: colors.text,
    textTransform: 'capitalize',
  },
  linkedAccounts: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  accountsList: {
    flex: 1,
  },
  accountItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  accountDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: StatusColors.improving,
    marginRight: 8,
  },
  accountText: {
    fontSize: 13,
    color: colors.text,
  },
  syncButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  syncText: {
    fontSize: 13,
    color: colors.textSecondary,
  },
});
