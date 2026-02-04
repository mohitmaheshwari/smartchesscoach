import React, { useState, useMemo, useRef } from 'react';
import { View, StyleSheet, Text, TouchableOpacity, Dimensions, PanResponder, Animated } from 'react-native';
import { Chess } from 'chess.js';
import { useTheme } from '../context/ThemeContext';

const { width } = Dimensions.get('window');

// Chess piece Unicode symbols
const PIECE_SYMBOLS = {
  'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
  'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
};

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
const RANKS = ['8', '7', '6', '5', '4', '3', '2', '1'];

/**
 * Chess Board Component with Swipe Navigation
 */
export const ChessBoardViewer = ({ 
  pgn, 
  currentMoveIndex = -1,
  userColor = 'white',
  onSwipeLeft,
  onSwipeRight,
  boardSize,
}) => {
  const { colors } = useTheme();
  const panX = useRef(new Animated.Value(0)).current;
  
  // Calculate board size
  const BOARD_SIZE = boardSize || (width - 24);
  const SQUARE_SIZE = BOARD_SIZE / 8;
  
  // Swipe gesture handler
  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: (_, gestureState) => {
        return Math.abs(gestureState.dx) > 10;
      },
      onPanResponderMove: (_, gestureState) => {
        panX.setValue(gestureState.dx * 0.3);
      },
      onPanResponderRelease: (_, gestureState) => {
        // Detect swipe direction
        if (gestureState.dx > 50 && onSwipeRight) {
          onSwipeRight(); // Previous move
        } else if (gestureState.dx < -50 && onSwipeLeft) {
          onSwipeLeft(); // Next move
        }
        // Animate back to center
        Animated.spring(panX, {
          toValue: 0,
          useNativeDriver: true,
          tension: 100,
          friction: 10,
        }).start();
      },
    })
  ).current;
  
  // Parse PGN and get position at current move
  const { board, currentMove } = useMemo(() => {
    const chess = new Chess();
    let history = [];
    let currentMoveData = null;
    
    try {
      if (pgn) {
        chess.loadPgn(pgn);
        history = chess.history({ verbose: true });
        chess.reset();
        
        // Replay to current position
        const moveIdx = currentMoveIndex >= 0 ? Math.min(currentMoveIndex, history.length - 1) : -1;
        for (let i = 0; i <= moveIdx; i++) {
          chess.move(history[i]);
        }
        
        if (moveIdx >= 0 && moveIdx < history.length) {
          currentMoveData = history[moveIdx];
        }
      }
    } catch (e) {
      console.log('PGN parse error:', e);
    }
    
    return { 
      board: chess.board(),
      currentMove: currentMoveData
    };
  }, [pgn, currentMoveIndex]);
  
  const isFlipped = userColor === 'black';
  const lightSquare = '#f0d9b5';
  const darkSquare = '#b58863';
  const highlightColor = 'rgba(255, 255, 0, 0.5)';
  
  // Get highlighted squares from last move
  const highlightSquares = currentMove ? [currentMove.from, currentMove.to] : [];
  
  const renderSquare = (row, col) => {
    const displayRow = isFlipped ? 7 - row : row;
    const displayCol = isFlipped ? 7 - col : col;
    
    const squareName = FILES[displayCol] + RANKS[displayRow];
    const isLight = (displayRow + displayCol) % 2 === 0;
    const isHighlighted = highlightSquares.includes(squareName);
    
    const piece = board[displayRow]?.[displayCol];
    const pieceSymbol = piece ? PIECE_SYMBOLS[piece.color === 'w' ? piece.type.toUpperCase() : piece.type] : null;
    
    return (
      <View 
        key={`${row}-${col}`}
        style={[
          styles.square,
          { 
            backgroundColor: isHighlighted ? highlightColor : (isLight ? lightSquare : darkSquare),
            width: SQUARE_SIZE,
            height: SQUARE_SIZE,
          }
        ]}
      >
        {pieceSymbol && (
          <Text style={[
            styles.piece,
            { 
              fontSize: SQUARE_SIZE * 0.75,
              color: piece.color === 'w' ? '#fff' : '#000',
              textShadowColor: piece.color === 'w' ? '#000' : '#fff',
            }
          ]}>
            {pieceSymbol}
          </Text>
        )}
        
        {/* Coordinates - only on edges */}
        {col === 0 && (
          <Text style={[styles.coordRank, { color: isLight ? darkSquare : lightSquare, fontSize: SQUARE_SIZE * 0.22 }]}>
            {RANKS[displayRow]}
          </Text>
        )}
        {row === 7 && (
          <Text style={[styles.coordFile, { color: isLight ? darkSquare : lightSquare, fontSize: SQUARE_SIZE * 0.22 }]}>
            {FILES[displayCol]}
          </Text>
        )}
      </View>
    );
  };
  
  return (
    <View style={styles.container}>
      <Animated.View 
        style={[
          styles.board, 
          { 
            width: BOARD_SIZE, 
            height: BOARD_SIZE,
            transform: [{ translateX: panX }]
          }
        ]}
        {...panResponder.panHandlers}
      >
        {Array(8).fill(0).map((_, row) => (
          <View key={row} style={styles.row}>
            {Array(8).fill(0).map((_, col) => renderSquare(row, col))}
          </View>
        ))}
      </Animated.View>
    </View>
  );
};

