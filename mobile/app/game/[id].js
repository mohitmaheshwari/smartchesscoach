import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TouchableOpacity, 
  ActivityIndicator,
  Dimensions,
  Alert
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../../src/context/ThemeContext';
import { gamesAPI, analysisAPI } from '../../src/services/api';
import { StatusColors } from '../../src/constants/config';

const { width } = Dimensions.get('window');

export default function GameAnalysisScreen() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { colors } = useTheme();
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentMove, setCurrentMove] = useState(0);
  const [expandedMoves, setExpandedMoves] = useState({});

  useEffect(() => {
    fetchData();
  }, [id]);

  const fetchData = async () => {
    try {
      const [gameData, analysisData] = await Promise.all([
        gamesAPI.getGame(id),
        analysisAPI.getAnalysis(id)
      ]);
      setGame(gameData);
      setAnalysis(analysisData);
    } catch (error) {
      console.error('Failed to fetch game:', error);
      Alert.alert('Error', 'Failed to load game');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const result = await analysisAPI.analyzeGame(id);
      setAnalysis(result);
      Alert.alert('Success', 'Game analyzed!');
    } catch (error) {
      Alert.alert('Error', error.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const toggleMoveExpanded = (index) => {
    setExpandedMoves(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const getEvalColor = (evaluation) => {
    const evalColors = {
      blunder: StatusColors.blunder,
      mistake: StatusColors.mistake,
      inaccuracy: StatusColors.inaccuracy,
      good: StatusColors.good,
      excellent: StatusColors.excellent,
      solid: StatusColors.excellent,
    };
    return evalColors[evaluation] || colors.textSecondary;
  };

  const styles = createStyles(colors);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.text} />
        </View>
      </SafeAreaView>
    );
  }

  if (!game) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <Text style={styles.errorText}>Game not found</Text>
          <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
            <Text style={styles.backButtonText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const moves = analysis?.move_by_move || [];
  const currentMoveData = moves[currentMove];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backIcon}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={styles.headerInfo}>
          <Text style={styles.headerTitle} numberOfLines={1}>
            {game.white_player} vs {game.black_player}
          </Text>
          <Text style={styles.headerMeta}>
            {game.platform} • {game.result} • {game.user_color}
          </Text>
        </View>
      </View>

      <ScrollView 
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
      >
        {/* Chessboard Placeholder */}
        <View style={styles.boardContainer}>
          <View style={styles.boardPlaceholder}>
            <Ionicons name="grid" size={80} color={colors.textSecondary} />
            <Text style={styles.boardPlaceholderText}>
              Interactive board coming soon
            </Text>
            {currentMoveData && (
              <View style={styles.currentMoveInfo}>
                <Text style={styles.currentMoveNumber}>Move {currentMoveData.move_number}</Text>
                <Text style={styles.currentMoveText}>{currentMoveData.move}</Text>
              </View>
            )}
          </View>
          
          {/* Move Navigation */}
          {moves.length > 0 && (
            <View style={styles.moveNav}>
              <TouchableOpacity 
                style={styles.navButton}
                onPress={() => setCurrentMove(0)}
                disabled={currentMove === 0}
              >
                <Ionicons name="play-skip-back" size={20} color={currentMove === 0 ? colors.textSecondary : colors.text} />
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.navButton}
                onPress={() => setCurrentMove(Math.max(0, currentMove - 1))}
                disabled={currentMove === 0}
              >
                <Ionicons name="play-back" size={20} color={currentMove === 0 ? colors.textSecondary : colors.text} />
              </TouchableOpacity>
              <Text style={styles.moveCounter}>{currentMove + 1} / {moves.length}</Text>
              <TouchableOpacity 
                style={styles.navButton}
                onPress={() => setCurrentMove(Math.min(moves.length - 1, currentMove + 1))}
                disabled={currentMove === moves.length - 1}
              >
                <Ionicons name="play-forward" size={20} color={currentMove === moves.length - 1 ? colors.textSecondary : colors.text} />
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.navButton}
                onPress={() => setCurrentMove(moves.length - 1)}
                disabled={currentMove === moves.length - 1}
              >
                <Ionicons name="play-skip-forward" size={20} color={currentMove === moves.length - 1 ? colors.textSecondary : colors.text} />
              </TouchableOpacity>
            </View>
          )}
        </View>

        {!analysis ? (
          /* No Analysis - CTA */
          <View style={styles.noAnalysis}>
            <Ionicons name="analytics-outline" size={48} color={colors.textSecondary} />
            <Text style={styles.noAnalysisTitle}>Game not analyzed yet</Text>
            <Text style={styles.noAnalysisText}>
              Get AI coaching insights for this game
            </Text>
            <TouchableOpacity 
              style={styles.analyzeButton}
              onPress={handleAnalyze}
              disabled={analyzing}
            >
              {analyzing ? (
                <ActivityIndicator color={colors.background} />
              ) : (
                <>
                  <Ionicons name="flash" size={20} color={colors.background} />
                  <Text style={styles.analyzeButtonText}>Analyze Game</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        ) : (
          <>
            {/* Game Summary */}
            <View style={styles.summaryCard}>
              <Text style={styles.sectionLabel}>GAME SUMMARY</Text>
              <Text style={styles.summaryText}>{analysis.game_summary}</Text>
              
              <View style={styles.statsRow}>
                <View style={styles.statItem}>
                  <Text style={[styles.statValue, { color: StatusColors.blunder }]}>
                    {analysis.blunders}
                  </Text>
                  <Text style={styles.statLabel}>Blunders</Text>
                </View>
                <View style={styles.statItem}>
                  <Text style={[styles.statValue, { color: StatusColors.mistake }]}>
                    {analysis.mistakes}
                  </Text>
                  <Text style={styles.statLabel}>Mistakes</Text>
                </View>
                <View style={styles.statItem}>
                  <Text style={[styles.statValue, { color: StatusColors.excellent }]}>
                    {analysis.best_moves}
                  </Text>
                  <Text style={styles.statLabel}>Best Moves</Text>
                </View>
              </View>
            </View>

            {/* Focus This Week */}
            {analysis.focus_this_week && (
              <View style={styles.focusCard}>
                <View style={styles.focusHeader}>
                  <Ionicons name="flag" size={18} color={colors.accent} />
                  <Text style={styles.focusLabel}>FOCUS THIS WEEK</Text>
                </View>
                <Text style={styles.focusText}>{analysis.focus_this_week}</Text>
              </View>
            )}

            {/* Move List */}
            <View style={styles.movesSection}>
              <Text style={styles.sectionLabel}>MOVE ANALYSIS</Text>
              {moves.slice(0, 20).map((move, index) => {
                const isExpanded = expandedMoves[index];
                const hasDetails = move.lesson || move.thinking_pattern;
                const isMistake = ['blunder', 'mistake', 'inaccuracy'].includes(move.evaluation);
                
                return (
                  <TouchableOpacity 
                    key={index}
                    style={[
                      styles.moveItem,
                      currentMove === index && styles.moveItemActive
                    ]}
                    onPress={() => {
                      setCurrentMove(index);
                      if (hasDetails) toggleMoveExpanded(index);
                    }}
                    activeOpacity={0.7}
                  >
                    <View style={styles.moveHeader}>
                      <View style={styles.moveLeft}>
                        <Text style={styles.moveNumber}>{move.move_number}.</Text>
                        <Text style={styles.moveText}>{move.move}</Text>
                      </View>
                      <View style={[
                        styles.evalBadge,
                        { backgroundColor: `${getEvalColor(move.evaluation)}20` }
                      ]}>
                        <Text style={[styles.evalText, { color: getEvalColor(move.evaluation) }]}>
                          {move.evaluation}
                        </Text>
                      </View>
                    </View>
                    
                    {move.lesson && (
                      <Text style={styles.moveLesson}>{move.lesson}</Text>
                    )}
                    
                    {isExpanded && hasDetails && (
                      <View style={styles.moveDetails}>
                        {move.thinking_pattern && (
                          <Text style={styles.movePattern}>
                            Pattern: {move.thinking_pattern.replace(/_/g, ' ')}
                          </Text>
                        )}
                        {move.consider && (
                          <Text style={styles.moveConsider}>
                            Consider: {move.consider}
                          </Text>
                        )}
                      </View>
                    )}
                    
                    {/* Best Move Suggestion */}
                    {isMistake && analysis.best_move_suggestions?.find(s => s.move_number === move.move_number) && (
                      <View style={styles.bestMoveBox}>
                        <Ionicons name="checkmark-circle" size={14} color={StatusColors.improving} />
                        <Text style={styles.bestMoveText}>
                          Better: {analysis.best_move_suggestions.find(s => s.move_number === move.move_number).best_move}
                        </Text>
                      </View>
                    )}
                  </TouchableOpacity>
                );
              })}
              
              {moves.length > 20 && (
                <Text style={styles.moreMovesText}>
                  + {moves.length - 20} more moves
                </Text>
              )}
            </View>
          </>
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
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorText: {
    color: colors.textSecondary,
    fontSize: 16,
    marginBottom: 16,
  },
  backButton: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    backgroundColor: colors.card,
    borderRadius: 8,
  },
  backButtonText: {
    color: colors.text,
    fontWeight: '500',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backIcon: {
    padding: 4,
    marginRight: 12,
  },
  headerInfo: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  headerMeta: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  scrollView: {
    flex: 1,
  },
  boardContainer: {
    padding: 16,
  },
  boardPlaceholder: {
    width: width - 32,
    height: width - 32,
    backgroundColor: colors.card,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  boardPlaceholderText: {
    color: colors.textSecondary,
    marginTop: 12,
    fontSize: 14,
  },
  currentMoveInfo: {
    marginTop: 16,
    alignItems: 'center',
  },
  currentMoveNumber: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  currentMoveText: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    fontFamily: 'monospace',
  },
  moveNav: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 16,
    gap: 8,
  },
  navButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.card,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  moveCounter: {
    color: colors.textSecondary,
    fontSize: 14,
    marginHorizontal: 12,
    minWidth: 60,
    textAlign: 'center',
  },
  noAnalysis: {
    alignItems: 'center',
    padding: 40,
  },
  noAnalysisTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
    marginBottom: 8,
  },
  noAnalysisText: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 24,
  },
  analyzeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.text,
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 12,
    gap: 8,
  },
  analyzeButtonText: {
    color: colors.background,
    fontSize: 16,
    fontWeight: '600',
  },
  summaryCard: {
    margin: 16,
    marginTop: 0,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 20,
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
  summaryText: {
    fontSize: 15,
    color: colors.text,
    lineHeight: 24,
    marginBottom: 16,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  statItem: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: 28,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  focusCard: {
    margin: 16,
    marginTop: 0,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 20,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    borderLeftColor: colors.accent,
  },
  focusHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  focusLabel: {
    fontSize: 11,
    color: colors.accent,
    letterSpacing: 1,
    fontWeight: '600',
  },
  focusText: {
    fontSize: 15,
    color: colors.text,
    lineHeight: 22,
  },
  movesSection: {
    padding: 16,
    paddingTop: 0,
  },
  moveItem: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  moveItemActive: {
    borderColor: colors.accent,
  },
  moveHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  moveLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  moveNumber: {
    fontSize: 13,
    color: colors.textSecondary,
    fontFamily: 'monospace',
  },
  moveText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    fontFamily: 'monospace',
  },
  evalBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  evalText: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  moveLesson: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 8,
    lineHeight: 20,
  },
  moveDetails: {
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  movePattern: {
    fontSize: 12,
    color: StatusColors.warning,
    marginBottom: 4,
  },
  moveConsider: {
    fontSize: 12,
    color: StatusColors.good,
  },
  bestMoveBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 8,
    padding: 10,
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    borderRadius: 8,
  },
  bestMoveText: {
    fontSize: 13,
    color: StatusColors.improving,
    fontWeight: '500',
  },
  moreMovesText: {
    textAlign: 'center',
    color: colors.textSecondary,
    fontSize: 13,
    marginTop: 8,
  },
});
