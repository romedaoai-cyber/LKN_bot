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
    """Headers for versioned /rest/ endpoints."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202601",
    }


def get_headers_v2(access_token):
    """Headers for legacy /v2/ endpoints (no version header)."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }


def fetch_org_posts(org_urn, headers):
    """Fetch ALL posts from the organization via LinkedIn API."""
    posts = []
    
    if not org_urn.startswith("urn:li:organization:"):
        org_urn = f"urn:li:organization:{org_urn}"
    
    params = {
        "author": org_urn,
        "q": "author",
        "count": 50,
    }
    
    try:
        resp = requests.get(ORG_POSTS_URL, headers=headers, params=params)
        print(f"📡 Fetching org posts... Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            elements = data.get("elements", [])
            for el in elements:
                post_id = el.get("id", "")
                content = el.get("commentary", "")
                created_at = el.get("createdAt", 0)
                title = content[:80].replace("\n", " ").strip() if content else "Untitled"
                if len(content) > 80: title += "..."
                created_date = datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d") if created_at else ""
                
                posts.append({
                    "urn": post_id,
                    "name": title,
                    "date": created_date,
                    "content_preview": content[:200] if content else "",
                })
            print(f"✅ Found {len(posts)} posts from organization")
        elif resp.status_code in (403, 426):
            print(f"⚠️ Primary API failed ({resp.status_code}). Trying fallbacks...")
            posts = fetch_org_posts_ugc(org_urn, headers)
            if not posts: posts = fetch_org_posts_shares(org_urn, headers)
        else:
            print(f"⚠️ Failed: {resp.status_code} {resp.text[:200]}")
            posts = fetch_org_posts_ugc(org_urn, headers)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return posts


def fetch_org_posts_ugc(org_urn, headers):
    """Fallback 1: UGC Posts API."""
    posts = []
    # Use headers without version for v2
    v2_headers = {k:v for k,v in headers.items() if k != "LinkedIn-Version"}
    url = f"https://api.linkedin.com/v2/ugcPosts?q=authors&authors=List({quote(org_urn)})&count=50"
    
    try:
        resp = requests.get(url, headers=v2_headers)
        print(f"📡 UGC fallback... Status: {resp.status_code}")
        if resp.status_code == 200:
            elements = resp.json().get("elements", [])
            for el in elements:
                post_id = el.get("id", "")
                sc = el.get("specificContent", {}).get("com.linkedin.ugc.ShareContent", {})
                content = sc.get("shareCommentary", {}).get("text", "")
                created_at = el.get("created", {}).get("time", 0)
                title = content[:80].replace("\n", " ").strip() if content else "Untitled"
                posts.append({
                    "urn": post_id,
                    "name": title,
                    "date": datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d") if created_at else "",
                    "content_preview": content[:200] if content else "",
                })
            print(f"✅ Found {len(posts)} posts via UGC")
    except Exception as e:
        print(f"❌ UGC Error: {e}")
    return posts


def fetch_org_posts_shares(org_urn, headers):
    """Fallback 2: Legacy Shares API."""
    posts = []
    v2_headers = {k:v for k,v in headers.items() if k != "LinkedIn-Version"}
    url = f"https://api.linkedin.com/v2/shares?q=owners&owners={quote(org_urn)}&count=50"
    
    try:
        resp = requests.get(url, headers=v2_headers)
        print(f"📡 Shares fallback... Status: {resp.status_code}")
        if resp.status_code == 200:
            elements = resp.json().get("elements", [])
            for el in elements:
                post_id = el.get("id", "")
                content = el.get("text", {}).get("text", "")
                created_at = el.get("created", {}).get("time", 0)
                posts.append({
                    "urn": post_id,
                    "name": content[:80].strip() or "Untitled",
                    "date": datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d") if created_at else "",
                    "content_preview": content[:200],
                })
            print(f"✅ Found {len(posts)} posts via Shares")
    except Exception as e:
        print(f"❌ Shares Error: {e}")
    return posts


def fetch_social_actions(urn, headers):
    v2_headers = {k:v for k,v in headers.items() if k != "LinkedIn-Version"}
    url = SOCIAL_ACTIONS_URL.format(share_urn=quote(urn))
    try:
        resp = requests.get(url, headers=v2_headers)
        if resp.status_code == 200:
            data = resp.json()
            likes = data.get("likesSummary", {}).get("totalLikes", 0)
            comments = data.get("commentsSummary", {}).get("totalFirstLevelComments", 0)
            return likes, comments
    except: pass
    return 0, 0


def fetch_impressions_batch(urns, org_urn, headers):
    if not org_urn: return {}
    if not org_urn.startswith("urn:li:organization:"): org_urn = f"urn:li:organization:{org_urn}"
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
                for el in resp.json().get("elements", []):
                    stats = el.get("totalShareStatistics", {})
                    stats_map[el.get("share")] = {"impressions": stats.get("impressionCount", 0), "clicks": stats.get("clickCount", 0)}
        except: pass
    return stats_map


def save_analytics(data):
    with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    try:
        from firebase_manager import fm
        if fm.initialize():
            for row in data:
                filename = row.get("filename")
                if filename: fm.db.collection("posts").document(filename).set(row, merge=True)
            fm.log_event("analytics", f"Synced {len(data)} post analytics")
    except: pass


def main():
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN") or load_env().get("LINKEDIN_ACCESS_TOKEN")
    org_id = os.environ.get("LINKEDIN_ORG_ID") or load_env().get("LINKEDIN_ORG_ID")
    if not token: 
        print("❌ Token missing")
        return

    headers = get_headers(token)
    print("✨ API Version: 202601")
    print("🔍 Fetching posts...")
    
    org_posts = fetch_org_posts(org_id, headers) if org_id else []
    
    # Also check local posts with urns
    local_posts = []
    if POSTS_DIR.exists():
        for f in POSTS_DIR.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            if "<!-- shareUrn:" in content:
                for line in content.split("\n"):
                    if line.startswith("<!-- shareUrn:"):
                        urn = line.split(":", 1)[1].strip().strip("-->").strip()
                        local_posts.append({"urn": urn, "name": f.name, "file": str(f)})
                        break

    seen = set()
    all_p = []
    for p in org_posts + local_posts:
        if p["urn"] not in seen:
            seen.add(p["urn"])
            all_p.append(p)

    if not all_p:
        print("📭 No posts found.")
        return

    urns = [p["urn"] for p in all_p]
    impressions = fetch_impressions_batch(urns, org_id, headers) if org_id else {}
    
    analytics = []
    print(f"\n{'Post':<50} {'Views':<10}")
    for p in all_p:
        urn = p["urn"]
        likes, comms = fetch_social_actions(urn, headers)
        stats = impressions.get(urn, {})
        views = stats.get("impressions", 0)
        
        filename = p.get("file", "").split("/")[-1] or f"linked_{urn.split(':')[-1][:8]}.md"
        row = {
            "filename": filename,
            "name": p["name"][:60],
            "urn": urn,
            "likes": likes,
            "comments": comms,
            "impressions": views,
            "fetched_at": datetime.now().isoformat()
        }
        analytics.append(row)
        print(f"{p['name'][:48]:<50} {views:<10}")
        time.sleep(0.1)

    save_analytics(analytics)
    print(f"\n✅ Synced {len(analytics)} posts.")

if __name__ == "__main__":
    main()
