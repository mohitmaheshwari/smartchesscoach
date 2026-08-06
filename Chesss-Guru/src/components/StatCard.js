import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { COLORS } from '../constants/config';

export const StatCard = ({ title, value, subtitle, icon, accentColor = COLORS.primary }) => {
  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>{title}</Text>
        {icon && <Text style={styles.icon}>{icon}</Text>}
      </View>
      <Text style={[styles.value, { color: accentColor }]}>{value}</Text>
      {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    borderRadius: 22,
    padding: 16,
    borderWidth: 1.5,
    borderColor: 'rgba(255, 255, 255, 0.38)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.6,
    shadowRadius: 12,
    elevation: 8,
    minWidth: 140,
    flex: 1,
    margin: 4,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  title: {
    color: '#e2e8f0',
    fontSize: 11,
    fontWeight: '800',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  icon: {
    fontSize: 22,
  },
  value: {
    fontSize: 28,
    fontWeight: '900',
    marginBottom: 4,
    textShadowColor: 'rgba(0, 0, 0, 0.95)',
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 6,
  },
  subtitle: {
    color: '#cbd5e1',
    fontSize: 12,
    fontWeight: '700',
  },
});
