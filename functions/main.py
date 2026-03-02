"""
Firebase Cloud Function: auto_publish
Triggered by Cloud Scheduler (Pub/Sub) every 5 minutes.
Checks Firestore for scheduled posts and publishes to LinkedIn.
"""
import os
import requests
from datetime import datetime, timezone
import pytz

import firebase_admin
from firebase_admin import credentials, firestore, storage
from firebase_functions import pubsub_fn

# ── Init Firebase ──
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

LINKEDIN_API_BASE = "https://api.linkedin.com"
LINKEDIN_VERSION = "202601"

# Publishing window: 6am – 3pm Eastern Time (North America)
PUBLISH_TZ = pytz.timezone("America/New_York")
PUBLISH_HOUR_START = 6   # 6:00 AM ET
PUBLISH_HOUR_END = 15    # 3:00 PM ET


def _within_publish_window() -> bool:
    """Return True only if current time is within allowed publish window."""
    now_et = datetime.now(PUBLISH_TZ)
    return PUBLISH_HOUR_START <= now_et.hour < PUBLISH_HOUR_END


def _get_secret(key: str) -> str:
    """Read from environment (set via Firebase Functions config)."""
    return os.environ.get(key, "")


def _upload_image_to_linkedin(token: str, org_urn: str, image_bytes: bytes, content_type: str = "image/jpeg") -> str | None:
    """Upload image to LinkedIn and return image URN."""
    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "Content-Type": "application/json",
    }
    # Step 1: Initialize upload
    init_resp = requests.post(
        f"{LINKEDIN_API_BASE}/rest/images?action=initializeUpload",
        headers=headers,
        json={"initializeUploadRequest": {"owner": org_urn}},
    )
    if init_resp.status_code != 200:
        print(f"Image init failed: {init_resp.status_code} {init_resp.text}")
        return None

    val = init_resp.json().get("value", {})
    upload_url = val.get("uploadUrl")
    image_urn = val.get("image")
    if not upload_url or not image_urn:
        return None

    # Step 2: Upload binary
    upload_resp = requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
        data=image_bytes,
    )
    if upload_resp.status_code not in (200, 201):
        print(f"Image upload failed: {upload_resp.status_code}")
        return None

    return image_urn


def _publish_to_linkedin(post: dict) -> str | None:
    """Publish a post to LinkedIn. Returns URN or None."""
    token = _get_secret("LINKEDIN_ACCESS_TOKEN")
    org_id = _get_secret("LINKEDIN_ORG_ID")
    if not token or not org_id:
        print("Missing LinkedIn credentials")
        return None

    author_urn = org_id if org_id.startswith("urn:") else f"urn:li:organization:{org_id}"

    body = {
        "author": author_urn,
        "commentary": post.get("content", ""),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    # Handle image from Firebase Storage
    image_url = post.get("image_url")
    if image_url:
        try:
            img_resp = requests.get(image_url, timeout=15)
            if img_resp.status_code == 200:
                content_type = img_resp.headers.get("Content-Type", "image/jpeg")
                image_urn = _upload_image_to_linkedin(token, author_urn, img_resp.content, content_type)
                if image_urn:
                    body["content"] = {"media": {"id": image_urn}}
        except Exception as e:
            print(f"Image fetch error: {e}")

    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    resp = requests.post(
        f"{LINKEDIN_API_BASE}/rest/posts",
        headers=headers,
        json=body,
    )

    if resp.status_code in (200, 201):
        return resp.headers.get("x-restli-id") or resp.json().get("id", "published")
    else:
        print(f"LinkedIn publish failed: {resp.status_code} {resp.text}")
        return None


@pubsub_fn.on_message_published(topic="auto-publish-trigger")
def auto_publish(event: pubsub_fn.CloudEvent) -> None:
    """
    Triggered by Cloud Scheduler every 5 minutes via Pub/Sub.
    Finds scheduled posts and publishes them to LinkedIn.
    """
    now_utc = datetime.now(timezone.utc)
    now = now_utc.isoformat()
    print(f"[auto_publish] Running at {now}")

    # Check publishing window: 6am–3pm Eastern Time
    if not _within_publish_window():
        now_et = datetime.now(PUBLISH_TZ)
        print(f"[auto_publish] Outside publish window ({now_et.strftime('%H:%M')} ET). Skipping.")
        return

    # Query posts: status == "scheduled" and scheduled_at <= now
    posts_ref = db.collection("scheduled_posts")
    candidates = posts_ref \
        .where("status", "==", "scheduled") \
        .where("scheduled_at", "<=", now) \
        .stream()

    published_count = 0
    for doc in candidates:
        post = doc.to_dict()
        post_id = doc.id
        title = post.get("title", post_id)
        print(f"[auto_publish] Publishing: {title}")

        urn = _publish_to_linkedin(post)
        if urn:
            # Update Firestore
            posts_ref.document(post_id).update({
                "status": "published",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "linkedin_urn": urn,
                "auto_published": True,
            })
            db.collection("logs").add({
                "timestamp": firestore.SERVER_TIMESTAMP,
                "category": "auto_publish",
                "message": f"✅ Published: {title}",
                "post_id": post_id,
                "linkedin_urn": urn,
            })
            published_count += 1
            print(f"[auto_publish] ✅ Success: {title} → {urn}")
        else:
            db.collection("logs").add({
                "timestamp": firestore.SERVER_TIMESTAMP,
                "category": "auto_publish_error",
                "message": f"❌ Failed: {title}",
                "post_id": post_id,
            })
            print(f"[auto_publish] ❌ Failed: {title}")

    print(f"[auto_publish] Done. Published {published_count} post(s).")
