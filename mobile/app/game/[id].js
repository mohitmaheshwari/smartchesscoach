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
import { ChessBoardViewer, MoveNavigation } from '../../src/components/ChessBoard';

const { width } = Dimensions.get('window');

export default function GameAnalysisScreen() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { colors } = useTheme();
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentMove, setCurrentMove] = useState(-1); // -1 = starting position
  const [expandedMoves, setExpandedMoves] = useState({});

  useEffect(() => {
    fetchData();
  }, [id]);

  const fetchData = async () => {
    try {
      const [gameData, analysisData] = await Promise.all([
        gamesAPI.getGame(id),
        analysisAPI.getAnalysis(id).catch(() => null)
      ]);
      setGame(gameData);
      // Only set analysis if it has actual data (not empty object)
      setAnalysis(analysisData && analysisData.game_id ? analysisData : null);
      console.log('Game loaded:', gameData?.game_id);
      console.log('Analysis loaded:', analysisData ? 'yes' : 'no');
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
      if (result && result.game_id) {
        setAnalysis(result);
        Alert.alert('Success', 'Game analyzed!');
      } else {
        throw new Error('Analysis failed');
      }
    } catch (error) {
      console.error('Analysis error:', error);
      Alert.alert('Error', error.message || 'Failed to analyze game');
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

  // Navigation handlers
  const goToFirst = () => setCurrentMove(-1);
  const goToPrevious = () => setCurrentMove(prev => Math.max(-1, prev - 1));
  const goToNext = () => setCurrentMove(prev => Math.min(moves.length - 1, prev + 1));
  const goToLast = () => setCurrentMove(moves.length - 1);

  const styles = createStyles(colors);
  const moves = analysis?.move_by_move || [];

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

  const currentMoveData = currentMove >= 0 && currentMove < moves.length ? moves[currentMove] : null;

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
            {game.platform} • {game.result} • You played {game.user_color}
          </Text>
        </View>
      </View>

      <ScrollView 
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
      >
        {/* Interactive Chessboard */}
        <View style={styles.boardContainer}>
          <ChessBoardViewer
            pgn={game.pgn}
            currentMoveIndex={currentMove}
            userColor={game.user_color}
          />
          
          {/* Move Navigation */}
          <MoveNavigation
            currentMove={currentMove + 1}
            totalMoves={moves.length || 1}
            onFirst={goToFirst}
            onPrevious={goToPrevious}
            onNext={goToNext}
            onLast={goToLast}
          />
        </View>

        {/* ALWAYS SHOW: Analyze button if no analysis */}
        {!analysis && (
          <View style={styles.noAnalysis}>
            <Ionicons name="analytics-outline" size={48} color={colors.textSecondary} />
            <Text style={styles.noAnalysisTitle}>Game not analyzed yet</Text>
            <Text style={styles.noAnalysisText}>
              Get AI coaching insights powered by Stockfish
            </Text>
            <TouchableOpacity 
              style={styles.analyzeButton}
              onPress={handleAnalyze}
              disabled={analyzing}
              testID="analyze-game-btn"
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
        )}

        {/* Show analysis if available */}
        {analysis && (
          <>
            {/* Current Move Analysis - only show if analysis exists and has move data */}
            {currentMoveData && (
              <View style={styles.currentMoveCard}>
                <View style={styles.currentMoveHeader}>
                  <View style={styles.currentMoveLeft}>
                    <Text style={styles.currentMoveNumber}>
                      {currentMoveData.move_number}.
                    </Text>
                    <Text style={styles.currentMoveText}>
                      {currentMoveData.move}
                    </Text>
                  </View>
                  <View style={[
                    styles.evalBadgeLarge,
                    { backgroundColor: `${getEvalColor(currentMoveData.evaluation)}20` }
                  ]}>
                    <Text style={[styles.evalTextLarge, { color: getEvalColor(currentMoveData.evaluation) }]}>
                      {currentMoveData.evaluation || 'neutral'}
                    </Text>
                  </View>
                </View>
                
                {currentMoveData.lesson && (
                  <Text style={styles.currentMoveLesson}>{currentMoveData.lesson}</Text>
                )}
                
                {currentMoveData.thinking_pattern && currentMoveData.thinking_pattern !== 'solid_thinking' && (
                  <View style={styles.patternBox}>
                    <Ionicons name="bulb-outline" size={16} color={StatusColors.attention} />
                    <Text style={styles.patternText}>
                      {currentMoveData.thinking_pattern.replace(/_/g, ' ')}
                    </Text>
                  </View>
                )}
                
                {currentMoveData.consider && (
                  <View style={styles.considerBox}>
                    <Ionicons name="arrow-forward-circle-outline" size={16} color={StatusColors.good} />
                    <Text style={styles.considerText}>{currentMoveData.consider}</Text>
                  </View>
                )}
              </View>
            )}

            {/* Stockfish Accuracy - NEW */}
            {analysis.stockfish_analysis?.accuracy && (
              <View style={styles.accuracyCard}>
                <View style={styles.accuracyHeader}>
                  <View style={styles.accuracyCircle}>
                    <Text style={styles.accuracyValue}>{analysis.stockfish_analysis.accuracy}%</Text>
                  </View>
                  <View style={styles.accuracyInfo}>
                    <Text style={styles.accuracyTitle}>Accuracy</Text>
                    <Text style={styles.accuracySubtitle}>Powered by Stockfish 15</Text>
                  </View>
                </View>
                {analysis.stockfish_analysis.avg_cp_loss !== undefined && (
                  <Text style={styles.avgCpLoss}>
                    Avg. loss: {analysis.stockfish_analysis.avg_cp_loss} centipawns
                  </Text>
                )}
              </View>
            )}

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
                  <Text style={styles.statLabel}>Best</Text>
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
              <Text style={styles.sectionLabel}>ALL MOVES</Text>
              <View style={styles.movesList}>
                {moves.map((move, index) => {
                  const isActive = currentMove === index;
                  const isMistake = ['blunder', 'mistake', 'inaccuracy'].includes(move.evaluation);
                  
                  return (
                    <TouchableOpacity 
                      key={index}
                      style={[
                        styles.moveChip,
                        isActive && styles.moveChipActive,
                        isMistake && styles.moveChipMistake,
                        { borderColor: isActive ? colors.accent : colors.border }
                      ]}
                      onPress={() => setCurrentMove(index)}
                    >
                      <Text style={[
                        styles.moveChipNumber,
                        { color: colors.textSecondary }
                      ]}>
                        {move.move_number}.
                      </Text>
                      <Text style={[
                        styles.moveChipText,
                        { color: isMistake ? getEvalColor(move.evaluation) : colors.text }
                      ]}>
                        {move.move}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
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
    alignItems: 'center',
  },
  currentMoveCard: {
    margin: 16,
    marginTop: 0,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  currentMoveHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  currentMoveLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  currentMoveNumber: {
    fontSize: 16,
    color: colors.textSecondary,
    fontFamily: 'monospace',
  },
  currentMoveText: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    fontFamily: 'monospace',
  },
  evalBadgeLarge: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 8,
  },
  evalTextLarge: {
    fontSize: 13,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  currentMoveLesson: {
    fontSize: 15,
    color: colors.text,
    lineHeight: 22,
    marginBottom: 12,
  },
  patternBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 12,
    backgroundColor: `${StatusColors.warning}15`,
    borderRadius: 8,
    marginBottom: 8,
  },
  patternText: {
    fontSize: 13,
    color: StatusColors.warning,
    flex: 1,
    textTransform: 'capitalize',
  },
  considerBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    padding: 12,
    backgroundColor: `${StatusColors.good}15`,
    borderRadius: 8,
    marginBottom: 8,
  },
  considerText: {
    fontSize: 13,
    color: StatusColors.good,
    flex: 1,
  },
  bestMoveBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    padding: 14,
    backgroundColor: `${StatusColors.improving}15`,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: `${StatusColors.improving}30`,
  },
  bestMoveContent: {
    flex: 1,
  },
  bestMoveLabel: {
    fontSize: 11,
    color: StatusColors.improving,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  bestMoveText: {
    fontSize: 18,
    fontWeight: '700',
    color: StatusColors.improving,
    fontFamily: 'monospace',
  },
  bestMoveReason: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 6,
    lineHeight: 20,
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
  accuracyCard: {
    margin: 16,
    marginTop: 0,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#3b82f630',
    borderLeftWidth: 4,
    borderLeftColor: '#3b82f6',
  },
  accuracyHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  accuracyCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#3b82f620',
    justifyContent: 'center',
    alignItems: 'center',
  },
  accuracyValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#3b82f6',
  },
  accuracyInfo: {
    flex: 1,
  },
  accuracyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  accuracySubtitle: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  avgCpLoss: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 12,
    textAlign: 'right',
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
  movesList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  moveChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: colors.card,
    borderWidth: 1,
    gap: 4,
  },
  moveChipActive: {
    backgroundColor: colors.muted,
  },
  moveChipMistake: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
  },
  moveChipNumber: {
    fontSize: 11,
    fontFamily: 'monospace',
  },
  moveChipText: {
    fontSize: 13,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
});
