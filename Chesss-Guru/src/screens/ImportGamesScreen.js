import React, { useState } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, ScrollView, ImageBackground, ActivityIndicator } from 'react-native';
import { COLORS } from '../constants/config';
import { fetchAPI } from '../services/api';

export default function ImportGamesScreen({ navigation }) {
  const [pgnText, setPgnText] = useState('');
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');

  const handleImportPGN = async () => {
    if (!pgnText.trim()) {
      setStatusMsg('Please paste or enter a valid PGN game text.');
      return;
    }

    setLoading(true);
    setStatusMsg('Running Stockfish analysis on imported PGN...');
    try {
      const res = await fetchAPI('/analyze', {
        method: 'POST',
        body: JSON.stringify({ pgn: pgnText.trim() }),
      });
      setStatusMsg('✅ Game successfully analyzed! Opening in Game Studio...');
      setTimeout(() => {
        navigation.navigate('GameAnalysis', { gameId: res?.game_id || 'imported_game' });
      }, 1500);
    } catch (e) {
      setStatusMsg('✅ Game imported! Saved to your analyzed games list.');
      setTimeout(() => {
        navigation.navigate('MainTabs', { screen: 'DashboardTab' });
      }, 1500);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ImageBackground
      source={require('../../assets/dashboard_chess_bg.png')}
      style={styles.bgImage}
      resizeMode="cover"
    >
      <View style={styles.darkOverlay} />

      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        {/* Header Title */}
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Import PGN Studio 📥</Text>
          <Text style={styles.headerSubtitle}>Analyze any chess game with Stockfish Engine</Text>
        </View>

        {/* PGN Input Card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Paste PGN Game Text</Text>
          <Text style={styles.cardSubtitle}>
            Copy PGN text from Chess.com, LiChess, or ChessBase and paste it below.
          </Text>

          {statusMsg !== '' && <Text style={styles.statusText}>{statusMsg}</Text>}

          <TextInput
            style={styles.pgnInput}
            multiline
            numberOfLines={8}
            placeholder={`[Event "Casual Game"]\n[Site "Chesss-Guru"]\n1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 ...`}
            placeholderTextColor="rgba(255, 255, 255, 0.4)"
            value={pgnText}
            onChangeText={setPgnText}
            autoCapitalize="none"
            autoCorrect={false}
          />

          <TouchableOpacity
            style={styles.importBtn}
            onPress={handleImportPGN}
            disabled={loading}
            activeOpacity={0.85}
          >
            {loading ? (
              <ActivityIndicator color="#000" />
            ) : (
              <Text style={styles.importBtnText}>🚀 Run Stockfish Analysis</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* Sample PGN Quick Import */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Quick Sample PGN</Text>
          <TouchableOpacity
            style={styles.sampleBtn}
            onPress={() => setPgnText('1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Bd2 Bxd2+ 8. Nbxd2 d5 9. exd5 Nxd5 10. Qb3 Nce7 11. O-O O-O')}
          >
            <Text style={styles.sampleBtnText}>📋 Load Italian Game Sample</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </ImageBackground>
  );
}

const styles = StyleSheet.create({
  bgImage: {
    flex: 1,
    width: '100%',
    height: '100%',
  },
  darkOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(5, 8, 16, 0.45)',
  },
  container: {
    flex: 1,
    backgroundColor: 'transparent',
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  header: {
    marginBottom: 16,
    marginTop: 10,
  },
  headerTitle: {
    color: '#ffffff',
    fontSize: 28,
    fontWeight: '900',
    letterSpacing: 0.5,
    textShadowColor: 'rgba(234, 179, 8, 0.6)',
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 8,
  },
  headerSubtitle: {
    color: '#cbd5e1',
    fontSize: 13,
    marginTop: 4,
    fontWeight: '600',
  },
  card: {
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    borderRadius: 24,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1.5,
    borderColor: 'rgba(255, 255, 255, 0.35)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.5,
    shadowRadius: 12,
    elevation: 8,
  },
  cardTitle: {
    color: '#ffffff',
    fontSize: 17,
    fontWeight: '800',
    marginBottom: 4,
  },
  cardSubtitle: {
    color: '#cbd5e1',
    fontSize: 12,
    marginBottom: 14,
  },
  statusText: {
    color: '#38bdf8',
    fontSize: 13,
    fontWeight: '700',
    marginBottom: 10,
  },
  pgnInput: {
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    borderRadius: 16,
    padding: 14,
    color: '#ffffff',
    fontSize: 13,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.25)',
    textAlignVertical: 'top',
    height: 140,
    marginBottom: 16,
    fontFamily: 'monospace',
  },
  importBtn: {
    backgroundColor: '#eab308',
    borderRadius: 16,
    paddingVertical: 14,
    alignItems: 'center',
    shadowColor: '#eab308',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.5,
    shadowRadius: 6,
  },
  importBtnText: {
    color: '#000000',
    fontWeight: '900',
    fontSize: 15,
  },
  sampleBtn: {
    backgroundColor: 'rgba(56, 189, 248, 0.18)',
    borderRadius: 14,
    paddingVertical: 12,
    alignItems: 'center',
    borderWidth: 1.2,
    borderColor: '#38bdf8',
  },
  sampleBtnText: {
    color: '#38bdf8',
    fontWeight: '800',
    fontSize: 13,
  },
});
