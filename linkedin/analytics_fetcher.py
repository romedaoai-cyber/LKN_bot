"""
Fetch analytics for published posts from LinkedIn API.
Reuses the fallback endpoint logic from linkedin_analytics.py.
"""
from __future__ import annotations
import requests
from datetime import datetime

import config
from linkedin.publisher import get_headers, check_token


def fetch_post_list() -> list[dict]:
    """Return list of posts from LinkedIn org page."""
    token = check_token()
    if not token:
        return []

    org_id = config.LINKEDIN_ORG_ID or ""
    author_urn = org_id if org_id.startswith("urn:") else f"urn:li:organization:{org_id}"
    headers = get_headers(token)

    # Try REST posts endpoint first
    resp = requests.get(
        f"{config.LINKEDIN_API_BASE}/rest/posts",
        headers=headers,
        params={"author": author_urn, "q": "author", "count": 50},
    )
    if resp.status_code == 200:
        return resp.json().get("elements", [])

    # Fallback: UGC posts
    resp = requests.get(
        f"{config.LINKEDIN_API_BASE}/v2/ugcPosts",
        headers=headers,
        params={"q": "authors", "authors": f"List({author_urn})", "count": 50},
    )
    if resp.status_code == 200:
        return resp.json().get("elements", [])

    return []


def fetch_metrics(linkedin_urn: str) -> dict:
    """Fetch likes, comments, impressions for a single post URN."""
    token = check_token()
    if not token:
        return {}

    org_id = config.LINKEDIN_ORG_ID or ""
    org_urn = org_id if org_id.startswith("urn:") else f"urn:li:organization:{org_id}"
    headers = get_headers(token)

    resp = requests.get(
        f"{config.LINKEDIN_API_BASE}/rest/organizationalEntityShareStatistics",
        headers=headers,
        params={
            "q": "organizationalEntity",
            "organizationalEntity": org_urn,
            "shares": f"List({linkedin_urn})",
        },
    )
    if resp.status_code != 200:
        return {}

    elements = resp.json().get("elements", [])
    if not elements:
        return {}

    stats = elements[0].get("totalShareStatistics", {})
    impressions = stats.get("impressionCount", 0)
    likes = stats.get("likeCount", 0)
    comments = stats.get("commentCount", 0)
    shares = stats.get("shareCount", 0)
    total_interactions = likes + comments + shares
    engagement_rate = round(total_interactions / impressions * 100, 2) if impressions else 0.0

    return {
        "impressions": impressions,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "engagement_rate": engagement_rate,
        "fetched_at": datetime.utcnow().isoformat(),
    }
