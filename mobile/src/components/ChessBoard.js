import React, { useState, useEffect, useRef, useMemo } from 'react';
import { View, StyleSheet, Dimensions, TouchableOpacity, Text, Platform } from 'react-native';
import { WebView } from 'react-native-webview';
import { Chess } from 'chess.js';
import { useTheme } from '../context/ThemeContext';

const { width } = Dimensions.get('window');
const BOARD_SIZE = width - 32;

/**
 * Interactive Chess Board Component using WebView
 * Displays a chessboard that can navigate through game moves
 */
export const ChessBoardViewer = ({ 
  pgn, 
  currentMoveIndex = -1,
  onMoveChange,
  userColor = 'white'
}) => {
  const { colors } = useTheme();
  const webviewRef = useRef(null);
  const [isReady, setIsReady] = useState(false);
  
  // Parse PGN and compute FEN for current position
  const { fen, moves, currentMove } = useMemo(() => {
    if (!pgn) {
      return { 
        fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', 
        moves: [],
        currentMove: null
      };
    }
    
    try {
      const chess = new Chess();
      chess.loadPgn(pgn);
      
      // Get all moves
      const history = chess.history({ verbose: true });
      
      // Reset and replay to current position
      chess.reset();
      
      const moveIdx = currentMoveIndex >= 0 ? Math.min(currentMoveIndex, history.length - 1) : -1;
      
      for (let i = 0; i <= moveIdx; i++) {
        chess.move(history[i]);
      }
      
      return { 
        fen: chess.fen(), 
        moves: history,
        currentMove: moveIdx >= 0 ? history[moveIdx] : null
      };
    } catch (error) {
      console.error('Failed to parse PGN:', error);
      return { 
        fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', 
        moves: [],
        currentMove: null
      };
    }
  }, [pgn, currentMoveIndex]);

  // Board colors based on theme
  const lightSquare = colors.background === '#0a0a0a' ? '#e8e8e8' : '#f0d9b5';
  const darkSquare = colors.background === '#0a0a0a' ? '#5d7a99' : '#b58863';
  const highlightColor = 'rgba(255, 255, 0, 0.5)';
  
  const orientation = userColor === 'black' ? 'black' : 'white';

  // HTML content for the chessboard
  const htmlContent = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
          display: flex; 
          justify-content: center; 
          align-items: center; 
          background: transparent;
          overflow: hidden;
          touch-action: none;
        }
        .board-container {
          width: ${BOARD_SIZE}px;
          height: ${BOARD_SIZE}px;
        }
        .board {
          display: grid;
          grid-template-columns: repeat(8, 1fr);
          width: 100%;
          height: 100%;
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .square {
          display: flex;
          justify-content: center;
          align-items: center;
          font-size: ${BOARD_SIZE / 10}px;
          user-select: none;
          -webkit-user-select: none;
        }
        .light { background: ${lightSquare}; }
        .dark { background: ${darkSquare}; }
        .highlight { background: ${highlightColor} !important; }
        .piece {
          font-family: 'Arial Unicode MS', sans-serif;
          text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
        }
        .coord {
          position: absolute;
          font-size: 10px;
          font-weight: 600;
          opacity: 0.6;
        }
        .coord-file { bottom: 2px; right: 4px; }
        .coord-rank { top: 2px; left: 4px; }
        .square { position: relative; }
      </style>
    </head>
    <body>
      <div class="board-container">
        <div class="board" id="board"></div>
      </div>
      <script>
        const pieceSymbols = {
          'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
          'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
        };
        
        const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
        const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];
        
        function fenToBoard(fen) {
          const parts = fen.split(' ');
          const position = parts[0];
          const rows = position.split('/');
          const board = [];
          
          for (const row of rows) {
            const boardRow = [];
            for (const char of row) {
              if (char >= '1' && char <= '8') {
                for (let i = 0; i < parseInt(char); i++) {
                  boardRow.push('');
                }
              } else {
                boardRow.push(char);
              }
            }
            board.push(boardRow);
          }
          return board;
        }
        
        function renderBoard(fen, orientation, lastMove) {
          const boardEl = document.getElementById('board');
          boardEl.innerHTML = '';
          
          const board = fenToBoard(fen);
          const isFlipped = orientation === 'black';
          
          // Get highlight squares from last move
          const highlightSquares = [];
          if (lastMove) {
            highlightSquares.push(lastMove.from);
            highlightSquares.push(lastMove.to);
          }
          
          for (let r = 0; r < 8; r++) {
            for (let f = 0; f < 8; f++) {
              const displayR = isFlipped ? 7 - r : r;
              const displayF = isFlipped ? 7 - f : f;
              
              const square = document.createElement('div');
              const isLight = (displayR + displayF) % 2 === 0;
              const squareName = files[displayF] + ranks[displayR];
              
              square.className = 'square ' + (isLight ? 'light' : 'dark');
              
              if (highlightSquares.includes(squareName)) {
                square.classList.add('highlight');
              }
              
              const piece = board[displayR][displayF];
              if (piece) {
                const pieceEl = document.createElement('span');
                pieceEl.className = 'piece';
                pieceEl.textContent = pieceSymbols[piece] || '';
                square.appendChild(pieceEl);
              }
              
              // Add coordinates on edge squares
              if (f === 7) {
                const rankCoord = document.createElement('span');
                rankCoord.className = 'coord coord-rank';
                rankCoord.style.color = isLight ? '${darkSquare}' : '${lightSquare}';
                rankCoord.textContent = ranks[displayR];
                square.appendChild(rankCoord);
              }
              if (r === 7) {
                const fileCoord = document.createElement('span');
                fileCoord.className = 'coord coord-file';
                fileCoord.style.color = isLight ? '${darkSquare}' : '${lightSquare}';
                fileCoord.textContent = files[displayF];
                square.appendChild(fileCoord);
              }
              
              boardEl.appendChild(square);
            }
          }
        }
        
        // Initial render
        window.updateBoard = function(fen, orientation, lastMove) {
          renderBoard(fen, orientation, lastMove);
        };
        
        // Signal ready
        window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'ready' }));
      </script>
    </body>
    </html>
  `;

  // Update board when FEN changes
  useEffect(() => {
    if (isReady && webviewRef.current) {
      const lastMoveData = currentMove ? JSON.stringify({ from: currentMove.from, to: currentMove.to }) : 'null';
      webviewRef.current.injectJavaScript(`
        window.updateBoard('${fen}', '${orientation}', ${lastMoveData});
        true;
      `);
    }
  }, [fen, orientation, currentMove, isReady]);

  const handleMessage = (event) => {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      if (data.type === 'ready') {
        setIsReady(true);
        // Initial render
        const lastMoveData = currentMove ? JSON.stringify({ from: currentMove.from, to: currentMove.to }) : 'null';
        webviewRef.current?.injectJavaScript(`
          window.updateBoard('${fen}', '${orientation}', ${lastMoveData});
          true;
        `);
      }
    } catch (e) {
      console.log('WebView message:', event.nativeEvent.data);
    }
  };

  return (
    <View style={styles.container}>
      <WebView
        ref={webviewRef}
        source={{ html: htmlContent }}
        style={[styles.webview, { width: BOARD_SIZE, height: BOARD_SIZE }]}
        scrollEnabled={false}
        bounces={false}
        onMessage={handleMessage}
        originWhitelist={['*']}
        javaScriptEnabled={true}
        domStorageEnabled={true}
        showsHorizontalScrollIndicator={false}
        showsVerticalScrollIndicator={false}
        overScrollMode="never"
        scalesPageToFit={Platform.OS === 'android'}
        setBuiltInZoomControls={false}
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
  const isAtStart = currentMove <= 0;
  const isAtEnd = currentMove >= totalMoves - 1;
  
  return (
    <View style={[styles.navContainer, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <TouchableOpacity 
        style={[styles.navButton, { borderColor: colors.border, opacity: isAtStart ? 0.4 : 1 }]}
        onPress={onFirst}
        disabled={isAtStart}
        activeOpacity={0.7}
      >
        <Text style={[styles.navIcon, { color: colors.text }]}>⏮</Text>
      </TouchableOpacity>
      
      <TouchableOpacity 
        style={[styles.navButton, { borderColor: colors.border, opacity: isAtStart ? 0.4 : 1 }]}
        onPress={onPrevious}
        disabled={isAtStart}
        activeOpacity={0.7}
      >
        <Text style={[styles.navIcon, { color: colors.text }]}>◀</Text>
      </TouchableOpacity>
      
      <View style={styles.moveCounter}>
        <Text style={[styles.counterText, { color: colors.textSecondary }]}>
          {Math.max(currentMove, 0) + 1} / {Math.max(totalMoves, 1)}
        </Text>
      </View>
      
      <TouchableOpacity 
        style={[styles.navButton, { borderColor: colors.border, opacity: isAtEnd ? 0.4 : 1 }]}
        onPress={onNext}
        disabled={isAtEnd}
        activeOpacity={0.7}
      >
        <Text style={[styles.navIcon, { color: colors.text }]}>▶</Text>
      </TouchableOpacity>
      
      <TouchableOpacity 
        style={[styles.navButton, { borderColor: colors.border, opacity: isAtEnd ? 0.4 : 1 }]}
        onPress={onLast}
        disabled={isAtEnd}
        activeOpacity={0.7}
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
  webview: {
    backgroundColor: 'transparent',
    borderRadius: 8,
    overflow: 'hidden',
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
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
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
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
});
