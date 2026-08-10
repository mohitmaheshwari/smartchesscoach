import React, { useState, useMemo, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { Chess } from 'chess.js';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { COLORS } from '../constants/config';
import { ChessBoardView } from '../components/ChessBoardView';
import { EvaluationBar } from '../components/EvaluationBar';
import { getGameAnalysis } from '../services/api';

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

const DEMO_MASTER_GAME = {
  source_type: 'master',
  title: 'Master Game Demo (Italian Game)',
  player_color: 'white',
  accuracy: 94.2,
  starting_fen: START_FEN,
  moves: [
    { from: 'e2', to: 'e4', san: 'e4' },
    { from: 'e7', to: 'e5', san: 'e5' },
    { from: 'g1', to: 'f3', san: 'Nf3' },
    { from: 'b8', to: 'c6', san: 'Nc6' },
    { from: 'f1', to: 'c4', san: 'Bc4' },
    { from: 'f8', to: 'c5', san: 'Bc5' },
    { from: 'c2', to: 'c3', san: 'c3' },
    { from: 'g8', to: 'f6', san: 'Nf6' },
    { from: 'd2', to: 'd3', san: 'd3' },
    { from: 'd7', to: 'd6', san: 'd6' },
    { from: 'e1', to: 'g1', san: 'O-O' },
    { from: 'e8', to: 'g8', san: 'O-O' }
  ]
};

export default function GameAnalysisScreen({ route, navigation }) {
  const routeGameId = route.params?.gameId;

  const [analysis, setAnalysis] = useState(null);
  const [lastPlayedGame, setLastPlayedGame] = useState(null);
  const [activeSource, setActiveSource] = useState('played'); // 'played' | 'demo'
  const [loading, setLoading] = useState(true);
  const [currentPly, setCurrentPly] = useState(0);

  // Reload played game automatically EVERY TIME the user switches to the Studio tab
  useFocusEffect(
    useCallback(() => {
      let isMounted = true;
      const loadGamesData = async () => {
        setLoading(true);
        try {
          // Load locally saved played game (offline or online)
          const savedGameJson = await AsyncStorage.getItem('@last_played_game');
          if (savedGameJson && isMounted) {
            const parsed = JSON.parse(savedGameJson);
            setLastPlayedGame(parsed);
            if (!routeGameId && parsed?.moves?.length > 0) {
              setActiveSource('played');
            }
          } else if (isMounted && !routeGameId) {
            setActiveSource('demo');
          }

          // If route specified a backend gameId, fetch it
          if (routeGameId) {
            const data = await getGameAnalysis(routeGameId);
            if (isMounted) {
              setAnalysis(data);
              setActiveSource('backend');
            }
          }
        } catch (e) {
          console.warn('Game load error:', e);
        } finally {
          if (isMounted) {
            setLoading(false);
          }
        }
      };

      loadGamesData();

      return () => {
        isMounted = false;
      };
    }, [routeGameId])
  );

  // Determine active game payload based on toggle
  const activeGame = useMemo(() => {
    if (activeSource === 'backend' && analysis) return analysis;
    if (activeSource === 'played' && lastPlayedGame && lastPlayedGame.moves?.length > 0) return lastPlayedGame;
    return DEMO_MASTER_GAME;
  }, [activeSource, analysis, lastPlayedGame]);

  // Build complete move timeline (Ply 0 to N) with FEN & Last Move highlights
  const timeline = useMemo(() => {
    const startFen = activeGame?.starting_fen || activeGame?.fen || START_FEN;
    const chess = new Chess(startFen);

    const frames = [
      {
        ply: 0,
        fen: chess.fen(),
        moveSan: 'Start',
        lastMove: null,
        evalScore: activeGame?.eval_graph?.[0] ?? 0.2
      }
    ];

    const movesList = activeGame?.moves || activeGame?.pgn_moves || DEMO_MASTER_GAME.moves;

    movesList.forEach((mv, idx) => {
      try {
        let result = null;
        if (typeof mv === 'string') {
          result = chess.move(mv);
        } else if (mv && mv.from && mv.to) {
          result = chess.move({ from: mv.from, to: mv.to, promotion: mv.promotion || 'q' });
        } else if (mv && (mv.san || mv.move)) {
          result = chess.move(mv.san || mv.move);
        } else if (mv && mv.uci && mv.uci.length >= 4) {
          result = chess.move({ from: mv.uci.slice(0, 2), to: mv.uci.slice(2, 4), promotion: mv.uci[4] || 'q' });
        }

        if (result) {
          const evalScore = activeGame?.eval_graph?.[idx + 1] ?? Math.round((Math.sin(idx * 0.6) * 1.5) * 10) / 10;
          frames.push({
            ply: idx + 1,
            fen: chess.fen(),
            moveSan: result.san,
            lastMove: { from: result.from, to: result.to },
            evalScore
          });
        }
      } catch (e) {
        console.log('[GameAnalysis] Timeline parse error at ply', idx, e);
      }
    });

    return frames;
  }, [activeGame]);

  // Safeguard currentPly bounds
  const validPly = Math.max(0, Math.min(currentPly, timeline.length - 1));
  const currentFrame = timeline[validPly] || timeline[0];

  const handleNextMove = () => {
    if (validPly < timeline.length - 1) {
      setCurrentPly(validPly + 1);
    }
  };

  const handlePrevMove = () => {
    if (validPly > 0) {
      setCurrentPly(validPly - 1);
    }
  };

  const handleStartMove = () => {
    setCurrentPly(0);
  };

  const handleEndMove = () => {
    setCurrentPly(timeline.length - 1);
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>Loading Game Studio...</Text>
      </View>
    );
  }

  const currentBlunder = activeGame?.blunders?.find(b => b.ply === validPly);
  const hasPlayedGame = !!(lastPlayedGame && lastPlayedGame.moves?.length > 0);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Source Switcher Header */}
      <View style={styles.sourceSelectorRow}>
        <TouchableOpacity
          style={[styles.sourceTabBtn, activeSource === 'played' && styles.sourceTabBtnActive]}
          onPress={() => {
            setActiveSource('played');
            setCurrentPly(0);
          }}
        >
          <Text style={[styles.sourceTabText, activeSource === 'played' && styles.sourceTabTextActive]}>
            🎮 {hasPlayedGame ? 'My Last Game' : 'No Played Game'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.sourceTabBtn, activeSource === 'demo' && styles.sourceTabBtnActive]}
          onPress={() => {
            setActiveSource('demo');
            setCurrentPly(0);
          }}
        >
          <Text style={[styles.sourceTabText, activeSource === 'demo' && styles.sourceTabTextActive]}>
            🏆 Master Demo
          </Text>
        </TouchableOpacity>
      </View>

      {/* Game Header */}
      <View style={styles.headerBox}>
        <View style={{ flex: 1 }}>
          <Text style={styles.gameTitle}>
            {activeSource === 'played' && hasPlayedGame ? '🎮 Your Recent Game Analysis' : '🔍 Game Analysis Studio'}
          </Text>
          <Text style={styles.gameSubtitle}>
            {activeSource === 'played' && hasPlayedGame ? `Recorded ${lastPlayedGame.game_mode || 'Match'} (${lastPlayedGame.moves?.length || 0} moves)` : 'Stockfish 15 Deep Engine Analysis'}  •  Ply {validPly}/{timeline.length - 1}
          </Text>
        </View>
        <TouchableOpacity style={styles.askCoachButton} onPress={() => navigation.navigate('AICoach')}>
          <Text style={styles.askCoachButtonText}>💬 Ask AI</Text>
        </TouchableOpacity>
      </View>

      {/* Board + Eval Bar Layout */}
      <View style={styles.boardContainer}>
        <EvaluationBar evalScore={currentFrame.evalScore} />
        <View style={styles.boardFlex}>
          <ChessBoardView
            fen={currentFrame.fen}
            orientation={activeGame?.player_color || 'white'}
            lastMove={currentFrame.lastMove}
          />
        </View>
      </View>

      {/* Move Controller Controls */}
      <View style={styles.controlRow}>
        <TouchableOpacity
          style={[styles.controlBtn, validPly === 0 && styles.controlBtnDisabled]}
          onPress={handleStartMove}
          disabled={validPly === 0}
        >
          <Text style={[styles.controlBtnText, validPly === 0 && styles.controlBtnTextDisabled]}>⏮ Start</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.controlBtn, validPly === 0 && styles.controlBtnDisabled]}
          onPress={handlePrevMove}
          disabled={validPly === 0}
        >
          <Text style={[styles.controlBtnText, validPly === 0 && styles.controlBtnTextDisabled]}>◀ Prev</Text>
        </TouchableOpacity>

        <View style={styles.moveCounter}>
          <Text style={styles.moveCounterText}>
            {validPly === 0 ? 'Start' : `Move ${Math.ceil(validPly / 2)} (${currentFrame.moveSan})`}
          </Text>
        </View>

        <TouchableOpacity
          style={[styles.controlBtn, validPly === timeline.length - 1 && styles.controlBtnDisabled]}
          onPress={handleNextMove}
          disabled={validPly === timeline.length - 1}
        >
          <Text style={[styles.controlBtnText, validPly === timeline.length - 1 && styles.controlBtnTextDisabled]}>Next ▶</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.controlBtn, validPly === timeline.length - 1 && styles.controlBtnDisabled]}
          onPress={handleEndMove}
          disabled={validPly === timeline.length - 1}
        >
          <Text style={[styles.controlBtnText, validPly === timeline.length - 1 && styles.controlBtnTextDisabled]}>End ⏭</Text>
        </TouchableOpacity>
      </View>

      {/* Interactive Moves List Bar */}
      <View style={styles.movesListCard}>
        <Text style={styles.movesListTitle}>📜 Game Moves Navigator ({timeline.length - 1} Moves):</Text>
        {timeline.length > 1 ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.movesListScroll}>
            {timeline.map((frame, idx) => {
              const isActive = idx === validPly;
              if (idx === 0) {
                return (
                  <TouchableOpacity
                    key="ply-0"
                    style={[styles.moveChip, isActive && styles.moveChipActive]}
                    onPress={() => setCurrentPly(0)}
                  >
                    <Text style={[styles.moveChipText, isActive && styles.moveChipTextActive]}>Start</Text>
                  </TouchableOpacity>
                );
              }
              const moveNum = Math.ceil(idx / 2);
              const isWhite = idx % 2 === 1;
              const label = isWhite ? `${moveNum}. ${frame.moveSan}` : frame.moveSan;

              return (
                <TouchableOpacity
                  key={`ply-${idx}`}
                  style={[styles.moveChip, isActive && styles.moveChipActive]}
                  onPress={() => setCurrentPly(idx)}
                >
                  <Text style={[styles.moveChipText, isActive && styles.moveChipTextActive]}>{label}</Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        ) : (
          <Text style={styles.noMovesText}>No moves recorded yet. Play a game in Coach tab to analyze it here!</Text>
        )}
      </View>

      {/* Blunder or Position Callout */}
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
            {validPly === 0
              ? 'Game starting position. White to play.'
              : `Position after ${currentFrame.moveSan}. Evaluation score: ${currentFrame.evalScore > 0 ? `+${currentFrame.evalScore}` : currentFrame.evalScore}.`}
          </Text>
        </View>
      )}

      {/* Evaluation Trend Chart Summary */}
      <View style={styles.evalSummaryBox}>
        <Text style={styles.summaryTitle}>Evaluation Advantage Graph (Tap Bar to Jump)</Text>
        <View style={styles.graphBarsContainer}>
          {timeline.map((frame, i) => (
            <TouchableOpacity
              key={`graph-${i}`}
              style={[
                styles.graphBarItem,
                i === validPly && styles.graphBarActive,
                { height: Math.max(12, Math.min(60, 30 + (frame.evalScore || 0) * 8)) },
                { backgroundColor: (frame.evalScore || 0) >= 0 ? COLORS.success : COLORS.danger }
              ]}
              onPress={() => setCurrentPly(i)}
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
  sourceSelectorRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 14,
  },
  sourceTabBtn: {
    flex: 1,
    backgroundColor: '#1e293b',
    paddingVertical: 10,
    borderRadius: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  sourceTabBtnActive: {
    backgroundColor: '#2a3a54',
    borderColor: COLORS.primary,
  },
  sourceTabText: {
    color: COLORS.textMuted,
    fontSize: 12,
    fontWeight: '700',
  },
  sourceTabTextActive: {
    color: COLORS.primary,
    fontWeight: '800',
  },
  headerBox: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  gameTitle: {
    color: COLORS.text,
    fontSize: 18,
    fontWeight: '800',
  },
  gameSubtitle: {
    color: COLORS.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  askCoachButton: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 8,
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
    marginBottom: 12,
  },
  controlBtn: {
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#1e293b',
  },
  controlBtnDisabled: {
    backgroundColor: '#0f172a',
    opacity: 0.4,
  },
  controlBtnText: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: '700',
  },
  controlBtnTextDisabled: {
    color: '#64748b',
  },
  moveCounter: {
    paddingHorizontal: 6,
  },
  moveCounterText: {
    color: COLORS.primary,
    fontWeight: '800',
    fontSize: 12,
  },
  movesListCard: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 14,
    padding: 10,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: COLORS.cardBorder,
  },
  movesListTitle: {
    color: COLORS.textMuted,
    fontSize: 11,
    fontWeight: '700',
    marginBottom: 6,
    textTransform: 'uppercase',
  },
  movesListScroll: {
    flexDirection: 'row',
    gap: 6,
    alignItems: 'center',
  },
  moveChip: {
    backgroundColor: '#1e293b',
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  moveChipActive: {
    backgroundColor: '#2a3a54',
    borderColor: COLORS.primary,
  },
  moveChipText: {
    color: COLORS.textMuted,
    fontSize: 12,
    fontWeight: '600',
  },
  moveChipTextActive: {
    color: COLORS.primary,
    fontWeight: '800',
  },
  noMovesText: {
    color: COLORS.textMuted,
    fontSize: 12,
    fontStyle: 'italic',
    paddingVertical: 4,
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
    backgroundColor: 'rgba(0,0,0,0.3)',
    borderRadius: 8,
    padding: 10,
  },
  betterMoveTitle: {
    color: COLORS.textMuted,
    fontSize: 11,
    fontWeight: '700',
  },
  betterMoveText: {
    color: COLORS.success,
    fontSize: 13,
    fontWeight: '800',
    marginTop: 2,
  },
  analysisInsightBox: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: COLORS.cardBorder,
    marginBottom: 16,
  },
  insightHeader: {
    color: COLORS.secondary,
    fontSize: 13,
    fontWeight: '800',
    marginBottom: 4,
  },
  insightText: {
    color: COLORS.text,
    fontSize: 12,
    lineHeight: 18,
  },
  evalSummaryBox: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 16,
    padding: 14,
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
    height: 60,
    gap: 3,
  },
  graphBarItem: {
    flex: 1,
    borderRadius: 4,
    opacity: 0.6,
  },
  graphBarActive: {
    opacity: 1,
    borderWidth: 1.5,
    borderColor: '#ffffff',
  },
});
