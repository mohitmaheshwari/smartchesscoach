import React, { useState, useEffect, useMemo } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Dimensions
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Chess } from 'chess.js';
import { useTheme } from '../../src/context/ThemeContext';
import { gamesAPI, analysisAPI } from '../../src/services/api';
import { ChessBoardViewer } from '../../src/components/ChessBoard';
import { StatusColors } from '../../src/constants/config';

const { width } = Dimensions.get('window');

export default function GameDetailScreen() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { colors } = useTheme();
  
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentMove, setCurrentMove] = useState(-1); // -1 = starting position

  // Parse PGN to get all moves
  const parsedMoves = useMemo(() => {
    if (!game?.pgn) return [];
    try {
      const chess = new Chess();
      chess.loadPgn(game.pgn);
      return chess.history({ verbose: true });
    } catch (e) {
      console.log('PGN parse error:', e);
      return [];
    }
  }, [game?.pgn]);

  const totalMoves = parsedMoves.length;

  useEffect(() => {
    loadGame();
  }, [id]);

  const loadGame = async () => {
    try {
      const gameData = await gamesAPI.getGame(id);
      setGame(gameData);
      
      try {
        const analysisData = await analysisAPI.getAnalysis(id);
        if (analysisData && analysisData.game_id) {
          setAnalysis(analysisData);
        }
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
      if (result && result.game_id) {
        setAnalysis(result);
        Alert.alert('Success', 'Game analyzed!');
      }
    } catch (error) {
      Alert.alert('Error', error.message || 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  // Move navigation functions
  const goToStart = () => setCurrentMove(-1);
  const goBack = () => setCurrentMove(prev => Math.max(-1, prev - 1));
  const goForward = () => setCurrentMove(prev => Math.min(totalMoves - 1, prev + 1));
  const goToEnd = () => setCurrentMove(totalMoves - 1);

  // Get current move info
  const currentMoveInfo = currentMove >= 0 ? parsedMoves[currentMove] : null;
  const moveNumber = currentMove >= 0 ? Math.floor(currentMove / 2) + 1 : 0;
  const isWhiteMove = currentMove >= 0 ? currentMove % 2 === 0 : true;

  // Get analysis for current move
  const currentMoveAnalysis = analysis?.move_by_move?.find(
    m => m.move_number === moveNumber && m.move === currentMoveInfo?.san
  );

  const styles = createStyles(colors);

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

  if (!game) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={48} color={colors.textSecondary} />
          <Text style={styles.errorText}>Game not found</Text>
          <TouchableOpacity style={styles.btn} onPress={() => router.back()}>
            <Text style={styles.btnText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={styles.headerInfo}>
          <Text style={styles.headerTitle} numberOfLines={1}>
            {game.white_player} vs {game.black_player}
          </Text>
          <Text style={styles.headerMeta}>
            {game.result} • {game.user_color}
          </Text>
        </View>
        {analysis && (
          <View style={styles.accuracyBadge}>
            <Text style={styles.accuracyText}>
              {analysis.stockfish_analysis?.accuracy || '--'}%
            </Text>
          </View>
        )}
      </View>

      <ScrollView 
        style={styles.scrollView} 
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Chessboard */}
        <View style={styles.boardContainer}>
          <ChessBoardViewer
            pgn={game.pgn}
            currentMoveIndex={currentMove}
            userColor={game.user_color}
          />
        </View>

        {/* Move Navigation */}
        <View style={styles.navContainer}>
          <TouchableOpacity 
            style={[styles.navBtn, currentMove <= -1 && styles.navBtnDisabled]} 
            onPress={goToStart}
            disabled={currentMove <= -1}
          >
            <Ionicons name="play-skip-back" size={20} color={currentMove <= -1 ? colors.textSecondary : colors.text} />
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.navBtn, currentMove <= -1 && styles.navBtnDisabled]} 
            onPress={goBack}
            disabled={currentMove <= -1}
          >
            <Ionicons name="chevron-back" size={24} color={currentMove <= -1 ? colors.textSecondary : colors.text} />
          </TouchableOpacity>
          
          <View style={styles.moveCounter}>
            <Text style={styles.moveCounterText}>
              {currentMove + 1} / {totalMoves}
            </Text>
            {currentMoveInfo && (
              <Text style={styles.currentMoveText}>
                {moveNumber}. {!isWhiteMove && '...'}{currentMoveInfo.san}
              </Text>
            )}
          </View>
          
          <TouchableOpacity 
            style={[styles.navBtn, currentMove >= totalMoves - 1 && styles.navBtnDisabled]} 
            onPress={goForward}
            disabled={currentMove >= totalMoves - 1}
          >
            <Ionicons name="chevron-forward" size={24} color={currentMove >= totalMoves - 1 ? colors.textSecondary : colors.text} />
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.navBtn, currentMove >= totalMoves - 1 && styles.navBtnDisabled]} 
            onPress={goToEnd}
            disabled={currentMove >= totalMoves - 1}
          >
            <Ionicons name="play-skip-forward" size={20} color={currentMove >= totalMoves - 1 ? colors.textSecondary : colors.text} />
          </TouchableOpacity>
        </View>

        {/* Current Move Analysis (if available) */}
        {currentMoveAnalysis && (
          <View style={[styles.moveAnalysisCard, { borderLeftColor: getEvalColor(currentMoveAnalysis.evaluation) }]}>
            <View style={styles.moveAnalysisHeader}>
              <View style={[styles.evalBadge, { backgroundColor: getEvalColor(currentMoveAnalysis.evaluation) + '20' }]}>
                <Text style={[styles.evalText, { color: getEvalColor(currentMoveAnalysis.evaluation) }]}>
                  {currentMoveAnalysis.evaluation}
                </Text>
              </View>
              {currentMoveAnalysis.cp_loss > 0 && (
                <Text style={styles.cpLoss}>-{(currentMoveAnalysis.cp_loss / 100).toFixed(1)}</Text>
              )}
            </View>
            {currentMoveAnalysis.lesson && (
              <Text style={styles.moveLesson}>{currentMoveAnalysis.lesson}</Text>
            )}
            {currentMoveAnalysis.best_move && currentMoveAnalysis.best_move !== currentMoveInfo?.san && (
              <View style={styles.bestMoveRow}>
                <Ionicons name="bulb" size={16} color={StatusColors.good} />
                <Text style={styles.bestMoveText}>Better: {currentMoveAnalysis.best_move}</Text>
              </View>
            )}
          </View>
        )}

        {/* Analyze Button (if no analysis) */}
        {!analysis && (
          <View style={styles.analyzeSection}>
            <View style={styles.analyzeIconContainer}>
              <Ionicons name="analytics" size={32} color={colors.accent} />
            </View>
            <Text style={styles.analyzeTitle}>Get AI Analysis</Text>
            <Text style={styles.analyzeDesc}>
              Stockfish engine + AI coaching insights
            </Text>
            <TouchableOpacity 
              style={[styles.analyzeBtn, analyzing && styles.analyzeBtnDisabled]}
              onPress={handleAnalyze}
              disabled={analyzing}
              activeOpacity={0.8}
            >
              {analyzing ? (
                <>
                  <ActivityIndicator size="small" color="#000" />
                  <Text style={styles.analyzeBtnText}>Analyzing...</Text>
                </>
              ) : (
                <>
                  <Ionicons name="flash" size={18} color="#000" />
                  <Text style={styles.analyzeBtnText}>Analyze Game</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        )}

        {/* Analysis Summary */}
        {analysis && (
          <View style={styles.analysisContainer}>
            {/* Stats Row */}
            <View style={styles.statsRow}>
              <View style={[styles.statBox, { backgroundColor: StatusColors.blunder + '15' }]}>
                <Text style={[styles.statNumber, { color: StatusColors.blunder }]}>{analysis.blunders || 0}</Text>
                <Text style={styles.statLabel}>Blunders</Text>
              </View>
              <View style={[styles.statBox, { backgroundColor: StatusColors.mistake + '15' }]}>
                <Text style={[styles.statNumber, { color: StatusColors.mistake }]}>{analysis.mistakes || 0}</Text>
                <Text style={styles.statLabel}>Mistakes</Text>
              </View>
              <View style={[styles.statBox, { backgroundColor: StatusColors.inaccuracy + '15' }]}>
                <Text style={[styles.statNumber, { color: StatusColors.inaccuracy }]}>{analysis.inaccuracies || 0}</Text>
                <Text style={styles.statLabel}>Inaccuracies</Text>
              </View>
              <View style={[styles.statBox, { backgroundColor: StatusColors.excellent + '15' }]}>
                <Text style={[styles.statNumber, { color: StatusColors.excellent }]}>{analysis.best_moves || 0}</Text>
                <Text style={styles.statLabel}>Best</Text>
              </View>
            </View>

            {/* Coach Summary */}
            {(analysis.overall_summary || analysis.summary_p1) && (
              <View style={styles.summaryCard}>
                <View style={styles.summaryHeader}>
                  <Ionicons name="person-circle" size={24} color={colors.accent} />
                  <Text style={styles.summaryTitle}>Coach's Analysis</Text>
                </View>
                <Text style={styles.summaryText}>
                  {analysis.summary_p1 || analysis.overall_summary}
                </Text>
                {analysis.summary_p2 && (
                  <Text style={[styles.summaryText, { marginTop: 12 }]}>
                    {analysis.summary_p2}
                  </Text>
                )}
              </View>
            )}

            {/* Focus Area */}
            {analysis.focus_this_week && (
              <View style={styles.focusCard}>
                <View style={styles.focusHeader}>
                  <Ionicons name="flag" size={18} color="#f59e0b" />
                  <Text style={styles.focusTitle}>Focus This Week</Text>
                </View>
                <Text style={styles.focusText}>{analysis.focus_this_week}</Text>
              </View>
            )}

            {/* Key Mistakes */}
            {analysis.best_move_suggestions?.length > 0 && (
              <View style={styles.mistakesCard}>
                <Text style={styles.mistakesTitle}>Key Moments</Text>
                {analysis.best_move_suggestions.slice(0, 5).map((mistake, idx) => (
                  <TouchableOpacity 
                    key={idx} 
                    style={styles.mistakeRow}
                    onPress={() => {
                      // Find the move index
                      const moveIdx = parsedMoves.findIndex(
                        (m, i) => Math.floor(i / 2) + 1 === mistake.move_number && m.san === mistake.played_move
                      );
                      if (moveIdx >= 0) setCurrentMove(moveIdx);
                    }}
                  >
                    <View style={[styles.mistakeBadge, { backgroundColor: getEvalColor(mistake.evaluation) + '20' }]}>
                      <Text style={[styles.mistakeBadgeText, { color: getEvalColor(mistake.evaluation) }]}>
                        {mistake.move_number}.
                      </Text>
                    </View>
                    <View style={styles.mistakeInfo}>
                      <Text style={styles.mistakeMove}>
                        {mistake.played_move} → {mistake.best_move}
                      </Text>
                      {mistake.cp_loss > 0 && (
                        <Text style={styles.mistakeCp}>-{(mistake.cp_loss / 100).toFixed(1)} pawns</Text>
                      )}
                    </View>
                    <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// Helper function
const getEvalColor = (evaluation) => {
  const evalColors = {
    blunder: StatusColors.blunder,
    mistake: StatusColors.mistake,
    inaccuracy: StatusColors.inaccuracy,
    good: StatusColors.good,
    excellent: StatusColors.excellent,
    best: StatusColors.excellent,
  };
  return evalColors[evaluation] || '#71717a';
};

const createStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  loadingText: {
    marginTop: 16,
    color: colors.textSecondary,
    fontSize: 15,
  },
  errorText: {
    marginTop: 16,
    marginBottom: 24,
    color: colors.textSecondary,
    fontSize: 16,
  },
  btn: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: colors.card,
    borderRadius: 10,
  },
  btnText: {
    color: colors.text,
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: 8,
  },
  backBtn: {
    padding: 6,
  },
  headerInfo: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  headerMeta: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  accuracyBadge: {
    backgroundColor: '#3b82f620',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  accuracyText: {
    color: '#3b82f6',
    fontWeight: '700',
    fontSize: 14,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 40,
  },
  boardContainer: {
    alignItems: 'center',
    paddingVertical: 16,
    paddingHorizontal: 16,
  },
  navContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
    paddingBottom: 16,
    gap: 8,
  },
  navBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.card,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  navBtnDisabled: {
    opacity: 0.4,
  },
  moveCounter: {
    alignItems: 'center',
    paddingHorizontal: 16,
    minWidth: 80,
  },
  moveCounterText: {
    fontSize: 13,
    color: colors.textSecondary,
    fontFamily: 'monospace',
  },
  currentMoveText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginTop: 2,
  },
  moveAnalysisCard: {
    marginHorizontal: 16,
    marginBottom: 16,
    padding: 14,
    backgroundColor: colors.card,
    borderRadius: 12,
    borderLeftWidth: 4,
  },
  moveAnalysisHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 8,
  },
  evalBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  evalText: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  cpLoss: {
    fontSize: 13,
    color: StatusColors.blunder,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  moveLesson: {
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
  bestMoveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  bestMoveText: {
    fontSize: 14,
    color: StatusColors.good,
    fontWeight: '500',
  },
  analyzeSection: {
    alignItems: 'center',
    margin: 16,
    padding: 24,
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  analyzeIconContainer: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.accent + '20',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  analyzeTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
  },
  analyzeDesc: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 6,
    marginBottom: 20,
  },
  analyzeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f59e0b',
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 12,
    gap: 8,
    width: '100%',
  },
  analyzeBtnDisabled: {
    opacity: 0.6,
  },
  analyzeBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#000',
  },
  analysisContainer: {
    paddingHorizontal: 16,
    gap: 12,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  statBox: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    borderRadius: 10,
  },
  statNumber: {
    fontSize: 20,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: 10,
    color: colors.textSecondary,
    marginTop: 2,
    textTransform: 'uppercase',
  },
  summaryCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  summaryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
  },
  summaryTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  summaryText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  focusCard: {
    backgroundColor: '#f59e0b10',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#f59e0b30',
  },
  focusHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  focusTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#f59e0b',
  },
  focusText: {
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
  mistakesCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  mistakesTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 12,
  },
  mistakeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: 10,
  },
  mistakeBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  mistakeBadgeText: {
    fontSize: 12,
    fontWeight: '600',
  },
  mistakeInfo: {
    flex: 1,
  },
  mistakeMove: {
    fontSize: 14,
    color: colors.text,
    fontWeight: '500',
  },
  mistakeCp: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
});
