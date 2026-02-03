import { useEffect, useRef } from 'react';
import { Stack, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { AuthProvider, useAuth } from '../src/context/AuthContext';
import { ThemeProvider, useTheme } from '../src/context/ThemeContext';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { 
  registerForPushNotifications, 
  addNotificationListeners,
  savePushTokenToBackend 
} from '../src/services/notifications';
import { getSessionToken } from '../src/services/api';

function RootLayoutNav() {
  const { colors, theme } = useTheme();
  const { user } = useAuth();
  const router = useRouter();
  const notificationListener = useRef();

  useEffect(() => {
    // Initialize push notifications when user is logged in
    if (user) {
      initializePushNotifications();
    }

    // Set up notification listeners
    const cleanup = addNotificationListeners(
      // On notification received (foreground)
      (notification) => {
        console.log('Notification received in foreground:', notification);
      },
      // On notification tapped
      (response) => {
        const data = response.notification.request.content.data;
        console.log('Notification tapped with data:', data);
        
        // Navigate based on notification type
        if (data?.type === 'game_analyzed') {
          router.push('/(tabs)/games');
        } else if (data?.game_id) {
          router.push(`/game/${data.game_id}`);
        }
      }
    );

    return cleanup;
  }, [user]);

  const initializePushNotifications = async () => {
    try {
      const token = await registerForPushNotifications();
      if (token) {
        const sessionToken = await getSessionToken();
        if (sessionToken) {
          await savePushTokenToBackend(token, sessionToken);
        }
      }
    } catch (error) {
      console.error('Failed to initialize push notifications:', error);
    }
  };

  return (
    <>
      <StatusBar style={theme === 'dark' ? 'light' : 'dark'} />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.background },
          animation: 'slide_from_right',
        }}
      />
    </>
  );
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ThemeProvider>
          <AuthProvider>
            <RootLayoutNav />
          </AuthProvider>
        </ThemeProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
