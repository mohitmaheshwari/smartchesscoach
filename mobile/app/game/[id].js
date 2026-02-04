import React, { useState, useEffect, useMemo } from 'react';
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

const { width } = Dimensions.get('window');

export default function GameDetailScreen() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { colors } = useTheme();
  
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentMove, setCurrentMove] = useState(-1);
  const [activeTab, setActiveTab] = useState('summary'); // 'summary' or 'moves'

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

  // Get move-by-move analysis data
  const moveAnalysis = analysis?.move_by_move || [];

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

  const goToStart = () => setCurrentMove(-1);
  const goBack = () => setCurrentMove(prev => Math.max(-1, prev - 1));
  const goForward = () => setCurrentMove(prev => Math.min(totalMoves - 1, prev + 1));
  const goToEnd = () => setCurrentMove(totalMoves - 1);

  const currentMoveInfo = currentMove >= 0 ? parsedMoves[currentMove] : null;
  const moveNumber = currentMove >= 0 ? Math.floor(currentMove / 2) + 1 : 0;
  const isWhiteMove = currentMove >= 0 ? currentMove % 2 === 0 : true;

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

  if (!game) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
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
          <Text style={styles.headerMeta}>{game.result} • {game.user_color}</Text>
        </View>
        {analysis?.stockfish_analysis?.accuracy && (
          <View style={styles.accuracyBadge}>
            <Text style={styles.accuracyText}>{analysis.stockfish_analysis.accuracy}%</Text>
          </View>
        )}
      </View>

      {/* Board + Navigation */}
      <View style={styles.boardSection}>
        <ChessBoardViewer
          pgn={game.pgn}
          currentMoveIndex={currentMove}
          userColor={game.user_color}
        />
        
        <View style={styles.navRow}>
          <TouchableOpacity style={[styles.navBtn, currentMove <= -1 && styles.navBtnDisabled]} onPress={goToStart} disabled={currentMove <= -1}>
            <Ionicons name="play-skip-back" size={18} color={currentMove <= -1 ? colors.textSecondary : colors.text} />
          </TouchableOpacity>
          <TouchableOpacity style={[styles.navBtn, currentMove <= -1 && styles.navBtnDisabled]} onPress={goBack} disabled={currentMove <= -1}>
            <Ionicons name="chevron-back" size={22} color={currentMove <= -1 ? colors.textSecondary : colors.text} />
          </TouchableOpacity>
          <View style={styles.moveInfo}>
            <Text style={styles.moveCount}>{currentMove + 1}/{totalMoves}</Text>
            {currentMoveInfo && <Text style={styles.moveSan}>{moveNumber}.{!isWhiteMove && '..'}{currentMoveInfo.san}</Text>}
          </View>
          <TouchableOpacity style={[styles.navBtn, currentMove >= totalMoves - 1 && styles.navBtnDisabled]} onPress={goForward} disabled={currentMove >= totalMoves - 1}>
            <Ionicons name="chevron-forward" size={22} color={currentMove >= totalMoves - 1 ? colors.textSecondary : colors.text} />
          </TouchableOpacity>
          <TouchableOpacity style={[styles.navBtn, currentMove >= totalMoves - 1 && styles.navBtnDisabled]} onPress={goToEnd} disabled={currentMove >= totalMoves - 1}>
            <Ionicons name="play-skip-forward" size={18} color={currentMove >= totalMoves - 1 ? colors.textSecondary : colors.text} />
          </TouchableOpacity>
        </View>
      </View>

      {/* Analyze Button (if no analysis) */}
      {!analysis && (
        <View style={styles.analyzeContainer}>
          <TouchableOpacity 
            style={[styles.analyzeBtn, analyzing && styles.analyzeBtnDisabled]}
            onPress={handleAnalyze}
            disabled={analyzing}
          >
            {analyzing ? (
              <ActivityIndicator size="small" color="#000" />
            ) : (
              <Ionicons name="flash" size={18} color="#000" />
            )}
            <Text style={styles.analyzeBtnText}>{analyzing ? 'Analyzing...' : 'Analyze with AI'}</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Tabs (only if analysis exists) */}
      {analysis && (
        <>
          <View style={styles.tabBar}>
            <TouchableOpacity 
              style={[styles.tab, activeTab === 'summary' && styles.tabActive]}
              onPress={() => setActiveTab('summary')}
            >
              <Ionicons name="document-text-outline" size={18} color={activeTab === 'summary' ? colors.accent : colors.textSecondary} />
              <Text style={[styles.tabText, activeTab === 'summary' && styles.tabTextActive]}>Summary</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={[styles.tab, activeTab === 'moves' && styles.tabActive]}
              onPress={() => setActiveTab('moves')}
            >
              <Ionicons name="list-outline" size={18} color={activeTab === 'moves' ? colors.accent : colors.textSecondary} />
              <Text style={[styles.tabText, activeTab === 'moves' && styles.tabTextActive]}>Moves</Text>
              {moveAnalysis.length > 0 && (
                <View style={styles.tabBadge}>
                  <Text style={styles.tabBadgeText}>{moveAnalysis.length}</Text>
                </View>
              )}
            </TouchableOpacity>
          </View>

          {/* Tab Content */}
          {activeTab === 'summary' ? (
            <ScrollView style={styles.tabContent} contentContainerStyle={styles.tabContentInner}>
              {/* Stats */}
              <View style={styles.statsRow}>
                <StatBox label="Blunders" value={analysis.blunders || 0} color={StatusColors.blunder} />
                <StatBox label="Mistakes" value={analysis.mistakes || 0} color={StatusColors.mistake} />
                <StatBox label="Inaccuracies" value={analysis.inaccuracies || 0} color={StatusColors.inaccuracy} />
                <StatBox label="Best" value={analysis.best_moves || 0} color={StatusColors.excellent} />
              </View>

              {/* Coach Summary */}
              {(analysis.overall_summary || analysis.summary_p1) && (
                <View style={styles.card}>
                  <View style={styles.cardHeader}>
                    <Ionicons name="chatbubble-ellipses" size={18} color={colors.accent} />
                    <Text style={styles.cardTitle}>Coach's Analysis</Text>
                  </View>
                  <Text style={styles.cardText}>{analysis.summary_p1 || analysis.overall_summary}</Text>
                  {analysis.summary_p2 && <Text style={[styles.cardText, { marginTop: 12 }]}>{analysis.summary_p2}</Text>}
                </View>
              )}

              {/* Focus */}
              {analysis.focus_this_week && (
                <View style={[styles.card, styles.focusCard]}>
                  <View style={styles.cardHeader}>
                    <Ionicons name="flag" size={18} color="#f59e0b" />
                    <Text style={[styles.cardTitle, { color: '#f59e0b' }]}>Focus This Week</Text>
                  </View>
                  <Text style={styles.cardText}>{analysis.focus_this_week}</Text>
                </View>
              )}
            </ScrollView>
          ) : (
            <FlatList
              data={moveAnalysis}
              keyExtractor={(item, idx) => `move-${idx}`}
              style={styles.tabContent}
              contentContainerStyle={styles.movesListContent}
              renderItem={({ item, index }) => (
                <TouchableOpacity 
                  style={[
                    styles.moveCard,
                    { borderLeftColor: getEvalColor(item.evaluation) },
                    currentMove === index && styles.moveCardActive
                  ]}
                  onPress={() => setCurrentMove(index)}
                  activeOpacity={0.7}
                >
                  <View style={styles.moveCardHeader}>
                    <Text style={styles.moveCardNumber}>{item.move_number}.</Text>
                    <Text style={styles.moveCardSan}>{item.move}</Text>
                    <View style={[styles.evalPill, { backgroundColor: getEvalColor(item.evaluation) + '20' }]}>
                      <Text style={[styles.evalPillText, { color: getEvalColor(item.evaluation) }]}>
                        {item.evaluation || 'neutral'}
                      </Text>
                    </View>
                    {item.cp_loss > 0 && (
                      <Text style={styles.cpLossText}>-{(item.cp_loss / 100).toFixed(1)}</Text>
                    )}
                  </View>
                  
                  {item.lesson && (
                    <Text style={styles.moveLesson}>{item.lesson}</Text>
                  )}
                  
                  {item.thinking_pattern && item.thinking_pattern !== 'solid_thinking' && (
                    <View style={styles.patternRow}>
                      <Ionicons name="bulb-outline" size={14} color="#f59e0b" />
                      <Text style={styles.patternText}>{item.thinking_pattern.replace(/_/g, ' ')}</Text>
                    </View>
                  )}
                  
                  {item.consider && (
                    <View style={styles.considerRow}>
                      <Ionicons name="arrow-forward-circle-outline" size={14} color={StatusColors.good} />
                      <Text style={styles.considerText}>{item.consider}</Text>
                    </View>
                  )}
                  
                  {item.best_move && item.best_move !== item.move && (
                    <View style={styles.bestMoveRow}>
                      <Ionicons name="checkmark-circle" size={14} color={StatusColors.excellent} />
                      <Text style={styles.bestMoveText}>Better: <Text style={styles.bestMoveSan}>{item.best_move}</Text></Text>
                    </View>
                  )}
                </TouchableOpacity>
              )}
              ListEmptyComponent={
                <View style={styles.emptyMoves}>
                  <Ionicons name="document-outline" size={40} color={colors.textSecondary} />
                  <Text style={styles.emptyMovesText}>No move-by-move analysis available</Text>
                </View>
              }
            />
          )}
        </>
      )}
    </SafeAreaView>
  );
}

