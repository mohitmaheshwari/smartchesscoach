import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Dimensions,
  FlatList,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Chess } from 'chess.js';
import { useTheme } from '../../src/context/ThemeContext';
import { gamesAPI, analysisAPI } from '../../src/services/api';
import { ChessBoardViewer, MoveNavigation } from '../../src/components/ChessBoard';
import { StatusColors } from '../../src/constants/config';

const { width, height } = Dimensions.get('window');
// Board takes ~40% of screen height for optimal thumb reach
const BOARD_SIZE = Math.min(width - 48, height * 0.38);

export default function GameDetailScreen() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { colors } = useTheme();
  const moveListRef = useRef(null);
  
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentMove, setCurrentMove] = useState(-1);

  // Parse PGN to get all moves
  const parsedMoves = useMemo(() => {
    if (!game?.pgn) return [];
    try {
      const chess = new Chess();
      chess.loadPgn(game.pgn);
      return chess.history({ verbose: true });
    } catch (e) {
      return [];
    }
  }, [game?.pgn]);

  const totalMoves = parsedMoves.length;
  const moveAnalysis = analysis?.commentary || [];

  // Combine moves with analysis data
  const movesWithAnalysis = useMemo(() => {
    return parsedMoves.map((move, idx) => {
      const moveNum = Math.floor(idx / 2) + 1;
      const isWhite = idx % 2 === 0;
      const analysisItem = moveAnalysis.find(
        a => a.move_number === moveNum && a.move === move.san
      );
      return {
        index: idx,
        moveNumber: moveNum,
        isWhite,
        san: move.san,
        from: move.from,
        to: move.to,
        analysis: analysisItem,
        evaluation: analysisItem?.evaluation || 'neutral',
        cpLoss: analysisItem?.centipawn_loss || 0,
      };
    });
  }, [parsedMoves, moveAnalysis]);

  const currentMoveData = currentMove >= 0 ? movesWithAnalysis[currentMove] : null;

  // Load game data
  useEffect(() => {
    loadGame();
  }, [id]);

  // Auto-scroll move list to current move
  useEffect(() => {
    if (moveListRef.current && currentMove >= 0 && movesWithAnalysis.length > 0) {
      try {
        moveListRef.current.scrollToIndex({ 
          index: currentMove, 
          animated: true,
          viewPosition: 0.5 
        });
      } catch (e) {
        // Fallback for out of range
      }
    }
  }, [currentMove]);

  const loadGame = async () => {
    try {
      const gameData = await gamesAPI.getGame(id);
      setGame(gameData);
      try {
        const analysisData = await analysisAPI.getAnalysis(id);
        if (analysisData?.game_id) setAnalysis(analysisData);
      } catch (e) {
        setAnalysis(null);
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to load game');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const result = await analysisAPI.analyzeGame(id);
      if (result?.game_id) {
        setAnalysis(result);
        Alert.alert('Analysis Complete', 'Your game has been analyzed!');
      }
    } catch (error) {
      Alert.alert('Error', error.message || 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  // Navigation handlers
  const goToMove = useCallback((index) => {
    setCurrentMove(Math.max(-1, Math.min(index, totalMoves - 1)));
  }, [totalMoves]);

  const handleSwipeLeft = useCallback(() => {
    goToMove(currentMove + 1);
  }, [currentMove, goToMove]);

  const handleSwipeRight = useCallback(() => {
    goToMove(currentMove - 1);
  }, [currentMove, goToMove]);

  const styles = createStyles(colors);

  // Loading state
  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={styles.loadingText}>Loading game...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Error state
  if (!game) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={48} color={colors.textSecondary} />
          <Text style={styles.errorText}>Game not found</Text>
          <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
            <Text style={styles.backBtnText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header - Compact */}
      <View style={styles.header}>
        <TouchableOpacity 
          onPress={() => router.back()} 
          style={styles.headerBack}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        >
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        
        <View style={styles.headerInfo}>
          <Text style={styles.headerPlayers} numberOfLines={1}>
            {game.white_player} vs {game.black_player}
          </Text>
          <Text style={styles.headerMeta}>
            {game.result} • You played {game.user_color}
          </Text>
        </View>

        {analysis?.stockfish_analysis?.accuracy && (
          <View style={styles.accuracyBadge}>
            <Text style={styles.accuracyValue}>{Math.round(analysis.stockfish_analysis.accuracy)}%</Text>
            <Text style={styles.accuracyLabel}>ACC</Text>
          </View>
        )}
      </View>

      {/* Main Content */}
      <ScrollView 
        style={styles.mainScroll}
        contentContainerStyle={styles.mainContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Board Section */}
        <View style={styles.boardSection}>
          <ChessBoardViewer
            pgn={game.pgn}
            currentMoveIndex={currentMove}
            userColor={game.user_color}
            boardSize={BOARD_SIZE}
            onSwipeLeft={handleSwipeLeft}
            onSwipeRight={handleSwipeRight}
          />
          
          {/* Swipe hint */}
          <Text style={styles.swipeHint}>
            <Ionicons name="swap-horizontal" size={12} color={colors.textSecondary} /> Swipe board to navigate
          </Text>
        </View>

        {/* Move Navigation */}
        <MoveNavigation
          currentMove={currentMove}
          totalMoves={totalMoves}
          onFirst={() => goToMove(-1)}
          onPrevious={() => goToMove(currentMove - 1)}
          onNext={() => goToMove(currentMove + 1)}
          onLast={() => goToMove(totalMoves - 1)}
        />

        {/* Move Strip - Horizontal Scrollable */}
        <View style={styles.moveStripWrapper}>
          <FlatList
            ref={moveListRef}
            data={movesWithAnalysis}
            horizontal
            showsHorizontalScrollIndicator={false}
            keyExtractor={(item) => `move-${item.index}`}
            contentContainerStyle={styles.moveStripContent}
            getItemLayout={(_, index) => ({ length: 56, offset: 56 * index, index })}
            onScrollToIndexFailed={() => {}}
            ListHeaderComponent={
              <TouchableOpacity
                style={[
                  styles.moveChip, 
                  styles.startChip,
                  currentMove === -1 && styles.moveChipActive
                ]}
                onPress={() => goToMove(-1)}
              >
                <Ionicons 
                  name="flag" 
                  size={16} 
                  color={currentMove === -1 ? colors.accent : colors.textSecondary} 
                />
              </TouchableOpacity>
            }
            renderItem={({ item }) => {
              const isSelected = currentMove === item.index;
              const evalColor = getEvalColor(item.evaluation);
              const hasBadMove = ['blunder', 'mistake', 'inaccuracy'].includes(item.evaluation);
              
              return (
                <TouchableOpacity
                  style={[
                    styles.moveChip,
                    { backgroundColor: hasBadMove ? evalColor + '18' : colors.card },
                    isSelected && styles.moveChipActive,
                  ]}
                  onPress={() => goToMove(item.index)}
                  activeOpacity={0.7}
                >
                  <Text style={[styles.moveChipNum, { color: colors.textSecondary }]}>
                    {item.isWhite ? item.moveNumber + '.' : ''}
                  </Text>
                  <Text style={[
                    styles.moveChipSan,
                    { color: hasBadMove ? evalColor : colors.text }
                  ]}>
                    {item.san}
                  </Text>
                  {hasBadMove && (
                    <View style={[styles.moveChipDot, { backgroundColor: evalColor }]} />
                  )}
                </TouchableOpacity>
              );
            }}
          />
        </View>

        {/* Analysis Section */}
        <View style={styles.analysisSection}>
          {/* Not analyzed yet - Show CTA */}
          {!analysis && (
            <View style={styles.analyzeCard}>
              <View style={styles.analyzeIconWrap}>
                <Ionicons name="analytics" size={32} color={colors.accent} />
              </View>
              <Text style={styles.analyzeTitle}>Get AI Analysis</Text>
              <Text style={styles.analyzeDesc}>
                Stockfish engine analysis with personalized coaching feedback
              </Text>
              <TouchableOpacity 
                style={[styles.analyzeBtn, analyzing && styles.analyzeBtnDisabled]}
                onPress={handleAnalyze}
                disabled={analyzing}
                activeOpacity={0.8}
              >
                {analyzing ? (
                  <ActivityIndicator size="small" color="#000" />
                ) : (
                  <Ionicons name="flash" size={18} color="#000" />
                )}
                <Text style={styles.analyzeBtnText}>
                  {analyzing ? 'Analyzing...' : 'Analyze Game'}
                </Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Analysis available */}
          {analysis && (
            <>
              {/* Current Move Detail */}
              {currentMove === -1 ? (
                <View style={styles.startingPosCard}>
                  <Ionicons name="flag-outline" size={28} color={colors.accent} />
                  <Text style={styles.startingPosTitle}>Starting Position</Text>
                  <Text style={styles.startingPosHint}>
                    Use the move strip or swipe the board to navigate through the game
                  </Text>
                </View>
              ) : currentMoveData?.analysis ? (
                <View style={[
                  styles.moveDetailCard,
                  { borderLeftColor: getEvalColor(currentMoveData.evaluation) }
                ]}>
                  {/* Move header */}
                  <View style={styles.moveDetailHeader}>
                    <View style={styles.moveDetailLeft}>
                      <Text style={styles.moveDetailSan}>
                        {currentMoveData.moveNumber}.{!currentMoveData.isWhite ? '..' : ''} {currentMoveData.san}
                      </Text>
                      <View style={[
                        styles.evalPill,
                        { backgroundColor: getEvalColor(currentMoveData.evaluation) + '20' }
                      ]}>
                        <Text style={[
                          styles.evalPillText,
                          { color: getEvalColor(currentMoveData.evaluation) }
                        ]}>
                          {currentMoveData.evaluation}
                        </Text>
                      </View>
                    </View>
                    {currentMoveData.cpLoss > 0 && (
                      <Text style={styles.cpLossText}>
                        -{currentMoveData.cpLoss} cp
                      </Text>
                    )}
                  </View>

                  {/* Lesson / Commentary */}
                  {currentMoveData.analysis.lesson && (
                    <Text style={styles.lessonText}>
                      {currentMoveData.analysis.lesson}
                    </Text>
                  )}

                  {/* Thinking pattern */}
                  {currentMoveData.analysis.thinking_pattern && 
                   currentMoveData.analysis.thinking_pattern !== 'solid_thinking' && (
                    <View style={styles.patternRow}>
                      <Ionicons name="bulb-outline" size={14} color="#f59e0b" />
                      <Text style={styles.patternText}>
                        {formatPattern(currentMoveData.analysis.thinking_pattern)}
                      </Text>
                    </View>
                  )}

                  {/* Better move suggestion */}
                  {currentMoveData.analysis.best_move && 
                   currentMoveData.analysis.best_move !== currentMoveData.san && (
                    <View style={styles.bestMoveRow}>
                      <Ionicons name="checkmark-circle" size={16} color={StatusColors.excellent} />
                      <Text style={styles.bestMoveLabel}>Better: </Text>
                      <Text style={styles.bestMoveSan}>{currentMoveData.analysis.best_move}</Text>
                    </View>
                  )}

                  {/* Consider alternative */}
                  {currentMoveData.analysis.consider && (
                    <View style={styles.considerRow}>
                      <Ionicons name="arrow-forward-circle-outline" size={14} color={StatusColors.good} />
                      <Text style={styles.considerText}>{currentMoveData.analysis.consider}</Text>
                    </View>
                  )}
                </View>
              ) : (
                <View style={styles.noFeedbackCard}>
                  <Text style={styles.noFeedbackMove}>
                    {currentMoveData?.moveNumber}.{!currentMoveData?.isWhite ? '..' : ''} {currentMoveData?.san}
                  </Text>
                  <Text style={styles.noFeedbackText}>
                    No specific issues with this move
                  </Text>
                </View>
              )}

              {/* Game Stats */}
              <View style={styles.statsGrid}>
                <StatBox 
                  value={analysis.blunders || 0} 
                  label="Blunders" 
                  color={StatusColors.blunder}
                />
                <StatBox 
                  value={analysis.mistakes || 0} 
                  label="Mistakes" 
                  color={StatusColors.mistake}
                />
                <StatBox 
                  value={analysis.inaccuracies || 0} 
                  label="Inaccuracies" 
                  color={StatusColors.inaccuracy}
                />
                <StatBox 
                  value={analysis.best_moves || 0} 
                  label="Best" 
                  color={StatusColors.excellent}
                />
              </View>

              {/* Coach Summary */}
              {(analysis.summary_p1 || analysis.overall_summary) && (
                <View style={styles.summaryCard}>
                  <View style={styles.summaryHeader}>
                    <Ionicons name="chatbubble-ellipses-outline" size={18} color={colors.accent} />
                    <Text style={styles.summaryTitle}>Coach's Summary</Text>
                  </View>
                  <Text style={styles.summaryText}>
                    {analysis.summary_p1 || analysis.overall_summary}
                  </Text>
                  {analysis.summary_p2 && (
                    <Text style={[styles.summaryText, { marginTop: 8 }]}>
                      {analysis.summary_p2}
                    </Text>
                  )}
                </View>
              )}

              {/* Focus This Week */}
              {analysis.focus_this_week && (
                <View style={styles.focusCard}>
                  <Ionicons name="flag" size={18} color="#f59e0b" />
                  <View style={styles.focusContent}>
                    <Text style={styles.focusLabel}>Focus This Week</Text>
                    <Text style={styles.focusText}>{analysis.focus_this_week}</Text>
                  </View>
                </View>
              )}
            </>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

// Stat Box Component
const StatBox = ({ value, label, color }) => {
  const { colors } = useTheme();
  return (
    <View style={[statStyles.box, { backgroundColor: color + '12' }]}>
      <Text style={[statStyles.value, { color }]}>{value}</Text>
      <Text style={[statStyles.label, { color: colors.textSecondary }]}>{label}</Text>
    </View>
  );
};

const statStyles = StyleSheet.create({
  box: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    borderRadius: 8,
  },
  value: {
    fontSize: 20,
    fontWeight: '700',
  },
  label: {
    fontSize: 10,
    fontWeight: '500',
    textTransform: 'uppercase',
    marginTop: 2,
  },
});

// Helper functions
const getEvalColor = (evaluation) => {
  const colorMap = {
    blunder: StatusColors.blunder,
    mistake: StatusColors.mistake,
    inaccuracy: StatusColors.inaccuracy,
    good: StatusColors.good,
    excellent: StatusColors.excellent,
    best: StatusColors.excellent,
  };
  return colorMap[evaluation] || '#71717a';
};

const formatPattern = (pattern) => {
  return pattern.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

// Styles
const createStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
    padding: 24,
  },
  loadingText: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  errorText: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: 8,
  },
  backBtn: {
    marginTop: 16,
    paddingVertical: 10,
    paddingHorizontal: 20,
    backgroundColor: colors.card,
    borderRadius: 8,
  },
  backBtnText: {
    color: colors.text,
    fontWeight: '600',
  },

  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: 8,
  },
  headerBack: {
    padding: 4,
  },
  headerInfo: {
    flex: 1,
  },
  headerPlayers: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
  },
  headerMeta: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 1,
  },
  accuracyBadge: {
    alignItems: 'center',
    backgroundColor: '#3b82f615',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  accuracyValue: {
    fontSize: 14,
    fontWeight: '700',
    color: '#3b82f6',
  },
  accuracyLabel: {
    fontSize: 8,
    fontWeight: '600',
    color: '#3b82f6',
    opacity: 0.7,
  },

  // Main scroll
  mainScroll: {
    flex: 1,
  },
  mainContent: {
    paddingBottom: 32,
  },

  // Board section
  boardSection: {
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 12,
  },
  swipeHint: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 8,
  },

  // Move strip
  moveStripWrapper: {
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.border,
    paddingVertical: 8,
  },
  moveStripContent: {
    paddingHorizontal: 12,
    gap: 6,
  },
  moveChip: {
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 6,
    alignItems: 'center',
    minWidth: 50,
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  moveChipActive: {
    borderColor: colors.accent,
  },
  startChip: {
    backgroundColor: colors.card,
    paddingHorizontal: 12,
  },
  moveChipNum: {
    fontSize: 9,
    fontWeight: '500',
  },
  moveChipSan: {
    fontSize: 14,
    fontWeight: '700',
  },
  moveChipDot: {
    position: 'absolute',
    top: 4,
    right: 4,
    width: 6,
    height: 6,
    borderRadius: 3,
  },

  // Analysis section
  analysisSection: {
    padding: 12,
    gap: 12,
  },

  // Analyze CTA
  analyzeCard: {
    alignItems: 'center',
    padding: 24,
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    gap: 10,
  },
  analyzeIconWrap: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: colors.accent + '15',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 4,
  },
  analyzeTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
  },
  analyzeDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 18,
    marginBottom: 4,
  },
  analyzeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f59e0b',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 10,
    gap: 8,
  },
  analyzeBtnDisabled: {
    opacity: 0.7,
  },
  analyzeBtnText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#000',
  },

  // Starting position
  startingPosCard: {
    alignItems: 'center',
    padding: 20,
    backgroundColor: colors.card,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    gap: 6,
  },
  startingPosTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  startingPosHint: {
    fontSize: 12,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 18,
  },

  // Move detail card
  moveDetailCard: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
  },
  moveDetailHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  moveDetailLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  moveDetailSan: {
    fontSize: 17,
    fontWeight: '700',
    color: colors.text,
  },
  evalPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  evalPillText: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  cpLossText: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  lessonText: {
    fontSize: 14,
    color: colors.text,
    lineHeight: 21,
  },
  patternRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  patternText: {
    fontSize: 13,
    color: '#f59e0b',
    fontWeight: '500',
  },
  bestMoveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  bestMoveLabel: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  bestMoveSan: {
    fontSize: 14,
    fontWeight: '700',
    color: StatusColors.excellent,
  },
  considerRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
    marginTop: 8,
  },
  considerText: {
    fontSize: 13,
    color: StatusColors.good,
    flex: 1,
    lineHeight: 18,
  },

  // No feedback
  noFeedbackCard: {
    alignItems: 'center',
    padding: 16,
    backgroundColor: colors.card,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  noFeedbackMove: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  noFeedbackText: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
  },

  // Stats grid
  statsGrid: {
    flexDirection: 'row',
    gap: 8,
  },

  // Summary card
  summaryCard: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  summaryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  summaryTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
  },
  summaryText: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 20,
  },

  // Focus card
  focusCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    backgroundColor: '#f59e0b10',
    borderRadius: 10,
    padding: 14,
    borderWidth: 1,
    borderColor: '#f59e0b25',
  },
  focusContent: {
    flex: 1,
  },
  focusLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#f59e0b',
    textTransform: 'uppercase',
    marginBottom: 3,
  },
  focusText: {
    fontSize: 13,
    color: colors.text,
    lineHeight: 18,
  },
});
