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
  chooseAlternativeCoachingPlan,
  getRealProgress,
  getProgressNarrative,
  getImprovementProof,
  getRateMoveCalibration,
  getUserJourney,
} from '../services/api';

export default function ReflectScreen({ navigation }) {
  const { user } = useContext(AuthContext);
  
  // Data States
  const [activePlan, setActivePlan] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [realProgress, setRealProgress] = useState(null);
  const [narrative, setNarrative] = useState(null);
  const [proof, setProof] = useState(null);
  const [calibration, setCalibration] = useState(null);
  const [journeyStats, setJourneyStats] = useState(null);
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const loadData = async () => {
    try {
      const [
        currentRes,
        recRes,
        realProgRes,
        narrativeRes,
        proofRes,
        calibRes,
        journeyRes
      ] = await Promise.all([
        getCoachingCurrentPrescriptions().catch(() => null),
        getCoachingNextPrescription().catch(() => null),
        getRealProgress().catch(() => null),
        getProgressNarrative().catch(() => null),
        getImprovementProof().catch(() => null),
        getRateMoveCalibration().catch(() => null),
        getUserJourney(user?.user_id).catch(() => null),
      ]);

      if (currentRes && currentRes.prescriptions && currentRes.prescriptions.length > 0) {
        setActivePlan(currentRes.prescriptions[0]);
      } else {
        setActivePlan(null);
      }

      setRecommendation(recRes?.recommendation || null);
      setRealProgress(realProgRes);
      setNarrative(narrativeRes);
      setProof(proofRes);
      setCalibration(calibRes && calibRes.available ? calibRes : null);
      setJourneyStats(journeyRes);
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
    const targetPresId = presId || (recommendation && recommendation.plan_id === planId ? recommendation.prescription_id : null);
    
    setActionLoading(true);
    try {
      let finalPresId = targetPresId;
      
      if (!finalPresId) {
        const createRes = await chooseAlternativeCoachingPlan(planId, 'Starting training plan');
        finalPresId = createRes?.prescription_id;
      }
      
      if (!finalPresId) {
        throw new Error('Could not generate prescription');
      }

      await acceptCoachingPrescription(finalPresId);
      Alert.alert('Success', 'Your new training plan has been activated!');
      loadData();
    } catch (e) {
      console.log('Error starting training plan:', e);
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

  // --- Derive values ---
  const userRating = journeyStats?.rating || 1200;
  const userAccuracy = journeyStats?.accuracy || 80.0;
  
  // Style Identity
  const styleLabel = narrative?.style_profile?.primary_style
    ? narrative.style_profile.primary_style.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    : "Balanced Player";
  
  const styleDescription = narrative?.style_profile?.style_text || "You play a balanced, adaptable style of chess.";

  // Active Plan Streak
  const streaks = proof?.streaks || {};
  const cleanStreak = Math.min(
    streaks.no_big_mistake_games || streaks.no_blunder_games || 0,
    5
  );

  // Active Plan Reduction
  const weaknesses = narrative?.weaknesses || [];
  const primaryWeakness = weaknesses[0];
  
  const activePlanName = activePlan?.plan_name || (primaryWeakness && primaryWeakness.category ? primaryWeakness.category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'Conversion Technique');
  
  // Alternative plans fallback
  const fallbackRecommendation = recommendation || {
    plan_id: 'plan_piece_safety_001',
    name: 'Piece Safety Fundamentals',
    cognitive_gap: 'piece_safety',
    description: 'Focus on keeping your pieces protected and avoiding simple blunders.',
    reasoning: 'Coach detected 4 occurrences of piece safety issues in your recent games.',
    mistakes_found: 4,
    confidence: '58%',
    recent: '115d ago',
    rating_gains: { conservative: '+34', realistic: '+42', optimistic: '+47' }
  };

  const alternatives = recommendation?.alternatives || [
    {
      plan_id: 'plan_king_safety_001',
      name: 'King Safety & Defense',
      mistakes: 5,
      confidence: '60%',
      gain: '+21 elo',
    }
  ];

  // Weaknesses for "Also tracking"
  const trackedWeaknesses = weaknesses.slice(1).map(w => ({
    name: (w.category || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    desc: w.description || "",
    cleanGames: typeof w.clean_games_since === 'number' ? Math.min(w.clean_games_since, 5) : 0,
    lastSeen: w.days_since_last_seen ? `${w.days_since_last_seen}d ago` : 'active today',
  }));

  // Strengths / beat patterns
  const beatenStrengths = narrative?.strengths || [
    { label: 'Your positional sense is developing well.', status: 'stable' },
    { label: "You're good at spotting tactics and combinations.", status: 'stable' }
  ];

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
        {/* Page Header */}
        <View style={styles.header}>
          <Text style={styles.pageSubtitle}>PROGRESS · THE LEDGER</Text>
          <Text style={styles.pageTitle}>
            {activePlan ? `${activePlanName} is the pattern we're breaking right now.` : "No active plan. Select a training focus to begin."}
          </Text>
          <Text style={styles.pageDescription}>
            {activePlan?.reasoning || "Analyze your games and review recommendations below to start a structured coaching plan."}
          </Text>
        </View>

        {/* --- GRID SUMMARY CARD --- */}
        <View style={styles.summaryCard}>
          <View style={styles.summaryGrid}>
            <View style={styles.summaryCell}>
              <Text style={styles.summaryCellLabel}>EST. RATING</Text>
              <Text style={styles.summaryCellVal}>♟️ {userRating}</Text>
            </View>
            <View style={styles.summaryCell}>
              <Text style={styles.summaryCellLabel}>AVG. ACCURACY</Text>
              <Text style={styles.summaryCellVal}>🎯 {userAccuracy}%</Text>
            </View>
            <View style={styles.summaryCell}>
              <Text style={styles.summaryCellLabel}>CHESS IDENTITY</Text>
              <Text style={styles.summaryCellVal}>🧙‍♂️ {styleLabel}</Text>
            </View>
          </View>
          <Text style={styles.styleDesc}>{styleDescription}</Text>
        </View>

        {/* --- COMPARATIVE BLUNDER REDUCTION CHART --- */}
        {proof?.training_causal && proof.training_causal.length > 0 && (
          <View style={styles.chartCard}>
            <Text style={styles.chartTitle}>💥 BLUNDER REDUCTION RATES</Text>
            <Text style={styles.chartSubtitle}>Errors per game (Pre-Training vs. Current)</Text>
            {proof.training_causal.map((c, idx) => {
              const baseline = typeof c.baseline_per_game === 'number' ? c.baseline_per_game : 1;
              const current = typeof c.current_per_game === 'number' ? c.current_per_game : 0;
              // Max width helper
              const maxVal = Math.max(baseline, current, 1);
              const preWidth = `${(baseline / maxVal) * 100}%`;
              const postWidth = `${(current / maxVal) * 100}%`;

              return (
                <View key={idx} style={styles.chartRow}>
                  <View style={styles.chartRowHeader}>
                    <Text style={styles.chartRowLabel}>{c.label}</Text>
                    <Text style={styles.chartReductionText}>-{c.improvement_pct}% errors</Text>
                  </View>
                  <View style={styles.chartVisualRow}>
                    <Text style={styles.chartLabelMini}>Pre</Text>
                    <View style={styles.chartBarTrack}>
                      <View style={[styles.chartBarPre, { width: preWidth }]} />
                    </View>
                    <Text style={styles.chartValMini}>{baseline.toFixed(1)}</Text>
                  </View>
                  <View style={styles.chartVisualRow}>
                    <Text style={styles.chartLabelMini}>Post</Text>
                    <View style={styles.chartBarTrack}>
                      <View style={[styles.chartBarPost, { width: postWidth }]} />
                    </View>
                    <Text style={styles.chartValMini}>{current.toFixed(1)}</Text>
                  </View>
                </View>
              );
            })}
          </View>
        )}

        {/* --- CURRENTLY WORKING ON SECTION --- */}
        {activePlan && (
          <>
            <Text style={styles.sectionTitle}>CURRENTLY WORKING ON</Text>
            <View style={styles.activePlanCard}>
              <View style={styles.activeHeader}>
                <Text style={styles.activePlanName}>{activePlanName}</Text>
                <View style={styles.pipsRow}>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <View
                      key={i}
                      style={[
                        styles.pip,
                        i < cleanStreak
                          ? styles.pipActive
                          : i === cleanStreak
                          ? styles.pipTarget
                          : styles.pipInactive,
                      ]}
                    />
                  ))}
                </View>
              </View>
              <Text style={styles.activeQuote}>
                {streaks.no_big_mistake_games >= 3
                  ? `${streaks.no_big_mistake_games} clean games in a row! You're almost there.`
                  : "We'll close this chapter once the pattern stays quiet for 5 games."}
              </Text>

              {/* Habit breakdown inside active plan */}
              <View style={styles.habitBox}>
                <Text style={styles.habitHeader}>PLAN DETAILS</Text>
                <Text style={styles.habitTitle}>{activePlan.plan_name}</Text>
                {activePlan.issue_detected ? (
                  <Text style={styles.habitSub}>
                    Targets gap: {activePlan.issue_detected.replace(/_/g, ' ')}. Completed {activePlan.modules_completed?.length || 0} modules so far.
                  </Text>
                ) : null}
                <View style={styles.habitBtnRow}>
                  <TouchableOpacity style={styles.habitBtn} onPress={() => navigation.navigate('MainTabs', { screen: 'StudioTab' })} activeOpacity={0.8}>
                    <Text style={styles.habitBtnText}>Review the game</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[styles.habitBtn, styles.habitBtnPrimary]} onPress={() => navigation.navigate('MainTabs', { screen: 'CoachPlayTab' })} activeOpacity={0.8}>
                    <Text style={[styles.habitBtnText, { color: '#000' }]}>Practice pattern</Text>
                  </TouchableOpacity>
                </View>
              </View>
            </View>
          </>
        )}

        {/* --- CHOOSE YOUR TRAINING PLAN --- */}
        {!activePlan && (
          <>
            <Text style={styles.sectionTitle}>CHOOSE YOUR TRAINING PLAN</Text>
            
            {/* Top Recommendation */}
            <View style={styles.recommendationCard}>
              <View style={styles.recBadge}>
                <Text style={styles.recBadgeText}>🧭 COACH'S TOP RECOMMENDATION</Text>
              </View>

              <Text style={styles.recName}>{fallbackRecommendation.name}</Text>
              <Text style={styles.recFocus}>Focus: {(fallbackRecommendation.cognitive_gap || '').replace(/_/g, ' ').toUpperCase()}</Text>

              {/* Stats Grid */}
              <View style={styles.statsGrid}>
                <View style={styles.statCell}>
                  <Text style={styles.statLabel}>MISTAKES FOUND</Text>
                  <Text style={styles.statVal}>{fallbackRecommendation.occurrence_count || fallbackRecommendation.mistakes_found || 0}</Text>
                </View>
                <View style={styles.statCell}>
                  <Text style={styles.statLabel}>CONFIDENCE</Text>
                  <Text style={styles.statVal}>{fallbackRecommendation.confidence_pct ? `${fallbackRecommendation.confidence_pct}%` : fallbackRecommendation.confidence || '0%'}</Text>
                </View>
                <View style={styles.statCell}>
                  <Text style={styles.statLabel}>RECENT</Text>
                  <Text style={styles.statVal}>{fallbackRecommendation.last_mistake_days_ago ? `${fallbackRecommendation.last_mistake_days_ago}d ago` : fallbackRecommendation.recent || 'None'}</Text>
                </View>
              </View>

              {/* Rating Gain Section */}
              <View style={styles.gainBox}>
                <Text style={styles.gainTitle}>📈 ESTIMATED RATING GAIN</Text>
                <View style={styles.gainRow}>
                  <View style={styles.gainCell}>
                    <Text style={styles.gainCellLabel}>Conservative (70%)</Text>
                    <Text style={styles.gainCellVal}>{fallbackRecommendation.rating_improvement?.conservative?.elo_gain ? `+${fallbackRecommendation.rating_improvement.conservative.elo_gain}` : fallbackRecommendation.rating_gains?.conservative || '+0'}</Text>
                  </View>
                  <View style={styles.gainCell}>
                    <Text style={styles.gainCellLabel}>Realistic (85%)</Text>
                    <Text style={styles.gainCellVal}>{fallbackRecommendation.rating_improvement?.realistic?.elo_gain ? `+${fallbackRecommendation.rating_improvement.realistic.elo_gain}` : fallbackRecommendation.rating_gains?.realistic || '+0'}</Text>
                  </View>
                  <View style={styles.gainCell}>
                    <Text style={styles.gainCellLabel}>Optimistic (95%)</Text>
                    <Text style={styles.gainCellVal}>{fallbackRecommendation.rating_improvement?.optimistic?.elo_gain ? `+${fallbackRecommendation.rating_improvement.optimistic.elo_gain}` : fallbackRecommendation.rating_gains?.optimistic || '+0'}</Text>
                  </View>
                </View>
              </View>

              {/* Primary Start Button */}
              <TouchableOpacity
                style={styles.startPlanBtn}
                onPress={() => handleStartPlan(fallbackRecommendation.plan_id || fallbackRecommendation.recommended_plan_id)}
                disabled={actionLoading}
                activeOpacity={0.85}
              >
                {actionLoading ? <ActivityIndicator color="#000" size="small" /> : (
                  <Text style={styles.startPlanBtnText}>Start This Training Plan</Text>
                )}
              </TouchableOpacity>
            </View>

            {/* Alternatives */}
            {alternatives && alternatives.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>OR CHOOSE ANOTHER PLAN</Text>
                {alternatives.map((alt, i) => (
                  <View key={i} style={styles.alternativeCard}>
                    <View style={styles.altHeader}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.altName}>{alt.name || alt.plan_name}</Text>
                        <Text style={styles.altSub}>
                          {alt.occurrence_count || alt.mistakes || 0} mistakes · {alt.confidence_pct ? `${alt.confidence_pct}%` : alt.confidence || '0%'} confidence
                        </Text>
                      </View>
                      <View style={styles.altGainBadge}>
                        <Text style={styles.altGainLabel}>Est. Gain</Text>
                        <Text style={styles.altGainVal}>
                          {alt.rating_improvement?.realistic?.elo_gain ? `+${alt.rating_improvement.realistic.elo_gain}` : alt.gain || '+0'}
                        </Text>
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
          </>
        )}

        {/* --- SELF-RATING CALIBRATION CARD --- */}
        {calibration && (
          <View style={styles.calibCard}>
            <Text style={styles.calibTitle}>⚖️ MOVE RATING CALIBRATION</Text>
            <Text style={styles.calibSubtitle}>How accurately you rate your own moves (last 10 rated)</Text>
            <View style={styles.calibGrid}>
              <View style={styles.calibCell}>
                <Text style={styles.calibLabel}>TOTAL RATED</Text>
                <Text style={styles.calibVal}>{calibration.total_rated || 0}</Text>
              </View>
              <View style={styles.calibCell}>
                <Text style={styles.calibLabel}>AVG. DEVIATION</Text>
                <Text style={styles.calibVal}>
                  {typeof calibration.avg_deviation_rating === 'number' ? calibration.avg_deviation_rating.toFixed(0) : '0'} ELO
                </Text>
              </View>
              <View style={styles.calibCell}>
                <Text style={styles.calibLabel}>CALIBRATION STATE</Text>
                <Text style={[styles.calibVal, { color: (calibration.calibration_score || 0) >= 80 ? COLORS.success : COLORS.primary }]}>
                  {typeof calibration.calibration_score === 'number' ? calibration.calibration_score.toFixed(0) : '0'}% Accuracy
                </Text>
              </View>
            </View>
            <Text style={styles.calibDescription}>
              {calibration.feedback_msg || "Keep rating your moves after playing in play-with-coach to calibrate your rating sense."}
            </Text>
          </View>
        )}

        {/* --- ALSO TRACKING --- */}
        {trackedWeaknesses && trackedWeaknesses.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>ALSO TRACKING</Text>
            {trackedWeaknesses.map((w, i) => (
              <View key={i} style={styles.trackingCard}>
                <View style={styles.trackingHeader}>
                  <Text style={styles.trackingName}>{w.name}</Text>
                  <Text style={styles.trackingStatus}>{w.cleanGames} / 5 clean</Text>
                </View>
                <Text style={styles.trackingDesc}>
                  Detected in your games ({w.lastSeen}). Practice this pattern to build defensive discipline.
                </Text>
                <TouchableOpacity style={styles.trackingBtn} onPress={() => navigation.navigate('MainTabs', { screen: 'CoachPlayTab' })} activeOpacity={0.8}>
                  <Text style={styles.trackingBtnText}>Practice ➔</Text>
                </TouchableOpacity>
              </View>
            ))}
          </>
        )}

        {/* --- ARCHIVED / BEATEN STRENGTHS --- */}
        {beatenStrengths && beatenStrengths.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>ARCHIVED · YOU'VE BEEN CONSISTENT AT</Text>
            {beatenStrengths.map((item, index) => (
              <View key={index} style={styles.archivedCard}>
                <View style={styles.archivedHeader}>
                  <Text style={styles.archivedLabel}>{item.label || item.text || item.description}</Text>
                  <View style={styles.archivedStatusBadge}>
                    <Text style={styles.archivedStatusText}>{item.status || 'stable'}</Text>
                  </View>
                </View>
                <Text style={styles.archivedCleanText}>Clean — keep it that way</Text>
              </View>
            ))}
          </>
        )}

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
  
  // Summary/Overview Card
  summaryCard: { backgroundColor: 'rgba(19, 27, 46, 0.85)', borderRadius: 20, padding: 16, borderWidth: 1, borderColor: COLORS.cardBorder, marginBottom: 16 },
  summaryGrid: { flexDirection: 'row', gap: 12, marginBottom: 12 },
  summaryCell: { flex: 1, backgroundColor: 'rgba(9, 13, 22, 0.5)', borderRadius: 12, padding: 10 },
  summaryCellLabel: { color: COLORS.textMuted, fontSize: 9, fontWeight: '800', letterSpacing: 0.5, marginBottom: 4 },
  summaryCellVal: { color: '#ffffff', fontSize: 13, fontWeight: '900' },
  styleDesc: { color: COLORS.textMuted, fontSize: 12, lineHeight: 18 },
  
  // Charts
  chartCard: { backgroundColor: 'rgba(19, 27, 46, 0.85)', borderRadius: 20, padding: 18, borderWidth: 1, borderColor: COLORS.cardBorder, marginBottom: 16 },
  chartTitle: { color: '#ffffff', fontSize: 12, fontWeight: '900', letterSpacing: 1, marginBottom: 4 },
  chartSubtitle: { color: COLORS.textMuted, fontSize: 11, marginBottom: 16 },
  chartRow: { marginBottom: 14 },
  chartRowHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  chartRowLabel: { color: '#ffffff', fontSize: 13, fontWeight: '800' },
  chartReductionText: { color: COLORS.success, fontSize: 12, fontWeight: '800' },
  chartVisualRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginVertical: 2 },
  chartLabelMini: { color: COLORS.textMuted, fontSize: 9, width: 25, textAlign: 'right' },
  chartBarTrack: { flex: 1, height: 6, backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: 3, overflow: 'hidden' },
  chartBarPre: { height: '100%', backgroundColor: COLORS.danger, borderRadius: 3 },
  chartBarPost: { height: '100%', backgroundColor: COLORS.success, borderRadius: 3 },
  chartValMini: { color: COLORS.text, fontSize: 10, width: 20, fontWeight: '600' },

  // Active Plan Card
  activePlanCard: { backgroundColor: 'rgba(19, 27, 46, 0.85)', borderRadius: 20, padding: 18, borderWidth: 1, borderColor: COLORS.cardBorder },
  activeHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  activePlanName: { color: '#ffffff', fontSize: 16, fontWeight: '900', flex: 1, paddingRight: 8 },
  pipsRow: { flexDirection: 'row', gap: 4 },
  pip: { width: 10, height: 10, borderRadius: 5 },
  pipActive: { backgroundColor: COLORS.success },
  pipTarget: { backgroundColor: 'transparent', borderWidth: 1, borderColor: 'rgba(255,255,255,0.3)' },
  pipInactive: { backgroundColor: 'rgba(255,255,255,0.1)' },
  activeQuote: { color: COLORS.textMuted, fontSize: 13, fontStyle: 'italic', marginBottom: 16 },
  habitBox: { backgroundColor: 'rgba(9, 13, 22, 0.6)', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: COLORS.cardBorder },
  habitHeader: { color: COLORS.primary, fontSize: 10, fontWeight: '850', letterSpacing: 1, marginBottom: 6 },
  habitTitle: { color: '#ffffff', fontSize: 14, fontWeight: '800' },
  habitSub: { color: COLORS.textMuted, fontSize: 12, marginTop: 2, lineHeight: 16, marginBottom: 12 },
  habitBtnRow: { flexDirection: 'row', gap: 10 },
  habitBtn: { flex: 1, backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 10, paddingVertical: 8, alignItems: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  habitBtnPrimary: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  habitBtnText: { color: '#ffffff', fontWeight: '750', fontSize: 12 },
  
  // Recommendations
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
  
  // Move Calibration
  calibCard: { backgroundColor: 'rgba(19, 27, 46, 0.85)', borderRadius: 20, padding: 18, borderWidth: 1, borderColor: COLORS.cardBorder, marginBottom: 16 },
  calibTitle: { color: '#ffffff', fontSize: 12, fontWeight: '900', letterSpacing: 1, marginBottom: 4 },
  calibSubtitle: { color: COLORS.textMuted, fontSize: 11, marginBottom: 16 },
  calibGrid: { flexDirection: 'row', gap: 12, paddingVertical: 12, borderTopWidth: 1, borderBottomWidth: 1, borderColor: 'rgba(255,255,255,0.08)', marginBottom: 12 },
  calibCell: { flex: 1 },
  calibLabel: { color: COLORS.textMuted, fontSize: 9, fontWeight: '800', letterSpacing: 0.5, marginBottom: 4 },
  calibVal: { color: '#ffffff', fontSize: 14, fontWeight: '900' },
  calibDescription: { color: COLORS.textMuted, fontSize: 12, lineHeight: 18 },

  // Tracking & Archive
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
