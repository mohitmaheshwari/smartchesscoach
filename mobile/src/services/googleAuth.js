import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import * as Crypto from 'expo-crypto';
import { makeRedirectUri } from 'expo-auth-session';
import { API_URL } from '../constants/config';
import * as SecureStore from 'expo-secure-store';

// Enable web browser redirect handling
WebBrowser.maybeCompleteAuthSession();

/**
 * Google OAuth configuration
 * Note: For production, you need to create OAuth credentials in Google Cloud Console
 * For Expo Go development, only the webClientId is needed
 */
const GOOGLE_CONFIG = {
  // Expo Go / Web client ID - works for development
  // For production standalone apps, you'd also set iosClientId and androidClientId
  expoClientId: '407408718192.apps.googleusercontent.com', // Expo's client ID for dev
};

/**
 * Custom hook for Google authentication
 * Uses expo-auth-session with PKCE flow for security
 */
export function useGoogleAuth() {
  const redirectUri = makeRedirectUri({
    scheme: 'chesscoach',
    path: 'auth/callback',
  });

  const [request, response, promptAsync] = Google.useAuthRequest({
    expoClientId: GOOGLE_CONFIG.expoClientId,
    scopes: ['profile', 'email'],
    redirectUri,
  });

  return { request, response, promptAsync };
}

/**
 * Exchange Google access token with our backend for a session
 */
export async function authenticateWithBackend(accessToken) {
  try {
    const response = await fetch(`${API_URL}/auth/google/mobile`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        access_token: accessToken,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Authentication failed');
    }

    const data = await response.json();
    
    // Store session token securely
    if (data.session_token) {
      await SecureStore.setItemAsync('session_token', data.session_token);
    }

    return data.user;
  } catch (error) {
    console.error('Backend authentication failed:', error);
    throw error;
  }
}

/**
 * Get user info directly from Google (for verification)
 */
export async function getGoogleUserInfo(accessToken) {
  try {
    const response = await fetch('https://www.googleapis.com/oauth2/v2/userinfo', {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    
    if (!response.ok) {
      throw new Error('Failed to get user info');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to get Google user info:', error);
    throw error;
  }
}

/**
 * Clear stored authentication data
 */
export async function clearAuthData() {
  try {
    await SecureStore.deleteItemAsync('session_token');
  } catch (error) {
    console.error('Failed to clear auth data:', error);
  }
}