/**
 * Evaluation Bar Component - Shows position evaluation
 */
export const EvalBar = ({ evaluation, style }) => {
  // evaluation: number from -10 to 10 (centipawns/100)
  // positive = white advantage, negative = black advantage
  const { colors } = useTheme();
  
  const clampedEval = Math.max(-10, Math.min(10, evaluation || 0));
  const whitePercent = 50 + (clampedEval * 5); // Convert to percentage
  
  const displayText = evaluation > 0 
    ? `+${Math.abs(evaluation).toFixed(1)}` 
    : evaluation < 0 
      ? `-${Math.abs(evaluation).toFixed(1)}`
      : '0.0';
  
  return (
    <View style={[styles.evalBarContainer, style]}>
      <View style={styles.evalBar}>
        <View style={[styles.evalWhite, { height: `${whitePercent}%` }]} />
        <View style={[styles.evalBlack, { height: `${100 - whitePercent}%` }]} />
      </View>
      <Text style={[styles.evalText, { color: colors.textSecondary }]}>{displayText}</Text>
    </View>
  );
};

/**
 * Compact Move Navigation Controls
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
  const isAtStart = currentMove <= -1;
  const isAtEnd = currentMove >= totalMoves - 1;
  
  const NavButton = ({ onPress, disabled, icon }) => (
    <TouchableOpacity 
      style={[
        styles.navButton, 
        { 
          backgroundColor: disabled ? colors.border : colors.card,
          borderColor: colors.border,
        }
      ]}
      onPress={onPress}
      disabled={disabled}
      activeOpacity={0.7}
    >
      <Text style={[styles.navIcon, { color: disabled ? colors.textSecondary : colors.text, opacity: disabled ? 0.4 : 1 }]}>
        {icon}
      </Text>
    </TouchableOpacity>
  );
  
  return (
    <View style={[styles.navContainer, { backgroundColor: colors.background }]}>
      <NavButton onPress={onFirst} disabled={isAtStart} icon="⏮" />
      <NavButton onPress={onPrevious} disabled={isAtStart} icon="◀" />
      <View style={styles.moveCounter}>
        <Text style={[styles.counterText, { color: colors.text }]}>
          {currentMove + 1} <Text style={{ color: colors.textSecondary }}>/ {totalMoves}</Text>
        </Text>
      </View>
      <NavButton onPress={onNext} disabled={isAtEnd} icon="▶" />
      <NavButton onPress={onLast} disabled={isAtEnd} icon="⏭" />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  board: {
    borderRadius: 4,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },
  row: {
    flexDirection: 'row',
  },
  square: {
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  piece: {
    textShadowOffset: { width: 1, height: 1 },
    textShadowRadius: 1,
  },
  coordRank: {
    position: 'absolute',
    top: 1,
    left: 2,
    fontWeight: '700',
  },
  coordFile: {
    position: 'absolute',
    bottom: 0,
    right: 2,
    fontWeight: '700',
  },
  
  // Eval bar styles
  evalBarContainer: {
    alignItems: 'center',
    width: 24,
  },
  evalBar: {
    width: 16,
    flex: 1,
    borderRadius: 2,
    overflow: 'hidden',
    flexDirection: 'column-reverse',
  },
  evalWhite: {
    backgroundColor: '#f5f5f5',
  },
  evalBlack: {
    backgroundColor: '#262626',
  },
  evalText: {
    fontSize: 9,
    fontWeight: '600',
    marginTop: 2,
  },
  
  // Navigation styles
  navContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    gap: 8,
  },
  navButton: {
    width: 40,
    height: 40,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
  },
  navIcon: {
    fontSize: 16,
  },
  moveCounter: {
    paddingHorizontal: 12,
    minWidth: 70,
    alignItems: 'center',
  },
  counterText: {
    fontSize: 14,
    fontWeight: '600',
  },
});

export default ChessBoardViewer;
