#!/usr/bin/env python3
"""
DaoAI LinkedIn Auto-Publisher
Publishes approved posts to the company LinkedIn page via LinkedIn Marketing API.

Usage:
    python linkedin_publisher.py publish <post_file.md>   # Publish a single post
    python linkedin_publisher.py preview <post_file.md>   # Preview without publishing
    python linkedin_publisher.py schedule                  # List all pending posts
    python linkedin_publisher.py auth                      # Start OAuth flow to get token

Requires:
    pip install requests python-dotenv
"""

import os
import sys
import json
import time
import hashlib
import requests
import webbrowser
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse

# Optional Firebase support
try:
    from firebase_manager import fm as _fm
except Exception:
    _fm = None

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
DOTENV_PATH = Path(__file__).parent / ".env"
POSTS_DIR = Path(__file__).parent / "linkedin_posts"
PUBLISHED_LOG = Path(__file__).parent / "linkedin_published.json"
NON_POST_FILES = {"plan.md"}  # Strategy/planning docs, not publishable posts

LINKEDIN_API_BASE = "https://api.linkedin.com"
LINKEDIN_VERSION = "202601"

# LinkedIn OAuth endpoints
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
REDIRECT_URI = "http://localhost:8585/callback"

# Required scopes for company page posting
SCOPES = "w_organization_social r_organization_social rw_organization_admin"


def load_env():
    """Load environment variables from .env file and merge with actual os.environ."""
    env = dict(os.environ)  # Start with actual system/subprocess env vars
    if DOTENV_PATH.exists():
        with open(DOTENV_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    # Don't overwrite existing higher-priority OS env vars 
                    if key.strip() not in env:
                        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def save_env_var(key, value):
    """Save or update a variable in .env file."""
    lines = []
    found = False
    if DOTENV_PATH.exists():
        with open(DOTENV_PATH, "r") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f'{key}="{value}"\n')
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f'{key}="{value}"\n')

    with open(DOTENV_PATH, "w") as f:
        f.writelines(new_lines)


# ──────────────────────────────────────────────
# OAuth 2.0 Flow
# ──────────────────────────────────────────────
class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback."""
    auth_code = None

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        if "code" in query:
            OAuthCallbackHandler.auth_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family: sans-serif; text-align: center; padding: 60px;">
                <h1>&#10004; Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                </body></html>
            """)
        else:
            self.send_response(400)
            self.end_headers()
            error = query.get("error", ["unknown"])[0]
            self.wfile.write(f"Error: {error}".encode())

    def log_message(self, format, *args):
        pass  # Suppress HTTP log noise


def start_oauth_flow():
    """Start the LinkedIn OAuth 2.0 flow to obtain access token."""
    env = load_env()
    client_id = env.get("LINKEDIN_CLIENT_ID")
    client_secret = env.get("LINKEDIN_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("\n❌ Missing LinkedIn credentials.")
        print("Please add to .env file:")
        print('  LINKEDIN_CLIENT_ID="your_client_id"')
        print('  LINKEDIN_CLIENT_SECRET="your_client_secret"')
        print("\nGet these from: https://www.linkedin.com/developers/apps")
        return

    # Build authorization URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": hashlib.sha256(os.urandom(32)).hexdigest()[:16],
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"

    print("\n🔐 Opening browser for LinkedIn authorization...")
    print(f"   If browser doesn't open, visit:\n   {auth_url}\n")
    webbrowser.open(auth_url)

    # Start local server to catch callback
    server = HTTPServer(("localhost", 8585), OAuthCallbackHandler)
    server.timeout = 120
    print("⏳ Waiting for authorization (2 min timeout)...")

    while OAuthCallbackHandler.auth_code is None:
        server.handle_request()

    auth_code = OAuthCallbackHandler.auth_code
    server.server_close()

    # Exchange code for access token
    print("🔄 Exchanging code for access token...")
    token_response = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret,
    })

    if token_response.status_code != 200:
        print(f"❌ Token exchange failed: {token_response.text}")
        return

    token_data = token_response.json()
    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", 5184000)  # Default 60 days

    # Save token
    save_env_var("LINKEDIN_ACCESS_TOKEN", access_token)
    expiry = datetime.now().timestamp() + expires_in
    save_env_var("LINKEDIN_TOKEN_EXPIRY", str(int(expiry)))

    print(f"\n✅ Access token saved! Expires in {expires_in // 86400} days.")

    # Get organization info
    get_organization_id(access_token)


