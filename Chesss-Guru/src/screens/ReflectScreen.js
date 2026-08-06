import React, { useState, useEffect, useContext } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, ImageBackground, Alert,
} from 'react-native';
import { COLORS } from '../constants/config';
import { AuthContext } from '../context/AuthContext';
import {
  getCoachingCurrentPrescriptions,
  getCoachingNextPrescription,
  acceptCoachingPrescription,
} from '../services/api';

export default function ReflectScreen({ navigation }) {
  const { user } = useContext(AuthContext);
  const [activePlan, setActivePlan] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const loadData = async () => {
    try {
      const [currentRes, recRes] = await Promise.all([
        getCoachingCurrentPrescriptions().catch(() => null),
        getCoachingNextPrescription().catch(() => null),
      ]);

      // If active plan exists, set it
      if (currentRes && currentRes.prescriptions && currentRes.prescriptions.length > 0) {
        setActivePlan(currentRes.prescriptions[0]);
      } else {
        setActivePlan(null);
      }

      setRecommendation(recRes?.recommendation || null);
    } catch (e) {
      console.log('Error loading Ledger data:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleStartPlan = async (planId, presId) => {
    if (!presId && !recommendation?.prescription_id) {
      // Fallback for mock/demo purposes
      setActionLoading(true);
      setTimeout(() => {
        setActionLoading(false);
        setActivePlan({
          plan_name: recommendation?.name || 'Piece Safety Fundamentals',
          issue_detected: recommendation?.cognitive_gap || 'piece_safety',
          reasoning: recommendation?.reasoning || "Coach detected 4 occurrences of piece safety issues.",
          status: 'active',
          current_metric: 0,
        });
        Alert.alert('Plan Started', 'Successfully started your new training plan!');
      }, 1000);
      return;
    }

    const targetPresId = presId || recommendation.prescription_id;
    setActionLoading(true);
    try {
      await acceptCoachingPrescription(targetPresId);
      Alert.alert('Success', 'Your new training plan has been activated!');
      loadData();
    } catch (e) {
      Alert.alert('Error', 'Failed to start training plan. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>Reading the ledger...</Text>
      </View>
    );
  }

  // FALLBACK DATA (Matches user screenshot exactly if no data exists in DB yet)
  const defaultRecommendation = {
    plan_id: 'rec_01',
    name: 'Piece Safety Fundamentals',
    cognitive_gap: 'piece_safety',
    description: 'Focus on keeping your pieces protected and avoiding simple blunders.',
    reasoning: 'Coach detected 4 occurrences of piece safety issues in your recent games.',
    mistakes_found: 4,
    confidence: '58%',
    recent: '115d ago',
    rating_gains: {
      conservative: '+34',
      realistic: '+42',
      optimistic: '+47',
    }
  };

  const defaultAlternatives = [
    {
      plan_id: 'alt_01',
      name: 'King Safety & Defense',
      mistakes: 5,
      confidence: '60%',
      gain: '+21 elo',
    }
  ];

  const finalRecommendation = recommendation || defaultRecommendation;

  return (
    <ImageBackground
      source={require('../../assets/dashboard_chess_bg.png')}
      style={styles.bgImage}
      resizeMode="cover"
    >
      <View style={styles.darkOverlay} />

      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadData(); }} tintColor={COLORS.primary} />
        }
      >
        {/* Title Header */}
        <View style={styles.header}>
          <Text style={styles.pageSubtitle}>PROGRESS · THE LEDGER</Text>
          <Text style={styles.pageTitle}>
            {activePlan ? `${activePlan.plan_name} is the pattern we're breaking right now.` : "Conversion technique is the pattern we're breaking right now."}
          </Text>
          <Text style={styles.pageDescription}>
            {activePlan?.reasoning || "You get good positions but then throw them away. Conversion is the issue."}
          </Text>
        </View>

        {/* CURRENTLY WORKING ON SECTION */}
        <Text style={styles.sectionTitle}>CURRENTLY WORKING ON</Text>
        <View style={styles.activePlanCard}>
          <View style={styles.activeHeader}>
            <Text style={styles.activePlanName}>{activePlan?.plan_name || 'Conversion technique'}</Text>
            <Text style={styles.cleanGamesText}>
              {activePlan?.current_metric || 0} / 5 clean games
            </Text>
          </View>
          <Text style={styles.activeQuote}>
            "We'll close this chapter once the pattern stays quiet for 5 games."
          </Text>

          {/* Habit breakdown inside active plan */}
          <View style={styles.habitBox}>
            <Text style={styles.habitHeader}>What you keep doing</Text>
            <Text style={styles.habitTitle}>What changed after the move?</Text>
            <Text style={styles.habitSub}>
              Seen 8 times across your recent games — last time vs TaryanKaushik.
            </Text>
            <View style={styles.habitBtnRow}>
              <TouchableOpacity style={styles.habitBtn} onPress={() => navigation.navigate('StudioTab')} activeOpacity={0.8}>
                <Text style={styles.habitBtnText}>Review the game</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.habitBtn, styles.habitBtnPrimary]} onPress={() => navigation.navigate('CoachPlayTab')} activeOpacity={0.8}>
                <Text style={[styles.habitBtnText, { color: '#000' }]}>Practice pattern</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* CHOOSE YOUR TRAINING PLAN */}
        {!activePlan && (
          <>
            <Text style={styles.sectionTitle}>CHOOSE YOUR TRAINING PLAN</Text>
            
            {/* Top Recommendation */}
            <View style={styles.recommendationCard}>
              <View style={styles.recBadge}>
                <Text style={styles.recBadgeText}>🧭 COACH'S TOP RECOMMENDATION</Text>
              </View>

              <Text style={styles.recName}>{finalRecommendation.name}</Text>
              <Text style={styles.recFocus}>Focus: {finalRecommendation.cognitive_gap?.replace('_', ' ')}</Text>

              {/* Stats Grid */}
              <View style={styles.statsGrid}>
                <View style={styles.statCell}>
                  <Text style={styles.statLabel}>MISTAKES FOUND</Text>
                  <Text style={styles.statVal}>{finalRecommendation.mistakes_found || 4}</Text>
                </View>
                <View style={styles.statCell}>
                  <Text style={styles.statLabel}>CONFIDENCE</Text>
                  <Text style={styles.statVal}>{finalRecommendation.confidence || '58%'}</Text>
                </View>
                <View style={styles.statCell}>
                  <Text style={styles.statLabel}>RECENT</Text>
                  <Text style={styles.statVal}>{finalRecommendation.recent || '115d ago'}</Text>
                </View>
              </View>

              {/* Rating Gain Section */}
              <View style={styles.gainBox}>
                <Text style={styles.gainTitle}>📈 ESTIMATED RATING GAIN</Text>
                <View style={styles.gainRow}>
                  <View style={styles.gainCell}>
                    <Text style={styles.gainCellLabel}>Conservative (70%)</Text>
                    <Text style={styles.gainCellVal}>{finalRecommendation.rating_gains?.conservative || '+34'}</Text>
                  </View>
                  <View style={styles.gainCell}>
                    <Text style={styles.gainCellLabel}>Realistic (85%)</Text>
                    <Text style={styles.gainCellVal}>{finalRecommendation.rating_gains?.realistic || '+42'}</Text>
                  </View>
                  <View style={styles.gainCell}>
                    <Text style={styles.gainCellLabel}>Optimistic (95%)</Text>
                    <Text style={styles.gainCellVal}>{finalRecommendation.rating_gains?.optimistic || '+47'}</Text>
                  </View>
                </View>
              </View>

              {/* Primary Start Button */}
              <TouchableOpacity
                style={styles.startPlanBtn}
                onPress={() => handleStartPlan(finalRecommendation.plan_id)}
                disabled={actionLoading}
                activeOpacity={0.85}
              >
                {actionLoading ? <ActivityIndicator color="#000" size="small" /> : (
                  <Text style={styles.startPlanBtnText}>Start This Training Plan</Text>
                )}
              </TouchableOpacity>
            </View>

            {/* Alternatives */}
            <Text style={styles.sectionTitle}>OR CHOOSE ANOTHER PLAN</Text>
            {defaultAlternatives.map((alt, i) => (
              <View key={i} style={styles.alternativeCard}>
                <View style={styles.altHeader}>
                  <View>
                    <Text style={styles.altName}>{alt.name}</Text>
                    <Text style={styles.altSub}>{alt.mistakes} mistakes · {alt.confidence} confidence</Text>
                  </View>
                  <View style={styles.altGainBadge}>
                    <Text style={styles.altGainLabel}>Estimated Gain</Text>
                    <Text style={styles.altGainVal}>{alt.gain}</Text>
                  </View>
                </View>
                <TouchableOpacity
                  style={styles.altStartBtn}
                  onPress={() => handleStartPlan(alt.plan_id)}
                  activeOpacity={0.85}
                >
                  <Text style={styles.altStartBtnText}>Start This Plan</Text>
                </TouchableOpacity>
              </View>
            ))}
          </>
        )}

        {/* ALSO TRACKING */}
        <Text style={styles.sectionTitle}>ALSO TRACKING</Text>
        <View style={styles.trackingCard}>
          <View style={styles.trackingHeader}>
            <Text style={styles.trackingName}>Threat Awareness</Text>
            <Text style={styles.trackingStatus}>0 / 5 clean</Text>
          </View>
          <Text style={styles.trackingDesc}>
            You often miss what your opponent is threatening. Before each move, ask: what did their last move attack?
          </Text>
          <TouchableOpacity style={styles.trackingBtn} onPress={() => navigation.navigate('CoachPlayTab')} activeOpacity={0.8}>
            <Text style={styles.trackingBtnText}>Practice ➔</Text>
          </TouchableOpacity>
        </View>

        {/* ARCHIVED SECTION */}
        <Text style={styles.sectionTitle}>ARCHIVED · YOU'VE BEEN CONSISTENT AT</Text>
        {[
          { label: 'Your positional sense is developing well.', status: 'stable' },
          { label: "You're good at spotting tactics and combinations.", status: 'stable' },
          { label: "You're good at keeping your king safe.", status: 'stable' }
        ].map((item, index) => (
          <View key={index} style={styles.archivedCard}>
            <View style={styles.archivedHeader}>
              <Text style={styles.archivedLabel}>{item.label}</Text>
              <View style={styles.archivedStatusBadge}>
                <Text style={styles.archivedStatusText}>{item.status}</Text>
              </View>
            </View>
            <Text style={styles.archivedCleanText}>Clean — keep it that way</Text>
          </View>
        ))}

      </ScrollView>
    </ImageBackground>
  );
}

