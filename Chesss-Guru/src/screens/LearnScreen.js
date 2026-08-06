import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ImageBackground, ActivityIndicator } from 'react-native';
import { COLORS } from '../constants/config';
import { getGamificationProgress, getOpeningsProgress } from '../services/api';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function LearnScreen({ navigation }) {
  const [loading, setLoading] = useState(true);

  // Live stats and mastery summary
  const [xpData, setXpData] = useState({ level: 1, xp: 0, next_level_xp: 1000, title: 'Grandmaster Scholar' });
  const [summary, setSummary] = useState({ total: 94, studied: 0, stale: 0 });
  const [byKind, setByKind] = useState({
    concept: [],
    endgame: [],
    mate_pattern: [],
    opening: [],
  });

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        // 1. Get Gamification details (Level/XP)
        try {
          const gamRes = await getGamificationProgress();
          if (gamRes) {
            setXpData({
              level: gamRes.level || 1,
              xp: gamRes.xp || 0,
              next_level_xp: gamRes.next_level_xp || 1000,
              title: gamRes.title || 'Grandmaster Scholar',
            });
          }
        } catch (_) {}

        // 2. Get Engine 2 mastery summary list
        try {
          const summaryRes = await getOpeningsProgress();
          if (summaryRes) {
            // Calculate total count
            const sumData = summaryRes.summary || {};
            const studied = sumData.studied || 0;
            const stale = sumData.stale || 0;
            const learning = sumData.learning || 0;
            const unseen = sumData.unseen || 0;
            const demonstrated = sumData.demonstrated || 0;
            const total = studied + stale + learning + unseen + demonstrated || 94;

            setSummary({
              total,
              studied,
              stale,
              learning,
              unseen,
              demonstrated,
            });

            if (summaryRes.by_kind) {
              setByKind({
                concept: summaryRes.by_kind.concept || [],
                endgame: summaryRes.by_kind.endgame || [],
                mate_pattern: summaryRes.by_kind.mate_pattern || [],
                opening: summaryRes.by_kind.opening || [],
              });
            }
          }
        } catch (e) {
          console.log('[LearnScreen] mastery summary load failed:', e);
        }

      } catch (e) {
        console.log('[LearnScreen] error:', e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const progressPercent = Math.min(100, Math.round((xpData.xp / xpData.next_level_xp) * 100)) + '%';

  // Helper to format state/status text
  const formatStatus = (item) => {
    const s = item.state;
    if (s === 'studied') return 'Studied';
    if (s === 'stale') return 'Worth a refresher';
    if (s === 'learning') return 'In Progress';
    if (s === 'demonstrated') return 'Demonstrated';
    return 'Not started';
  };

  // Helper to format tier badges
  const getTierLabel = (tier) => {
    if (tier === undefined || tier === null) return '';
    return `T${tier}`;
  };

  // Helper to format item state styling
  const getBadgeStyle = (state) => {
    if (state === 'studied' || state === 'demonstrated') return styles.completedBadge;
    if (state === 'stale') return styles.staleBadge;
    if (state === 'learning') return styles.progressBadge;
    return styles.lockedBadge;
  };

  const getBadgeTextStyle = (state) => {
    if (state === 'studied' || state === 'demonstrated') return { color: '#22c55e' };
    if (state === 'stale') return { color: '#ef4444' };
    if (state === 'learning') return { color: '#eab308' };
    return { color: '#94a3b8' };
  };

  const handleItemPress = (item) => {
    // Navigate to Play tab (CoachPlayScreen) with startup parameters
    navigation.navigate('CoachPlayTab', {
      startSkillId: item.skill_id,
      startLabel: item.label,
      startKind: item.kind,
      startContentRef: item.content_ref,
      startColor: item.kind === 'opening' && item.skill_id.endsWith('_black') ? 'black' : 'white',
    });
  };

  return (
    <ImageBackground
      source={require('../../assets/dashboard_chess_bg.png')}
      style={styles.bgImage}
      resizeMode="cover"
    >
      <View style={styles.darkOverlay} />

      <SafeAreaView style={styles.safe}>
        <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.headerTitle}>Learn & Mastery 🎓</Text>
            <Text style={styles.headerSubtitle}>Master Chess Curriculum & Opening Guides</Text>
          </View>

          {/* Level XP Progress Banner */}
          <View style={styles.xpCard}>
            <View style={styles.xpHeader}>
              <Text style={styles.xpLevel}>Level {xpData.level} • {xpData.title}</Text>
              <Text style={styles.xpPoints}>{xpData.xp} / {xpData.next_level_xp} XP</Text>
            </View>
            <View style={styles.progressBarBg}>
              <View style={[styles.progressBarFill, { width: progressPercent }]} />
            </View>
          </View>

          {/* Skills study overview stats bar */}
          <View style={styles.statsCard}>
            <Text style={styles.statsTitle}>Skills • what you've studied</Text>
            <Text style={styles.statsSubtitle}>
              {summary.studied || 0} of {summary.total} studied • {summary.stale || 0} to refresh
            </Text>
          </View>

          {loading ? (
            <View style={styles.loaderContainer}>
              <ActivityIndicator size="large" color="#eab308" />
            </View>
          ) : (
            <View style={styles.sectionsContainer}>

              {/* ── CONCEPTS SECTION ── */}
              <View style={styles.sectionBlock}>
                <Text style={styles.sectionHeader}>Concepts</Text>
                {byKind.concept.length > 0 ? byKind.concept.map((item, idx) => (
                  <TouchableOpacity key={idx} style={styles.itemRow} onPress={() => handleItemPress(item)} activeOpacity={0.75}>
                    <View style={styles.itemInfo}>
                      <Text style={styles.itemLabel}>{item.label}</Text>
                      {item.progress_hint ? <Text style={styles.itemHint}>{item.progress_hint}</Text> : null}
                    </View>
                    <View style={styles.rightGroup}>
                      {getTierLabel(item.tier) ? (
                        <View style={styles.tierTag}><Text style={styles.tierText}>{getTierLabel(item.tier)}</Text></View>
                      ) : null}
                      <View style={[styles.statusBadge, getBadgeStyle(item.state)]}>
                        <Text style={[styles.statusBadgeText, getBadgeTextStyle(item.state)]}>
                          {formatStatus(item)}
                        </Text>
                      </View>
                    </View>
                  </TouchableOpacity>
                )) : <Text style={styles.emptyText}>No concepts available.</Text>}
              </View>

              {/* ── ENDGAMES SECTION ── */}
              <View style={styles.sectionBlock}>
                <Text style={styles.sectionHeader}>Endgames</Text>
                {byKind.endgame.length > 0 ? byKind.endgame.map((item, idx) => (
                  <TouchableOpacity key={idx} style={styles.itemRow} onPress={() => handleItemPress(item)} activeOpacity={0.75}>
                    <View style={styles.itemInfo}>
                      <Text style={styles.itemLabel}>{item.label}</Text>
                      {item.progress_hint ? <Text style={styles.itemHint}>{item.progress_hint}</Text> : null}
                    </View>
                    <View style={styles.rightGroup}>
                      {getTierLabel(item.tier) ? (
                        <View style={styles.tierTag}><Text style={styles.tierText}>{getTierLabel(item.tier)}</Text></View>
                      ) : null}
                      <View style={[styles.statusBadge, getBadgeStyle(item.state)]}>
                        <Text style={[styles.statusBadgeText, getBadgeTextStyle(item.state)]}>
                          {formatStatus(item)}
                        </Text>
                      </View>
                    </View>
                  </TouchableOpacity>
                )) : <Text style={styles.emptyText}>No endgames available.</Text>}
              </View>

              {/* ── MATE PATTERNS SECTION ── */}
              <View style={styles.sectionBlock}>
                <Text style={styles.sectionHeader}>Mate patterns</Text>
                {byKind.mate_pattern.length > 0 ? byKind.mate_pattern.map((item, idx) => (
                  <TouchableOpacity key={idx} style={styles.itemRow} onPress={() => handleItemPress(item)} activeOpacity={0.75}>
                    <View style={styles.itemInfo}>
                      <Text style={styles.itemLabel}>{item.label}</Text>
                      {item.progress_hint ? <Text style={styles.itemHint}>{item.progress_hint}</Text> : null}
                    </View>
                    <View style={styles.rightGroup}>
                      {getTierLabel(item.tier) ? (
                        <View style={styles.tierTag}><Text style={styles.tierText}>{getTierLabel(item.tier)}</Text></View>
                      ) : null}
                      <View style={[styles.statusBadge, getBadgeStyle(item.state)]}>
                        <Text style={[styles.statusBadgeText, getBadgeTextStyle(item.state)]}>
                          {formatStatus(item)}
                        </Text>
                      </View>
                    </View>
                  </TouchableOpacity>
                )) : <Text style={styles.emptyText}>No mate patterns available.</Text>}
              </View>

              {/* ── OPENINGS SECTION ── */}
              <View style={styles.sectionBlock}>
                <Text style={styles.sectionHeader}>Openings</Text>
                {byKind.opening.length > 0 ? byKind.opening.map((item, idx) => (
                  <TouchableOpacity key={idx} style={styles.itemRow} onPress={() => handleItemPress(item)} activeOpacity={0.75}>
                    <View style={styles.itemInfo}>
                      <Text style={styles.itemLabel}>{item.label}</Text>
                      {item.progress_hint ? <Text style={styles.itemHint}>{item.progress_hint}</Text> : null}
                    </View>
                    <View style={styles.rightGroup}>
                      {getTierLabel(item.tier) ? (
                        <View style={styles.tierTag}><Text style={styles.tierText}>{getTierLabel(item.tier)}</Text></View>
                      ) : null}
                      <View style={[styles.statusBadge, getBadgeStyle(item.state)]}>
                        <Text style={[styles.statusBadgeText, getBadgeTextStyle(item.state)]}>
                          {formatStatus(item)}
                        </Text>
                      </View>
                    </View>
                  </TouchableOpacity>
                )) : <Text style={styles.emptyText}>No openings available.</Text>}
              </View>

            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    </ImageBackground>
  );
}

const styles = StyleSheet.create({
  bgImage: { flex: 1, width: '100%', height: '100%' },
  darkOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(5, 8, 16, 0.55)' },
  safe: { flex: 1 },
  container: { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },

  header: { marginBottom: 16, marginTop: 4 },
  headerTitle: { color: '#ffffff', fontSize: 26, fontWeight: '900', letterSpacing: 0.5 },
  headerSubtitle: { color: '#cbd5e1', fontSize: 13, marginTop: 4, fontWeight: '600' },

  xpCard: { backgroundColor: 'rgba(15, 23, 42, 0.85)', borderRadius: 20, padding: 16, borderWidth: 1.2, borderColor: 'rgba(255, 255, 255, 0.15)', marginBottom: 14 },
  xpHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10 },
  xpLevel: { color: '#ffffff', fontSize: 13, fontWeight: '800' },
  xpPoints: { color: '#eab308', fontSize: 13, fontWeight: '900' },
  progressBarBg: { height: 6, backgroundColor: 'rgba(255, 255, 255, 0.15)', borderRadius: 3, overflow: 'hidden' },
  progressBarFill: { height: '100%', backgroundColor: '#eab308', borderRadius: 3 },

  statsCard: { backgroundColor: 'rgba(30, 41, 59, 0.7)', borderRadius: 16, padding: 16, borderWidth: 1, borderColor: 'rgba(255, 255, 255, 0.1)', marginBottom: 16 },
  statsTitle: { color: '#fff', fontSize: 15, fontWeight: '900' },
  statsSubtitle: { color: '#eab308', fontSize: 13, fontWeight: '700', marginTop: 4 },

  sectionsContainer: { gap: 18 },
  sectionBlock: { backgroundColor: 'rgba(15, 23, 42, 0.85)', borderRadius: 22, padding: 16, borderWidth: 1.2, borderColor: 'rgba(234, 179, 8, 0.3)' },
  sectionHeader: { color: '#ffffff', fontSize: 15, fontWeight: '900', borderBottomWidth: 1.5, borderColor: 'rgba(255,255,255,0.1)', paddingBottom: 8, marginBottom: 12 },

  itemRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderColor: 'rgba(255,255,255,0.06)' },
  itemInfo: { flex: 1, paddingRight: 8 },
  itemLabel: { color: '#ffffff', fontSize: 14, fontWeight: '800' },
  itemHint: { color: '#94a3b8', fontSize: 11, fontWeight: '600', marginTop: 2 },

  rightGroup: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  tierTag: { backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 8, paddingHorizontal: 6, paddingVertical: 3, borderWidth: 1, borderColor: 'rgba(255,255,255,0.15)' },
  tierText: { color: '#fef08a', fontSize: 10, fontWeight: '900' },

  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10, minWidth: 80, alignItems: 'center' },
  completedBadge: { backgroundColor: 'rgba(34, 197, 94, 0.15)', borderWidth: 1, borderColor: 'rgba(34, 197, 94, 0.3)' },
  staleBadge: { backgroundColor: 'rgba(239, 68, 68, 0.15)', borderWidth: 1, borderColor: 'rgba(239, 68, 68, 0.3)' },
  progressBadge: { backgroundColor: 'rgba(234, 179, 8, 0.15)', borderWidth: 1, borderColor: 'rgba(234, 179, 8, 0.3)' },
  lockedBadge: { backgroundColor: 'rgba(255, 255, 255, 0.05)', borderWidth: 1, borderColor: 'rgba(255, 255, 255, 0.1)' },
  statusBadgeText: { fontSize: 10, fontWeight: '900' },

  emptyText: { color: '#64748b', fontSize: 12, paddingVertical: 8, fontStyle: 'italic' },
  loaderContainer: { marginVertical: 40, alignItems: 'center', justifyContent: 'center' },
});
