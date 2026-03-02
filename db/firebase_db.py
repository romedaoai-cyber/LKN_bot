"""
Firebase Firestore backend — mirrors LocalStore API.
Falls back gracefully when Firebase is not configured.
"""
import os
import json

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False


class FirebaseDB:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.db = None
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        if not FIREBASE_AVAILABLE:
            return
        try:
            if not firebase_admin._apps:
                sa_path = "serviceAccountKey.json"
                if os.path.exists(sa_path):
                    cred = credentials.Certificate(sa_path)
                elif os.environ.get("FIREBASE_SERVICE_ACCOUNT"):
                    info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
                    cred = credentials.Certificate(info)
                else:
                    return
                # Derive storage bucket: env var > project_id.appspot.com
                project_id = getattr(cred, "project_id", None)
                bucket_name = os.environ.get(
                    "FIREBASE_STORAGE_BUCKET",
                    f"{project_id}.appspot.com" if project_id else "",
                )
                app_options = {"storageBucket": bucket_name} if bucket_name else {}
                firebase_admin.initialize_app(cred, app_options)
            self.db = firestore.client()
        except Exception as e:
            print(f"Firebase init error: {e}")

    @property
    def active(self):
        return self.db is not None

    # ── Collection helpers ──

    def all(self, collection: str) -> list:
        if not self.active:
            return []
        try:
            return [doc.to_dict() for doc in self.db.collection(collection).stream()]
        except Exception:
            return []

    def get(self, collection: str, id_: str) -> dict | None:
        if not self.active:
            return None
        try:
            doc = self.db.collection(collection).document(id_).get()
            return doc.to_dict() if doc.exists else None
        except Exception:
            return None

    def save(self, collection: str, record: dict):
        if not self.active:
            return
        doc_id = record.get("id") or record.get("post_id") or "unknown"
        try:
            self.db.collection(collection).document(str(doc_id)).set(record, merge=True)
        except Exception as e:
            print(f"Firebase save error [{collection}]: {e}")

    def delete(self, collection: str, id_: str):
        if not self.active:
            return
        try:
            self.db.collection(collection).document(id_).delete()
        except Exception as e:
            print(f"Firebase delete error [{collection}]: {e}")

    def log(self, category: str, message: str, metadata: dict = None):
        if not self.active:
            return
        try:
            from firebase_admin import firestore as _fs
            self.db.collection("logs").add({
                "timestamp": _fs.SERVER_TIMESTAMP,
                "category": category,
                "message": message,
                "metadata": metadata or {},
            })
        except Exception:
            pass


firebase = FirebaseDB()
