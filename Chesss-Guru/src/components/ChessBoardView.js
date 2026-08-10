import React, { useRef, useEffect, useState } from 'react';
import { View, Text, StyleSheet, Dimensions, TouchableOpacity, ScrollView, Modal } from 'react-native';
import Chessboard from 'react-native-chessboard';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { COLORS } from '../constants/config';

const { width } = Dimensions.get('window');
const COORD_MARGIN = 18;
const BOARD_SIZE = Math.min(width - 48, 340);
const ASYNC_STORAGE_THEME_KEY = '@chess_board_theme_id';
const ASYNC_STORAGE_HIGHLIGHT_KEY = '@chess_board_highlight_id';

export const BOARD_THEMES = {
  wood: {
    id: 'wood',
    name: 'Classic Wood',
    colors: { white: '#f0d9b5', black: '#b58863' }
  },
  emerald: {
    id: 'emerald',
    name: 'Emerald',
    colors: { white: '#eeeed2', black: '#769656' }
  },
  ocean: {
    id: 'ocean',
    name: 'Ocean Blue',
    colors: { white: '#eaedf1', black: '#4b7399' }
  },
  cyber: {
    id: 'cyber',
    name: 'Dark Slate',
    colors: { white: '#94a3b8', black: '#334155' }
  },
  purple: {
    id: 'purple',
    name: 'Royal Purple',
    colors: { white: '#e9d5ff', black: '#7c3aed' }
  },
  bronze: {
    id: 'bronze',
    name: 'Warm Bronze',
    colors: { white: '#e2d6b5', black: '#8b5a2b' }
  }
};

export const HIGHLIGHT_COLORS = {
  gold: {
    id: 'gold',
    name: 'Gold',
    color: 'rgba(234, 179, 8, 0.65)',
    dotColor: '#eab308'
  },
  green: {
    id: 'green',
    name: 'Emerald',
    color: 'rgba(34, 197, 94, 0.65)',
    dotColor: '#22c55e'
  },
  blue: {
    id: 'blue',
    name: 'Sky Blue',
    color: 'rgba(56, 189, 248, 0.65)',
    dotColor: '#38bdf8'
  },
  purple: {
    id: 'purple',
    name: 'Purple',
    color: 'rgba(168, 85, 247, 0.65)',
    dotColor: '#a855f7'
  },
  red: {
    id: 'red',
    name: 'Crimson',
    color: 'rgba(239, 68, 68, 0.65)',
    dotColor: '#ef4444'
  }
};

