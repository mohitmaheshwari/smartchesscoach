import React, { useState, useEffect, useCallback } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TouchableOpacity, 
  RefreshControl,
  ActivityIndicator,
  TextInput,
  Alert,
  Modal
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../../src/context/ThemeContext';
import { gamesAPI } from '../../src/services/api';
import { StatusColors } from '../../src/constants/config';

export default function GamesScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [importModal, setImportModal] = useState(false);
  const [platform, setPlatform] = useState('chess.com');
  const [username, setUsername] = useState('');
  const [importing, setImporting] = useState(false);

  const fetchGames = async () => {
    try {
      const data = await gamesAPI.getGames();
      setGames(data);
    } catch (error) {
      console.error('Failed to fetch games:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGames();
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchGames();
    setRefreshing(false);
  }, []);

  const handleImport = async () => {
    if (!username.trim()) {
      Alert.alert('Error', 'Please enter a username');
      return;
    }
    setImporting(true);
    try {
      const result = await gamesAPI.importGames(platform, username.trim(), 10);
      Alert.alert('Success', `Imported ${result.imported_count || result.length || 0} games!`);
      setImportModal(false);
      setUsername('');
      fetchGames();
    } catch (error) {
      Alert.alert('Error', error.message);
    } finally {
      setImporting(false);
    }
  };

  const styles = createStyles(colors);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.text} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.greeting}>YOUR LIBRARY</Text>
          <Text style={styles.title}>Games</Text>
        </View>
        <TouchableOpacity 
          style={styles.importButton}
          onPress={() => setImportModal(true)}
        >
          <Ionicons name="add" size={24} color={colors.text} />
        </TouchableOpacity>
      </View>

      <ScrollView 
        style={styles.scrollView}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.text} />
        }
        showsVerticalScrollIndicator={false}
      >
        {games.length === 0 ? (
          <View style={styles.emptyState}>
            <View style={styles.emptyIcon}>
              <Ionicons name="game-controller-outline" size={48} color={colors.textSecondary} />
            </View>
            <Text style={styles.emptyTitle}>No games yet</Text>
            <Text style={styles.emptyText}>
              Import games from Chess.com or Lichess to get started with AI analysis.
            </Text>
            <TouchableOpacity 
              style={styles.primaryButton}
              onPress={() => setImportModal(true)}
            >
              <Ionicons name="cloud-download-outline" size={20} color={colors.background} />
              <Text style={styles.primaryButtonText}>Import Games</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.gamesList}>
            {games.map((game) => (
              <TouchableOpacity 
                key={game.game_id}
                style={styles.gameCard}
                onPress={() => router.push(`/game/${game.game_id}`)}
                activeOpacity={0.7}
              >
                <View style={styles.gameMain}>
                  <View style={[
                    styles.colorBadge,
                    { backgroundColor: game.user_color === 'white' ? '#fff' : '#333' }
                  ]}>
                    <Text style={[
                      styles.colorText,
                      { color: game.user_color === 'white' ? '#000' : '#fff' }
                    ]}>
                      {game.user_color === 'white' ? 'W' : 'B'}
                    </Text>
                  </View>
                  
                  <View style={styles.gameInfo}>
                    <Text style={styles.gamePlayers} numberOfLines={1}>
                      {game.white_player} vs {game.black_player}
                    </Text>
                    <View style={styles.gameMeta}>
                      <Text style={styles.gameMetaText}>{game.platform}</Text>
                      <Text style={styles.gameMetaDot}>•</Text>
                      <Text style={styles.gameMetaText}>{game.result}</Text>
                      {game.opening && (
                        <>
                          <Text style={styles.gameMetaDot}>•</Text>
                          <Text style={styles.gameMetaText} numberOfLines={1}>
                            {game.opening}
                          </Text>
                        </>
                      )}
                    </View>
                  </View>
                </View>
                
                <View style={styles.gameRight}>
                  {game.is_analyzed ? (
                    <View style={styles.analyzedBadge}>
                      <Ionicons name="checkmark" size={14} color={StatusColors.improving} />
                    </View>
                  ) : (
                    <View style={styles.pendingBadge}>
                      <Ionicons name="hourglass-outline" size={14} color={colors.textSecondary} />
                    </View>
                  )}
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </ScrollView>

      {/* Import Modal */}
      <Modal
        visible={importModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setImportModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Import Games</Text>
              <TouchableOpacity onPress={() => setImportModal(false)}>
                <Ionicons name="close" size={24} color={colors.text} />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalLabel}>Platform</Text>
            <View style={styles.platformSelector}>
              <TouchableOpacity 
                style={[
                  styles.platformOption,
                  platform === 'chess.com' && styles.platformOptionActive
                ]}
                onPress={() => setPlatform('chess.com')}
              >
                <Text style={[
                  styles.platformOptionText,
                  platform === 'chess.com' && styles.platformOptionTextActive
                ]}>Chess.com</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={[
                  styles.platformOption,
                  platform === 'lichess' && styles.platformOptionActive
                ]}
                onPress={() => setPlatform('lichess')}
              >
                <Text style={[
                  styles.platformOptionText,
                  platform === 'lichess' && styles.platformOptionTextActive
                ]}>Lichess</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.modalLabel}>Username</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="Enter your username"
              placeholderTextColor={colors.textSecondary}
              value={username}
              onChangeText={setUsername}
              autoCapitalize="none"
              autoCorrect={false}
            />

            <TouchableOpacity 
              style={styles.importModalButton}
              onPress={handleImport}
              disabled={importing}
            >
              {importing ? (
                <ActivityIndicator color={colors.background} />
              ) : (
                <>
                  <Ionicons name="cloud-download" size={20} color={colors.background} />
                  <Text style={styles.importModalButtonText}>Import 10 Games</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const createStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 16,
  },
  greeting: {
    fontSize: 11,
    color: colors.textSecondary,
    letterSpacing: 1,
    marginBottom: 4,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    letterSpacing: -0.5,
  },
  importButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.card,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  scrollView: {
    flex: 1,
  },
  content: {
    padding: 20,
    paddingTop: 0,
    paddingBottom: 40,
  },
  emptyState: {
    alignItems: 'center',
    padding: 40,
    marginTop: 60,
  },
  emptyIcon: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: colors.card,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
    borderWidth: 2,
    borderColor: colors.border,
    borderStyle: 'dashed',
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 8,
  },
  emptyText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 22,
  },
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.text,
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 12,
    gap: 8,
  },
  primaryButtonText: {
    color: colors.background,
    fontSize: 16,
    fontWeight: '600',
  },
  gamesList: {
    gap: 8,
  },
  gameCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  gameMain: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  colorBadge: {
    width: 32,
    height: 32,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  colorText: {
    fontSize: 14,
    fontWeight: '700',
  },
  gameInfo: {
    flex: 1,
  },
  gamePlayers: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  gameMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  gameMetaText: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  gameMetaDot: {
    fontSize: 12,
    color: colors.textSecondary,
    marginHorizontal: 6,
  },
  gameRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginLeft: 12,
  },
  analyzedBadge: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  pendingBadge: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.muted,
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.card,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
  },
  modalLabel: {
    fontSize: 11,
    color: colors.textSecondary,
    letterSpacing: 1,
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  platformSelector: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 20,
  },
  platformOption: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
  },
  platformOptionActive: {
    backgroundColor: colors.text,
    borderColor: colors.text,
  },
  platformOptionText: {
    color: colors.text,
    fontWeight: '500',
  },
  platformOptionTextActive: {
    color: colors.background,
  },
  modalInput: {
    backgroundColor: colors.muted,
    borderRadius: 10,
    padding: 14,
    color: colors.text,
    fontSize: 15,
    marginBottom: 24,
  },
  importModalButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.text,
    paddingVertical: 16,
    borderRadius: 12,
    gap: 8,
  },
  importModalButtonText: {
    color: colors.background,
    fontSize: 16,
    fontWeight: '600',
  },
});
