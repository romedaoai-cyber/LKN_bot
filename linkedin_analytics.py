import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, urlencode

# Configuration
POSTS_DIR = Path(__file__).parent / "linkedin_posts"
DOTENV_PATH = Path(__file__).parent / ".env"
ANALYTICS_FILE = Path(__file__).parent / "linkedin_analytics_data.json"

# LinkedIn API Endpoints
SOCIAL_ACTIONS_URL = "https://api.linkedin.com/v2/socialActions/{share_urn}"
ORG_STATS_URL = "https://api.linkedin.com/rest/organizationalEntityShareStatistics"

def load_env():
    """Load environment variables from .env file."""
    env = {}
    if DOTENV_PATH.exists():
        with open(DOTENV_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def get_headers(access_token):
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202401",
    }


def get_posts_with_urns():
    """Scan posts directory for files with shareUrn."""
    posts = []
    if not POSTS_DIR.exists():
        return posts

    for f in POSTS_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        urn = None
        for line in content.split("\n"):
            if line.startswith("<!-- shareUrn:"):
                parts = line.split(":", 1)
                if len(parts) > 1:
                    urn = parts[1].strip().strip("-->").strip()
                break
        
        if urn:
            posts.append({
                "file": str(f),
                "name": f.name,
                "urn": urn
            })
    return posts


def fetch_social_actions(urn, headers):
    """Fetch likes and comments counts for a specific URN."""
    encoded_urn = quote(urn)
    url = SOCIAL_ACTIONS_URL.format(share_urn=encoded_urn)
    
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        likes = data.get("likesSummary", {}).get("totalLikes", 0)
        comments = data.get("commentsSummary", {}).get("totalFirstLevelComments", 0)
        return likes, comments
    
    # If 403/404, maybe using different URN type?
    # Some endpoints need urn:li:share, others urn:li:ugcPost
    return 0, 0


def fetch_impressions_batch(urns, org_urn, headers):
    """Fetch impressions for a list of URNs."""
    if not org_urn:
        return {}

    # Ensure org_urn is a URN
    if not org_urn.startswith("urn:li:organization:"):
        org_urn = f"urn:li:organization:{org_urn}"

    stats_map = {}
    
    # API allows batching shares
    # Logic: ?q=organizationalEntity&organizationalEntity={orgUrn}&shares=List(urn1,urn2)
    
    # Process in chunks of 20 to be safe
    chunk_size = 20
    for i in range(0, len(urns), chunk_size):
        chunk = urns[i:i + chunk_size]
        
        # Build shares parameter: List(urn1,urn2)
        shares_param = "List(" + ",".join([quote(u) for u in chunk]) + ")"
        
        params = {
            "q": "organizationalEntity",
            "organizationalEntity": org_urn,
            "shares": shares_param
        }
        
        # Actually requests params encoding might double encode if we use requests.get(params=...) with already quoted string?
        # Manually building query string is safer for "List(...)" syntax which is non-standard
        
        query = f"q=organizationalEntity&organizationalEntity={quote(org_urn)}&shares={shares_param}"
        url = f"{ORG_STATS_URL}?{query}"
        
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 200:
            data = resp.json()
            elements = data.get("elements", [])
            for el in elements:
                share_urn = el.get("share")
                impressions = el.get("totalShareStatistics", {}).get("impressionCount", 0)
                stats_map[share_urn] = impressions
        else:
            print(f"⚠️ Failed to fetch impressions: {resp.status_code} {resp.text}")

    return stats_map


def save_analytics(data):
    """Save analytics data to JSON and sync to Firebase."""
    # 1. Save Local JSON
    with open(ANALYTICS_FILE, "w") as f:
        json.dump(data, f, indent=2)

    # 2. Sync to Firebase
    from firebase_manager import fm
    if fm.initialize():
        print("🔥 Syncing analytics to Firebase...")
        for row in data:
            filename = row.get("filename")
            if filename:
                # Merge analytics data into the post document
                # We use the filename as the key just like in sync_post
                fm.db.collection("posts").document(filename).set(row, merge=True)
        
        # Log the sync event
        fm.log_event("analytics", f"Synced {len(data)} post analytics", {"count": len(data)})


def main():
    env = load_env()
    access_token = env.get("LINKEDIN_ACCESS_TOKEN")
    org_id = env.get("LINKEDIN_ORG_ID")

    if not access_token:
        print("❌ No access token found. Run 'python linkedin_publisher.py auth' first.")
        return

    print("🔍 Scanning for published posts...")
    posts = get_posts_with_urns()
    
    if not posts:
        print("📭 No published posts found (no files with <!-- shareUrn: ... -->).")
        return

    print(f"Found {len(posts)} posts with URNs.")
    
    # 1. Fetch Social Actions (Likes/Comments) - Loop
    # 2. Fetch Impressions - Batch
    
    urns = [p["urn"] for p in posts]
    impressions_map = fetch_impressions_batch(urns, org_id, get_headers(access_token))
    
    analytics_data = []

    print("\n📊 Fetching analytics...")
    print(f"{'Post':<40} {'Likes':<8} {'Comm.':<8} {'Views':<8}")
    print("─" * 70)

    for post in posts:
        urn = post["urn"]
        likes, comments = fetch_social_actions(urn, get_headers(access_token))
        views = impressions_map.get(urn, 0)
        
        row = {
            "file": post["file"],
            "filename": post["name"], # Standardized name
            "urn": urn,
            "likes": likes,
            "comments": comments,
            "impressions": views,
            "fetched_at": datetime.now().isoformat()
        }
        analytics_data.append(row)
        
        print(f"{post['name']:<40} {likes:<8} {comments:<8} {views:<8}")
        time.sleep(0.2) 

    save_analytics(analytics_data)
    print(f"\n✅ Data saved to {ANALYTICS_FILE}")

if __name__ == "__main__":
    main()
