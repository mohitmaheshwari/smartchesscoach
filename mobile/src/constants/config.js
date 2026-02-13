// API Configuration
export const API_URL = 'https://chess-audit.preview.emergentagent.com/api';

// Google OAuth
export const GOOGLE_CLIENT_ID = ''; // Will be configured for mobile

// Colors - Dark theme (matching web app)
export const Colors = {
  dark: {
    background: '#0a0a0a',
    card: '#121212',
    text: '#ffffff',
    textSecondary: '#a1a1aa',
    border: '#27272a',
    primary: '#ffffff',
    accent: '#f59e0b',
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    muted: '#1e1e1e',
  },
  light: {
    background: '#f5f5f4',
    card: '#ffffff',
    text: '#0a0a0a',
    textSecondary: '#71717a',
    border: '#e4e4e7',
    primary: '#0a0a0a',
    accent: '#f59e0b',
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    muted: '#f4f4f5',
  }
};

// Status colors for chess
export const StatusColors = {
  improving: '#10b981',
  stable: '#71717a',
  attention: '#f59e0b',
  warning: '#f59e0b',
  blunder: '#ef4444',
  mistake: '#f97316',
  inaccuracy: '#eab308',
  good: '#3b82f6',
  excellent: '#10b981',
};

// Trend icons
export const TrendIcons = {
  improving: '↑',
  stable: '→',
  worsening: '↓',
};
