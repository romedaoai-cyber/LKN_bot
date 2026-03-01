"""
Fetch analytics for published posts from LinkedIn API.
Full port of original linkedin_analytics.py with:
- 3 fallback endpoints (REST posts → UGC → Shares)
- Social actions for likes/comments (v2 endpoint, no version header)
- Batch impressions (20 URNs per request)
- Local .md file URN scanning
"""
from __future__ import annotations
import time
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import config
from linkedin.publisher import get_headers, check_token


def _get_headers_v2(token: str) -> dict:
    """Legacy v2 endpoints don't accept LinkedIn-Version header."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }


# ── Fetch post list (3 fallbacks) ──

def fetch_post_list() -> list[dict]:
    """Fetch all posts from LinkedIn org page with 3 fallback endpoints."""
    token = check_token()
    if not token:
        return []

    org_id = config.LINKEDIN_ORG_ID or ""
    org_urn = org_id if org_id.startswith("urn:") else f"urn:li:organization:{org_id}"
    headers = get_headers(token)

    # 1. REST /rest/posts (primary)
    resp = requests.get(
        f"{config.LINKEDIN_API_BASE}/rest/posts",
        headers=headers,
        params={"author": org_urn, "q": "author", "count": 50},
    )
    if resp.status_code == 200:
        return [_parse_rest_post(el) for el in resp.json().get("elements", [])]

    # 2. UGC Posts fallback
    v2_headers = _get_headers_v2(token)
    resp = requests.get(
        f"{config.LINKEDIN_API_BASE}/v2/ugcPosts",
        headers=v2_headers,
        params={"q": "authors", "authors": f"List({quote(org_urn)})", "count": 50},
    )
    if resp.status_code == 200:
        return [_parse_ugc_post(el) for el in resp.json().get("elements", [])]

    # 3. Legacy Shares fallback
    resp = requests.get(
        f"{config.LINKEDIN_API_BASE}/v2/shares",
        headers=v2_headers,
        params={"q": "owners", "owners": quote(org_urn), "count": 50},
    )
    if resp.status_code == 200:
        return [_parse_share_post(el) for el in resp.json().get("elements", [])]

    return []


def _parse_rest_post(el: dict) -> dict:
    content = el.get("commentary", "")
    created_at = el.get("createdAt", 0)
    title = content[:80].replace("\n", " ").strip()
    if len(content) > 80:
        title += "..."
    return {
        "urn": el.get("id", ""),
        "title": title or "Untitled",
        "date": datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d") if created_at else "",
        "content_preview": content[:200],
    }


def _parse_ugc_post(el: dict) -> dict:
    sc = el.get("specificContent", {}).get("com.linkedin.ugc.ShareContent", {})
    content = sc.get("shareCommentary", {}).get("text", "")
    created_at = el.get("created", {}).get("time", 0)
    return {
        "urn": el.get("id", ""),
        "title": content[:80].replace("\n", " ").strip() or "Untitled",
        "date": datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d") if created_at else "",
        "content_preview": content[:200],
    }


def _parse_share_post(el: dict) -> dict:
    content = el.get("text", {}).get("text", "")
    created_at = el.get("created", {}).get("time", 0)
    return {
        "urn": el.get("id", ""),
        "title": content[:80].strip() or "Untitled",
        "date": datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d") if created_at else "",
        "content_preview": content[:200],
    }


# ── Social actions (likes + comments via v2) ──

def fetch_social_actions(urn: str, token: str) -> tuple[int, int]:
    """Fetch likes and comments via socialActions endpoint."""
    try:
        resp = requests.get(
            f"{config.LINKEDIN_API_BASE}/v2/socialActions/{quote(urn)}",
            headers=_get_headers_v2(token),
        )
        if resp.status_code == 200:
            data = resp.json()
            likes = data.get("likesSummary", {}).get("totalLikes", 0)
            comments = data.get("commentsSummary", {}).get("totalFirstLevelComments", 0)
            return likes, comments
    except Exception:
        pass
    return 0, 0


# ── Batch impressions (20 URNs per request) ──

def fetch_impressions_batch(urns: list[str], token: str) -> dict:
    """Fetch impression counts for multiple URNs. Returns {urn: {impressions, clicks}}."""
    org_id = config.LINKEDIN_ORG_ID or ""
    org_urn = org_id if org_id.startswith("urn:") else f"urn:li:organization:{org_id}"
    headers = get_headers(token)
    stats_map = {}

    for i in range(0, len(urns), 20):
        chunk = urns[i:i + 20]
        shares_param = "List(" + ",".join([quote(u) for u in chunk]) + ")"
        query = f"q=organizationalEntity&organizationalEntity={quote(org_urn)}&shares={shares_param}"
        try:
            resp = requests.get(
                f"{config.LINKEDIN_API_BASE}/rest/organizationalEntityShareStatistics?{query}",
                headers=headers,
            )
            if resp.status_code == 200:
                for el in resp.json().get("elements", []):
                    s = el.get("totalShareStatistics", {})
                    stats_map[el.get("share")] = {
                        "impressions": s.get("impressionCount", 0),
                        "clicks": s.get("clickCount", 0),
                    }
        except Exception:
            pass
    return stats_map


# ── Single post metrics (used by p6 per-post sync) ──

def fetch_metrics(linkedin_urn: str) -> dict:
    """Fetch full metrics for a single post URN."""
    token = check_token()
    if not token:
        return {}

    likes, comments = fetch_social_actions(linkedin_urn, token)
    impressions_map = fetch_impressions_batch([linkedin_urn], token)
    stats = impressions_map.get(linkedin_urn, {})
    impressions = stats.get("impressions", 0)
    total = likes + comments
    engagement_rate = round(total / impressions * 100, 2) if impressions else 0.0

    return {
        "impressions": impressions,
        "likes": likes,
        "comments": comments,
        "shares": 0,
        "engagement_rate": engagement_rate,
        "fetched_at": datetime.utcnow().isoformat(),
    }


# ── Full sync: API posts + local markdown URNs ──

def sync_all_analytics(posts_dir: Path | None = None) -> list[dict]:
    """
    Fetch all posts (API + local .md files with shareUrn), return analytics rows.
    Used by p6 for a full refresh.
    """
    token = check_token()
    if not token:
        return []

    api_posts = fetch_post_list()
    seen_urns = {p["urn"] for p in api_posts}
    all_posts = list(api_posts)

    # Also scan legacy local .md files for shareUrn metadata
    if posts_dir and posts_dir.exists():
        for md_file in posts_dir.glob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            if "<!-- shareUrn:" not in content:
                continue
            for line in content.split("\n"):
                if line.startswith("<!-- shareUrn:"):
                    urn = line.split(":", 1)[1].strip().rstrip("-->").strip()
                    if urn and urn not in seen_urns:
                        seen_urns.add(urn)
                        all_posts.append({"urn": urn, "title": md_file.stem, "date": ""})
                    break

    if not all_posts:
        return []

    urns = [p["urn"] for p in all_posts]
    impressions_map = fetch_impressions_batch(urns, token)

    analytics = []
    for post in all_posts:
        urn = post["urn"]
        likes, comments = fetch_social_actions(urn, token)
        stats = impressions_map.get(urn, {})
        impressions = stats.get("impressions", 0)
        total = likes + comments
        engagement_rate = round(total / impressions * 100, 2) if impressions else 0.0

        analytics.append({
            "id": urn,
            "linkedin_urn": urn,
            "title": post.get("title", ""),
            "date": post.get("date", ""),
            "impressions": impressions,
            "likes": likes,
            "comments": comments,
            "shares": 0,
            "engagement_rate": engagement_rate,
            "fetched_at": datetime.utcnow().isoformat(),
        })
        time.sleep(0.1)

    return analytics
