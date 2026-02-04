import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Dimensions,
  FlatList
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Chess } from 'chess.js';
import { useTheme } from '../../src/context/ThemeContext';
import { gamesAPI, analysisAPI } from '../../src/services/api';
import { ChessBoardViewer } from '../../src/components/ChessBoard';
import { StatusColors } from '../../src/constants/config';

const { width, height } = Dimensions.get('window');
const BOARD_SIZE = Math.min(width - 32, height * 0.38); // Smaller board

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

  // Parse PGN
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

  // Create combined move data with analysis
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
      };
    });
  }, [parsedMoves, moveAnalysis]);

  const currentMoveData = currentMove >= 0 ? movesWithAnalysis[currentMove] : null;

  useEffect(() => {
    loadGame();
  }, [id]);

  // Scroll to current move in the list
  useEffect(() => {
    if (moveListRef.current && currentMove >= 0) {
      moveListRef.current.scrollToIndex({ 
        index: currentMove, 
        animated: true,
        viewPosition: 0.5 
      });
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
        Alert.alert('Success', 'Game analyzed!');
      }
    } catch (error) {
      Alert.alert('Error', error.message || 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const styles = createStyles(colors, BOARD_SIZE);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  if (!game) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <Text style={{ color: colors.textSecondary }}>Game not found</Text>
          <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
            <Text style={{ color: colors.text }}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Compact Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle} numberOfLines={1}>
            {game.white_player} vs {game.black_player}
          </Text>
          <Text style={styles.headerSub}>{game.result} • {game.user_color}</Text>
        </View>
        {analysis?.stockfish_analysis?.accuracy && (
          <View style={styles.accuracyPill}>
            <Text style={styles.accuracyNum}>{analysis.stockfish_analysis.accuracy}%</Text>
          </View>
        )}
      </View>

      {/* Board Section - Fixed */}
      <View style={styles.boardWrapper}>
        <ChessBoardViewer
          pgn={game.pgn}
          currentMoveIndex={currentMove}
          userColor={game.user_color}
        />
      </View>

      {/* Move Strip - Horizontal Scrollable */}
      <View style={styles.moveStripContainer}>
        <TouchableOpacity 
          style={styles.navArrow} 
          onPress={() => setCurrentMove(prev => Math.max(-1, prev - 1))}
        >
          <Ionicons name="chevron-back" size={20} color={currentMove <= -1 ? colors.border : colors.text} />
        </TouchableOpacity>
        
        <FlatList
          ref={moveListRef}
          data={movesWithAnalysis}
          horizontal
          showsHorizontalScrollIndicator={false}
          keyExtractor={(item) => `move-${item.index}`}
          contentContainerStyle={styles.moveStripContent}
          getItemLayout={(data, index) => ({ length: 52, offset: 52 * index, index })}
          onScrollToIndexFailed={() => {}}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[
                styles.moveChip,
                { backgroundColor: getEvalBg(item.evaluation, colors) },
                currentMove === item.index && styles.moveChipActive
              ]}
              onPress={() => setCurrentMove(item.index)}
            >
              <Text style={[
                styles.moveChipNum,
                { color: currentMove === item.index ? colors.text : colors.textSecondary }
              ]}>
                {item.moveNumber}{item.isWhite ? '.' : '...'}
              </Text>
              <Text style={[
                styles.moveChipSan,
                { color: getEvalColor(item.evaluation) }
              ]}>
                {item.san}
              </Text>
            </TouchableOpacity>
          )}
          ListHeaderComponent={
            <TouchableOpacity
              style={[styles.moveChip, styles.startChip, currentMove === -1 && styles.moveChipActive]}
              onPress={() => setCurrentMove(-1)}
            >
              <Ionicons name="flag" size={14} color={currentMove === -1 ? colors.accent : colors.textSecondary} />
            </TouchableOpacity>
          }
        />
        
        <TouchableOpacity 
          style={styles.navArrow}
          onPress={() => setCurrentMove(prev => Math.min(totalMoves - 1, prev + 1))}
        >
          <Ionicons name="chevron-forward" size={20} color={currentMove >= totalMoves - 1 ? colors.border : colors.text} />
        </TouchableOpacity>
      </View>

      {/* Analysis Content - Scrollable */}
      <ScrollView style={styles.analysisScroll} contentContainerStyle={styles.analysisContent}>
        {/* No Analysis Yet */}
        {!analysis && (
          <View style={styles.analyzeCard}>
            <Ionicons name="analytics" size={28} color={colors.accent} />
            <Text style={styles.analyzeTitle}>Get AI Analysis</Text>
            <TouchableOpacity 
              style={styles.analyzeBtn}
              onPress={handleAnalyze}
              disabled={analyzing}
            >
              {analyzing ? (
                <ActivityIndicator size="small" color="#000" />
              ) : (
                <Ionicons name="flash" size={16} color="#000" />
              )}
              <Text style={styles.analyzeBtnText}>{analyzing ? 'Analyzing...' : 'Analyze'}</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Current Move Analysis */}
        {analysis && currentMoveData?.analysis && (
          <View style={[styles.moveDetailCard, { borderLeftColor: getEvalColor(currentMoveData.evaluation) }]}>
            <View style={styles.moveDetailHeader}>
              <Text style={styles.moveDetailNum}>
                {currentMoveData.moveNumber}.{!currentMoveData.isWhite && '..'} {currentMoveData.san}
              </Text>
              <View style={[styles.evalBadge, { backgroundColor: getEvalColor(currentMoveData.evaluation) + '20' }]}>
                <Text style={[styles.evalBadgeText, { color: getEvalColor(currentMoveData.evaluation) }]}>
                  {currentMoveData.evaluation}
                </Text>
              </View>
            </View>
            
            {currentMoveData.analysis.lesson && (
              <Text style={styles.lessonText}>{currentMoveData.analysis.lesson}</Text>
            )}
            
            {currentMoveData.analysis.thinking_pattern && currentMoveData.analysis.thinking_pattern !== 'solid_thinking' && (
              <View style={styles.infoRow}>
                <Ionicons name="bulb" size={14} color="#f59e0b" />
                <Text style={styles.patternText}>{currentMoveData.analysis.thinking_pattern.replace(/_/g, ' ')}</Text>
              </View>
            )}
            
            {currentMoveData.analysis.consider && (
              <View style={styles.infoRow}>
                <Ionicons name="arrow-forward-circle" size={14} color={StatusColors.good} />
                <Text style={styles.considerText}>{currentMoveData.analysis.consider}</Text>
              </View>
            )}
            
            {currentMoveData.analysis.best_move && currentMoveData.analysis.best_move !== currentMoveData.san && (
              <View style={styles.bestMoveBox}>
                <Ionicons name="checkmark-circle" size={16} color={StatusColors.excellent} />
                <Text style={styles.bestMoveLabel}>Better move: </Text>
                <Text style={styles.bestMoveSan}>{currentMoveData.analysis.best_move}</Text>
              </View>
            )}
          </View>
        )}

        {/* Starting position message */}
        {analysis && currentMove === -1 && (
          <View style={styles.startingCard}>
            <Ionicons name="flag" size={24} color={colors.accent} />
            <Text style={styles.startingText}>Starting position</Text>
            <Text style={styles.startingHint}>Tap a move above to see analysis</Text>
          </View>
        )}

        {/* No analysis for this move */}
        {analysis && currentMove >= 0 && !currentMoveData?.analysis && (
          <View style={styles.noAnalysisCard}>
            <Text style={styles.noAnalysisMove}>
              {currentMoveData?.moveNumber}.{!currentMoveData?.isWhite && '..'} {currentMoveData?.san}
            </Text>
            <Text style={styles.noAnalysisText}>No specific feedback for this move</Text>
          </View>
        )}

        {/* Game Summary (below current move) */}
        {analysis && (
          <View style={styles.summarySection}>
            {/* Stats Row */}
            <View style={styles.statsRow}>
              <View style={[styles.statBox, { backgroundColor: StatusColors.blunder + '15' }]}>
                <Text style={[styles.statNum, { color: StatusColors.blunder }]}>{analysis.blunders || 0}</Text>
                <Text style={styles.statLabel}>Blunders</Text>
              </View>
              <View style={[styles.statBox, { backgroundColor: StatusColors.mistake + '15' }]}>
                <Text style={[styles.statNum, { color: StatusColors.mistake }]}>{analysis.mistakes || 0}</Text>
                <Text style={styles.statLabel}>Mistakes</Text>
              </View>
              <View style={[styles.statBox, { backgroundColor: StatusColors.inaccuracy + '15' }]}>
                <Text style={[styles.statNum, { color: StatusColors.inaccuracy }]}>{analysis.inaccuracies || 0}</Text>
                <Text style={styles.statLabel}>Inaccuracies</Text>
              </View>
              <View style={[styles.statBox, { backgroundColor: StatusColors.excellent + '15' }]}>
                <Text style={[styles.statNum, { color: StatusColors.excellent }]}>{analysis.best_moves || 0}</Text>
                <Text style={styles.statLabel}>Best</Text>
              </View>
            </View>

            {/* Coach Summary */}
            {(analysis.summary_p1 || analysis.overall_summary) && (
              <View style={styles.summaryCard}>
                <Text style={styles.summaryTitle}>Coach's Summary</Text>
                <Text style={styles.summaryText}>{analysis.summary_p1 || analysis.overall_summary}</Text>
                {analysis.summary_p2 && (
                  <Text style={[styles.summaryText, { marginTop: 10 }]}>{analysis.summary_p2}</Text>
                )}
              </View>
            )}

            {/* Focus */}
            {analysis.focus_this_week && (
              <View style={styles.focusCard}>
                <Ionicons name="flag" size={16} color="#f59e0b" />
                <View style={{ flex: 1 }}>
                  <Text style={styles.focusLabel}>Focus This Week</Text>
                  <Text style={styles.focusText}>{analysis.focus_this_week}</Text>
                </View>
              </View>
            )}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const getEvalColor = (evaluation) => {
  const colors = {
    blunder: StatusColors.blunder,
    mistake: StatusColors.mistake,
    inaccuracy: StatusColors.inaccuracy,
    good: StatusColors.good,
    excellent: StatusColors.excellent,
    best: StatusColors.excellent,
  };
  return colors[evaluation] || '#71717a';
};

const getEvalBg = (evaluation, colors) => {
  if (['blunder', 'mistake', 'inaccuracy'].includes(evaluation)) {
    return getEvalColor(evaluation) + '15';
  }
  return colors.card;
};

const createStyles = (colors, boardSize) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 16 },
  backButton: { padding: 12, backgroundColor: colors.card, borderRadius: 8 },
  
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerCenter: { flex: 1 },
  headerTitle: { fontSize: 14, fontWeight: '600', color: colors.text },
  headerSub: { fontSize: 11, color: colors.textSecondary },
  accuracyPill: { backgroundColor: '#3b82f620', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  accuracyNum: { fontSize: 13, fontWeight: '700', color: '#3b82f6' },

  boardWrapper: {
    alignItems: 'center',
    paddingVertical: 8,
  },

  moveStripContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  navArrow: {
    padding: 8,
  },
  moveStripContent: {
    paddingHorizontal: 4,
    gap: 4,
  },
  moveChip: {
    paddingHorizontal: 8,
    paddingVertical: 6,
    borderRadius: 6,
    alignItems: 'center',
    minWidth: 48,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  moveChipActive: {
    borderColor: colors.accent,
  },
  startChip: {
    backgroundColor: colors.card,
    paddingHorizontal: 10,
  },
  moveChipNum: { fontSize: 9, fontWeight: '500' },
  moveChipSan: { fontSize: 13, fontWeight: '700' },

  analysisScroll: { flex: 1 },
  analysisContent: { padding: 12, gap: 12, paddingBottom: 30 },

  analyzeCard: {
    alignItems: 'center',
    padding: 20,
    backgroundColor: colors.card,
    borderRadius: 12,
    gap: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  analyzeTitle: { fontSize: 16, fontWeight: '600', color: colors.text },
  analyzeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f59e0b',
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 8,
    gap: 6,
  },
  analyzeBtnText: { fontSize: 14, fontWeight: '700', color: '#000' },

  moveDetailCard: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 12,
    borderLeftWidth: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  moveDetailHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  moveDetailNum: { fontSize: 16, fontWeight: '700', color: colors.text },
  evalBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  evalBadgeText: { fontSize: 11, fontWeight: '600', textTransform: 'capitalize' },
  
  lessonText: { fontSize: 14, color: colors.text, lineHeight: 20, marginBottom: 8 },
  
  infoRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 6, marginTop: 6 },
  patternText: { fontSize: 13, color: '#f59e0b', flex: 1, textTransform: 'capitalize' },
  considerText: { fontSize: 13, color: StatusColors.good, flex: 1 },
  
  bestMoveBox: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 6,
  },
  bestMoveLabel: { fontSize: 13, color: colors.textSecondary },
  bestMoveSan: { fontSize: 14, fontWeight: '700', color: StatusColors.excellent },

  startingCard: {
    alignItems: 'center',
    padding: 24,
    backgroundColor: colors.card,
    borderRadius: 10,
    gap: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  startingText: { fontSize: 15, fontWeight: '600', color: colors.text },
  startingHint: { fontSize: 12, color: colors.textSecondary },

  noAnalysisCard: {
    alignItems: 'center',
    padding: 16,
    backgroundColor: colors.card,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  noAnalysisMove: { fontSize: 15, fontWeight: '600', color: colors.text, marginBottom: 4 },
  noAnalysisText: { fontSize: 13, color: colors.textSecondary },

  summarySection: { gap: 10, marginTop: 4 },
  
  statsRow: { flexDirection: 'row', gap: 6 },
  statBox: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: 8 },
  statNum: { fontSize: 18, fontWeight: '700' },
  statLabel: { fontSize: 9, color: '#71717a', marginTop: 1, textTransform: 'uppercase' },

  summaryCard: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  summaryTitle: { fontSize: 13, fontWeight: '600', color: colors.text, marginBottom: 8 },
  summaryText: { fontSize: 13, color: colors.textSecondary, lineHeight: 20 },

  focusCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#f59e0b10',
    borderRadius: 10,
    padding: 12,
    gap: 10,
    borderWidth: 1,
    borderColor: '#f59e0b30',
  },
  focusLabel: { fontSize: 11, fontWeight: '600', color: '#f59e0b', marginBottom: 2 },
  focusText: { fontSize: 13, color: colors.text, lineHeight: 18 },
});
