import React, { useState, useContext, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, ScrollView, ActivityIndicator, ImageBackground, Animated } from 'react-native';
import { COLORS } from '../constants/config';
import { AuthContext } from '../context/AuthContext';

export default function AuthScreen({ navigation }) {
  const { login, register, guestLogin, googleLogin } = useContext(AuthContext);

  const [isLoginMode, setIsLoginMode] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [chessComUsername, setChessComUsername] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);

  // Animation values
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(20)).current;

  useEffect(() => {
    fadeAnim.setValue(0);
    slideAnim.setValue(20);
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 500,
        useNativeDriver: true,
      }),
      Animated.spring(slideAnim, {
        toValue: 0,
        friction: 7,
        tension: 50,
        useNativeDriver: true,
      }),
    ]).start();
  }, [isLoginMode]);

  const handleAuthSubmit = async () => {
    setErrorMsg('');
    if (!email.trim() || !password.trim()) {
      setErrorMsg('Please enter both email and password.');
      return;
    }

    if (!isLoginMode && password.length < 8) {
      setErrorMsg('Password must be at least 8 characters long.');
      return;
    }

    setLoading(true);
    try {
      if (isLoginMode) {
        await login(email.trim(), password);
      } else {
        await register(email.trim(), password, name.trim() || email.split('@')[0], chessComUsername.trim(), null);
      }
    } catch (err) {
      if (err.message?.includes('409') || err.message?.includes('already registered')) {
        setErrorMsg('Email is already registered! Switched to Log In below.');
        setIsLoginMode(true);
      } else {
        setErrorMsg(err.message || 'Authentication failed. Please check your details or try 1-Tap Guest Play.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSubmit = async () => {
    setErrorMsg('');
    setLoading(true);
    try {
      await googleLogin();
    } catch (err) {
      setErrorMsg('Google login failed. Try email or guest login.');
    } finally {
      setLoading(false);
    }
  };

  const handleGuestSubmit = async () => {
    setErrorMsg('');
    setLoading(true);
    try {
      await guestLogin();
    } catch (err) {
      setErrorMsg('Guest login failed. Check backend URL in settings.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ImageBackground
      source={require('../../assets/aesthetic_chess_bg.png')}
      style={styles.bgImage}
      resizeMode="cover"
    >
      {/* Dark ambient vignette overlay */}
      <View style={styles.darkOverlay} />

      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        {/* Animated Brand Header */}
        <Animated.View style={[styles.header, { opacity: fadeAnim, transform: [{ translateY: slideAnim }] }]}>
          <View style={styles.badgePill}>
            <Text style={styles.badgePillText}>✨ NEXT-GEN AI CHESS COACH</Text>
          </View>
          <Text style={styles.title}>Chesss-Guru</Text>
          <Text style={styles.subtitle}>AI-Powered Master Analytics & Real-Time Engine</Text>
        </Animated.View>

        {/* Animated Glassmorphic Auth Card */}
        <Animated.View style={[styles.card, { opacity: fadeAnim, transform: [{ translateY: slideAnim }] }]}>
          <Text style={styles.cardHeading}>
            {isLoginMode ? 'Login to Account' : 'Create New Account'}
          </Text>

          {/* Error Alert */}
          {errorMsg !== '' && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>⚠️ {errorMsg}</Text>
            </View>
          )}

          {/* Signup-only fields */}
          {!isLoginMode && (
            <>
              <Text style={styles.inputLabel}>👤 Full Name</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. Magnus Carlsen"
                placeholderTextColor="rgba(255, 255, 255, 0.45)"
                value={name}
                onChangeText={setName}
              />

              <Text style={styles.inputLabel}>♟️ Chess.com Handle (Optional)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. Hikaru"
                placeholderTextColor="rgba(255, 255, 255, 0.45)"
                value={chessComUsername}
                onChangeText={setChessComUsername}
                autoCapitalize="none"
              />
            </>
          )}

          {/* Common Email / Password fields */}
          <Text style={styles.inputLabel}>✉️ Email Address</Text>
          <TextInput
            style={styles.input}
            placeholder="your.email@example.com"
            placeholderTextColor="rgba(255, 255, 255, 0.45)"
            keyboardType="email-address"
            autoCapitalize="none"
            value={email}
            onChangeText={setEmail}
          />

          <Text style={styles.inputLabel}>🔒 Password</Text>
          <TextInput
            style={styles.input}
            placeholder="••••••••"
            placeholderTextColor="rgba(255, 255, 255, 0.45)"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />

          {/* Primary Action Button */}
          <TouchableOpacity
            style={styles.primaryGoldButton}
            onPress={handleAuthSubmit}
            disabled={loading}
            activeOpacity={0.85}
          >
            {loading ? (
              <ActivityIndicator color="#000" />
            ) : (
              <Text style={styles.primaryButtonText}>
                {isLoginMode ? 'Login to Chesss-Guru ➔' : 'Create Account ➔'}
              </Text>
            )}
          </TouchableOpacity>

          {/* Google & Guest Play Options (shown in Login mode) */}
          {isLoginMode && (
            <>
              <View style={styles.dividerRow}>
                <View style={styles.dividerLine} />
                <Text style={styles.dividerText}>OR SIGN IN WITH</Text>
                <View style={styles.dividerLine} />
              </View>

              <TouchableOpacity
                style={styles.googleButton}
                onPress={handleGoogleSubmit}
                disabled={loading}
                activeOpacity={0.85}
              >
                <Text style={styles.googleButtonText}>🌐 Continue with Google</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.guestCyanButton}
                onPress={handleGuestSubmit}
                disabled={loading}
                activeOpacity={0.85}
              >
                <Text style={styles.guestButtonText}>⚡ Instant 1-Tap Guest Play</Text>
              </TouchableOpacity>
            </>
          )}

          {/* Mode Switcher Footer */}
          <TouchableOpacity
            style={styles.toggleFooter}
            onPress={() => {
              setIsLoginMode(!isLoginMode);
              setErrorMsg('');
            }}
            activeOpacity={0.8}
          >
            <Text style={styles.toggleFooterText}>
              {isLoginMode ? (
                <>Don't have an account? <Text style={styles.toggleFooterHighlight}>Sign Up</Text></>
              ) : (
                <>Already have an account? <Text style={styles.toggleFooterHighlight}>Log In</Text></>
              )}
            </Text>
          </TouchableOpacity>
        </Animated.View>
      </ScrollView>
    </ImageBackground>
  );
}

const styles = StyleSheet.create({
  bgImage: {
    flex: 1,
    width: '100%',
    height: '100%',
  },
  darkOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(5, 8, 16, 0.35)',
  },
  container: {
    backgroundColor: 'transparent',
  },
  content: {
    paddingHorizontal: 16,
    paddingTop: 45,
    paddingBottom: 40,
    gap: 20,
  },
  header: {
    alignItems: 'center',
    marginBottom: 10,
    width: '100%',
  },
  badgePill: {
    backgroundColor: 'rgba(234, 179, 8, 0.15)',
    paddingHorizontal: 14,
    paddingVertical: 5,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(234, 179, 8, 0.5)',
    marginBottom: 8,
  },
  badgePillText: {
    color: '#fef08a',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1,
  },
  title: {
    color: '#ffffff',
    fontSize: 32,
    fontWeight: '900',
    letterSpacing: 1.2,
    textAlign: 'center',
    textShadowColor: 'rgba(234, 179, 8, 0.75)',
    textShadowOffset: { width: 0, height: 3 },
    textShadowRadius: 14,
  },
  subtitle: {
    color: '#cbd5e1',
    fontSize: 12,
    marginTop: 4,
    textAlign: 'center',
    fontWeight: '700',
    letterSpacing: 0.2,
    textShadowColor: 'rgba(0, 0, 0, 0.9)',
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 6,
  },
  card: {
    backgroundColor: 'rgba(11, 17, 32, 0.42)',
    borderRadius: 26,
    padding: 22,
    borderWidth: 1.2,
    borderColor: 'rgba(255, 255, 255, 0.35)',
    justifyContent: 'center',
  },
  cardHeading: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: '900',
    marginBottom: 16,
    letterSpacing: 0.5,
    textAlign: 'center',
  },
  errorBox: {
    backgroundColor: 'rgba(45, 21, 24, 0.85)',
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.danger,
    marginBottom: 16,
  },
  errorText: {
    color: COLORS.danger,
    fontSize: 13,
    fontWeight: '700',
  },
  inputLabel: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '800',
    marginBottom: 6,
    letterSpacing: 0.4,
    textShadowColor: 'rgba(0, 0, 0, 0.95)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4,
  },
  input: {
    backgroundColor: 'rgba(0, 0, 0, 0.50)',
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 12,
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
    borderWidth: 1.5,
    borderColor: 'rgba(255, 255, 255, 0.30)',
    marginBottom: 14,
  },
  primaryGoldButton: {
    backgroundColor: '#eab308',
    borderRadius: 18,
    paddingVertical: 15,
    alignItems: 'center',
    marginTop: 6,
    shadowColor: '#eab308',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.6,
    shadowRadius: 12,
    elevation: 8,
  },
  primaryButtonText: {
    color: '#000000',
    fontWeight: '900',
    fontSize: 16,
    letterSpacing: 0.5,
  },
  dividerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 16,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: 'rgba(255, 255, 255, 0.22)',
  },
  dividerText: {
    color: 'rgba(255, 255, 255, 0.8)',
    paddingHorizontal: 12,
    fontSize: 11,
    fontWeight: '800',
  },
  googleButton: {
    backgroundColor: 'rgba(255, 255, 255, 0.90)',
    borderRadius: 18,
    paddingVertical: 14,
    alignItems: 'center',
    marginBottom: 12,
    borderWidth: 1.5,
    borderColor: '#ffffff',
    shadowColor: '#ffffff',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
  },
  googleButtonText: {
    color: '#0f172a',
    fontWeight: '900',
    fontSize: 14,
    letterSpacing: 0.5,
  },
  guestCyanButton: {
    backgroundColor: 'rgba(14, 165, 233, 0.15)',
    borderRadius: 18,
    paddingVertical: 14,
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: '#38bdf8',
    shadowColor: '#38bdf8',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.5,
    shadowRadius: 8,
  },
  guestButtonText: {
    color: '#38bdf8',
    fontWeight: '900',
    fontSize: 14,
    letterSpacing: 0.5,
  },
  toggleFooter: {
    marginTop: 18,
    alignItems: 'center',
    paddingVertical: 4,
  },
  toggleFooterText: {
    color: 'rgba(255, 255, 255, 0.85)',
    fontSize: 13,
    fontWeight: '600',
  },
  toggleFooterHighlight: {
    color: '#eab308',
    fontWeight: '900',
    textDecorationLine: 'underline',
  },
});
