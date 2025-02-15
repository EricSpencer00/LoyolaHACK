import firebase_admin
from firebase_admin import credentials

# Replace with the path to your Firebase service account key
cred = credentials.Certificate("path/to/firebase-service-account.json")
firebase_admin.initialize_app(cred)
