import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  RefreshControl,
  ActivityIndicator,
  TouchableOpacity
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';
import { API_URL } from '../constants/config';
import { getSessionToken } from '../services/api';

// Fetch helper with auth
const fetchWithAuth = async (endpoint) => {
  const token = await getSessionToken();
  const response = await fetch(`${API_URL}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
  });
  if (!response.ok) throw new Error('Failed to fetch');
  return response.json();
};

// Rating milestone colors
const getMilestoneColor = (rating) => {
  if (rating >= 2000) return '#a78bfa'; // purple
  if (rating >= 1800) return '#60a5fa'; // blue
  if (rating >= 1600) return '#34d399'; // green
  if (rating >= 1400) return '#fbbf24'; // yellow
  if (rating >= 1200) return '#fb923c'; // orange
  return '#a1a1aa'; // gray
};

const getTrendIcon = (trend) => {
  if (trend === 'rapid_improvement' || trend === 'steady_improvement') {
    return { name: 'trending-up', color: '#10b981' };
  }
  if (trend === 'slight_decline' || trend === 'needs_attention') {
    return { name: 'trending-down', color: '#ef4444' };
  }
  return { name: 'remove', color: '#71717a' };
};

const getTrendLabel = (trend) => {
  const labels = {
    'rapid_improvement': 'Rapid Improvement 🔥',
    'steady_improvement': 'Steady Progress 📈',
    'stable': 'Holding Steady',
    'slight_decline': 'Slight Dip',
    'needs_attention': 'Needs Focus',
    'insufficient_data': 'Analyzing...'
  };
  return labels[trend] || trend;
};

// Rating Trajectory Component
export const RatingTrajectoryCard = ({ data }) => {
  const { colors } = useTheme();
  
  if (!data) return null;
  
  const { trajectory, platform_ratings, current_rating, improvement_velocity, rating_source } = data;
  const nextMilestone = trajectory?.next_milestone;
  const projectedRating = trajectory?.projected_rating;
  const trendIcon = getTrendIcon(improvement_velocity?.trend);

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      {/* Header with gradient effect */}
      <View style={[styles.cardHeader, { backgroundColor: `${colors.accent}15` }]}>
        <View>
          <Text style={[styles.label, { color: colors.textSecondary }]}>Current Rating</Text>
          <View style={styles.ratingRow}>
            <Text style={[styles.ratingValue, { color: getMilestoneColor(current_rating) }]}>
              {current_rating}
            </Text>
            <Text style={[styles.ratingSource, { color: colors.textSecondary }]}>
              {rating_source?.replace(/_/g, ' ').replace('chess com', 'Chess.com')}
            </Text>
          </View>
        </View>
        <View style={styles.trendContainer}>
          <View style={styles.trendRow}>
            <Ionicons name={trendIcon.name} size={16} color={trendIcon.color} />
            <Text style={[styles.trendText, { color: trendIcon.color }]}>
              {getTrendLabel(improvement_velocity?.trend)}
            </Text>
          </View>
          {improvement_velocity?.velocity !== 0 && (
            <Text style={[styles.velocityText, { color: colors.textSecondary }]}>
              {improvement_velocity?.velocity > 0 ? '+' : ''}{improvement_velocity?.velocity} pts/month
            </Text>
          )}
        </View>
      </View>

      {/* Projections */}
      <View style={styles.projectionsContainer}>
        <View style={[styles.projectionBox, { backgroundColor: colors.muted }]}>
          <Text style={[styles.projectionLabel, { color: colors.textSecondary }]}>1 Month</Text>
          <Text style={[styles.projectionValue, { color: colors.text }]}>{projectedRating?.['1_month']}</Text>
        </View>
        <View style={[styles.projectionBoxMain, { backgroundColor: colors.muted, borderColor: colors.accent }]}>
          <Text style={[styles.projectionLabel, { color: colors.textSecondary }]}>3 Months</Text>
          <Text style={[styles.projectionValueMain, { color: colors.accent }]}>{projectedRating?.['3_months']}</Text>
          <Text style={[styles.projectionRange, { color: colors.textSecondary }]}>
            {projectedRating?.range_3m?.[0]}-{projectedRating?.range_3m?.[1]}
          </Text>
        </View>
        <View style={[styles.projectionBox, { backgroundColor: colors.muted }]}>
          <Text style={[styles.projectionLabel, { color: colors.textSecondary }]}>6 Months</Text>
          <Text style={[styles.projectionValue, { color: colors.text }]}>{projectedRating?.['6_months']}</Text>
        </View>
      </View>

      {/* Next Milestone */}
      {nextMilestone && (
        <View style={[styles.milestoneContainer, { backgroundColor: '#10b98115', borderColor: '#10b98130' }]}>
          <View style={styles.milestoneLeft}>
            <View style={[styles.milestoneIcon, { backgroundColor: '#10b98130' }]}>
              <Ionicons name="trophy" size={18} color="#10b981" />
            </View>
            <View>
              <Text style={[styles.milestoneName, { color: colors.text }]}>Next: {nextMilestone.name}</Text>
              <Text style={[styles.milestonePoints, { color: colors.textSecondary }]}>
                {nextMilestone.points_needed} points to {nextMilestone.rating}
              </Text>
            </View>
          </View>
          <View style={styles.milestoneRight}>
            {nextMilestone.estimated_months ? (
              <>
                <Text style={styles.milestoneMonths}>{nextMilestone.estimated_months}</Text>
                <Text style={[styles.milestoneMonthsLabel, { color: colors.textSecondary }]}>months</Text>
              </>
            ) : (
              <Text style={[styles.milestoneKeepGoing, { color: colors.textSecondary }]}>Keep practicing!</Text>
            )}
          </View>
        </View>
      )}
    </View>
  );
};

// Time Management Component
export const TimeManagementCard = ({ data }) => {
  const { colors } = useTheme();
  
  if (!data?.has_data) {
    return (
      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.cardTitleRow}>
          <Ionicons name="time-outline" size={18} color="#3b82f6" />
          <Text style={[styles.cardTitle, { color: colors.text }]}>Time Management</Text>
        </View>
        <View style={styles.emptyState}>
          <Ionicons name="time-outline" size={32} color={colors.textSecondary} />
          <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
            {data?.message || 'Play more timed games to see analysis'}
          </Text>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.cardTitleRow}>
        <Ionicons name="time-outline" size={18} color="#3b82f6" />
        <Text style={[styles.cardTitle, { color: colors.text }]}>Time Management</Text>
      </View>

      {/* Phase breakdown */}
      <View style={styles.phaseContainer}>
        {data.phase_breakdown?.opening && (
          <View style={[styles.phaseBox, { backgroundColor: colors.muted }]}>
            <Text style={[styles.phaseLabel, { color: colors.textSecondary }]}>Opening</Text>
            <Text style={[styles.phaseValue, { color: colors.text }]}>{data.phase_breakdown.opening.avg_time}s</Text>
          </View>
        )}
        {data.phase_breakdown?.middlegame && (
          <View style={[styles.phaseBox, { backgroundColor: colors.muted }]}>
            <Text style={[styles.phaseLabel, { color: colors.textSecondary }]}>Middle</Text>
            <Text style={[styles.phaseValue, { color: colors.text }]}>{data.phase_breakdown.middlegame.avg_time}s</Text>
          </View>
        )}
        {data.phase_breakdown?.endgame && (
          <View style={[styles.phaseBox, { backgroundColor: colors.muted }]}>
            <Text style={[styles.phaseLabel, { color: colors.textSecondary }]}>Endgame</Text>
            <Text style={[styles.phaseValue, { color: colors.text }]}>{data.phase_breakdown.endgame.avg_time}s</Text>
          </View>
        )}
      </View>

      {/* Insights */}
      {data.insights?.map((insight, i) => (
        <View 
          key={i} 
          style={[
            styles.insightBox, 
            { 
              backgroundColor: insight.type === 'critical' ? '#ef444415' : 
                             insight.type === 'warning' ? '#f59e0b15' : '#3b82f615'
            }
          ]}
        >
          <Text style={[
            styles.insightText,
            { 
              color: insight.type === 'critical' ? '#ef4444' : 
                     insight.type === 'warning' ? '#f59e0b' : '#3b82f6'
            }
          ]}>
            {insight.message}
          </Text>
        </View>
      ))}
    </View>
  );
};

// Fast Thinking Component
export const FastThinkingCard = ({ data }) => {
  const { colors } = useTheme();
  
  if (!data?.has_data) {
    return (
      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.cardTitleRow}>
          <Ionicons name="flash-outline" size={18} color="#a855f7" />
          <Text style={[styles.cardTitle, { color: colors.text }]}>Calculation Speed</Text>
        </View>
        <View style={styles.emptyState}>
          <Ionicons name="flash-outline" size={32} color={colors.textSecondary} />
          <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
            Analyze more games to see thinking patterns
          </Text>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.cardTitleRow}>
        <Ionicons name="flash-outline" size={18} color="#a855f7" />
        <Text style={[styles.cardTitle, { color: colors.text }]}>Calculation Speed</Text>
      </View>

      {/* Speed issues */}
      {data.speed_issues?.map((issue, i) => (
        <View key={i} style={[styles.issueBox, { backgroundColor: colors.muted }]}>
          <Ionicons name="warning-outline" size={16} color="#f59e0b" />
          <View style={styles.issueContent}>
            <Text style={[styles.issuePattern, { color: colors.text }]}>{issue.pattern}</Text>
            <Text style={[styles.issueTip, { color: colors.textSecondary }]}>{issue.tip}</Text>
          </View>
        </View>
      ))}

      {data.overall_tip && (
        <Text style={[styles.overallTip, { color: colors.textSecondary }]}>{data.overall_tip}</Text>
      )}

      {data.recommended_drill_time && (
        <View style={styles.drillTimeRow}>
          <Ionicons name="time-outline" size={14} color={colors.accent} />
          <Text style={[styles.drillTimeText, { color: colors.text }]}>
            Recommended: {data.recommended_drill_time}
          </Text>
        </View>
      )}
    </View>
  );
};

// Puzzle Trainer Component
export const PuzzleTrainerCard = ({ data }) => {
  const { colors } = useTheme();
  const [currentPuzzle, setCurrentPuzzle] = useState(0);
  
  const puzzle = data?.puzzles?.[currentPuzzle];

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.cardTitleRow}>
        <Ionicons name="bulb-outline" size={18} color="#f59e0b" />
        <Text style={[styles.cardTitle, { color: colors.text }]}>
          {data?.session_type === 'targeted' ? `Training: ${data.target_weakness}` : 'Tactical Training'}
        </Text>
      </View>

      {/* Tips */}
      {data?.tips?.length > 0 && (
        <View style={[styles.tipsBox, { backgroundColor: '#f59e0b15', borderColor: '#f59e0b30' }]}>
          <Text style={styles.tipsTitle}>💡 Tips</Text>
          {data.tips.slice(0, 2).map((tip, i) => (
            <Text key={i} style={[styles.tipText, { color: colors.textSecondary }]}>{tip}</Text>
          ))}
        </View>
      )}

      {/* Puzzle display */}
      {puzzle && (
        <View style={styles.puzzleContainer}>
          <Text style={[styles.puzzleCounter, { color: colors.textSecondary }]}>
            Puzzle {currentPuzzle + 1} of {data.puzzles.length}
          </Text>
          <Text style={[styles.puzzleTheme, { color: colors.text }]}>{puzzle.theme}</Text>
          <Text style={[styles.puzzleHint, { color: colors.textSecondary }]}>
            Find the best move! (Difficulty: {puzzle.difficulty})
          </Text>
        </View>
      )}

      {/* Navigation */}
      <View style={styles.puzzleNav}>
        <TouchableOpacity 
          style={[styles.navButton, { borderColor: colors.border, opacity: currentPuzzle === 0 ? 0.5 : 1 }]}
          onPress={() => setCurrentPuzzle(Math.max(0, currentPuzzle - 1))}
          disabled={currentPuzzle === 0}
        >
          <Text style={[styles.navButtonText, { color: colors.text }]}>Previous</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.navButton, { borderColor: colors.border, opacity: currentPuzzle >= (data?.puzzles?.length - 1) ? 0.5 : 1 }]}
          onPress={() => setCurrentPuzzle(Math.min(data?.puzzles?.length - 1, currentPuzzle + 1))}
          disabled={currentPuzzle >= (data?.puzzles?.length - 1)}
        >
          <Text style={[styles.navButtonText, { color: colors.text }]}>Next</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

// Main Screen Component
export const RatingScreen = () => {
  const { colors } = useTheme();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [trajectoryData, setTrajectoryData] = useState(null);
  const [timeData, setTimeData] = useState(null);
  const [thinkingData, setThinkingData] = useState(null);
  const [puzzleData, setPuzzleData] = useState(null);

  const fetchAllData = async () => {
    try {
      const [trajectory, time, thinking, puzzles] = await Promise.all([
        fetchWithAuth('/rating/trajectory').catch(() => null),
        fetchWithAuth('/training/time-management').catch(() => null),
        fetchWithAuth('/training/fast-thinking').catch(() => null),
        fetchWithAuth('/training/puzzles?count=5').catch(() => null),
      ]);
      
      setTrajectoryData(trajectory);
      setTimeData(time);
      setThinkingData(thinking);
      setPuzzleData(puzzles);
    } catch (error) {
      console.error('Failed to fetch rating data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchAllData();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <View style={[styles.loadingContainer, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="large" color={colors.text} />
      </View>
    );
  }

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: colors.background }]}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.text} />
      }
      showsVerticalScrollIndicator={false}
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerIcon}>
          <Ionicons name="trending-up" size={20} color={colors.accent} />
        </View>
        <View>
          <Text style={[styles.headerLabel, { color: colors.textSecondary }]}>YOUR PROGRESS</Text>
          <Text style={[styles.headerTitle, { color: colors.text }]}>Rating & Training</Text>
        </View>
      </View>

      {/* Rating Trajectory */}
      {trajectoryData && <RatingTrajectoryCard data={trajectoryData} />}

      {/* Training Cards */}
      <TimeManagementCard data={timeData} />
      <FastThinkingCard data={thinkingData} />
      <PuzzleTrainerCard data={puzzleData} />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 20,
  },
  headerIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerLabel: {
    fontSize: 10,
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: 2,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '700',
    letterSpacing: -0.5,
  },
  card: {
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 12,
    overflow: 'hidden',
  },
  cardHeader: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.1)',
  },
  label: {
    fontSize: 10,
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  ratingRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 8,
  },
  ratingValue: {
    fontSize: 36,
    fontWeight: '700',
  },
  ratingSource: {
    fontSize: 12,
  },
  trendContainer: {
    position: 'absolute',
    right: 16,
    top: 16,
    alignItems: 'flex-end',
  },
  trendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  trendText: {
    fontSize: 12,
    fontWeight: '500',
  },
  velocityText: {
    fontSize: 10,
    marginTop: 2,
  },
  projectionsContainer: {
    flexDirection: 'row',
    padding: 16,
    gap: 8,
  },
  projectionBox: {
    flex: 1,
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  projectionBoxMain: {
    flex: 1,
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
  },
  projectionLabel: {
    fontSize: 10,
    marginBottom: 4,
  },
  projectionValue: {
    fontSize: 18,
    fontWeight: '600',
  },
  projectionValueMain: {
    fontSize: 22,
    fontWeight: '700',
  },
  projectionRange: {
    fontSize: 10,
    marginTop: 2,
  },
  milestoneContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    margin: 16,
    marginTop: 0,
    padding: 14,
    borderRadius: 10,
    borderWidth: 1,
  },
  milestoneLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  milestoneIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  milestoneName: {
    fontSize: 14,
    fontWeight: '600',
  },
  milestonePoints: {
    fontSize: 12,
    marginTop: 2,
  },
  milestoneRight: {
    alignItems: 'flex-end',
  },
  milestoneMonths: {
    fontSize: 24,
    fontWeight: '700',
    color: '#10b981',
  },
  milestoneMonthsLabel: {
    fontSize: 10,
  },
  milestoneKeepGoing: {
    fontSize: 12,
  },
  cardTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.05)',
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  emptyState: {
    alignItems: 'center',
    padding: 24,
  },
  emptyText: {
    fontSize: 12,
    marginTop: 8,
    textAlign: 'center',
  },
  phaseContainer: {
    flexDirection: 'row',
    padding: 12,
    gap: 8,
  },
  phaseBox: {
    flex: 1,
    padding: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
  phaseLabel: {
    fontSize: 10,
    marginBottom: 4,
  },
  phaseValue: {
    fontSize: 14,
    fontWeight: '600',
  },
  insightBox: {
    marginHorizontal: 12,
    marginBottom: 8,
    padding: 10,
    borderRadius: 8,
  },
  insightText: {
    fontSize: 12,
  },
  issueBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    margin: 12,
    marginBottom: 8,
    padding: 12,
    borderRadius: 8,
  },
  issueContent: {
    flex: 1,
  },
  issuePattern: {
    fontSize: 13,
    fontWeight: '500',
    marginBottom: 4,
  },
  issueTip: {
    fontSize: 11,
  },
  overallTip: {
    fontSize: 12,
    padding: 12,
    paddingTop: 0,
  },
  drillTimeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingBottom: 12,
  },
  drillTimeText: {
    fontSize: 12,
  },
  tipsBox: {
    margin: 12,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
  },
  tipsTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: '#f59e0b',
    marginBottom: 6,
  },
  tipText: {
    fontSize: 11,
    marginBottom: 2,
  },
  puzzleContainer: {
    alignItems: 'center',
    padding: 16,
  },
  puzzleCounter: {
    fontSize: 10,
    marginBottom: 8,
  },
  puzzleTheme: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 4,
    textTransform: 'capitalize',
  },
  puzzleHint: {
    fontSize: 12,
  },
  puzzleNav: {
    flexDirection: 'row',
    gap: 8,
    padding: 12,
    paddingTop: 0,
  },
  navButton: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },
  navButtonText: {
    fontSize: 13,
    fontWeight: '500',
  },
});

export default RatingScreen;
