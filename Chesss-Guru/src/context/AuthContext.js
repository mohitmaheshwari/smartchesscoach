import React, { createContext, useState, useEffect, useContext } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { loginUser, registerUser, getDemoUserToken, loginWithGoogleToken, logoutUser } from '../services/api';
import { useGoogleAuth } from './GoogleAuthContext';

export const AuthContext = createContext({
  user: null,
  sessionToken: null,
  loading: true,
  login: async () => {},
  register: async () => {},
  guestLogin: async () => {},
  googleLogin: async () => {},
  logout: async () => {},
});

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [sessionToken, setSessionToken] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if session token exists in storage on app launch
    const loadSession = async () => {
      const startTime = Date.now();
      try {
        const token = await AsyncStorage.getItem('session_token');
        const storedUser = await AsyncStorage.getItem('user_data');
        if (token && storedUser) {
          setSessionToken(token);
          setUser(JSON.parse(storedUser));
        }
      } catch (e) {
        console.warn('AuthContext load session error:', e);
      } finally {
        const elapsedTime = Date.now() - startTime;
        const minimumSplashTime = 2200; // 2.2 seconds minimum display time
        const remainingDelay = Math.max(0, minimumSplashTime - elapsedTime);
        setTimeout(() => {
          setLoading(false);
        }, remainingDelay);
      }
    };
    loadSession();
  }, []);

  const login = async (email, password) => {
    const res = await loginUser(email, password);
    const token = res?.session_token || res?.token;
    if (token) {
      setSessionToken(token);
      setUser(res.user || { name: email.split('@')[0], email });
    }
    return res;
  };

  const register = async (email, password, name, chessComUsername, lichessUsername) => {
    const res = await registerUser(email, password, name, chessComUsername, lichessUsername);
    const token = res?.session_token || res?.token;
    if (token) {
      setSessionToken(token);
      setUser(res.user || { name, email });
    }
    return res;
  };

  const guestLogin = async () => {
    const res = await getDemoUserToken();
    const token = res?.session_token || res?.token;
    if (token) {
      setSessionToken(token);
      setUser(res.user || { name: 'Guru Guest', email: 'guest@chessguru.ai' });
    }
    return res;
  };

  const { signIn: googleSignIn } = useGoogleAuth();

  const googleLogin = async () => {
    // Step 1: Firebase Google Sign-In — returns { firebaseUser, accessToken }
    const result = await googleSignIn();
    if (!result) throw new Error('Google Authentication was cancelled or failed.');

    const firebaseUser = result.firebaseUser || result;
    const googleAccessToken = result.accessToken;

    // Step 2: Try to send Google accessToken to backend for a session token
    try {
      const res = await loginWithGoogleToken(googleAccessToken);
      const token = res?.session_token || res?.token;
      if (token) {
        setSessionToken(token);
        const userData = res.user || {
          name: firebaseUser.displayName || 'Google User',
          email: firebaseUser.email || '',
          photo: firebaseUser.photoURL || null,
        };
        setUser(userData);
        await AsyncStorage.setItem('user_data', JSON.stringify(userData));
      }
      return res;
    } catch (backendErr) {
      // Fallback: backend unreachable — use Firebase user data directly
      console.warn('[AuthContext] Backend unavailable, using Firebase user:', backendErr.message);
      const userData = {
        name: firebaseUser.displayName || 'Google User',
        email: firebaseUser.email || '',
        photo: firebaseUser.photoURL || null,
        uid: firebaseUser.uid,
      };
      setUser(userData);
      await AsyncStorage.setItem('user_data', JSON.stringify(userData));
      return { user: userData };
    }
  };

  const logout = async () => {
    await logoutUser();
    setSessionToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        sessionToken,
        loading,
        login,
        register,
        guestLogin,
        googleLogin,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
