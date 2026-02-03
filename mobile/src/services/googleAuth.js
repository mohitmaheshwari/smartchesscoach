import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import { makeRedirectUri } from 'expo-auth-session';
import { API_URL } from '../constants/config';
import * as SecureStore from 'expo-secure-store';

// Enable web browser redirect
WebBrowser.maybeCompleteAuthSession();

// Google OAuth configuration
// NOTE: You need to create OAuth credentials in Google Cloud Console
// and add these client IDs:
const GOOGLE_CONFIG = {
  // Web client ID (used for Expo Go and web)
  webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID || '',
  // iOS client ID (for standalone iOS app)
  iosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID || '',
  // Android client ID (for standalone Android app)
  androidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID || '',
};

/**
 * Hook for Google authentication
 * Returns request, response, and promptAsync function
 */
export function useGoogleAuth() {
  const redirectUri = makeRedirectUri({
    scheme: 'chesscoach',
    path: 'auth',
  });

  const [request, response, promptAsync] = Google.useAuthRequest({
    webClientId: GOOGLE_CONFIG.webClientId,
    iosClientId: GOOGLE_CONFIG.iosClientId,
    androidClientId: GOOGLE_CONFIG.androidClientId,
    scopes: ['profile', 'email'],
    redirectUri,
  });

  return { request, response, promptAsync };
}

/**
 * Exchange Google auth code/token with our backend
 */
export async function authenticateWithBackend(googleToken) {
  try {
    const response = await fetch(`${API_URL}/auth/google/mobile`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        id_token: googleToken,
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
 * Get user info from Google token
 */
export async function getGoogleUserInfo(accessToken) {
  try {
    const response = await fetch('https://www.googleapis.com/userinfo/v2/me', {
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
