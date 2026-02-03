# Chess Coach AI - Mobile App

A React Native (Expo) mobile application for the Chess Coach AI platform.

## Features

- **Interactive Chessboard**: WebView-based chess board for reviewing game positions
- **Google Sign-In**: Secure authentication using expo-auth-session
- **Push Notifications**: Get notified when your games are analyzed
- **Game Analysis**: View AI-powered analysis of your chess games
- **Journey Dashboard**: Track your improvement over time
- **Dark/Light Theme**: System-aware theming

## Prerequisites

- Node.js 18+
- npm or yarn
- Expo CLI (`npm install -g expo-cli`)
- Expo Go app on your mobile device (for development)

## Setup

1. Install dependencies:
```bash
cd /app/mobile
npm install
```

2. Start the development server:
```bash
npx expo start
```

3. Open the app:
   - Scan the QR code with Expo Go (Android)
   - Scan the QR code with Camera app (iOS)
   - Or press `w` to open web version (requires additional dependencies)

## Project Structure

```
/app/mobile/
├── app/                    # Expo Router screens
│   ├── (tabs)/            # Tab-based navigation
│   │   ├── dashboard.js   # Dashboard screen
│   │   ├── journey.js     # Journey tracking
│   │   ├── games.js       # Games list
│   │   └── settings.js    # User settings
│   ├── game/              
│   │   └── [id].js        # Game analysis with chessboard
│   ├── login.js           # Google Sign-In
│   ├── index.js           # Entry point
│   └── _layout.js         # Root layout with providers
├── src/
│   ├── components/
│   │   └── ChessBoard.js  # WebView-based chessboard
│   ├── context/
│   │   ├── AuthContext.js # Authentication state
│   │   └── ThemeContext.js # Theme state
│   ├── services/
│   │   ├── api.js         # Backend API calls
│   │   ├── googleAuth.js  # Google OAuth helpers
│   │   └── notifications.js # Push notification setup
│   └── constants/
│       └── config.js      # App configuration
├── assets/                 # App icons and images
├── app.json               # Expo configuration
└── package.json           # Dependencies
```

## Key Technologies

- **Expo SDK 54**: Modern React Native development
- **Expo Router**: File-based navigation
- **expo-auth-session**: Google OAuth integration
- **expo-notifications**: Push notification support
- **react-native-webview**: Interactive chessboard rendering
- **chess.js**: Chess game logic and PGN parsing

## API Configuration

The mobile app connects to the same backend as the web app:
- API URL: Configured in `src/constants/config.js`
- Authentication: Bearer token stored in SecureStore

## Google OAuth Setup

For development, the app uses Expo's development client ID. For production:

1. Create OAuth credentials in [Google Cloud Console](https://console.cloud.google.com/)
2. Add client IDs for iOS and Android
3. Update `src/services/googleAuth.js` with your credentials

## Push Notifications

Push notifications require:
1. A physical device (not supported in simulators)
2. Proper permission grants from the user
3. Valid Expo push token registration with backend

The app automatically registers for push notifications when a user logs in.

## Building for Production

### Development Build
```bash
npx expo prebuild
npx expo run:ios   # or run:android
```

### Production Build (EAS)
```bash
npm install -g eas-cli
eas build --platform ios
eas build --platform android
```

## Backend Endpoints Used

- `POST /api/auth/google/mobile` - Mobile Google authentication
- `GET /api/auth/me` - Current user info
- `POST /api/auth/logout` - Sign out
- `GET /api/dashboard-stats` - Dashboard statistics
- `GET /api/journey` - Journey dashboard data
- `GET /api/games` - User's games list
- `GET /api/games/:id` - Single game details
- `GET /api/analysis/:id` - Game analysis
- `POST /api/notifications/register-device` - Register push token

## Troubleshooting

### "Not authenticated" errors
- Ensure you're logged in with Google
- Check that the session token is properly stored
- Try logging out and back in

### Chessboard not rendering
- Check WebView is properly installed
- Ensure the device has internet connectivity
- Try force-closing and reopening the app

### Push notifications not working
- Must be on a physical device
- Grant notification permissions when prompted
- Check backend logs for push token registration
