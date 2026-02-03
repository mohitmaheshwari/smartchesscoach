import React, { useState } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TouchableOpacity, 
  ActivityIndicator,
  Image,
  Dimensions 
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as WebBrowser from 'expo-web-browser';
import { useTheme } from '../src/context/ThemeContext';
import { useAuth } from '../src/context/AuthContext';
import { API_URL } from '../src/constants/config';
import { Ionicons } from '@expo/vector-icons';

const { width } = Dimensions.get('window');

export default function LoginScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const { login, refresh } = useAuth();
  const [loading, setLoading] = useState(false);

  const handleGoogleLogin = async () => {
    setLoading(true);
    try {
      // Open Google OAuth in browser
      const result = await WebBrowser.openAuthSessionAsync(
        `${API_URL}/auth/google`,
        'chesscoach://'
      );
      
      if (result.type === 'success') {
        // Refresh auth state
        await refresh();
        router.replace('/(tabs)/dashboard');
      }
    } catch (error) {
      console.error('Login error:', error);
    } finally {
      setLoading(false);
    }
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
            text="Analyzes your games from Chess.com & Lichess"
            colors={colors}
          />
          <FeatureItem 
            icon="bulb-outline" 
            text="Identifies recurring patterns in your play"
            colors={colors}
          />
          <FeatureItem 
            icon="trending-up-outline" 
            text="Tracks your progress over time"
            colors={colors}
          />
          <FeatureItem 
            icon="mic-outline" 
            text="Voice coaching for game reviews"
            colors={colors}
          />
        </View>

        {/* Login Button */}
        <View style={styles.buttonContainer}>
          <TouchableOpacity 
            style={styles.googleButton}
            onPress={handleGoogleLogin}
            disabled={loading}
            activeOpacity={0.8}
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
  },
  googleButtonText: {
    color: '#000',
    fontSize: 16,
    fontWeight: '600',
  },
  disclaimer: {
    color: colors.textSecondary,
    fontSize: 12,
    textAlign: 'center',
    marginTop: 16,
  },
});
