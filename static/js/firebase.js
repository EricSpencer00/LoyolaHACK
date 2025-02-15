// Import the Firebase SDK
import firebase from 'firebase/app';
import 'firebase/auth';
import 'firebase/firestore';

// Your Firebase configuration
const firebaseConfig = {
    apiKey: 'YOUR_API_KEY',
    authDomain: 'YOUR_AUTH_DOMAIN',
    projectId: 'YOUR_PROJECT_ID',
    storageBucket: 'YOUR_STORAGE_BUCKET',
    messagingSenderId: 'YOUR_MESSAGING_SENDER_ID',
    appId: 'YOUR_APP_ID'
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);

// Export the Firebase modules you need
export const auth = firebase.auth();
export const firestore = firebase.firestore();
