import React, { useRef, useEffect } from 'react';
import { View, StyleSheet, Dimensions } from 'react-native';
import { WebView } from 'react-native-webview';
import { COLORS } from '../constants/config';

const { width } = Dimensions.get('window');
const BOARD_SIZE = Math.min(width - 32, 360);

export const ChessBoardView = ({ fen = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', orientation = 'white', onMove, onNoMoves, onGameOver }) => {
  const webViewRef = useRef(null);

  // Sync FEN & orientation updates to WebView via postMessage
  useEffect(() => {
    if (webViewRef.current) {
      webViewRef.current.postMessage(JSON.stringify({ fen, orientation }));
    }
  }, [fen, orientation]);

  const cleanFen = fen ? fen.split(' ')[0] : 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR';

  // Self-contained HTML with explicit board sizing for 100% visibility
  const htmlContent = `
    <!DOCTYPE html>
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <link rel="stylesheet" href="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css">
        <script src="https://code.jquery.com/jquery-3.5.1.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
        <script src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
        <style>
          * {
            box-sizing: border-box;
            -webkit-touch-callout: none;
            -webkit-user-select: none;
            user-select: none;
          }
          html, body {
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            background-color: #090d16;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
          }
          #board {
            width: 340px;
            max-width: 94vw;
            margin: 0 auto;
          }
          .board-b72b1 {
            border: 2.5px solid #334155;
            border-radius: 8px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.5);
          }
          .white-1e1d7 { background-color: #f0d9b5; color: #b58863; }
          .black-3c85d { background-color: #b58863; color: #f0d9b5; }
          
          .piece-417cd {
            width: 100% !important;
            height: 100% !important;
          }

          /* Destination square highlights & active piece selection ring */
          .highlight-active {
            box-shadow: inset 0 0 0 3px #eab308 !important;
            background-color: rgba(234, 179, 8, 0.45) !important;
          }
          .highlight-dest {
            background: radial-gradient(circle, rgba(234, 179, 8, 0.85) 30%, transparent 31%) !important;
          }
          .highlight-capture {
            background: radial-gradient(circle, rgba(239, 68, 68, 0.85) 34%, transparent 35%) !important;
            box-shadow: inset 0 0 0 3px #ef4444 !important;
          }

          /* Toast overlay */
          #toast {
            position: absolute;
            bottom: 12px;
            background: rgba(15, 23, 42, 0.95);
            color: #fef08a;
            border: 1.5px solid #eab308;
            border-radius: 12px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 800;
            font-family: sans-serif;
            box-shadow: 0 4px 12px rgba(0,0,0,0.7);
            display: none;
            z-index: 1000;
            pointer-events: none;
            text-align: center;
          }
        </style>
      </head>
      <body>
        <div id="board"></div>
        <div id="toast"></div>

        <script>
          var game = new Chess('${fen}');
          var selectedSquare = null;
          var playerColor = '${orientation === "white" ? "w" : "b"}';

          function showToast(msg) {
            $('#toast').text(msg).stop(true, true).fadeIn(150).delay(2000).fadeOut(300);
          }

          function removeHighlights() {
            $('#board .square-55d63').removeClass('highlight-active highlight-dest highlight-capture');
          }

          function checkAndReportGameOver() {
            if (game.in_checkmate()) {
              var winner = game.turn() === 'w' ? 'Black' : 'White';
              showToast('🏆 CHECKMATE! ' + winner + ' wins!');
              window.ReactNativeWebView.postMessage(JSON.stringify({
                type: 'GAME_OVER',
                reason: 'CHECKMATE',
                winner: winner
              }));
              return true;
            } else if (game.in_draw() || game.in_stalemate() || game.in_threefold_repetition()) {
              showToast('🤝 Game Drawn');
              window.ReactNativeWebView.postMessage(JSON.stringify({
                type: 'GAME_OVER',
                reason: 'STALEMATE'
              }));
              return true;
            }
            return false;
          }

          function highlightDestinations(square) {
            removeHighlights();

            if (checkAndReportGameOver()) return;

            var piece = game.get(square);
            if (!piece) return;

            if (piece.color !== playerColor) {
              selectedSquare = null;
              showToast("You are playing as " + (playerColor === 'w' ? 'White' : 'Black') + "! Tap your own piece.");
              return;
            }

            var moves = game.moves({
              square: square,
              verbose: true
            });

            if (moves.length === 0) {
              selectedSquare = null;
              showToast('⚠️ Piece on ' + square.toUpperCase() + ' cannot move!');
              window.ReactNativeWebView.postMessage(JSON.stringify({
                type: 'NO_MOVES',
                square: square
              }));
              return;
            }

            selectedSquare = square;
            $('#board .square-' + square).addClass('highlight-active');
            for (var i = 0; i < moves.length; i++) {
              var targetSq = moves[i].to;
              var $target = $('#board .square-' + targetSq);
              if (moves[i].captured) {
                $target.addClass('highlight-capture');
              } else {
                $target.addClass('highlight-dest');
              }
            }
          }

          function handleSquareTap(square) {
            if (!square) return;

            if (checkAndReportGameOver()) return;

            var piece = game.get(square);

            // Case A: Piece selected -> execute move/capture
            if (selectedSquare) {
              if (selectedSquare === square) return;

              var move = game.move({
                from: selectedSquare,
                to: square,
                promotion: 'q'
              });

              if (move !== null) {
                board.position(game.fen().split(' ')[0], false);
                var fromSq = selectedSquare;
                selectedSquare = null;
                removeHighlights();
                window.ReactNativeWebView.postMessage(JSON.stringify({
                  type: 'MOVE',
                  from: fromSq,
                  to: square
                }));
                checkAndReportGameOver();
                return;
              }
            }

            // Case B: Tapping own piece -> select and open move options
            if (piece && piece.color === playerColor) {
              if (game.turn() !== playerColor) {
                showToast("Waiting for Black AI to move...");
                return;
              }
              highlightDestinations(square);
              return;
            }

            // Case C: Tapping opponent piece directly without prior selection
            if (piece && piece.color !== playerColor) {
              selectedSquare = null;
              removeHighlights();
              showToast("You are playing as White! Tap your White piece to move.");
              return;
            }

            selectedSquare = null;
            removeHighlights();
          }

          var board = Chessboard('board', {
            position: '${cleanFen}',
            orientation: '${orientation}',
            draggable: true,
            pieceTheme: 'https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png',
            onDragStart: function(source, piece, position, orientation) {
              if (checkAndReportGameOver()) return false;
              if ((playerColor === 'w' && piece.search(/^b/) !== -1) || (playerColor === 'b' && piece.search(/^w/) !== -1)) {
                showToast("You are playing as White! You cannot move Black pieces.");
                return false;
              }
              if (game.turn() !== playerColor) {
                showToast("Waiting for Black AI to move...");
                return false;
              }
              highlightDestinations(source);
            },
            onDrop: function(source, target) {
              if (source === target) {
                highlightDestinations(source);
                return;
              }

              var move = game.move({
                from: source,
                to: target,
                promotion: 'q'
              });

              if (move === null) {
                if (source !== selectedSquare) {
                  removeHighlights();
                }
                return 'snapback';
              }
              
              selectedSquare = null;
              removeHighlights();
              board.position(game.fen().split(' ')[0], false);
              window.ReactNativeWebView.postMessage(JSON.stringify({
                type: 'MOVE',
                from: source,
                to: target
              }));
              checkAndReportGameOver();
            },
            onSnapEnd: function() {
              board.position(game.fen().split(' ')[0], false);
            }
          });

          board.resize();

          // Event delegation for both square containers and piece images
          $('#board').on('touchstart mousedown', '.square-55d63, .piece-417cd', function(e) {
            var $sq = $(this).closest('.square-55d63');
            var sq = $sq.attr('data-square');
            if (sq) {
              handleSquareTap(sq);
            }
          });

          function handleFenMessage(event) {
            try {
              var raw = event.data;
              if (typeof raw === 'string') {
                try { raw = JSON.parse(raw); } catch(e){}
              }
              if (raw && typeof raw.data === 'string') {
                try { raw = JSON.parse(raw.data); } catch(e){}
              }
              if (raw && raw.fen) {
                game.load(raw.fen);
                var pos = raw.fen.split(' ')[0];
                board.position(pos, false);
                selectedSquare = null;
                removeHighlights();
                checkAndReportGameOver();
              }
              if (raw && raw.orientation) {
                board.orientation(raw.orientation);
                playerColor = raw.orientation === 'white' ? 'w' : 'b';
              }
            } catch(e){}
          }

          window.addEventListener('message', handleFenMessage);
          document.addEventListener('message', handleFenMessage);
        </script>
      </body>
    </html>
  `;

  const handleMessage = (event) => {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      if (data.type === 'MOVE' && onMove) {
        onMove({ from: data.from, to: data.to });
      } else if (data.type === 'NO_MOVES' && onNoMoves) {
        onNoMoves(data.square);
      } else if (data.type === 'GAME_OVER' && onGameOver) {
        onGameOver(data);
      }
    } catch (e) {}
  };

  return (
    <View style={styles.container}>
      <View style={styles.boardWrapper}>
        <WebView
          ref={webViewRef}
          originWhitelist={['*']}
          source={{ html: htmlContent }}
          style={styles.webview}
          onMessage={handleMessage}
          scrollEnabled={false}
          bounces={false}
          javaScriptEnabled={true}
          domStorageEnabled={true}
          mixedContentMode="always"
          allowUniversalAccessFromFileURLs={true}
        />
      </View>
    </View>
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
  },
  webview: {
    width: '100%',
    height: '100%',
    backgroundColor: COLORS.background,
  },
});
