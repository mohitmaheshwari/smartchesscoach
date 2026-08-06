import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator } from 'react-native';
import { COLORS } from '../constants/config';
import { MistakeCard } from '../components/MistakeCard';
import { ChessBoardView } from '../components/ChessBoardView';
import { getMistakeCards } from '../services/api';

export default function MistakeMasteryScreen() {
  const [cards, setCards] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCards = async () => {
      try {
        const data = await getMistakeCards();
        setCards(data);
      } catch (e) {
        console.warn('Mistake cards load error:', e);
      } finally {
        setLoading(false);
      }
    };
    fetchCards();
  }, []);

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>Fetching your personalized mistake cards...</Text>
      </View>
    );
  }

  const currentCard = cards[currentIndex];

  const handleNextCard = () => {
    if (currentIndex < cards.length - 1) {
      setCurrentIndex(prev => prev + 1);
    } else {
      setCurrentIndex(0); // Loop back
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Top Banner */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Mistake Mastery System 🧩</Text>
        <Text style={styles.headerSubtitle}>
          Card {currentIndex + 1} of {cards.length} • Powered by Spaced Repetition Algorithm
        </Text>
      </View>

      {currentCard && (
        <>
          {/* Interactive Chess Board for Puzzle Position */}
          <ChessBoardView fen={currentCard.fen} orientation="white" />

          {/* Interactive Mistake Card */}
          <MistakeCard card={currentCard} onSolve={handleNextCard} />
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  centerContainer: {
    flex: 1,
    backgroundColor: COLORS.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: COLORS.textMuted,
    marginTop: 12,
    fontSize: 14,
  },
  header: {
    marginBottom: 10,
  },
  headerTitle: {
    color: COLORS.text,
    fontSize: 20,
    fontWeight: '800',
  },
  headerSubtitle: {
    color: COLORS.textMuted,
    fontSize: 12,
    marginTop: 4,
  },
});
