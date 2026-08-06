import React, { useRef, useEffect } from 'react';
import { View, StyleSheet, Dimensions } from 'react-native';
import Chessboard from 'react-native-chessboard';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { COLORS } from '../constants/config';

const { width } = Dimensions.get('window');
const BOARD_SIZE = Math.min(width - 32, 360);

export const ChessBoardView = ({
  fen = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
  orientation = 'white',
  onMove,
  onGameOver
}) => {
  const boardRef = useRef(null);

  // Sync FEN & orientation updates to Chessboard
  useEffect(() => {
    if (boardRef.current && boardRef.current.resetBoard) {
      boardRef.current.resetBoard(fen);
    }
  }, [fen]);

  const handleMove = (result) => {
    if (result && result.move) {
      const from = result.move.from;
      const to = result.move.to;
      
      if (onMove) {
        onMove({ from, to });
      }

      // Check for checkmate/draw in state to notify parent
      if (result.state) {
        if (result.state.isCheckmate) {
          const winner = result.state.turn === 'w' ? 'Black' : 'White';
          if (onGameOver) {
            onGameOver({ type: 'GAME_OVER', reason: 'CHECKMATE', winner });
          }
        } else if (result.state.isDraw || result.state.isStalemate) {
          if (onGameOver) {
            onGameOver({ type: 'GAME_OVER', reason: 'STALEMATE' });
          }
        }
      }
    }
  };

  return (
    <GestureHandlerRootView style={styles.container}>
      <View style={styles.boardWrapper}>
        <Chessboard
          ref={boardRef}
          fen={fen}
          boardSize={BOARD_SIZE - 4}
          flipped={orientation === 'black'}
          gestureEnabled={!!onMove}
          withLetters={true}
          withNumbers={true}
          onMove={handleMove}
        />
      </View>
    </GestureHandlerRootView>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: 12,
  },
  boardWrapper: {
    width: BOARD_SIZE,
    height: BOARD_SIZE,
    borderRadius: 14,
    overflow: 'hidden',
    borderWidth: 2,
    borderColor: 'rgba(255, 255, 255, 0.35)',
    backgroundColor: COLORS.cardBg,
    elevation: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.5,
    shadowRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
