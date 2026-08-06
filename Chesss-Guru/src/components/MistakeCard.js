import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { COLORS } from '../constants/config';

export const MistakeCard = ({ card, onSolve }) => {
  const [revealed, setRevealed] = useState(false);

  return (
    <View style={styles.card}>
      <View style={styles.badgeRow}>
        <Text style={styles.badgeText}>🎯 BLUNDER MASTERY</Text>
        <Text style={styles.ratingText}>Difficulty: Medium</Text>
      </View>
      <Text style={styles.title}>{card.title}</Text>
      <Text style={styles.question}>{card.question}</Text>

      {revealed ? (
        <View style={styles.solutionBox}>
          <Text style={styles.solutionTitle}>Solution Move:</Text>
          <Text style={styles.solutionMove}>{card.solution_san}</Text>
          <Text style={styles.explanation}>{card.explanation}</Text>
        </View>
      ) : (
        <TouchableOpacity
          style={styles.revealButton}
          onPress={() => setRevealed(true)}
          activeOpacity={0.8}
        >
          <Text style={styles.revealButtonText}>💡 Reveal Best Move & Explanation</Text>
        </TouchableOpacity>
      )}

      {revealed && (
        <TouchableOpacity
          style={styles.completeButton}
          onPress={() => {
            setRevealed(false);
            if (onSolve) onSolve(card.id);
          }}
          activeOpacity={0.8}
        >
          <Text style={styles.completeButtonText}>Next Spaced Repetition Card ➔</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: COLORS.cardBorder,
    marginVertical: 10,
  },
  badgeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  badgeText: {
    color: COLORS.primary,
    fontWeight: '800',
    fontSize: 11,
    letterSpacing: 0.5,
  },
  ratingText: {
    color: COLORS.textMuted,
    fontSize: 12,
  },
  title: {
    color: COLORS.text,
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 8,
  },
  question: {
    color: COLORS.textMuted,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 16,
  },
  revealButton: {
    backgroundColor: '#1e293b',
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  revealButtonText: {
    color: COLORS.primary,
    fontWeight: '700',
    fontSize: 14,
  },
  solutionBox: {
    backgroundColor: '#0f172a',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: COLORS.cardBorder,
    marginBottom: 12,
  },
  solutionTitle: {
    color: COLORS.textMuted,
    fontSize: 12,
  },
  solutionMove: {
    color: COLORS.success,
    fontSize: 22,
    fontWeight: '800',
    marginVertical: 4,
  },
  explanation: {
    color: COLORS.text,
    fontSize: 13,
    lineHeight: 18,
  },
  completeButton: {
    backgroundColor: COLORS.primary,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
  },
  completeButtonText: {
    color: '#000',
    fontWeight: '800',
    fontSize: 14,
  },
});
