from firebase_manager import fm
from linkedin_dashboard import load_posts
import time

def seed():
    print("🚀 Starting Firebase Seeding...")
    if not fm.initialize():
        print("❌ Firebase not initialized. Please ensure 'serviceAccountKey.json' exists.")
        return

    posts = load_posts()
    print(f"📦 Found {len(posts)} local posts.")

    for i, post in enumerate(posts):
        # Convert Path objects to strings for JSON/Firestore compatibility
        p_copy = post.copy()
        if "file" in p_copy:
            p_copy["file"] = str(p_copy["file"])
        
        print(f"  [{i+1}/{len(posts)}] Syncing: {p_copy['filename']}...")
        fm.sync_post(p_copy)
        time.sleep(0.1)  # Brief pause

    print("✅ Seeding complete! Your posts are now in the cloud.")

if __name__ == "__main__":
    seed()
