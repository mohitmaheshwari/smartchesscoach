import React, { useState, useEffect } from 'react';
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
import { useTheme } from '../../src/context/ThemeContext';
import { gamesAPI, analysisAPI } from '../../src/services/api';
import { ChessBoardViewer, MoveNavigation } from '../../src/components/ChessBoard';
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
  const [currentMove, setCurrentMove] = useState(0);

  useEffect(() => {
    loadGame();
  }, [id]);

  const loadGame = async () => {
    try {
      console.log('Loading game:', id);
      const gameData = await gamesAPI.getGame(id);
      console.log('Game loaded:', gameData?.game_id);
      setGame(gameData);
      
      // Try to load analysis separately
      try {
        const analysisData = await analysisAPI.getAnalysis(id);
        console.log('Analysis loaded:', analysisData?.game_id);
        if (analysisData && analysisData.game_id) {
          setAnalysis(analysisData);
        }
      } catch (e) {
        console.log('No analysis yet (this is normal for new games)');
        setAnalysis(null);
      }
    } catch (error) {
      console.error('Failed to load game:', error);
      Alert.alert('Error', 'Failed to load game');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    console.log('Starting analysis for game:', id);
    setAnalyzing(true);
    try {
      const result = await analysisAPI.analyzeGame(id);
      console.log('Analysis complete:', result?.game_id);
      if (result && result.game_id) {
        setAnalysis(result);
        Alert.alert('Success', 'Game analyzed with Stockfish!');
      }
    } catch (error) {
      console.error('Analysis failed:', error);
      Alert.alert('Error', error.message || 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const styles = createStyles(colors);
  const moves = analysis?.move_by_move || [];
  const totalMoves = moves.length;

  // Loading state
  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.text} />
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
    <SafeAreaView style={styles.container}>
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

      <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent}>
        {/* Chessboard */}
        <View style={styles.boardSection}>
          <ChessBoardViewer
            pgn={game.pgn}
            currentMoveIndex={currentMove}
            userColor={game.user_color}
          />
          
          {/* Move Navigation */}
          <MoveNavigation
            currentMove={currentMove + 1}
            totalMoves={totalMoves || 1}
            onFirst={() => setCurrentMove(0)}
            onPrevious={() => setCurrentMove(Math.max(0, currentMove - 1))}
            onNext={() => setCurrentMove(Math.min(totalMoves - 1, currentMove + 1))}
            onLast={() => setCurrentMove(Math.max(0, totalMoves - 1))}
          />
        </View>

        {/* ANALYZE BUTTON - Always visible when no analysis */}
        {!analysis && (
          <View style={styles.analyzeSection}>
            <Ionicons name="analytics-outline" size={40} color={colors.accent} />
            <Text style={styles.analyzeTitle}>Ready for Analysis</Text>
            <Text style={styles.analyzeDesc}>
              Get AI coaching insights powered by Stockfish engine
            </Text>
            <TouchableOpacity 
              style={[styles.analyzeBtn, analyzing && styles.analyzeBtnDisabled]}
              onPress={handleAnalyze}
              disabled={analyzing}
            >
              {analyzing ? (
                <>
                  <ActivityIndicator size="small" color="#000" />
                  <Text style={styles.analyzeBtnText}>Analyzing...</Text>
                </>
              ) : (
                <>
                  <Ionicons name="flash" size={20} color="#000" />
                  <Text style={styles.analyzeBtnText}>Analyze Game</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        )}

        {/* ANALYSIS RESULTS - Show when analysis exists */}
        {analysis && (
          <View style={styles.analysisSection}>
            {/* Accuracy Card */}
            {analysis.stockfish_analysis?.accuracy && (
              <View style={styles.accuracyCard}>
                <View style={styles.accuracyLeft}>
                  <Text style={styles.accuracyValue}>{analysis.stockfish_analysis.accuracy}%</Text>
                  <Text style={styles.accuracyLabel}>Accuracy</Text>
                </View>
                <View style={styles.accuracyRight}>
                  <Text style={styles.statsText}>Blunders: {analysis.blunders || 0}</Text>
                  <Text style={styles.statsText}>Mistakes: {analysis.mistakes || 0}</Text>
                  <Text style={styles.statsText}>Inaccuracies: {analysis.inaccuracies || 0}</Text>
                </View>
              </View>
            )}

            {/* Summary */}
            {analysis.overall_summary && (
              <View style={styles.summaryCard}>
                <Text style={styles.summaryTitle}>Coach's Summary</Text>
                <Text style={styles.summaryText}>{analysis.overall_summary}</Text>
              </View>
            )}

            {/* Focus Area */}
            {analysis.focus_this_week && (
              <View style={styles.focusCard}>
                <Ionicons name="flag" size={20} color={colors.accent} />
                <View style={styles.focusContent}>
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
    marginTop: 12,
    color: colors.textSecondary,
    fontSize: 14,
  },
  errorText: {
    marginTop: 12,
    marginBottom: 20,
    color: colors.textSecondary,
    fontSize: 16,
  },
  backBtn: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    backgroundColor: colors.card,
    borderRadius: 8,
  },
  backBtnText: {
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
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  boardSection: {
    alignItems: 'center',
    marginBottom: 20,
  },
  analyzeSection: {
    alignItems: 'center',
    padding: 24,
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 20,
  },
  analyzeTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginTop: 12,
  },
  analyzeDesc: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 8,
    marginBottom: 20,
  },
  analyzeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f59e0b',
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 12,
    gap: 8,
    width: '100%',
  },
  analyzeBtnDisabled: {
    opacity: 0.7,
  },
  analyzeBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
  analysisSection: {
    gap: 16,
  },
  accuracyCard: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  accuracyLeft: {
    alignItems: 'center',
    paddingRight: 20,
    borderRightWidth: 1,
    borderRightColor: colors.border,
  },
  accuracyValue: {
    fontSize: 32,
    fontWeight: '700',
    color: '#3b82f6',
  },
  accuracyLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  accuracyRight: {
    flex: 1,
    justifyContent: 'center',
    paddingLeft: 20,
  },
  statsText: {
    fontSize: 14,
    color: colors.text,
    marginVertical: 2,
  },
  summaryCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  summaryTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 8,
  },
  summaryText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  focusCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.accent,
    gap: 12,
  },
  focusContent: {
    flex: 1,
  },
  focusLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.accent,
    marginBottom: 4,
  },
  focusText: {
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
});
