import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

# Configuration
POSTS_DIR = Path(__file__).parent / "linkedin_posts"
DOTENV_PATH = Path(__file__).parent / ".env"
ANALYTICS_FILE = Path(__file__).parent / "linkedin_analytics_data.json"

# LinkedIn API Endpoints
ORG_POSTS_URL = "https://api.linkedin.com/rest/posts"
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
        "LinkedIn-Version": "202410",
    }


def fetch_org_posts(org_urn, headers):
    """Fetch ALL posts from the organization via LinkedIn API."""
    posts = []
    
    # Ensure org_urn is properly formatted
    if not org_urn.startswith("urn:li:organization:"):
        org_urn = f"urn:li:organization:{org_urn}"
    
    params = {
        "author": org_urn,
        "q": "author",
        "count": 50,  # Max per page
    }
    
    url = ORG_POSTS_URL
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        print(f"📡 Fetching org posts... Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            elements = data.get("elements", [])
            
            for el in elements:
                post_id = el.get("id", "")
                content = el.get("commentary", "")
                created_at = el.get("createdAt", 0)
                
                # Extract a short title from the content
                title = content[:80].replace("\n", " ").strip() if content else "Untitled"
                if len(content) > 80:
                    title += "..."
                
                # Convert timestamp to readable date
                created_date = ""
                if created_at:
                    created_date = datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d")
                
                posts.append({
                    "urn": post_id,
                    "name": title,
                    "date": created_date,
                    "content_preview": content[:200] if content else "",
                })
            
            print(f"✅ Found {len(posts)} posts from organization")
        elif resp.status_code == 403:
            print(f"⚠️ Permission denied. Trying UGC Posts API fallback...")
            posts = fetch_org_posts_ugc(org_urn, headers)
        else:
            print(f"⚠️ Failed to fetch org posts: {resp.status_code}")
            print(f"   Response: {resp.text[:300]}")
            # Try UGC fallback
            posts = fetch_org_posts_ugc(org_urn, headers)
    except Exception as e:
        print(f"❌ Error fetching org posts: {e}")
    
    return posts


def fetch_org_posts_ugc(org_urn, headers):
    """Fallback: Use UGC Posts API to fetch org posts."""
    posts = []
    
    url = f"https://api.linkedin.com/v2/ugcPosts?q=authors&authors=List({quote(org_urn)})&count=50"
    
    try:
        resp = requests.get(url, headers=headers)
        print(f"📡 UGC fallback... Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            elements = data.get("elements", [])
            
            for el in elements:
                post_id = el.get("id", "")
                
                # UGC posts have different content structure
                specific_content = el.get("specificContent", {})
                share_content = specific_content.get("com.linkedin.ugc.ShareContent", {})
                share_commentary = share_content.get("shareCommentary", {})
                content = share_commentary.get("text", "")
                
                created_at = el.get("created", {}).get("time", 0)
                
                title = content[:80].replace("\n", " ").strip() if content else "Untitled"
                if len(content) > 80:
                    title += "..."
                
                created_date = ""
                if created_at:
                    created_date = datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d")
                
                posts.append({
                    "urn": post_id,
                    "name": title,
                    "date": created_date,
                    "content_preview": content[:200] if content else "",
                })
            
            print(f"✅ Found {len(posts)} posts via UGC API")
        else:
            print(f"⚠️ UGC fallback also failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"❌ Error in UGC fallback: {e}")
    
    return posts


def fetch_social_actions(urn, headers):
    """Fetch likes and comments counts for a specific URN."""
    encoded_urn = quote(urn)
    url = SOCIAL_ACTIONS_URL.format(share_urn=encoded_urn)
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            likes = data.get("likesSummary", {}).get("totalLikes", 0)
            comments = data.get("commentsSummary", {}).get("totalFirstLevelComments", 0)
            return likes, comments
    except:
        pass
    return 0, 0


def fetch_impressions_batch(urns, org_urn, headers):
    """Fetch impressions for a list of URNs."""
    if not org_urn:
        return {}

    if not org_urn.startswith("urn:li:organization:"):
        org_urn = f"urn:li:organization:{org_urn}"

    stats_map = {}
    chunk_size = 20
    
    for i in range(0, len(urns), chunk_size):
        chunk = urns[i:i + chunk_size]
        shares_param = "List(" + ",".join([quote(u) for u in chunk]) + ")"
        query = f"q=organizationalEntity&organizationalEntity={quote(org_urn)}&shares={shares_param}"
        url = f"{ORG_STATS_URL}?{query}"
        
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                elements = data.get("elements", [])
                for el in elements:
                    share_urn = el.get("share")
                    stats = el.get("totalShareStatistics", {})
                    impressions = stats.get("impressionCount", 0)
                    clicks = stats.get("clickCount", 0)
                    stats_map[share_urn] = {"impressions": impressions, "clicks": clicks}
            else:
                print(f"⚠️ Impressions batch failed: {resp.status_code}")
        except Exception as e:
            print(f"⚠️ Impressions error: {e}")

    return stats_map


def save_analytics(data):
    """Save analytics data to JSON and sync to Firebase."""
    with open(ANALYTICS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    try:
        from firebase_manager import fm
        if fm.initialize():
            print("🔥 Syncing analytics to Firebase...")
            for row in data:
                filename = row.get("filename")
                if filename:
                    fm.db.collection("posts").document(filename).set(row, merge=True)
            fm.log_event("analytics", f"Synced {len(data)} post analytics", {"count": len(data)})
    except Exception as e:
        print(f"⚠️ Firebase sync skipped: {e}")


def main():
    # Check os.environ FIRST (Streamlit Cloud), then .env file
    access_token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    org_id = os.environ.get("LINKEDIN_ORG_ID")
    
    if not access_token:
        env = load_env()
        access_token = env.get("LINKEDIN_ACCESS_TOKEN")
        org_id = org_id or env.get("LINKEDIN_ORG_ID")

    if not access_token:
        print("❌ No access token found. Set LINKEDIN_ACCESS_TOKEN in secrets or .env.")
        return

    headers = get_headers(access_token)

    # ── Step 1: Fetch ALL posts from organization ──
    print("🔍 Fetching all published posts from LinkedIn...")
    org_posts = fetch_org_posts(org_id, headers) if org_id else []
    
    # ── Step 2: Also scan local files for any with shareUrn ──
    local_posts = []
    if POSTS_DIR.exists():
        for f in POSTS_DIR.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            for line in content.split("\n"):
                if line.startswith("<!-- shareUrn:"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        urn = parts[1].strip().strip("-->").strip()
                        local_posts.append({"urn": urn, "name": f.name, "file": str(f)})
                    break
    
    # ── Step 3: Merge (avoid duplicates) ──
    seen_urns = set()
    all_posts = []
    
    for p in org_posts:
        if p["urn"] not in seen_urns:
            seen_urns.add(p["urn"])
            all_posts.append(p)
    
    for p in local_posts:
        if p["urn"] not in seen_urns:
            seen_urns.add(p["urn"])
            all_posts.append(p)
    
    if not all_posts:
        print("📭 No published posts found.")
        return

    print(f"\n📊 Found {len(all_posts)} total posts. Fetching analytics...")
    
    # ── Step 4: Fetch engagement data ──
    urns = [p["urn"] for p in all_posts]
    impressions_map = fetch_impressions_batch(urns, org_id, headers) if org_id else {}
    
    analytics_data = []
    
    print(f"\n{'Post':<50} {'Likes':<8} {'Comm.':<8} {'Views':<8}")
    print("─" * 80)

    for post in all_posts:
        urn = post["urn"]
        likes, comments = fetch_social_actions(urn, headers)
        stats = impressions_map.get(urn, {})
        views = stats.get("impressions", 0) if isinstance(stats, dict) else 0
        clicks = stats.get("clicks", 0) if isinstance(stats, dict) else 0
        
        # Generate a safe filename for storage
        safe_name = post.get("name", "untitled")[:60]
        filename = post.get("file", safe_name).split("/")[-1] if "file" in post else f"linkedin_{urn.split(':')[-1][:12]}.md"
        
        row = {
            "filename": filename,
            "name": safe_name,
            "urn": urn,
            "likes": likes,
            "comments": comments,
            "impressions": views,
            "clicks": clicks,
            "date": post.get("date", ""),
            "content_preview": post.get("content_preview", ""),
            "fetched_at": datetime.now().isoformat()
        }
        analytics_data.append(row)
        
        display_name = safe_name[:48]
        print(f"{display_name:<50} {likes:<8} {comments:<8} {views:<8}")
        time.sleep(0.2)

    save_analytics(analytics_data)
    print(f"\n✅ Data saved! {len(analytics_data)} posts tracked.")

if __name__ == "__main__":
    main()
