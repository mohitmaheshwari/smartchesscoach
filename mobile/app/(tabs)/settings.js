import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TouchableOpacity, 
  Switch,
  Alert,
  ActivityIndicator
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../../src/context/ThemeContext';
import { useAuth } from '../../src/context/AuthContext';
import { settingsAPI } from '../../src/services/api';

export default function SettingsScreen() {
  const { colors, theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const [emailSettings, setEmailSettings] = useState({
    game_analyzed: true,
    weekly_summary: true,
    weakness_alert: true,
  });
  const [loadingEmail, setLoadingEmail] = useState(true);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    fetchEmailSettings();
  }, []);

  const fetchEmailSettings = async () => {
    try {
      const data = await settingsAPI.getEmailSettings();
      setEmailSettings(data.notifications);
    } catch (error) {
      console.error('Failed to fetch email settings:', error);
    } finally {
      setLoadingEmail(false);
    }
  };

  const updateEmailSetting = async (key, value) => {
    const newSettings = { ...emailSettings, [key]: value };
    setEmailSettings(newSettings);
    try {
      await settingsAPI.updateEmailSettings(newSettings);
    } catch (error) {
      // Revert on error
      setEmailSettings(prev => ({ ...prev, [key]: !value }));
      Alert.alert('Error', 'Failed to update settings');
    }
  };

  const handleLogout = async () => {
    Alert.alert(
      'Sign Out',
      'Are you sure you want to sign out?',
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Sign Out', 
          style: 'destructive',
          onPress: async () => {
            setLoggingOut(true);
            await logout();
          }
        },
      ]
    );
  };

  const styles = createStyles(colors);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView 
        style={styles.scrollView}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.greeting}>PREFERENCES</Text>
          <Text style={styles.title}>Settings</Text>
        </View>

        {/* Profile Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>PROFILE</Text>
          <View style={styles.card}>
            <View style={styles.profileRow}>
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>{user?.name?.charAt(0) || 'U'}</Text>
              </View>
              <View style={styles.profileInfo}>
                <Text style={styles.profileName}>{user?.name}</Text>
                <Text style={styles.profileEmail}>{user?.email}</Text>
              </View>
            </View>
          </View>
        </View>

        {/* Appearance Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>APPEARANCE</Text>
          <View style={styles.card}>
            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Ionicons 
                  name={theme === 'dark' ? 'moon' : 'sunny'} 
                  size={22} 
                  color={colors.text} 
                />
                <Text style={styles.settingLabel}>Dark Mode</Text>
              </View>
              <Switch
                value={theme === 'dark'}
                onValueChange={toggleTheme}
                trackColor={{ false: colors.muted, true: colors.accent }}
                thumbColor="#fff"
              />
            </View>
          </View>
        </View>

        {/* Email Notifications Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>EMAIL NOTIFICATIONS</Text>
          <View style={styles.card}>
            {loadingEmail ? (
              <ActivityIndicator color={colors.text} style={{ padding: 20 }} />
            ) : (
              <>
                <View style={styles.settingRow}>
                  <View style={styles.settingInfo}>
                    <Ionicons name="game-controller-outline" size={22} color={colors.text} />
                    <View>
                      <Text style={styles.settingLabel}>Game Analyzed</Text>
                      <Text style={styles.settingDescription}>When new games are analyzed</Text>
                    </View>
                  </View>
                  <Switch
                    value={emailSettings.game_analyzed}
                    onValueChange={(v) => updateEmailSetting('game_analyzed', v)}
                    trackColor={{ false: colors.muted, true: colors.accent }}
                    thumbColor="#fff"
                  />
                </View>
                
                <View style={styles.divider} />
                
                <View style={styles.settingRow}>
                  <View style={styles.settingInfo}>
                    <Ionicons name="calendar-outline" size={22} color={colors.text} />
                    <View>
                      <Text style={styles.settingLabel}>Weekly Summary</Text>
                      <Text style={styles.settingDescription}>Progress report every week</Text>
                    </View>
                  </View>
                  <Switch
                    value={emailSettings.weekly_summary}
                    onValueChange={(v) => updateEmailSetting('weekly_summary', v)}
                    trackColor={{ false: colors.muted, true: colors.accent }}
                    thumbColor="#fff"
                  />
                </View>
                
                <View style={styles.divider} />
                
                <View style={styles.settingRow}>
                  <View style={styles.settingInfo}>
                    <Ionicons name="alert-circle-outline" size={22} color={colors.text} />
                    <View>
                      <Text style={styles.settingLabel}>Weakness Alerts</Text>
                      <Text style={styles.settingDescription}>When patterns are detected</Text>
                    </View>
                  </View>
                  <Switch
                    value={emailSettings.weakness_alert}
                    onValueChange={(v) => updateEmailSetting('weakness_alert', v)}
                    trackColor={{ false: colors.muted, true: colors.accent }}
                    thumbColor="#fff"
                  />
                </View>
              </>
            )}
          </View>
        </View>

        {/* About Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>ABOUT</Text>
          <View style={styles.card}>
            <View style={styles.aboutRow}>
              <Text style={styles.aboutLabel}>Version</Text>
              <Text style={styles.aboutValue}>1.0.0</Text>
            </View>
            <View style={styles.divider} />
            <TouchableOpacity style={styles.aboutRow}>
              <Text style={styles.aboutLabel}>Privacy Policy</Text>
              <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
            <View style={styles.divider} />
            <TouchableOpacity style={styles.aboutRow}>
              <Text style={styles.aboutLabel}>Terms of Service</Text>
              <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
        </View>

        {/* Logout Button */}
        <TouchableOpacity 
          style={styles.logoutButton}
          onPress={handleLogout}
          disabled={loggingOut}
        >
          {loggingOut ? (
            <ActivityIndicator color={colors.error} />
          ) : (
            <>
              <Ionicons name="log-out-outline" size={20} color={colors.error} />
              <Text style={styles.logoutText}>Sign Out</Text>
            </>
          )}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const createStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollView: {
    flex: 1,
  },
  content: {
    padding: 20,
    paddingBottom: 40,
  },
  header: {
    marginBottom: 24,
  },
  greeting: {
    fontSize: 11,
    color: colors.textSecondary,
    letterSpacing: 1,
    marginBottom: 4,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    letterSpacing: -0.5,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 11,
    color: colors.textSecondary,
    letterSpacing: 1,
    marginBottom: 12,
    fontWeight: '600',
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  profileRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.muted,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 16,
  },
  avatarText: {
    fontSize: 22,
    fontWeight: '600',
    color: colors.text,
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 2,
  },
  profileEmail: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  settingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
  },
  settingInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  settingLabel: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.text,
  },
  settingDescription: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginHorizontal: 16,
  },
  aboutRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
  },
  aboutLabel: {
    fontSize: 15,
    color: colors.text,
  },
  aboutValue: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.error,
    gap: 8,
    marginTop: 8,
  },
  logoutText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.error,
  },
});