export const ChessBoardView = ({
  fen = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
  orientation = 'white',
  lastMove = null,
  onMove,
  onGameOver,
  showControls = true
}) => {
  const boardRef = useRef(null);

  // Customization state
  const [activeThemeId, setActiveThemeId] = useState('wood');
  const [activeHighlightId, setActiveHighlightId] = useState('gold');
  const [isFlipped, setIsFlipped] = useState(orientation === 'black');
  const [showNotation, setShowNotation] = useState(true);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);

  // Sync orientation prop updates
  useEffect(() => {
    setIsFlipped(orientation === 'black');
  }, [orientation]);

  // Load saved theme & highlight preferences on mount
  useEffect(() => {
    (async () => {
      try {
        const savedTheme = await AsyncStorage.getItem(ASYNC_STORAGE_THEME_KEY);
        if (savedTheme && BOARD_THEMES[savedTheme]) {
          setActiveThemeId(savedTheme);
        }
        const savedHighlight = await AsyncStorage.getItem(ASYNC_STORAGE_HIGHLIGHT_KEY);
        if (savedHighlight && HIGHLIGHT_COLORS[savedHighlight]) {
          setActiveHighlightId(savedHighlight);
        }
      } catch (err) {
        console.warn('Failed to load board preferences', err);
      }
    })();
  }, []);

  // Sync FEN & lastMove updates to Chessboard
  useEffect(() => {
    if (boardRef.current && boardRef.current.resetBoard) {
      if (lastMove && lastMove.from && lastMove.to) {
        boardRef.current.resetBoard(fen, {
          lastMove: { from: lastMove.from, to: lastMove.to }
        });
      } else {
        boardRef.current.resetBoard(fen);
      }
    }
  }, [fen, lastMove]);

  // Change theme handler
  const handleSelectTheme = async (themeId) => {
    setActiveThemeId(themeId);
    try {
      await AsyncStorage.setItem(ASYNC_STORAGE_THEME_KEY, themeId);
    } catch (err) {
      console.warn('Failed to save board theme preference', err);
    }
  };

  // Change highlight color handler
  const handleSelectHighlight = async (highlightId) => {
    setActiveHighlightId(highlightId);
    try {
      await AsyncStorage.setItem(ASYNC_STORAGE_HIGHLIGHT_KEY, highlightId);
    } catch (err) {
      console.warn('Failed to save highlight preference', err);
    }
  };

  const handleMove = (result) => {
    if (result && result.move) {
      const from = result.move.from;
      const to = result.move.to;
      let promotion = result.move.promotion;
      if (!promotion && result.move.san && typeof result.move.san === 'string' && result.move.san.includes('=')) {
        const parts = result.move.san.split('=');
        if (parts[1]) {
          promotion = parts[1][0].toLowerCase();
        }
      }
      
      if (onMove) {
        onMove({ from, to, promotion, san: result.move.san });
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

  const themeColors = BOARD_THEMES[activeThemeId]?.colors || BOARD_THEMES.wood.colors;
  const moveDotColor = HIGHLIGHT_COLORS[activeHighlightId]?.color || HIGHLIGHT_COLORS.gold.color;

  const currentColors = {
    white: themeColors.white,
    black: themeColors.black,
    validMoveDot: moveDotColor,
    validMoveCapture: 'rgba(239, 68, 68, 0.95)',
    lastMoveHighlight: 'rgba(234, 179, 8, 0.55)',
    lastMove: 'rgba(234, 179, 8, 0.55)',
    checkmateHighlight: 'rgba(239, 68, 68, 0.85)',
    checkmate: 'rgba(239, 68, 68, 0.85)',
  };

  // File alphabets (Columns A-H) and Rank numbers (Rows 1-8)
  const files = isFlipped
    ? ['H', 'G', 'F', 'E', 'D', 'C', 'B', 'A']
    : ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

  const ranks = isFlipped
    ? ['1', '2', '3', '4', '5', '6', '7', '8']
    : ['8', '7', '6', '5', '4', '3', '2', '1'];

  return (
    <GestureHandlerRootView style={styles.container}>
      {/* Top Header Bar with Small Round Settings Button */}
      {showControls && (
        <View style={styles.topHeaderBar}>
          <Text style={styles.boardHeaderTitle}>
            {BOARD_THEMES[activeThemeId]?.name || 'Chessboard'}
            {lastMove?.from && lastMove?.to ? ` • Move: ${lastMove.from.toUpperCase()} ➔ ${lastMove.to.toUpperCase()}` : ''}
          </Text>
          <TouchableOpacity
            style={styles.roundSettingsBtn}
            onPress={() => setIsSettingsModalOpen(true)}
            activeOpacity={0.8}
          >
            <Text style={styles.settingsIconText}>⚙️</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Outer Board Frame with Rank Numbers & File Alphabets */}
      <View style={styles.outerBoardFrame}>
        {/* Top File Alphabets Bar */}
        {showNotation && (
          <View style={styles.horizontalCoordsBar}>
            <View style={{ width: COORD_MARGIN }} />
            {files.map((file, idx) => (
              <Text key={`top-${file}-${idx}`} style={styles.coordTextHorizontal}>
                {file}
              </Text>
            ))}
            <View style={{ width: COORD_MARGIN }} />
          </View>
        )}

        <View style={styles.middleRowWrapper}>
          {/* Left Rank Numbers Column */}
          {showNotation && (
            <View style={styles.verticalCoordsBar}>
              {ranks.map((rank, idx) => (
                <Text key={`left-${rank}-${idx}`} style={styles.coordTextVertical}>
                  {rank}
                </Text>
              ))}
            </View>
          )}

          {/* Actual Interactive Chessboard */}
          <View style={styles.boardWrapper}>
            <Chessboard
              ref={boardRef}
              fen={fen}
              boardSize={BOARD_SIZE}
              flipped={isFlipped}
              gestureEnabled={!!onMove}
              withLetters={false}
              withNumbers={false}
              colors={currentColors}
              onMove={handleMove}
            />
          </View>

          {/* Right Rank Numbers Column */}
          {showNotation && (
            <View style={styles.verticalCoordsBar}>
              {ranks.map((rank, idx) => (
                <Text key={`right-${rank}-${idx}`} style={styles.coordTextVertical}>
                  {rank}
                </Text>
              ))}
            </View>
          )}
        </View>

        {/* Bottom File Alphabets Bar */}
        {showNotation && (
          <View style={styles.horizontalCoordsBar}>
            <View style={{ width: COORD_MARGIN }} />
            {files.map((file, idx) => (
              <Text key={`bot-${file}-${idx}`} style={styles.coordTextHorizontal}>
                {file}
              </Text>
            ))}
            <View style={{ width: COORD_MARGIN }} />
          </View>
        )}
      </View>

      {/* Board Customization Modal Settings */}
      <Modal
        visible={isSettingsModalOpen}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setIsSettingsModalOpen(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            {/* Modal Header */}
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>⚙️ Board Settings</Text>
              <TouchableOpacity
                style={styles.closeBtn}
                onPress={() => setIsSettingsModalOpen(false)}
              >
                <Text style={styles.closeBtnText}>✕</Text>
              </TouchableOpacity>
            </View>

            <ScrollView showsVerticalScrollIndicator={false} style={styles.modalBody}>
              {/* Option 1: Board Flip */}
              <View style={styles.settingSection}>
                <Text style={styles.sectionHeading}>Board Orientation</Text>
                <View style={styles.optionsRow}>
                  <TouchableOpacity
                    style={[styles.modalToggleBtn, !isFlipped && styles.modalToggleBtnActive]}
                    onPress={() => setIsFlipped(false)}
                  >
                    <Text style={[styles.modalToggleText, !isFlipped && styles.modalToggleTextActive]}>
                      ♙ White View
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.modalToggleBtn, isFlipped && styles.modalToggleBtnActive]}
                    onPress={() => setIsFlipped(true)}
                  >
                    <Text style={[styles.modalToggleText, isFlipped && styles.modalToggleTextActive]}>
                      ♟ Black View
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>

              {/* Option 2: Coordinates A-H / 1-8 */}
              <View style={styles.settingSection}>
                <Text style={styles.sectionHeading}>Coordinates & Labels</Text>
                <View style={styles.optionsRow}>
                  <TouchableOpacity
                    style={[styles.modalToggleBtn, showNotation && styles.modalToggleBtnActive]}
                    onPress={() => setShowNotation(true)}
                  >
                    <Text style={[styles.modalToggleText, showNotation && styles.modalToggleTextActive]}>
                      123 A-H Show Labels
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.modalToggleBtn, !showNotation && styles.modalToggleBtnActive]}
                    onPress={() => setShowNotation(false)}
                  >
                    <Text style={[styles.modalToggleText, !showNotation && styles.modalToggleTextActive]}>
                      🚫 Hide Labels
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>

              {/* Option 3: Move & Destination Highlight Color */}
              <View style={styles.settingSection}>
                <Text style={styles.sectionHeading}>Move Highlight Color</Text>
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.highlightScrollView}
                >
                  {Object.values(HIGHLIGHT_COLORS).map((hl) => {
                    const isActive = hl.id === activeHighlightId;
                    return (
                      <TouchableOpacity
                        key={hl.id}
                        style={[styles.highlightChip, isActive && styles.highlightChipActive]}
                        onPress={() => handleSelectHighlight(hl.id)}
                        activeOpacity={0.8}
                      >
                        <View style={[styles.highlightDot, { backgroundColor: hl.dotColor }]} />
                        <Text style={[styles.highlightChipText, isActive && styles.highlightChipTextActive]}>
                          {hl.name}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </ScrollView>
              </View>

              {/* Option 4: Color Themes */}
              <View style={styles.settingSection}>
                <Text style={styles.sectionHeading}>Board Theme</Text>
                <View style={styles.themeGrid}>
                  {Object.values(BOARD_THEMES).map((theme) => {
                    const isActive = theme.id === activeThemeId;
                    return (
                      <TouchableOpacity
                        key={theme.id}
                        style={[styles.themeGridCard, isActive && styles.themeGridCardActive]}
                        onPress={() => handleSelectTheme(theme.id)}
                      >
                        <View style={styles.largeSwatchContainer}>
                          <View style={[styles.largeSwatchHalf, { backgroundColor: theme.colors.white }]} />
                          <View style={[styles.largeSwatchHalf, { backgroundColor: theme.colors.black }]} />
                        </View>
                        <Text style={[styles.themeCardText, isActive && styles.themeCardTextActive]}>
                          {theme.name}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </View>
            </ScrollView>

            {/* Apply & Close Button */}
            <TouchableOpacity
              style={styles.doneBtn}
              onPress={() => setIsSettingsModalOpen(false)}
            >
              <Text style={styles.doneBtnText}>Done</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </GestureHandlerRootView>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: 6,
    width: '100%',
  },
  topHeaderBar: {
    width: BOARD_SIZE + (COORD_MARGIN * 2),
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
    paddingHorizontal: 4,
  },
  boardHeaderTitle: {
    color: COLORS.textMuted,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
  roundSettingsBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: '#1e293b',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.25)',
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.4,
    shadowRadius: 4,
  },
  settingsIconText: {
    fontSize: 16,
  },
  outerBoardFrame: {
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0f172a',
    padding: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.15)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.5,
    shadowRadius: 10,
    elevation: 8,
  },
  middleRowWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  horizontalCoordsBar: {
    width: BOARD_SIZE + (COORD_MARGIN * 2),
    height: 18,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  verticalCoordsBar: {
    width: COORD_MARGIN,
    height: BOARD_SIZE,
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  coordTextHorizontal: {
    flex: 1,
    textAlign: 'center',
    color: '#94a3b8',
    fontSize: 11,
    fontWeight: '700',
  },
  coordTextVertical: {
    height: BOARD_SIZE / 8,
    lineHeight: BOARD_SIZE / 8,
    textAlign: 'center',
    color: '#94a3b8',
    fontSize: 11,
    fontWeight: '700',
  },
  boardWrapper: {
    width: BOARD_SIZE,
    height: BOARD_SIZE,
    borderRadius: 8,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.25)',
    backgroundColor: COLORS.cardBg,
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#0f172a',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 20,
    maxHeight: '82%',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.15)',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.1)',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: COLORS.text,
  },
  closeBtn: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#1e293b',
    alignItems: 'center',
    justifyContent: 'center',
  },
  closeBtnText: {
    color: COLORS.textMuted,
    fontSize: 14,
    fontWeight: '700',
  },
  modalBody: {
    marginBottom: 16,
  },
  settingSection: {
    marginBottom: 18,
  },
  sectionHeading: {
    color: COLORS.textMuted,
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  optionsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  modalToggleBtn: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
    backgroundColor: '#1e293b',
    borderRadius: 10,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  modalToggleBtnActive: {
    backgroundColor: '#2a3a54',
    borderColor: COLORS.secondary,
  },
  modalToggleText: {
    color: COLORS.textMuted,
    fontSize: 13,
    fontWeight: '600',
  },
  modalToggleTextActive: {
    color: COLORS.secondary,
    fontWeight: '700',
  },
  highlightScrollView: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
  },
  highlightChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    paddingVertical: 7,
    paddingHorizontal: 12,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'transparent',
    gap: 6,
  },
  highlightChipActive: {
    backgroundColor: '#2a3a54',
    borderColor: COLORS.secondary,
  },
  highlightDot: {
    width: 14,
    height: 14,
    borderRadius: 7,
  },
  highlightChipText: {
    color: COLORS.textMuted,
    fontSize: 12,
    fontWeight: '600',
  },
  highlightChipTextActive: {
    color: COLORS.text,
    fontWeight: '700',
  },
  themeGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  themeGridCard: {
    width: '48%',
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    padding: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'transparent',
    gap: 10,
  },
  themeGridCardActive: {
    backgroundColor: '#2a3a54',
    borderColor: COLORS.primary,
  },
  largeSwatchContainer: {
    width: 24,
    height: 24,
    borderRadius: 12,
    overflow: 'hidden',
    flexDirection: 'row',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.25)',
  },
  largeSwatchHalf: {
    flex: 1,
    height: '100%',
  },
  themeCardText: {
    color: COLORS.textMuted,
    fontSize: 13,
    fontWeight: '500',
  },
  themeCardTextActive: {
    color: COLORS.primary,
    fontWeight: '700',
  },
  doneBtn: {
    backgroundColor: COLORS.primary,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  doneBtnText: {
    color: '#090d16',
    fontSize: 16,
    fontWeight: '700',
  },
});
