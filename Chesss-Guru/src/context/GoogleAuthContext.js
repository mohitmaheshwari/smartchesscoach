import {
  GoogleSignin,
  isErrorWithCode,
  isSuccessResponse,
  statusCodes,
} from '@react-native-google-signin/google-signin';
import * as WebBrowser from 'expo-web-browser';
import { createContext, useContext, useState } from 'react';
import { Alert } from 'react-native';
import { signInWithCredential, GoogleAuthProvider } from 'firebase/auth';
import { auth } from '../config/firebase';

// Configure Google Sign-In only once
let isConfigured = false;
if (!isConfigured) {
  GoogleSignin.configure({
    webClientId:
      '889695197064-jdtos42bki52t70l5h21164mbnd3dv21.apps.googleusercontent.com',
    scopes: [
      'https://www.googleapis.com/auth/userinfo.profile',
      'https://www.googleapis.com/auth/userinfo.email',
    ],
    offlineAccess: true,
    iosClientId:
      '661715330732-krp7j6t365f81un5thpfml8iauen10bo.apps.googleusercontent.com',
    profileImageSize: 120,
  });
  isConfigured = true;
}

WebBrowser.maybeCompleteAuthSession();

const GoogleAuthContext = createContext(null);

export const GoogleAuthContextProvider = ({ children }) => {
  const [googleUserInfo, setGoogleUserInfo] = useState(null);
  const [idToken, setIdToken] = useState(null);
  const [accessToken, setAccessToken] = useState(null);

  const signIn = async () => {
    try {
      await GoogleSignin.hasPlayServices();

      // Always sign out first to force the account picker to show
      await GoogleSignin.signOut();

      const response = await GoogleSignin.signIn();

      if (!isSuccessResponse(response)) return null;

      const tokens = await GoogleSignin.getTokens();
      const idToken = tokens.idToken || null;
      const accessToken = tokens.accessToken || null;

      if (!idToken && !accessToken) {
        console.log('[GoogleAuth] No tokens available from GoogleSignin');
        return null;
      }

      // Sign in with Firebase using the Google credential
      // idToken can be null when offlineAccess=true; accessToken works as fallback
      const googleCredential = GoogleAuthProvider.credential(idToken, accessToken);
      const userCredential = await signInWithCredential(auth, googleCredential);
      const firebaseUser = userCredential.user;

      setGoogleUserInfo(firebaseUser);
      setIdToken(idToken);
      setAccessToken(accessToken);

      console.log('🔥 Firebase User:', firebaseUser);

      // Return both so AuthContext can send accessToken to backend
      return { firebaseUser, accessToken };
    } catch (error) {
      console.log('Firebase Google Sign-In Error:', error);

      if (isErrorWithCode(error)) {
        switch (error.code) {
          case statusCodes.IN_PROGRESS:
            Alert.alert('Sign in already in progress');
            break;
          case statusCodes.PLAY_SERVICES_NOT_AVAILABLE:
            Alert.alert('Play services not available');
            break;
          default:
            Alert.alert('Google sign in failed');
        }
      } else {
        Alert.alert('Unknown Google sign in error');
      }

      return null;
    }
  };

  const signOut = async () => {
    try {
      await GoogleSignin.signOut();
      setGoogleUserInfo(null);
      setIdToken(null);
      setAccessToken(null);
    } catch (error) {
      console.log('Google sign out error:', error);
    }
  };

  return (
    <GoogleAuthContext.Provider
      value={{ googleUserInfo, idToken, accessToken, signIn, signOut }}
    >
      {children}
    </GoogleAuthContext.Provider>
  );
};

export const useGoogleAuth = () => {
  const context = useContext(GoogleAuthContext);
  if (!context) {
    throw new Error(
      'useGoogleAuth must be used within GoogleAuthContextProvider',
    );
  }
  return context;
};
