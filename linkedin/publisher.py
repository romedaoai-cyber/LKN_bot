"""
LinkedIn publisher — clean rewrite focused on the new post model.
Reuses the core API logic from the original linkedin_publisher.py.
"""
from __future__ import annotations
import os
import json
import hashlib
import webbrowser
import requests
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse

import config

REDIRECT_URI = "http://localhost:8585/callback"
SCOPES = "w_organization_social r_organization_social rw_organization_admin"
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"


# ── Headers ──

def get_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": config.LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }


def check_token() -> str | None:
    token = config.LINKEDIN_ACCESS_TOKEN
    expiry = config.LINKEDIN_TOKEN_EXPIRY
    if not token:
        return None
    if expiry and float(expiry) < datetime.now().timestamp():
        return None
    return token


# ── OAuth ──

class _OAuthHandler(BaseHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        if "code" in query:
            _OAuthHandler.auth_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization successful! Close this tab.</h1>")
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, *args):
        pass


def start_oauth_flow() -> bool:
    params = {
        "response_type": "code",
        "client_id": config.LINKEDIN_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": hashlib.sha256(os.urandom(32)).hexdigest()[:16],
    }
    webbrowser.open(f"{AUTH_URL}?{urlencode(params)}")

    server = HTTPServer(("localhost", 8585), _OAuthHandler)
    server.timeout = 120
    while _OAuthHandler.auth_code is None:
        server.handle_request()
    server.server_close()

    code = _OAuthHandler.auth_code
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": config.LINKEDIN_CLIENT_ID,
        "client_secret": config.LINKEDIN_CLIENT_SECRET,
    })
    if resp.status_code != 200:
        return False

    data = resp.json()
    token = data["access_token"]
    expiry = int(datetime.now().timestamp()) + data.get("expires_in", 5184000)

    _save_env("LINKEDIN_ACCESS_TOKEN", token)
    _save_env("LINKEDIN_TOKEN_EXPIRY", str(expiry))
    return True


# ── Image Upload ──

def upload_image(token: str, org_urn: str, image_path: str) -> str | None:
    headers = get_headers(token)
    resp = requests.post(
        f"{config.LINKEDIN_API_BASE}/rest/images?action=initializeUpload",
        headers=headers,
        json={"initializeUploadRequest": {"owner": org_urn}},
    )
    if resp.status_code not in (200, 201):
        return None

    val = resp.json().get("value", {})
    upload_url = val.get("uploadUrl")
    image_urn = val.get("image")
    if not upload_url or not image_urn:
        return None

    with open(image_path, "rb") as f:
        data = f.read()
    up_resp = requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        data=data,
    )
    if up_resp.status_code not in (200, 201):
        return None
    return image_urn


# ── Publish ──

def publish_post(post: dict, dry_run: bool = False) -> str | None:
    """
    post dict keys: content, image_path (optional)
    Returns LinkedIn URN or None.
    """
    token = check_token()
    if not token and not dry_run:
        return None

    org_id = config.LINKEDIN_ORG_ID or ""
    author_urn = org_id if org_id.startswith("urn:") else f"urn:li:organization:{org_id}"

    body = {
        "author": author_urn,
        "commentary": post["content"],
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
    }

    image_path = post.get("image_path")
    if image_path and os.path.exists(image_path) and not dry_run:
        image_urn = upload_image(token, author_urn, image_path)
        if image_urn:
            body["content"] = {"media": {"id": image_urn}}

    if dry_run:
        return "dry-run-urn"

    headers = get_headers(token)
    resp = requests.post(
        f"{config.LINKEDIN_API_BASE}/rest/posts",
        headers=headers,
        json=body,
    )
    if resp.status_code in (200, 201):
        post_id = resp.headers.get("x-restli-id") or resp.json().get("id", "")
        return post_id
    return None


# ── Helpers ──

def _save_env(key: str, value: str):
    dotenv = Path(config.DOTENV_PATH if hasattr(config, "DOTENV_PATH") else ".env")
    lines = dotenv.read_text().splitlines() if dotenv.exists() else []
    new_lines = []
    found = False
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f'{key}="{value}"')
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f'{key}="{value}"')
    dotenv.write_text("\n".join(new_lines) + "\n")
