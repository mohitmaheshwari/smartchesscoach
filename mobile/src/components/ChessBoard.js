import React, { useState, useMemo } from 'react';
import { View, StyleSheet, Text, TouchableOpacity, Dimensions } from 'react-native';
import { Chess } from 'chess.js';
import { useTheme } from '../context/ThemeContext';

const { width } = Dimensions.get('window');
const BOARD_SIZE = width - 32;
const SQUARE_SIZE = BOARD_SIZE / 8;

// Chess piece Unicode symbols
const PIECE_SYMBOLS = {
  'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
  'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
};

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
const RANKS = ['8', '7', '6', '5', '4', '3', '2', '1'];

/**
 * Simple Chess Board Component (no WebView)
 */
export const ChessBoardViewer = ({ 
  pgn, 
  currentMoveIndex = -1,
  userColor = 'white'
}) => {
  const { colors } = useTheme();
  
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
              color: piece.color === 'w' ? '#fff' : '#000',
              textShadowColor: piece.color === 'w' ? '#000' : '#fff',
            }
          ]}>
            {pieceSymbol}
          </Text>
        )}
        
        {/* Coordinates */}
        {col === 0 && (
          <Text style={[styles.coordRank, { color: isLight ? darkSquare : lightSquare }]}>
            {RANKS[displayRow]}
          </Text>
        )}
        {row === 7 && (
          <Text style={[styles.coordFile, { color: isLight ? darkSquare : lightSquare }]}>
            {FILES[displayCol]}
          </Text>
        )}
      </View>
    );
  };
  
  return (
    <View style={styles.container}>
      <View style={[styles.board, { width: BOARD_SIZE, height: BOARD_SIZE }]}>
        {Array(8).fill(0).map((_, row) => (
          <View key={row} style={styles.row}>
            {Array(8).fill(0).map((_, col) => renderSquare(row, col))}
          </View>
        ))}
      </View>
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
  const isAtStart = currentMove <= 0;
  const isAtEnd = currentMove >= totalMoves;
  
  return (
    <View style={[styles.navContainer, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <TouchableOpacity 
        style={[styles.navButton, { borderColor: colors.border, opacity: isAtStart ? 0.4 : 1 }]}
        onPress={onFirst}
        disabled={isAtStart}
      >
        <Text style={[styles.navIcon, { color: colors.text }]}>⏮</Text>
      </TouchableOpacity>
      
      <TouchableOpacity 
        style={[styles.navButton, { borderColor: colors.border, opacity: isAtStart ? 0.4 : 1 }]}
        onPress={onPrevious}
        disabled={isAtStart}
      >
        <Text style={[styles.navIcon, { color: colors.text }]}>◀</Text>
      </TouchableOpacity>
      
      <View style={styles.moveCounter}>
        <Text style={[styles.counterText, { color: colors.textSecondary }]}>
          {currentMove} / {totalMoves}
        </Text>
      </View>
      
      <TouchableOpacity 
        style={[styles.navButton, { borderColor: colors.border, opacity: isAtEnd ? 0.4 : 1 }]}
        onPress={onNext}
        disabled={isAtEnd}
      >
        <Text style={[styles.navIcon, { color: colors.text }]}>▶</Text>
      </TouchableOpacity>
      
      <TouchableOpacity 
        style={[styles.navButton, { borderColor: colors.border, opacity: isAtEnd ? 0.4 : 1 }]}
        onPress={onLast}
        disabled={isAtEnd}
      >
        <Text style={[styles.navIcon, { color: colors.text }]}>⏭</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  board: {
    borderRadius: 8,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
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
    fontSize: SQUARE_SIZE * 0.7,
    textShadowOffset: { width: 1, height: 1 },
    textShadowRadius: 2,
  },
  coordRank: {
    position: 'absolute',
    top: 2,
    left: 3,
    fontSize: 10,
    fontWeight: '600',
  },
  coordFile: {
    position: 'absolute',
    bottom: 1,
    right: 3,
    fontSize: 10,
    fontWeight: '600',
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

export default ChessBoardViewer;
