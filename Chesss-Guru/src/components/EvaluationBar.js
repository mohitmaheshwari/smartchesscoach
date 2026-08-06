import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { COLORS } from '../constants/config';

export const EvaluationBar = ({ evalScore = 0 }) => {
  // Cap evaluation score between -10 and +10 for visual bar
  const cappedEval = Math.max(-10, Math.min(10, evalScore));
  
  // Calculate percentage of white bar (0% to 100%)
  // eval 0 = 50%, eval +10 = 100%, eval -10 = 0%
  const whitePercent = Math.round(((cappedEval + 10) / 20) * 100);
  const blackPercent = 100 - whitePercent;

  const formattedEval = evalScore > 0 ? `+${evalScore.toFixed(1)}` : `${evalScore.toFixed(1)}`;

  return (
    <View style={styles.container}>
      <View style={styles.barContainer}>
        {/* Black side (top) */}
        <View style={[styles.blackBar, { flex: blackPercent }]} />
        {/* White side (bottom) */}
        <View style={[styles.whiteBar, { flex: whitePercent }]} />
      </View>
      <Text style={styles.evalText}>{formattedEval}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    marginRight: 8,
  },
  barContainer: {
    width: 14,
    height: 320,
    borderRadius: 7,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#334155',
    backgroundColor: '#000',
  },
  blackBar: {
    backgroundColor: '#1e293b',
    width: '100%',
  },
  whiteBar: {
    backgroundColor: '#f8fafc',
    width: '100%',
  },
  evalText: {
    color: COLORS.primary,
    fontWeight: '700',
    fontSize: 11,
    marginTop: 6,
  },
});
