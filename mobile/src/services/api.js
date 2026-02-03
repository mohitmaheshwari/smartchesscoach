import { API_URL } from '../constants/config';
import * as SecureStore from 'expo-secure-store';

// Store session token securely
export const setSessionToken = async (token) => {
  await SecureStore.setItemAsync('session_token', token);
};

export const getSessionToken = async () => {
  return await SecureStore.getItemAsync('session_token');
};

export const clearSessionToken = async () => {
  await SecureStore.deleteItemAsync('session_token');
};

// API helper with auth
const fetchWithAuth = async (endpoint, options = {}) => {
  const token = await getSessionToken();
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  
  // For mobile, we use Authorization header instead of cookie
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });
  
  return response;
};

// Auth APIs
export const authAPI = {
  // Get current user
  getCurrentUser: async () => {
    const response = await fetchWithAuth('/auth/me');
    if (!response.ok) return null;
    return response.json();
  },
  
  // Logout
  logout: async () => {
    const response = await fetchWithAuth('/auth/logout', { method: 'POST' });
    await clearSessionToken();
    return response.ok;
  },
  
  // Google OAuth - get auth URL
  getGoogleAuthUrl: async () => {
    const response = await fetch(`${API_URL}/auth/google`);
    if (!response.ok) throw new Error('Failed to get auth URL');
    return response.json();
  },
};

// Dashboard APIs
export const dashboardAPI = {
  getStats: async () => {
    const response = await fetchWithAuth('/dashboard-stats');
    if (!response.ok) throw new Error('Failed to fetch stats');
    return response.json();
  },
};

// Journey APIs
export const journeyAPI = {
  getDashboard: async () => {
    const response = await fetchWithAuth('/journey');
    if (!response.ok) throw new Error('Failed to fetch journey');
    return response.json();
  },
  
  getLinkedAccounts: async () => {
    const response = await fetchWithAuth('/journey/linked-accounts');
    if (!response.ok) throw new Error('Failed to fetch accounts');
    return response.json();
  },
  
  linkAccount: async (platform, username) => {
    const response = await fetchWithAuth('/journey/link-account', {
      method: 'POST',
      body: JSON.stringify({ platform, username }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to link account');
    }
    return response.json();
  },
  
  syncNow: async () => {
    const response = await fetchWithAuth('/journey/sync-now', { method: 'POST' });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to sync');
    }
    return response.json();
  },
};

// Games APIs
export const gamesAPI = {
  getGames: async () => {
    const response = await fetchWithAuth('/games');
    if (!response.ok) throw new Error('Failed to fetch games');
    return response.json();
  },
  
  getGame: async (gameId) => {
    const response = await fetchWithAuth(`/games/${gameId}`);
    if (!response.ok) throw new Error('Game not found');
    return response.json();
  },
  
  importGames: async (platform, username, count = 10) => {
    const response = await fetchWithAuth('/import-games', {
      method: 'POST',
      body: JSON.stringify({ platform, username, count }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to import games');
    }
    return response.json();
  },
};

// Analysis APIs
export const analysisAPI = {
  getAnalysis: async (gameId) => {
    const response = await fetchWithAuth(`/analysis/${gameId}`);
    if (!response.ok) return null;
    return response.json();
  },
  
  analyzeGame: async (gameId, force = false) => {
    const response = await fetchWithAuth('/analyze-game', {
      method: 'POST',
      body: JSON.stringify({ game_id: gameId, force }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Analysis failed');
    }
    return response.json();
  },
};

// Profile APIs
export const profileAPI = {
  getProfile: async () => {
    const response = await fetchWithAuth('/profile');
    if (!response.ok) return null;
    return response.json();
  },
};

// Settings APIs
export const settingsAPI = {
  getEmailSettings: async () => {
    const response = await fetchWithAuth('/settings/email-notifications');
    if (!response.ok) throw new Error('Failed to fetch settings');
    return response.json();
  },
  
  updateEmailSettings: async (settings) => {
    const response = await fetchWithAuth('/settings/email-notifications', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
    if (!response.ok) throw new Error('Failed to update settings');
    return response.json();
  },
};