// Stat Box Component
const StatBox = ({ label, value, color }) => (
  <View style={[statStyles.box, { backgroundColor: color + '15' }]}>
    <Text style={[statStyles.value, { color }]}>{value}</Text>
    <Text style={statStyles.label}>{label}</Text>
  </View>
);

const statStyles = StyleSheet.create({
  box: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: 8 },
  value: { fontSize: 20, fontWeight: '700' },
  label: { fontSize: 9, color: '#71717a', marginTop: 2, textTransform: 'uppercase' },
});

const getEvalColor = (evaluation) => {
  const colors = {
    blunder: StatusColors.blunder,
    mistake: StatusColors.mistake,
    inaccuracy: StatusColors.inaccuracy,
    good: StatusColors.good,
    excellent: StatusColors.excellent,
    best: StatusColors.excellent,
    neutral: '#71717a',
  };
  return colors[evaluation] || '#71717a';
};

const createStyles = (colors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  errorText: { color: colors.textSecondary, marginBottom: 16 },
  btn: { backgroundColor: colors.card, paddingHorizontal: 20, paddingVertical: 10, borderRadius: 8 },
  btnText: { color: colors.text, fontWeight: '500' },
  
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: 8,
  },
  backBtn: { padding: 4 },
  headerInfo: { flex: 1 },
  headerTitle: { fontSize: 14, fontWeight: '600', color: colors.text },
  headerMeta: { fontSize: 11, color: colors.textSecondary, marginTop: 1 },
  accuracyBadge: { backgroundColor: '#3b82f620', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  accuracyText: { color: '#3b82f6', fontWeight: '700', fontSize: 13 },

  boardSection: { alignItems: 'center', paddingVertical: 12 },
  navRow: { flexDirection: 'row', alignItems: 'center', marginTop: 10, gap: 6 },
  navBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.card,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  navBtnDisabled: { opacity: 0.4 },
  moveInfo: { alignItems: 'center', minWidth: 70, paddingHorizontal: 8 },
  moveCount: { fontSize: 11, color: colors.textSecondary, fontFamily: 'monospace' },
  moveSan: { fontSize: 15, fontWeight: '600', color: colors.text },

  analyzeContainer: { paddingHorizontal: 16, paddingVertical: 12 },
  analyzeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f59e0b',
    paddingVertical: 14,
    borderRadius: 12,
    gap: 8,
  },
  analyzeBtnDisabled: { opacity: 0.6 },
  analyzeBtnText: { fontSize: 15, fontWeight: '700', color: '#000' },

  tabBar: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    gap: 6,
  },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.accent },
  tabText: { fontSize: 13, color: colors.textSecondary, fontWeight: '500' },
  tabTextActive: { color: colors.accent },
  tabBadge: { backgroundColor: colors.accent + '30', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 10 },
  tabBadgeText: { fontSize: 10, color: colors.accent, fontWeight: '600' },

  tabContent: { flex: 1 },
  tabContentInner: { padding: 16, gap: 12 },
  movesListContent: { padding: 12, gap: 8 },

  statsRow: { flexDirection: 'row', gap: 6 },

  card: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  cardTitle: { fontSize: 14, fontWeight: '600', color: colors.text },
  cardText: { fontSize: 14, color: colors.textSecondary, lineHeight: 22 },
  focusCard: { backgroundColor: '#f59e0b10', borderColor: '#f59e0b30' },

  moveCard: {
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 12,
    borderLeftWidth: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  moveCardActive: { borderColor: colors.accent },
  moveCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  moveCardNumber: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  moveCardSan: { fontSize: 15, fontWeight: '700', color: colors.text },
  evalPill: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  evalPillText: { fontSize: 11, fontWeight: '600', textTransform: 'capitalize' },
  cpLossText: { fontSize: 12, color: StatusColors.blunder, fontWeight: '600', fontFamily: 'monospace', marginLeft: 'auto' },
  
  moveLesson: { fontSize: 13, color: colors.text, lineHeight: 20, marginBottom: 6 },
  patternRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  patternText: { fontSize: 12, color: '#f59e0b', textTransform: 'capitalize' },
  considerRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 6, marginTop: 6 },
  considerText: { fontSize: 12, color: StatusColors.good, flex: 1 },
  bestMoveRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, paddingTop: 8, borderTopWidth: 1, borderTopColor: colors.border },
  bestMoveText: { fontSize: 12, color: colors.textSecondary },
  bestMoveSan: { fontWeight: '700', color: StatusColors.excellent },

  emptyMoves: { alignItems: 'center', paddingVertical: 40 },
  emptyMovesText: { color: colors.textSecondary, marginTop: 12, fontSize: 14 },
});
