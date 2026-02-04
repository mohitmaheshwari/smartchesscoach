import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TouchableOpacity, 
  ActivityIndicator,
  Dimensions,
  Alert,
  TextInput,
  Platform
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '../src/context/ThemeContext';
import { useAuth } from '../src/context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import * as SecureStore from 'expo-secure-store';
import { API_URL } from '../src/constants/config';

const { width } = Dimensions.get('window');

export default function LoginScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const { login } = useAuth();
  const [loading, setLoading] = useState(false);
  const [showDemoLogin, setShowDemoLogin] = useState(false);
  const [demoEmail, setDemoEmail] = useState('');

  // Demo login - creates/logs in a test user
  const handleDemoLogin = async () => {
    if (!demoEmail || !demoEmail.includes('@')) {
      Alert.alert('Invalid Email', 'Please enter a valid email address');
      return;
    }

    setLoading(true);
    try {
      // Call demo login endpoint
      const response = await fetch(`${API_URL}/auth/demo-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: demoEmail }),
      });

      if (!response.ok) {
        throw new Error('Demo login failed');
      }

      const data = await response.json();
      
      // Store session token
      if (data.session_token) {
        await SecureStore.setItemAsync('session_token', data.session_token);
      }

      if (data.user) {
        login(data.user);
        router.replace('/(tabs)/dashboard');
      }
    } catch (error) {
      console.error('Demo login error:', error);
      Alert.alert('Login Failed', 'Could not complete demo login. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    // Show info about Google OAuth setup
    Alert.alert(
      'Google OAuth Setup Required',
      'To use Google Sign-In, you need to:\n\n' +
      '1. Create a project in Google Cloud Console\n' +
      '2. Enable OAuth 2.0\n' +
      '3. Add Android/iOS client IDs\n\n' +
      'For now, use Demo Login to test the app.',
      [
        { text: 'Use Demo Login', onPress: () => setShowDemoLogin(true) },
        { text: 'OK', style: 'cancel' }
      ]
    );
  };

  const styles = createStyles(colors);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        {/* Logo & Title */}
        <View style={styles.header}>
          <View style={styles.logoContainer}>
            <Text style={styles.logoText}>♟</Text>
          </View>
          <Text style={styles.title}>Chess Coach AI</Text>
          <Text style={styles.subtitle}>
            Your personal AI coach that remembers{'\n'}your mistakes and helps you improve
          </Text>
        </View>

        {/* Features */}
        <View style={styles.features}>
          <FeatureItem 
            icon="analytics-outline" 
            text="Analyzes your games with Stockfish engine"
            colors={colors}
          />
          <FeatureItem 
            icon="bulb-outline" 
            text="Identifies recurring patterns in your play"
            colors={colors}
          />
          <FeatureItem 
            icon="trending-up-outline" 
            text="Tracks your progress and predicts rating"
            colors={colors}
          />
          <FeatureItem 
            icon="mic-outline" 
            text="Voice coaching for game reviews"
            colors={colors}
          />
        </View>

        {/* Login Buttons */}
        <View style={styles.buttonContainer}>
          {showDemoLogin ? (
            <>
              {/* Demo Login Form */}
              <View style={styles.demoForm}>
                <Text style={[styles.demoLabel, { color: colors.textSecondary }]}>
                  Enter your email to continue:
                </Text>
                <TextInput
                  style={[styles.demoInput, { 
                    backgroundColor: colors.card, 
                    color: colors.text,
                    borderColor: colors.border 
                  }]}
                  placeholder="your@email.com"
                  placeholderTextColor={colors.textSecondary}
                  value={demoEmail}
                  onChangeText={setDemoEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoCorrect={false}
                />
                <TouchableOpacity 
                  style={styles.demoButton}
                  onPress={handleDemoLogin}
                  disabled={loading}
                  activeOpacity={0.8}
                  testID="demo-login-btn"
                >
                  {loading ? (
                    <ActivityIndicator color="#000" />
                  ) : (
                    <>
                      <Ionicons name="enter-outline" size={20} color="#000" />
                      <Text style={styles.demoButtonText}>Continue with Demo</Text>
                    </>
                  )}
                </TouchableOpacity>
                <TouchableOpacity onPress={() => setShowDemoLogin(false)}>
                  <Text style={[styles.backLink, { color: colors.accent }]}>
                    ← Back to login options
                  </Text>
                </TouchableOpacity>
              </View>
            </>
          ) : (
            <>
              {/* Google Login Button */}
              <TouchableOpacity 
                style={styles.googleButton}
                onPress={handleGoogleLogin}
                disabled={loading}
                activeOpacity={0.8}
                testID="google-login-btn"
              >
                {loading ? (
                  <ActivityIndicator color="#000" />
                ) : (
                  <>
                    <Ionicons name="logo-google" size={20} color="#000" />
                    <Text style={styles.googleButtonText}>Continue with Google</Text>
                  </>
                )}
              </TouchableOpacity>
              
              {/* Demo Login Option */}
              <TouchableOpacity 
                style={[styles.demoOptionButton, { borderColor: colors.border }]}
                onPress={() => setShowDemoLogin(true)}
                activeOpacity={0.8}
                testID="show-demo-btn"
              >
                <Ionicons name="flask-outline" size={20} color={colors.text} />
                <Text style={[styles.demoOptionText, { color: colors.text }]}>
                  Demo Login (for testing)
                </Text>
              </TouchableOpacity>
            </>
          )}
          
          <Text style={styles.disclaimer}>
            By continuing, you agree to our Terms of Service
          </Text>
        </View>
      </View>
    </SafeAreaView>
  );
}

const FeatureItem = ({ icon, text, colors }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 16 }}>
    <View style={{ 
      width: 40, 
      height: 40, 
      borderRadius: 20, 
      backgroundColor: colors.muted,
      justifyContent: 'center',
      alignItems: 'center',
      marginRight: 12,
    }}>
      <Ionicons name={icon} size={20} color={colors.accent} />
    </View>
    <Text style={{ color: colors.textSecondary, flex: 1, fontSize: 14 }}>{text}</Text>
  </View>
);

const createStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    flex: 1,
    paddingHorizontal: 24,
    justifyContent: 'space-between',
    paddingVertical: 40,
  },
  header: {
    alignItems: 'center',
    marginTop: 40,
  },
  logoContainer: {
    width: 80,
    height: 80,
    borderRadius: 20,
    backgroundColor: colors.card,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
    borderWidth: 1,
    borderColor: colors.border,
  },
  logoText: {
    fontSize: 40,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 12,
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 24,
  },
  features: {
    paddingVertical: 20,
  },
  buttonContainer: {
    marginBottom: 20,
  },
  googleButton: {
    backgroundColor: '#fff',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 12,
    gap: 12,
    marginBottom: 12,
  },
  googleButtonText: {
    color: '#000',
    fontSize: 16,
    fontWeight: '600',
  },
  demoOptionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 12,
    borderWidth: 1,
    gap: 12,
  },
  demoOptionText: {
    fontSize: 16,
    fontWeight: '500',
  },
  demoForm: {
    gap: 12,
  },
  demoLabel: {
    fontSize: 14,
    marginBottom: 4,
  },
  demoInput: {
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1,
    fontSize: 16,
  },
  demoButton: {
    backgroundColor: '#f59e0b',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 12,
    gap: 12,
    marginTop: 8,
  },
  demoButtonText: {
    color: '#000',
    fontSize: 16,
    fontWeight: '600',
  },
  backLink: {
    textAlign: 'center',
    marginTop: 16,
    fontSize: 14,
  },
  disclaimer: {
    color: colors.textSecondary,
    fontSize: 12,
    textAlign: 'center',
    marginTop: 16,
  },
});
