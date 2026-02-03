# Chess Coach AI - Mobile App

React Native (Expo) mobile app for the Chess Coach AI platform.

## Features

- **Dashboard** - Overview of games, stats, and quick actions
- **Journey** - Progress tracking with weakness trends and coach assessment
- **Games** - Import and view games from Chess.com/Lichess
- **Game Analysis** - AI-powered move-by-move analysis with best move suggestions
- **Settings** - Theme toggle, email notifications, profile

## Tech Stack

- **Expo** (SDK 54)
- **Expo Router** - File-based navigation
- **React Native** - Cross-platform mobile
- **Expo Secure Store** - Secure token storage

## Project Structure

```
mobile/
├── app/                    # Expo Router screens
│   ├── _layout.js          # Root layout with providers
│   ├── index.js            # Entry point (auth check)
│   ├── login.js            # Login screen
│   ├── (tabs)/             # Tab navigator
│   │   ├── _layout.js      # Tab configuration
│   │   ├── dashboard.js    # Dashboard screen
│   │   ├── journey.js      # Journey/progress screen
│   │   ├── games.js        # Games list screen
│   │   └── settings.js     # Settings screen
│   └── game/
│       └── [id].js         # Game analysis screen
├── src/
│   ├── constants/
│   │   └── config.js       # API URL, colors, constants
│   ├── context/
│   │   ├── AuthContext.js  # Authentication state
│   │   └── ThemeContext.js # Theme state (dark/light)
│   └── services/
│       └── api.js          # API service functions
├── app.json                # Expo configuration
└── package.json
```

## Setup

1. **Install dependencies:**
   ```bash
   cd mobile
   npm install
   ```

2. **Configure API URL:**
   Edit `src/constants/config.js`:
   ```javascript
   export const API_URL = 'https://your-backend-url/api';
   ```

3. **Run the app:**
   ```bash
   # Start Expo dev server
   npm start
   
   # Or run on specific platform
   npm run ios
   npm run android
   ```

## Building for Production

### iOS (App Store)
```bash
eas build --platform ios
```

### Android (Play Store)
```bash
eas build --platform android
```

## API Integration

The mobile app connects to the same backend API as the web app:

| Endpoint | Description |
|----------|-------------|
| `/api/auth/me` | Get current user |
| `/api/dashboard-stats` | Dashboard statistics |
| `/api/journey` | Journey dashboard data |
| `/api/journey/linked-accounts` | Linked chess accounts |
| `/api/games` | List of imported games |
| `/api/games/:id` | Single game details |
| `/api/analysis/:id` | Game analysis |
| `/api/analyze-game` | Trigger AI analysis |
| `/api/settings/email-notifications` | Email preferences |

## Environment Variables

For production, set these in your EAS build:

```bash
eas secret:create --name API_URL --value "https://api.yourdomain.com/api"
```

## Features Roadmap

- [ ] Interactive chessboard (react-native-chessboard)
- [ ] Push notifications for new analysis
- [ ] Offline mode with local caching
- [ ] Voice coaching playback
- [ ] Opening repertoire builder
- [ ] Parent dashboard
