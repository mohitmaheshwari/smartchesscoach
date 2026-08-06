import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { COLORS } from '../constants/config';
import { ChessBoardView } from '../components/ChessBoardView';
import { EvaluationBar } from '../components/EvaluationBar';
import { getGameAnalysis } from '../services/api';

export default function GameAnalysisScreen({ route, navigation }) {
  const gameId = route.params?.gameId || 'game_demo_1';
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentPly, setCurrentPly] = useState(0);
  const [evalScore, setEvalScore] = useState(0.4);

  useEffect(() => {
    const fetchAnalysis = async () => {
      setLoading(true);
      try {
        const data = await getGameAnalysis(gameId);
        setAnalysis(data);
        if (data.eval_graph && data.eval_graph.length > 0) {
          setEvalScore(data.eval_graph[0]);
        }
      } catch (e) {
        console.warn('Analysis load error:', e);
      } finally {
        setLoading(false);
      }
    };
    fetchAnalysis();
  }, [gameId]);

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>Analyzing Game with Stockfish 15...</Text>
      </View>
    );
  }

  const handleNextMove = () => {
    if (analysis && analysis.eval_graph && currentPly < analysis.eval_graph.length - 1) {
      const nextPly = currentPly + 1;
      setCurrentPly(nextPly);
      setEvalScore(analysis.eval_graph[nextPly] || 0);
    }
  };

  const handlePrevMove = () => {
    if (currentPly > 0) {
      const prevPly = currentPly - 1;
      setCurrentPly(prevPly);
      setEvalScore(analysis?.eval_graph?.[prevPly] || 0);
    }
  };

  const currentBlunder = analysis?.blunders?.find(b => b.ply === currentPly);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Game Header */}
      <View style={styles.headerBox}>
        <View>
          <Text style={styles.gameTitle}>Game Analysis Studio</Text>
          <Text style={styles.gameSubtitle}>Accuracy: {analysis?.accuracy || 89.4}%  •  White vs Black</Text>
        </View>
        <TouchableOpacity style={styles.askCoachButton} onPress={() => navigation.navigate('AICoach')}>
          <Text style={styles.askCoachButtonText}>💬 Ask AI Coach</Text>
        </TouchableOpacity>
      </View>

      {/* Board + Eval Bar Layout */}
      <View style={styles.boardContainer}>
        <EvaluationBar evalScore={evalScore} />
        <View style={styles.boardFlex}>
          <ChessBoardView
            fen={analysis?.fen || 'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2PP1N2/PP3PPP/RNBQ1RK1 b kq - 0 6'}
            orientation={analysis?.player_color || 'white'}
          />
        </View>
      </View>

      {/* Move Controller Controls */}
      <View style={styles.controlRow}>
        <TouchableOpacity style={styles.controlBtn} onPress={() => setCurrentPly(0)}>
          <Text style={styles.controlBtnText}>⏮ Start</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.controlBtn} onPress={handlePrevMove}>
          <Text style={styles.controlBtnText}>◀ Prev</Text>
        </TouchableOpacity>
        <View style={styles.moveCounter}>
          <Text style={styles.moveCounterText}>Move {Math.floor(currentPly / 2) + 1}</Text>
        </View>
        <TouchableOpacity style={styles.controlBtn} onPress={handleNextMove}>
          <Text style={styles.controlBtnText}>Next ▶</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.controlBtn}
          onPress={() => setCurrentPly((analysis?.eval_graph?.length || 10) - 1)}
        >
          <Text style={styles.controlBtnText}>End ⏭</Text>
        </TouchableOpacity>
      </View>

      {/* Blunder or Turn Callout */}
      {currentBlunder ? (
        <View style={styles.blunderAlertBox}>
          <Text style={styles.blunderAlertHeader}>🚨 BLUNDER DETECTED ({currentBlunder.move})</Text>
          <Text style={styles.blunderAlertExplanation}>{currentBlunder.explanation}</Text>
          <View style={styles.betterMoveBox}>
            <Text style={styles.betterMoveTitle}>Recommended Engine Move:</Text>
            <Text style={styles.betterMoveText}>{currentBlunder.better_move}</Text>
          </View>
        </View>
      ) : (
        <View style={styles.analysisInsightBox}>
          <Text style={styles.insightHeader}>💡 Stockfish Position Insight</Text>
          <Text style={styles.insightText}>
            White maintains space advantage in the center. Both sides have completed kingside castling.
            Evaluation: {evalScore > 0 ? `+${evalScore}` : evalScore}.
          </Text>
        </View>
      )}

      {/* Evaluation Trend Chart Summary */}
      <View style={styles.evalSummaryBox}>
        <Text style={styles.summaryTitle}>Evaluation Advantage Graph</Text>
        <View style={styles.graphBarsContainer}>
          {analysis?.eval_graph?.map((score, i) => (
            <TouchableOpacity
              key={i}
              style={[
                styles.graphBarItem,
                i === currentPly && styles.graphBarActive,
                { height: Math.max(12, Math.min(60, 30 + score * 6)) },
                { backgroundColor: score >= 0 ? COLORS.success : COLORS.danger }
              ]}
              onPress={() => {
                setCurrentPly(i);
                setEvalScore(score);
              }}
            />
          ))}
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  centerContainer: {
    flex: 1,
    backgroundColor: COLORS.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: COLORS.textMuted,
    marginTop: 12,
    fontSize: 14,
  },
  headerBox: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  gameTitle: {
    color: COLORS.text,
    fontSize: 20,
    fontWeight: '800',
  },
  gameSubtitle: {
    color: COLORS.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  askCoachButton: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
  },
  askCoachButtonText: {
    color: '#000',
    fontWeight: '800',
    fontSize: 12,
  },
  boardContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  boardFlex: {
    flex: 1,
    alignItems: 'center',
  },
  controlRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: COLORS.cardBg,
    borderRadius: 14,
    padding: 8,
    borderWidth: 1,
    borderColor: COLORS.cardBorder,
    marginBottom: 16,
  },
  controlBtn: {
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#1e293b',
  },
  controlBtnText: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: '700',
  },
  moveCounter: {
    paddingHorizontal: 12,
  },
  moveCounterText: {
    color: COLORS.primary,
    fontWeight: '800',
    fontSize: 14,
  },
  blunderAlertBox: {
    backgroundColor: '#2d1518',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: COLORS.danger,
    marginBottom: 16,
  },
  blunderAlertHeader: {
    color: COLORS.danger,
    fontSize: 14,
    fontWeight: '800',
    marginBottom: 6,
  },
  blunderAlertExplanation: {
    color: COLORS.text,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 10,
  },
  betterMoveBox: {
    backgroundColor: '#1a0d0f',
    padding: 10,
    borderRadius: 8,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  betterMoveTitle: {
    color: COLORS.textMuted,
    fontSize: 12,
  },
  betterMoveText: {
    color: COLORS.success,
    fontSize: 16,
    fontWeight: '800',
  },
  analysisInsightBox: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: COLORS.cardBorder,
    marginBottom: 16,
  },
  insightHeader: {
    color: COLORS.primary,
    fontWeight: '800',
    fontSize: 14,
    marginBottom: 6,
  },
  insightText: {
    color: COLORS.text,
    fontSize: 13,
    lineHeight: 19,
  },
  evalSummaryBox: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: COLORS.cardBorder,
  },
  summaryTitle: {
    color: COLORS.textMuted,
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 10,
  },
  graphBarsContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    height: 64,
  },
  graphBarItem: {
    width: 14,
    borderRadius: 4,
  },
  graphBarActive: {
    borderWidth: 2,
    borderColor: COLORS.primary,
  },
});
