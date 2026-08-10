import { Platform } from 'react-native';

// Machine local Wi-Fi IP for physical phone testing via Expo Go
const LOCAL_HOST_IP = '10.140.51.139';

const getDefaultApiUrl = () => {
  // Use local Wi-Fi IP in dev so physical phones via Expo Go & emulators can connect
  if (__DEV__) {
    return `http://${LOCAL_HOST_IP}:8000/api`;
  }
  return 'https://chessguru.ai/api';
};

export const CONFIG = {
  API_BASE_URL: getDefaultApiUrl(),
  EMULATOR_API_URL: 'http://10.0.2.2:8000/api',
  LOCAL_WIFI_API_URL: `http://${LOCAL_HOST_IP}:8000/api`,
  PROD_API_URL: 'https://chessguru.ai/api',
  DEFAULT_USER_ID: 'user_guru_001',
  APP_TITLE: 'Chesss-Guru',
};

export const COLORS = {
  background: '#090d16',
  cardBg: '#131b2e',
  cardBorder: '#1e293b',
  primary: '#eab308', // Gold accent
  primaryHover: '#ca8a04',
  secondary: '#38bdf8', // Cyan accent
  success: '#22c55e',
  danger: '#ef4444',
  warning: '#f97316',
  text: '#f8fafc',
  textMuted: '#94a3b8',
  boardLight: '#f0d9b5',
  boardDark: '#b58863',
};