def get_organization_id(access_token):
    """Fetch and save the organization (company page) ID."""
    headers = get_headers(access_token)

    # Get admin organizations
    resp = requests.get(
        f"{LINKEDIN_API_BASE}/rest/organizationAcls?q=roleAssignee",
        headers=headers,
    )

    if resp.status_code == 200:
        data = resp.json()
        elements = data.get("elements", [])
        if elements:
            # Look for APPROVED roles
            for el in elements:
                status = el.get("state", "")
                role = el.get("role", "")
                if status == "APPROVED" and role in ("ADMINISTRATOR", "DIRECT_SPONSORED_CONTENT_POSTER"):
                    org_urn = el.get("organization")
                    save_env_var("LINKEDIN_ORG_ID", org_urn) # Save full URN is safer for new code
                    print(f"✅ Organization ID saved: {org_urn}")
                    return org_urn
    
    print("⚠️  Could not auto-detect organization. Please add LINKEDIN_ORG_ID (e.g. 123456) to .env manually.")
    return None


# ──────────────────────────────────────────────
# API Helpers
# ──────────────────────────────────────────────
def get_headers(access_token):
    """Build LinkedIn API request headers."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }


def check_token():
    """Check if access token is valid and not expired."""
    env = load_env()
    token = env.get("LINKEDIN_ACCESS_TOKEN")
    expiry = env.get("LINKEDIN_TOKEN_EXPIRY")

    if not token:
        print("❌ No access token found. Run: python linkedin_publisher.py auth")
        return None

    if expiry and float(expiry) < datetime.now().timestamp():
        print("❌ Access token expired. Run: python linkedin_publisher.py auth")
        return None

    return token


# ──────────────────────────────────────────────
# Image Upload
# ──────────────────────────────────────────────
def upload_image(access_token, org_id, image_path):
    """Upload an image to LinkedIn and return the asset URN."""
    headers = get_headers(access_token)

    # Handle if org_id is already a URN (e.g. urn:li:person:...)
    if org_id.startswith("urn:"):
        owner_urn = org_id
    else:
        owner_urn = f"urn:li:organization:{org_id}"

    # Step 1: Register upload
    register_body = {
        "initializeUploadRequest": {
            "owner": owner_urn,
        }
    }

    resp = requests.post(
        f"{LINKEDIN_API_BASE}/rest/images?action=initializeUpload",
        headers=headers,
        json=register_body,
    )

    if resp.status_code not in (200, 201):
        print(f"❌ Image register failed: {resp.status_code} {resp.text}")
        return None

    upload_data = resp.json().get("value", {})
    upload_url = upload_data.get("uploadUrl")
    image_urn = upload_data.get("image")

    if not upload_url or not image_urn:
        print(f"❌ Missing upload URL or image URN in response")
        return None

    # Step 2: Upload binary
    with open(image_path, "rb") as f:
        image_data = f.read()

    upload_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/octet-stream",
    }

    resp = requests.put(upload_url, headers=upload_headers, data=image_data)

    if resp.status_code not in (200, 201):
        print(f"❌ Image upload failed: {resp.status_code} {resp.text}")
        return None

    print(f"   ✅ Image uploaded: {Path(image_path).name}")
    return image_urn


# ──────────────────────────────────────────────
# Post Publishing
# ──────────────────────────────────────────────
def parse_post_file(filepath):
    """Parse a post markdown file into structured data."""
    path = Path(filepath)
    if not path.exists():
        print(f"❌ File not found: {filepath}")
        return None

    content = path.read_text(encoding="utf-8")
    post = {
        "file": str(path),
        "text": "",
        "image": None,
        "date": None,
        "time": None,
        "status": "pending",
    }

    lines = content.split("\n")
    in_content = False
    text_lines = []

    for line in lines:
        # Parse metadata
        if line.startswith("<!-- date:"):
            post["date"] = line.replace("<!-- date:", "").replace("-->", "").strip()
        elif line.startswith("<!-- time:"):
            post["time"] = line.replace("<!-- time:", "").replace("-->", "").strip()
        elif line.startswith("<!-- image:"):
            post["image"] = line.replace("<!-- image:", "").replace("-->", "").strip()
        elif line.startswith("<!-- status:"):
            post["status"] = line.replace("<!-- status:", "").replace("-->", "").strip()
        # Parse content block
        elif line.strip() == "---CONTENT---":
            in_content = True
        elif line.strip() == "---END---":
            in_content = False
        elif in_content:
            text_lines.append(line)

    post["text"] = "\n".join(text_lines).strip()
    return post


def publish_post(post, access_token, org_id, dry_run=False):
    """Publish a post to LinkedIn company page or personal profile."""
    if not post["text"]:
        print("❌ Post has no content text.")
        return False

    # Handle if org_id is already a URN (e.g. urn:li:person:...)
    if org_id.startswith("urn:"):
        author_urn = org_id
    else:
        author_urn = f"urn:li:organization:{org_id}"

    # Build post body
    post_body = {
        "author": author_urn,
        "commentary": post["text"],
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
    }

    # Handle image
    if post["image"] and os.path.exists(post["image"]):
        if dry_run:
            print(f"   📷 Would upload image: {post['image']}")
        else:
            image_urn = upload_image(access_token, org_id, post["image"])
            if image_urn:
                post_body["content"] = {
                    "media": {
                        "id": image_urn,
                    }
                }

    if dry_run:
        print("\n📋 Preview Mode — Would publish:")
        print(f"   Author: urn:li:organization:{org_id}")
        print(f"   Image: {post.get('image', 'None')}")
        print(f"\n   --- Post Text ---")
        for line in post["text"].split("\n"):
            print(f"   {line}")
        print(f"   --- End ---\n")
        return True

    # Publish
    headers = get_headers(access_token)
    resp = requests.post(
        f"{LINKEDIN_API_BASE}/rest/posts",
        headers=headers,
        json=post_body,
    )

    if resp.status_code in (200, 201):
        post_id = resp.headers.get("x-restli-id", "unknown")
        # If headers missing, check body
        if post_id == "unknown":
            post_id = resp.json().get("id", "unknown")

        print(f"   ✅ Published! Post ID: {post_id}")
        log_published(post, post_id)
        return post_id
    else:
        print(f"   ❌ Publish failed: {resp.status_code}")
        print(f"   Response: {resp.text}")
        return False


def save_post_urn(filepath, urn):
    """Save the published URN to the post file metadata."""
    path = Path(filepath)
    if not path.exists():
        return

    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")
    new_lines = []
    inserted = False

    for line in lines:
        if line.startswith("<!-- shareUrn:"):
            new_lines.append(f"<!-- shareUrn: {urn} -->")
            inserted = True
        elif line.strip() == "---CONTENT---" and not inserted:
            new_lines.append(f"<!-- shareUrn: {urn} -->")
            new_lines.append(line)
            inserted = True
        else:
            new_lines.append(line)

    if not inserted:
        # Fallback
        new_lines.insert(0, f"<!-- shareUrn: {urn} -->")

    path.write_text("\n".join(new_lines), encoding="utf-8")
    print(f"   💾 Post URN saved to file.")


def log_published(post, post_id):
    """Log published posts for tracking."""
    log = []
    if PUBLISHED_LOG.exists():
        with open(PUBLISHED_LOG, "r") as f:
            log = json.load(f)

    log.append({
        "file": post["file"],
        "post_id": post_id,
        "published_at": datetime.now().isoformat(),
        "date": post.get("date"),
    })

    with open(PUBLISHED_LOG, "w") as f:
        json.dump(log, f, indent=2)


# ──────────────────────────────────────────────
# Post File Management
# ──────────────────────────────────────────────
def list_pending_posts():
    """List all post files and their status."""
    if not POSTS_DIR.exists():
        print(f"📁 No posts directory found. Creating {POSTS_DIR}")
        POSTS_DIR.mkdir(parents=True, exist_ok=True)
        return

    post_files = sorted(POSTS_DIR.glob("*.md"))
    if not post_files:
        print("📭 No post files found.")
        return

    published = set()
    if PUBLISHED_LOG.exists():
        with open(PUBLISHED_LOG, "r") as f:
            for entry in json.load(f):
                published.add(entry["file"])

    print(f"\n📋 LinkedIn Posts ({len(post_files)} total):\n")
    print(f"{'Status':<12} {'Date':<12} {'File':<40}")
    print("─" * 64)

    for pf in post_files:
        post = parse_post_file(pf)
        if post:
            status = "✅ Published" if str(pf) in published else "⏳ Pending"
            date = post.get("date", "—")
            print(f"{status:<12} {date:<12} {pf.name:<40}")

    print()


# ──────────────────────────────────────────────
# Main CLI
# ──────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1].lower()

    if command == "auth":
        start_oauth_flow()

    elif command == "preview":
        if len(sys.argv) < 3:
            print("Usage: python linkedin_publisher.py preview <post_file.md>")
            return
        post = parse_post_file(sys.argv[2])
        if post:
            env = load_env()
            org_id = env.get("LINKEDIN_ORG_ID", "UNKNOWN")
            publish_post(post, None, org_id, dry_run=True)

    elif command == "publish":
        if len(sys.argv) < 3:
            print("Usage: python linkedin_publisher.py publish <post_file.md>")
            return
        token = check_token()
        if not token:
            return
        env = load_env()
        org_id = env.get("LINKEDIN_ORG_ID")
        if not org_id:
            print("❌ No LINKEDIN_ORG_ID in .env. Run 'auth' first or add manually.")
            return
        post = parse_post_file(sys.argv[2])
        if post:
            print(f"\n🚀 Publishing: {sys.argv[2]}")
            post_urn = publish_post(post, token, org_id)
            if post_urn:
                save_post_urn(post["file"], post_urn)

    elif command == "schedule":
        list_pending_posts()

    elif command == "publish-all-pending":
        token = check_token()
        if not token:
            return
        env = load_env()
        org_id = env.get("LINKEDIN_ORG_ID")
        if not org_id:
            print("❌ No LINKEDIN_ORG_ID.")
            return

        published = set()
        published_filenames = set()
        if PUBLISHED_LOG.exists():
            with open(PUBLISHED_LOG, "r") as f:
                for entry in json.load(f):
                    published.add(entry["file"])
                    published_filenames.add(Path(entry["file"]).name)

        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M")

        print(f"\n🔍 Checking for approved posts due on or before {now_str}...\n")

        # ── Build candidate list: local files + Firebase cloud posts ──
        candidates = []

        # 1. Local .md files
        for pf in sorted(POSTS_DIR.glob("*.md")):
            if pf.name in NON_POST_FILES:
                continue
            if str(pf) in published:
                continue
            post = parse_post_file(pf)
            if post:
                post["_source"] = "local"
                candidates.append(post)

        # 2. Firebase cloud posts (only those NOT already covered by local files)
        local_filenames = {Path(c["file"]).name for c in candidates}
        if _fm and _fm.is_active():
            print("☁️  Also checking Firebase for approved posts...")
            cloud_posts = _fm.get_all_posts()
            for cp in cloud_posts:
                fname = cp.get("filename", "")
                if not fname:
                    continue
                if fname in published_filenames:
                    continue
                if fname in local_filenames:
                    continue  # already handled by local file
                # Cloud-only post: use Firebase data directly
                post = {
                    "file": str(POSTS_DIR / fname),
                    "text": cp.get("text", ""),
                    "image": cp.get("image"),
                    "date": cp.get("date"),
                    "time": cp.get("time"),
                    "status": cp.get("status", "pending"),
                    "_source": "firebase",
                    "_filename": fname,
                }
                candidates.append(post)

        processed_count = 0
        for post in candidates:
            post_date = post.get("date")
            post_time = post.get("time") or "00:00"
            post_status = post.get("status", "pending").lower()

            if not post_date:
                continue

            # Combine date + time for comparison
            try:
                scheduled_dt = datetime.strptime(f"{post_date} {post_time}", "%Y-%m-%d %H:%M")
            except ValueError:
                scheduled_dt = datetime.strptime(post_date, "%Y-%m-%d")

            fname_display = post.get("_filename") or Path(post["file"]).name

            # Logic: Must be APPROVED and scheduled datetime must be NOW or EARLIER
            if post_status == "approved" and scheduled_dt <= now:
                src = post.get("_source", "local")
                print(f"\n🚀 Publishing [{src}] post due {post_date} {post_time}: {fname_display}")
                post_urn = publish_post(post, token, org_id)
                if post_urn:
                    save_post_urn(post["file"], post_urn)
                    # If from Firebase, mark as published there too
                    if src == "firebase" and _fm and _fm.is_active():
                        _fm.sync_post({"filename": fname_display, "status": "published"})
                    processed_count += 1
                    time.sleep(5)  # Rate limit courtesy

            elif post_status != "approved" and scheduled_dt <= now:
                print(f"⚠️  Skipping due post (status={post_status}): {fname_display}")

        if processed_count == 0:
            print("\n✨ No approved posts due for publishing.")

    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
