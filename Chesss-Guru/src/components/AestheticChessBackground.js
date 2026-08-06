import React from 'react';
import { View, StyleSheet, Dimensions } from 'react-native';
import { WebView } from 'react-native-webview';

const { width, height } = Dimensions.get('window');

export const AestheticChessBackground = () => {
  const htmlContent = `
    <!DOCTYPE html>
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <link rel="stylesheet" href="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css">
        <script src="https://code.jquery.com/jquery-3.5.1.min.js"></script>
        <script src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
        <style>
          * { box-sizing: border-box; }
          html, body {
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            background-color: #060911;
            overflow: hidden;
          }
          .board-fullscreen-wrapper {
            position: absolute;
            top: -15vh;
            left: -15vw;
            width: 130vw;
            height: 130vh;
            display: flex;
            justify-content: center;
            align-items: center;
            opacity: 0.70;
            transform: rotate(-6deg) scale(1.35);
          }
          #bg-board {
            width: 110vw;
            height: 110vw;
            max-width: 700px;
            max-height: 700px;
          }
          .board-b72b1 {
            border: 6px solid #eab308 !important;
            border-radius: 20px;
            box-shadow: 0 0 50px rgba(234, 179, 8, 0.4), inset 0 0 30px rgba(0,0,0,0.8);
          }
          .white-1e1d7 { background-color: #334155 !important; color: #f8fafc !important; }
          .black-3c85d { background-color: #0f172a !important; color: #334155 !important; }
        </style>
      </head>
      <body>
        <div class="board-fullscreen-wrapper">
          <div id="bg-board"></div>
        </div>

        <script>
          var board = Chessboard('bg-board', {
            position: 'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2PP1N2/PP3PPP/RNBQ1RK1 b kq - 0 6',
            draggable: false,
            sparePieces: false
          });

          // Famous game move FEN positions for smooth continuous live playback loop
          var fens = [
            'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1',
            'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2',
            'rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2',
            'r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3',
            'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3',
            'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
            'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R b KQkq - 0 4',
            'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 1 5',
            'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2PP1N2/PP3PPP/RNBQK2R b KQkq - 0 5',
            'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2PP1N2/PP3PPP/RNBQ1RK1 b kq - 1 5'
          ];

          var index = 0;
          function loopMatch() {
            board.position(fens[index]);
            index = (index + 1) % fens.length;
            setTimeout(loopMatch, 1200);
          }
          setTimeout(loopMatch, 800);
        </script>
      </body>
    </html>
  `;

  return (
    <View style={styles.absoluteContainer} pointerEvents="none">
      <WebView
        originWhitelist={['*']}
        source={{ html: htmlContent }}
        style={styles.webview}
        scrollEnabled={false}
        bounces={false}
      />
      {/* Subtle vignette overlay */}
      <View style={styles.vignetteOverlay} />
    </View>
  );
};

const styles = StyleSheet.create({
  absoluteContainer: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 0,
  },
  webview: {
    width: width,
    height: height,
    backgroundColor: '#060911',
  },
  vignetteOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(6, 9, 17, 0.45)',
  },
});
