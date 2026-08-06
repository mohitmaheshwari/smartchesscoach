// Import the functions you need from the SDKs you need
import { initializeApp } from 'firebase/app';
import { initializeAuth, inMemoryPersistence } from 'firebase/auth';

// Your web app's Firebase configuration (Chess Guru project)
const firebaseConfig = {
  apiKey: 'AIzaSyANeD-fwrf8Kcu6z2PSjLZd1XSAszGb9a8',
  authDomain: 'chess-guru-4bc55.firebaseapp.com',
  projectId: 'chess-guru-4bc55',
  storageBucket: 'chess-guru-4bc55.firebasestorage.app',
  messagingSenderId: '889695197064',
  appId: '1:889695197064:android:9d3da461fdf7482e334c3d',
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Use inMemoryPersistence for React Native (AsyncStorage-based persistence
// can be added later via getReactNativePersistence if needed)
export const auth = initializeAuth(app, {
  persistence: inMemoryPersistence,
});

export default app;
