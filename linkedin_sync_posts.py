#!/usr/bin/env python3
"""
LinkedIn Post Sync Tool

Fetches all published posts from LinkedIn API and syncs URNs to local markdown files.
This enables analytics tracking for posts that were published without local URN records.
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

# Configuration
POSTS_DIR = Path("linkedin_posts")
DOTENV_PATH = Path(".env")
LINKEDIN_API_BASE = "https://api.linkedin.com"

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


def fetch_organization_posts(org_urn, access_token):
    """Fetch all posts for the organization from LinkedIn API."""
    headers = get_headers(access_token)
    
    # Ensure org_urn is properly formatted
    if not org_urn.startswith("urn:li:"):
        org_urn = f"urn:li:organization:{org_urn}"
    
    # API endpoint to list posts by author
    params = {
        "q": "author",
        "author": org_urn,
        "count": 50,  # Max posts to fetch
        "sortBy": "LAST_MODIFIED"
    }
    
    url = f"{LINKEDIN_API_BASE}/rest/posts"
    
    print(f"🔍 Fetching posts for {org_urn}...")
    resp = requests.get(url, headers=headers, params=params)
    
    if resp.status_code == 200:
        data = resp.json()
        posts = data.get("elements", [])
        print(f"✅ Found {len(posts)} posts on LinkedIn")
        return posts
    else:
        print(f"❌ Failed to fetch posts: {resp.status_code}")
        print(f"   Response: {resp.text}")
        return []


def match_and_update_local_files(linkedin_posts):
    """Match LinkedIn posts to local markdown files and update URNs."""
    if not POSTS_DIR.exists():
        print("⚠️  No linkedin_posts directory found.")
        return
    
    local_files = list(POSTS_DIR.glob("*.md"))
    print(f"\n📁 Found {len(local_files)} local markdown files")
    
    matched_count = 0
    
    for lp in linkedin_posts:
        post_id = lp.get("id")  # This is the URN
        commentary = lp.get("commentary", "")
        created_time = lp.get("createdAt", 0)
        
        # Convert timestamp to date
        if created_time:
            post_date = datetime.fromtimestamp(created_time / 1000).strftime("%Y-%m-%d")
        else:
            post_date = None
        
        print(f"\n🔗 LinkedIn Post: {post_id}")
        print(f"   Date: {post_date}")
        print(f"   Preview: {commentary[:60]}...")
        
        # Try to match by date and content similarity
        best_match = None
        best_score = 0
        
        for local_file in local_files:
            content = local_file.read_text(encoding="utf-8")
            
            # Extract date from metadata
            local_date = None
            for line in content.split("\n"):
                if line.startswith("<!-- date:"):
                    local_date = line.split(":", 1)[1].strip().strip("-->").strip()
                    break
            
            # Check if already has URN
            has_urn = False
            for line in content.split("\n"):
                if line.startswith("<!-- shareUrn:"):
                    has_urn = True
                    break
            
            if has_urn:
                continue  # Skip files that already have URN
            
            # Match by date
            if post_date and local_date and post_date == local_date:
                # Additional check: content similarity
                if commentary and commentary[:100] in content:
                    best_match = local_file
                    best_score = 100
                    break
        
        if best_match:
            print(f"   ✅ Matched to: {best_match.name}")
            
            # Update the file with URN
            content = best_match.read_text(encoding="utf-8")
            lines = content.split("\n")
            new_lines = []
            inserted = False
            
            for line in lines:
                if line.strip() == "---CONTENT---" and not inserted:
                    new_lines.append(f"<!-- shareUrn: {post_id} -->")
                    new_lines.append(line)
                    inserted = True
                else:
                    new_lines.append(line)
            
            if not inserted:
                # Fallback: insert at top
                new_lines.insert(0, f"<!-- shareUrn: {post_id} -->")
            
            best_match.write_text("\n".join(new_lines), encoding="utf-8")
            print(f"   💾 URN saved to {best_match.name}")
            matched_count += 1
        else:
            print(f"   ⚠️  No matching local file found")
    
    print(f"\n✅ Synced {matched_count} posts")
    return matched_count


def main():
    print("🔄 LinkedIn Post Sync Tool\n")
    
    env = load_env()
    access_token = env.get("LINKEDIN_ACCESS_TOKEN")
    org_id = env.get("LINKEDIN_ORG_ID")
    
    if not access_token:
        print("❌ No access token found. Run 'python3 linkedin_publisher.py auth' first.")
        return
    
    if not org_id:
        print("❌ No organization ID found in .env")
        return
    
    # Fetch posts from LinkedIn
    linkedin_posts = fetch_organization_posts(org_id, access_token)
    
    if not linkedin_posts:
        print("\n⚠️  No posts found on LinkedIn. Have you published any posts yet?")
        return
    
    # Match and update local files
    matched = match_and_update_local_files(linkedin_posts)
    
    if matched > 0:
        print(f"\n✅ Sync complete! You can now run:")
        print(f"   python3 linkedin_analytics.py")
        print(f"   to fetch analytics data.")


if __name__ == "__main__":
    main()
