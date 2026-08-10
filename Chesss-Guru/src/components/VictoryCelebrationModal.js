import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  Animated,
  Dimensions,
  Easing
} from 'react-native';
import { COLORS } from '../constants/config';

const { width, height } = Dimensions.get('window');

const CONFETTI_ITEMS = ['🎉', '🎊', '⭐', '✨', '🏆', '🥳', '💎', '🔥', '👑'];
const PARTICLE_COUNT = 32;

const ConfettiParticle = ({ delay, item, startX }) => {
  const translateY = useRef(new Animated.Value(-50)).current;
  const translateX = useRef(new Animated.Value(startX)).current;
  const rotate = useRef(new Animated.Value(0)).current;
  const scale = useRef(new Animated.Value(0.4 + Math.random() * 0.8)).current;

  useEffect(() => {
    const driftX = startX + (Math.random() * 120 - 60);

    const animation = Animated.loop(
      Animated.sequence([
        Animated.delay(delay),
        Animated.parallel([
          Animated.timing(translateY, {
            toValue: height + 60,
            duration: 2800 + Math.random() * 1500,
            easing: Easing.linear,
            useNativeDriver: true,
          }),
          Animated.timing(translateX, {
            toValue: driftX,
            duration: 2800 + Math.random() * 1500,
            easing: Easing.sin,
            useNativeDriver: true,
          }),
          Animated.timing(rotate, {
            toValue: 1,
            duration: 2000 + Math.random() * 1000,
            easing: Easing.linear,
            useNativeDriver: true,
          }),
        ]),
      ])
    );

    animation.start();

    return () => animation.stop();
  }, []);

  const spin = rotate.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  return (
    <Animated.Text
      style={[
        styles.particleText,
        {
          transform: [
            { translateX },
            { translateY },
            { rotate: spin },
            { scale },
          ],
        },
      ]}
    >
      {item}
    </Animated.Text>
  );
};

