import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { View, StyleSheet, Dimensions, TouchableOpacity, Text } from 'react-native';
import Chessboard from 'react-native-chessboard';
import { Chess } from 'chess.js';
import { useTheme } from '../context/ThemeContext';

const { width } = Dimensions.get('window');
const BOARD_SIZE = width - 32;

/**
 * Interactive Chess Board Component
 * Displays a chessboard that can navigate through game moves
 */
export const ChessBoardViewer = ({ 
  pgn, 
  currentMoveIndex = 0,
  onMoveChange,
  userColor = 'white'
}) => {
  const { colors } = useTheme();
  const [fen, setFen] = useState('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
  const [moves, setMoves] = useState([]);
  
  // Parse PGN and extract moves
  useEffect(() => {
    if (!pgn) return;
    
    try {
      const chess = new Chess();
      chess.loadPgn(pgn);
      
      // Get all moves
      const history = chess.history({ verbose: true });
      setMoves(history);
      
      // Reset to starting position
      chess.reset();
      
      // Apply moves up to current index
      for (let i = 0; i <= Math.min(currentMoveIndex, history.length - 1); i++) {
        chess.move(history[i]);
      }
      
      setFen(chess.fen());
    } catch (error) {
      console.error('Failed to parse PGN:', error);
    }
  }, [pgn, currentMoveIndex]);
  
  // Board orientation
  const boardOrientation = userColor === 'black' ? 'black' : 'white';
  
  // Custom colors for the board
  const boardColors = {
    white: colors.background === '#0a0a0a' ? '#e8e8e8' : '#f0d9b5',
    black: colors.background === '#0a0a0a' ? '#5d7a99' : '#b58863',
  };

  return (
    <View style={styles.container}>
      <Chessboard
        fen={fen}
        boardSize={BOARD_SIZE}
        gestureEnabled={false}
        colors={{
          white: boardColors.white,
          black: boardColors.black,
          lastMoveHighlight: 'rgba(255, 255, 0, 0.4)',
          checkmateHighlight: 'rgba(255, 0, 0, 0.4)',
        }}
        boardOrientation={boardOrientation}
      />
      
      {/* Current move indicator */}
      {moves.length > 0 && currentMoveIndex >= 0 && currentMoveIndex < moves.length && (
        <View style={[styles.moveIndicator, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Text style={[styles.moveNumber, { color: colors.textSecondary }]}>
            Move {Math.floor(currentMoveIndex / 2) + 1}
            {currentMoveIndex % 2 === 0 ? '.' : '...'}
          </Text>
          <Text style={[styles.moveText, { color: colors.text }]}>
            {moves[currentMoveIndex]?.san || ''}
          </Text>
        </View>
      )}
    </View>
  );
};

/**
 * Move Navigation Controls
 */
export const MoveNavigation = ({ 
  currentMove, 
  totalMoves, 
  onFirst, 
  onPrevious, 
  onNext, 
  onLast 
}) => {
  const { colors } = useTheme();
  
  return (
    <View style={[styles.navContainer, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <TouchableOpacity 
        style={[styles.navButton, { borderColor: colors.border }]}
        onPress={onFirst}
        disabled={currentMove <= 0}
      >
        <Text style={[styles.navIcon, { color: currentMove <= 0 ? colors.textSecondary : colors.text }]}>
          ⏮
        </Text>
      </TouchableOpacity>
      
      <TouchableOpacity 
        style={[styles.navButton, { borderColor: colors.border }]}
        onPress={onPrevious}
        disabled={currentMove <= 0}
      >
        <Text style={[styles.navIcon, { color: currentMove <= 0 ? colors.textSecondary : colors.text }]}>
          ◀
        </Text>
      </TouchableOpacity>
      
      <View style={styles.moveCounter}>
        <Text style={[styles.counterText, { color: colors.textSecondary }]}>
          {currentMove + 1} / {totalMoves}
        </Text>
      </View>
      
      <TouchableOpacity 
        style={[styles.navButton, { borderColor: colors.border }]}
        onPress={onNext}
        disabled={currentMove >= totalMoves - 1}
      >
        <Text style={[styles.navIcon, { color: currentMove >= totalMoves - 1 ? colors.textSecondary : colors.text }]}>
          ▶
        </Text>
      </TouchableOpacity>
      
      <TouchableOpacity 
        style={[styles.navButton, { borderColor: colors.border }]}
        onPress={onLast}
        disabled={currentMove >= totalMoves - 1}
      >
        <Text style={[styles.navIcon, { color: currentMove >= totalMoves - 1 ? colors.textSecondary : colors.text }]}>
          ⏭
        </Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  moveIndicator: {
    position: 'absolute',
    bottom: 8,
    left: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  moveNumber: {
    fontSize: 12,
  },
  moveText: {
    fontSize: 16,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  navContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1,
    marginTop: 12,
    gap: 8,
  },
  navButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
  },
  navIcon: {
    fontSize: 18,
  },
  moveCounter: {
    paddingHorizontal: 16,
  },
  counterText: {
    fontSize: 14,
    fontFamily: 'monospace',
  },
});
