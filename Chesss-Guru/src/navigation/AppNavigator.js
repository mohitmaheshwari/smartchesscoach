import React, { useContext } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { StatusBar } from 'expo-status-bar';
import { COLORS } from '../constants/config';
import { AuthProvider, AuthContext } from '../context/AuthContext';
import { GoogleAuthContextProvider } from '../context/GoogleAuthContext';

import AuthScreen from '../screens/AuthScreen';
import DashboardScreen from '../screens/DashboardScreen';
import GameAnalysisScreen from '../screens/GameAnalysisScreen';
import AICoachScreen from '../screens/AICoachScreen';
import CoachPlayScreen from '../screens/CoachPlayScreen';
import LearnScreen from '../screens/LearnScreen';
import ImportGamesScreen from '../screens/ImportGamesScreen';
import ReflectScreen from '../screens/ReflectScreen';
import MistakeMasteryScreen from '../screens/MistakeMasteryScreen';
import SettingsScreen from '../screens/SettingsScreen';

import { View, Text, ImageBackground, ActivityIndicator, StyleSheet } from 'react-native';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

// Bottom Tab Navigation Bar
function MainTabNavigator() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: '#090d16',
          borderTopWidth: 1.2,
          borderTopColor: 'rgba(255, 255, 255, 0.22)',
          height: 64,
          paddingBottom: 8,
          paddingTop: 6,
          elevation: 10,
        },
        tabBarActiveTintColor: '#eab308',
        tabBarInactiveTintColor: '#94a3b8',
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '800',
        },
      }}
    >
      <Tab.Screen
        name="DashboardTab"
        component={DashboardScreen}
        options={{
          tabBarLabel: 'Home',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20 }}>🏠</Text>,
        }}
      />

      <Tab.Screen
        name="CoachPlayTab"
        component={CoachPlayScreen}
        options={{
          tabBarLabel: 'Play',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20 }}>♟️</Text>,
        }}
      />

      <Tab.Screen
        name="LearnTab"
        component={LearnScreen}
        options={{
          tabBarLabel: 'Learn',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20 }}>🎓</Text>,
        }}
      />

      <Tab.Screen
        name="ReflectTab"
        component={ReflectScreen}
        options={{
          tabBarLabel: 'Ledger',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20 }}>📈</Text>,
        }}
      />

      <Tab.Screen
        name="StudioTab"
        component={GameAnalysisScreen}
        options={{
          tabBarLabel: 'Studio',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20 }}>🔍</Text>,
        }}
      />

      <Tab.Screen
        name="SettingsTab"
        component={SettingsScreen}
        options={{
          tabBarLabel: 'Settings',
          tabBarIcon: ({ color }) => <Text style={{ fontSize: 20 }}>⚙️</Text>,
        }}
      />
    </Tab.Navigator>
  );
}

function NavigationStack() {
  const { user, loading } = useContext(AuthContext);

  if (loading) {
    return (
      <ImageBackground
        source={require('../../assets/app_opening_splash.png')}
        style={styles.splashBg}
        resizeMode="cover"
      >
        <View style={styles.splashOverlay}>
          <Text style={styles.splashTitle}>Chesss-Guru</Text>
          <Text style={styles.splashSubtitle}>AI-Powered Master Chess Analytics</Text>
          <ActivityIndicator size="large" color="#eab308" style={{ marginTop: 24 }} />
        </View>
      </ImageBackground>
    );
  }

  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: {
          backgroundColor: COLORS.cardBg,
        },
        headerTintColor: COLORS.text,
        headerTitleStyle: {
          fontWeight: '800',
          fontSize: 18,
        },
        contentStyle: {
          backgroundColor: COLORS.background,
        },
      }}
    >
      {!user ? (
        <Stack.Screen
          name="Auth"
          component={AuthScreen}
          options={{
            headerShown: false,
          }}
        />
      ) : (
        <>
          <Stack.Screen
            name="MainTabs"
            component={MainTabNavigator}
            options={{
              headerShown: false,
            }}
          />
          <Stack.Screen
            name="CoachPlay"
            component={CoachPlayScreen}
            options={{
              title: '♟️ Play with AI Coach',
            }}
          />
          <Stack.Screen
            name="Learn"
            component={LearnScreen}
            options={{
              title: '🎓 Learn & Openings',
            }}
          />
        </>
      )}

      <Stack.Screen
        name="ImportGames"
        component={ImportGamesScreen}
        options={{
          title: '📥 Import PGN Studio',
        }}
      />

      <Stack.Screen
        name="Reflect"
        component={ReflectScreen}
        options={{
          title: '📈 Progress & The Ledger',
        }}
      />

      <Stack.Screen
        name="GameAnalysis"
        component={GameAnalysisScreen}
        options={{
          title: '🔍 Game Analysis Studio',
        }}
      />

      <Stack.Screen
        name="AICoach"
        component={AICoachScreen}
        options={{
          title: '🧙‍♂️ AI Coach Guru',
        }}
      />

      <Stack.Screen
        name="MistakeMastery"
        component={MistakeMasteryScreen}
        options={{
          title: '🧩 Mistake Mastery Cards',
        }}
      />

      <Stack.Screen
        name="Settings"
        component={SettingsScreen}
        options={{
          title: '⚙️ App Settings',
        }}
      />
    </Stack.Navigator>
  );
}

export default function AppNavigator() {
  return (
    <GoogleAuthContextProvider>
      <AuthProvider>
        <NavigationContainer>
          <StatusBar style="light" />
          <NavigationStack />
        </NavigationContainer>
      </AuthProvider>
    </GoogleAuthContextProvider>
  );
}

const styles = StyleSheet.create({
  splashBg: {
    flex: 1,
    width: '100%',
    height: '100%',
  },
  splashOverlay: {
    flex: 1,
    backgroundColor: 'rgba(6, 9, 17, 0.65)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  splashTitle: {
    color: '#ffffff',
    fontSize: 36,
    fontWeight: '900',
    letterSpacing: 1.2,
    textShadowColor: 'rgba(234, 179, 8, 0.8)',
    textShadowOffset: { width: 0, height: 3 },
    textShadowRadius: 16,
  },
  splashSubtitle: {
    color: '#e2e8f0',
    fontSize: 13,
    marginTop: 8,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
});