export const VictoryCelebrationModal = ({
  visible,
  winningMove = '',
  totalMoves = 0,
  onPlayAgain,
  onClose
}) => {
  const cardScale = useRef(new Animated.Value(0.3)).current;
  const cardOpacity = useRef(new Animated.Value(0)).current;
  const bannerBounce = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (visible) {
      // Card pop animation
      Animated.parallel([
        Animated.spring(cardScale, {
          toValue: 1,
          friction: 6,
          tension: 80,
          useNativeDriver: true,
        }),
        Animated.timing(cardOpacity, {
          toValue: 1,
          duration: 300,
          useNativeDriver: true,
        }),
      ]).start();

      // Bounce header emoji loop
      const bounceLoop = Animated.loop(
        Animated.sequence([
          Animated.timing(bannerBounce, {
            toValue: 1.15,
            duration: 600,
            easing: Easing.out(Easing.ease),
            useNativeDriver: true,
          }),
          Animated.timing(bannerBounce, {
            toValue: 1,
            duration: 600,
            easing: Easing.in(Easing.ease),
            useNativeDriver: true,
          }),
        ])
      );
      bounceLoop.start();

      return () => bounceLoop.stop();
    } else {
      cardScale.setValue(0.3);
      cardOpacity.setValue(0);
    }
  }, [visible]);

  // Generate particle parameters
  const particles = useRef(
    Array.from({ length: PARTICLE_COUNT }).map((_, i) => ({
      id: i,
      delay: Math.random() * 2000,
      item: CONFETTI_ITEMS[i % CONFETTI_ITEMS.length],
      startX: Math.random() * (width - 40) + 20,
    }))
  ).current;

  if (!visible) return null;

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={onClose}>
      <View style={styles.overlay}>
        {/* Falling Party Popper Particles */}
        <View style={StyleSheet.absoluteFillObject} pointerEvents="none">
          {particles.map((p) => (
            <ConfettiParticle key={p.id} delay={p.delay} item={p.item} startX={p.startX} />
          ))}
        </View>

        {/* Victory Celebration Card */}
        <Animated.View
          style={[
            styles.victoryCard,
            {
              opacity: cardOpacity,
              transform: [{ scale: cardScale }],
            },
          ]}
        >
          {/* Animated Header Party Popper + Trophy */}
          <Animated.View style={{ transform: [{ scale: bannerBounce }], alignItems: 'center' }}>
            <Text style={styles.trophyBanner}>🎉 🏆 🎊</Text>
          </Animated.View>

          <Text style={styles.victoryTitle}>VICTORY!</Text>
          <Text style={styles.victorySubtitle}>YOU WON BY CHECKMATE!</Text>

          {/* Stats Box */}
          <View style={styles.statsContainer}>
            <View style={styles.statRow}>
              <Text style={styles.statLabel}>🏆 Match Result:</Text>
              <Text style={styles.statValueWin}>Checkmate Win</Text>
            </View>
            {!!winningMove && (
              <View style={styles.statRow}>
                <Text style={styles.statLabel}>♟️ Winning Move:</Text>
                <Text style={styles.statValueHighlight}>{winningMove}</Text>
              </View>
            )}
            <View style={styles.statRow}>
              <Text style={styles.statLabel}>📊 Total Moves:</Text>
              <Text style={styles.statValue}>{totalMoves}</Text>
            </View>
            <View style={styles.statRow}>
              <Text style={styles.statLabel}>⭐ Bonus XP:</Text>
              <Text style={styles.statValueBonus}>+50 Rating XP 🎉</Text>
            </View>
          </View>

          {/* Buttons */}
          <View style={styles.btnRow}>
            <TouchableOpacity
              style={styles.playAgainBtn}
              onPress={onPlayAgain}
              activeOpacity={0.8}
            >
              <Text style={styles.playAgainBtnText}>🚀 Play Again</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.closeBtn}
              onPress={onClose}
              activeOpacity={0.8}
            >
              <Text style={styles.closeBtnText}>Close</Text>
            </TouchableOpacity>
          </View>
        </Animated.View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(9, 13, 22, 0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  particleText: {
    position: 'absolute',
    top: 0,
    fontSize: 26,
  },
  victoryCard: {
    width: Math.min(width - 36, 360),
    backgroundColor: '#0f172a',
    borderRadius: 24,
    padding: 24,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#eab308',
    shadowColor: '#eab308',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.6,
    shadowRadius: 16,
    elevation: 12,
  },
  trophyBanner: {
    fontSize: 44,
    marginBottom: 6,
  },
  victoryTitle: {
    fontSize: 28,
    fontWeight: '900',
    color: '#eab308',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
  },
  victorySubtitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#38bdf8',
    letterSpacing: 1,
    marginTop: 2,
    marginBottom: 16,
  },
  statsContainer: {
    width: '100%',
    backgroundColor: '#1e293b',
    borderRadius: 14,
    padding: 14,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    gap: 8,
  },
  statRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  statLabel: {
    color: COLORS.textMuted,
    fontSize: 13,
    fontWeight: '600',
  },
  statValue: {
    color: COLORS.text,
    fontSize: 13,
    fontWeight: '700',
  },
  statValueWin: {
    color: '#22c55e',
    fontSize: 13,
    fontWeight: '800',
  },
  statValueHighlight: {
    color: '#eab308',
    fontSize: 14,
    fontWeight: '800',
  },
  statValueBonus: {
    color: '#38bdf8',
    fontSize: 13,
    fontWeight: '700',
  },
  btnRow: {
    width: '100%',
    flexDirection: 'column',
    gap: 10,
  },
  playAgainBtn: {
    width: '100%',
    backgroundColor: '#eab308',
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
    shadowColor: '#eab308',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 6,
  },
  playAgainBtnText: {
    color: '#0f172a',
    fontSize: 16,
    fontWeight: '800',
  },
  closeBtn: {
    width: '100%',
    backgroundColor: '#1e293b',
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.15)',
  },
  closeBtnText: {
    color: COLORS.textMuted,
    fontSize: 14,
    fontWeight: '600',
  },
});
