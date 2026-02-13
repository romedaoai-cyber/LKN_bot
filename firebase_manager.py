import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
from pathlib import Path

class FirebaseManager:
    def __init__(self, key_path="serviceAccountKey.json"):
        self.db = None
        self.key_path = key_path
        self.initialize()

    def initialize(self):
        """Initialize Firebase with local key or environment variables (for Cloud)"""
        try:
            if not firebase_admin._apps:
                # 1. Try local file
                if os.path.exists(self.key_path):
                    cred = credentials.Certificate(self.key_path)
                    firebase_admin.initialize_app(cred)
                # 2. Try environment variable (Streamlit Cloud Secrets)
                elif os.environ.get("FIREBASE_SERVICE_ACCOUNT"):
                    # For Cloud, we can pass the JSON string directly
                    service_account_info = json.loads(os.environ.get("FIREBASE_SERVICE_ACCOUNT"))
                    cred = credentials.Certificate(service_account_info)
                    firebase_admin.initialize_app(cred)
                else:
                    print("⚠️ Firebase credentials not found. Local file mode will be used.")
                    return False
            
            self.db = firestore.client()
            return True
        except Exception as e:
            print(f"❌ Firebase Init Error: {e}")
            return False

    def is_active(self):
        return self.db is not None

    def get_all_posts(self):
        """Fetch all posts from 'posts' collection"""
        if not self.db: return []
        posts_ref = self.db.collection("posts")
        docs = posts_ref.stream()
        return [doc.to_dict() for doc in docs]

    def sync_post(self, post_data):
        """Save or update a post in Firestore. Uses 'filename' as document ID."""
        if not self.db: return
        doc_id = post_data.get("filename")
        if not doc_id: return
        self.db.collection("posts").document(doc_id).set(post_data, merge=True)

    def log_event(self, category, message, metadata=None):
        """Log events to 'logs' collection"""
        if not self.db: return
        log_data = {
            "timestamp": firestore.SERVER_TIMESTAMP,
            "category": category,
            "message": message,
            "metadata": metadata or {}
        }
        self.db.collection("logs").add(log_data)

# Singleton instance
fm = FirebaseManager()