const styles = StyleSheet.create({
  bgImage: { flex: 1, width: '100%', height: '100%' },
  darkOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(9, 13, 22, 0.45)' },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: 16, paddingBottom: 40 },
  center: { flex: 1, backgroundColor: COLORS.background, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: COLORS.textMuted, marginTop: 12, fontSize: 14 },
  header: { marginBottom: 24, marginTop: 10 },
  pageSubtitle: { color: COLORS.primary, fontSize: 11, fontWeight: '800', letterSpacing: 1.5, marginBottom: 8 },
  pageTitle: { color: '#ffffff', fontSize: 24, fontWeight: '900', lineHeight: 32, marginBottom: 8 },
  pageDescription: { color: COLORS.textMuted, fontSize: 14, lineHeight: 20 },
  sectionTitle: { color: '#ffffff', fontSize: 11, fontWeight: '800', letterSpacing: 1.5, marginTop: 24, marginBottom: 12 },
  activePlanCard: { backgroundColor: 'rgba(19, 27, 46, 0.85)', borderRadius: 20, padding: 18, borderWidth: 1, borderColor: COLORS.cardBorder },
  activeHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  activePlanName: { color: '#ffffff', fontSize: 16, fontWeight: '900' },
  cleanGamesText: { color: COLORS.secondary, fontSize: 13, fontWeight: '800' },
  activeQuote: { color: COLORS.textMuted, fontSize: 13, fontStyle: 'italic', marginBottom: 16 },
  habitBox: { backgroundColor: 'rgba(9, 13, 22, 0.6)', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: COLORS.cardBorder },
  habitHeader: { color: COLORS.primary, fontSize: 10, fontWeight: '850', letterSpacing: 1, marginBottom: 6 },
  habitTitle: { color: '#ffffff', fontSize: 14, fontWeight: '800' },
  habitSub: { color: COLORS.textMuted, fontSize: 12, marginTop: 2, lineHeight: 16, marginBottom: 12 },
  habitBtnRow: { flexDirection: 'row', gap: 10 },
  habitBtn: { flex: 1, backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 10, paddingVertical: 8, alignItems: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  habitBtnPrimary: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  habitBtnText: { color: '#ffffff', fontWeight: '750', fontSize: 12 },
  recommendationCard: { backgroundColor: 'rgba(19, 27, 46, 0.85)', borderRadius: 22, padding: 18, borderWidth: 1.5, borderColor: '#3b82f6', marginBottom: 16 },
  recBadge: { marginBottom: 10 },
  recBadgeText: { color: '#3b82f6', fontSize: 10, fontWeight: '850', letterSpacing: 1 },
  recName: { color: '#ffffff', fontSize: 18, fontWeight: '950' },
  recFocus: { color: COLORS.textMuted, fontSize: 13, marginTop: 2, marginBottom: 16 },
  statsGrid: { flexDirection: 'row', gap: 12, paddingVertical: 12, borderTopWidth: 1, borderBottomWidth: 1, borderColor: 'rgba(255,255,255,0.08)', marginBottom: 16 },
  statCell: { flex: 1 },
  statLabel: { color: COLORS.textMuted, fontSize: 9, fontWeight: '800', letterSpacing: 0.5, marginBottom: 4 },
  statVal: { color: '#ffffff', fontSize: 15, fontWeight: '900' },
  gainBox: { backgroundColor: 'rgba(9, 13, 22, 0.5)', borderRadius: 14, padding: 14, marginBottom: 16 },
  gainTitle: { color: COLORS.secondary, fontSize: 10, fontWeight: '850', letterSpacing: 1, marginBottom: 12 },
  gainRow: { flexDirection: 'row', gap: 10 },
  gainCell: { flex: 1 },
  gainCellLabel: { color: COLORS.textMuted, fontSize: 9, marginBottom: 3 },
  gainCellVal: { color: COLORS.secondary, fontSize: 16, fontWeight: '950' },
  startPlanBtn: { backgroundColor: '#2563eb', borderRadius: 14, paddingVertical: 13, alignItems: 'center' },
  startPlanBtnText: { color: '#ffffff', fontWeight: '900', fontSize: 14 },
  alternativeCard: { backgroundColor: 'rgba(19, 27, 46, 0.85)', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: COLORS.cardBorder, marginBottom: 10 },
  altHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  altName: { color: '#ffffff', fontSize: 14, fontWeight: '850' },
  altSub: { color: COLORS.textMuted, fontSize: 12, marginTop: 2 },
  altGainBadge: { alignItems: 'flex-end' },
  altGainLabel: { color: COLORS.textMuted, fontSize: 9 },
  altGainVal: { color: COLORS.secondary, fontSize: 14, fontWeight: '850', marginTop: 1 },
  altStartBtn: { backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 12, paddingVertical: 10, alignItems: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  altStartBtnText: { color: '#ffffff', fontWeight: '750', fontSize: 13 },
  trackingCard: { backgroundColor: 'rgba(19, 27, 46, 0.85)', borderRadius: 16, padding: 16, borderWidth: 1, borderColor: COLORS.cardBorder, marginBottom: 10 },
  trackingHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  trackingName: { color: '#ffffff', fontSize: 14, fontWeight: '800' },
  trackingStatus: { color: COLORS.textMuted, fontSize: 12, fontWeight: '700' },
  trackingDesc: { color: COLORS.textMuted, fontSize: 13, lineHeight: 18, marginBottom: 12 },
  trackingBtn: { alignSelf: 'flex-start', paddingVertical: 6, paddingHorizontal: 12, backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 8 },
  trackingBtnText: { color: COLORS.secondary, fontSize: 12, fontWeight: '800' },
  archivedCard: { backgroundColor: 'rgba(19, 27, 46, 0.85)', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: COLORS.cardBorder, marginBottom: 8 },
  archivedHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  archivedLabel: { color: COLORS.textMuted, fontSize: 13, flex: 1, paddingRight: 8 },
  archivedStatusBadge: { backgroundColor: 'rgba(34,197,94,0.12)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  archivedStatusText: { color: '#22c55e', fontSize: 10, fontWeight: '800' },
  archivedCleanText: { color: '#22c55e', fontSize: 12, fontWeight: '800' },
});
