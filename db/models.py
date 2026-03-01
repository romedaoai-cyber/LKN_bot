"""
Data models (plain dicts with helper constructors — no external dependency needed).
"""
import uuid
from datetime import datetime


def _now():
    return datetime.utcnow().isoformat()


def new_inspiration(type_: str, title: str, content: str, source: str = "manual",
                    tags: list = None, ai_summary: str = "") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "type": type_,          # trend | personal | qa | idea
        "title": title,
        "content": content,
        "source": source,       # url | manual | linkedin_comment
        "tags": tags or [],
        "ai_summary": ai_summary,
        "created_at": _now(),
        "used_in_posts": [],
    }


def new_post(title: str, content: str = "", type_: str = "opinion",
             inspiration_ids: list = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "content": content,
        "type": type_,          # opinion | tutorial | trend
        "status": "draft",      # draft | review | approved | scheduled | published
        "inspiration_ids": inspiration_ids or [],
        "skills_used": [],
        "pre_review": {
            "trend_check": None,
            "brand_aligned": None,
            "content_type": type_,
            "risk_level": None,
            "risk_note": "",
        },
        "scheduled_at": None,
        "published_at": None,
        "linkedin_urn": None,
        "image_path": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


def new_qa_record(question: str, answer: str = "", source: str = "manual",
                  post_id: str = None, tags: list = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "question": question,
        "answer": answer,
        "source": source,       # linkedin_comment | manual
        "post_id": post_id,
        "tags": tags or [],
        "converted": False,
        "inspiration_id": None,
        "created_at": _now(),
    }


def new_analytics(post_id: str, linkedin_urn: str, type_: str = "opinion") -> dict:
    return {
        "post_id": post_id,
        "linkedin_urn": linkedin_urn,
        "type": type_,
        "impressions": 0,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "engagement_rate": 0.0,
        "fetched_at": _now(),
    }


def default_brand_profile() -> dict:
    return {
        "name": "",
        "tone": "",
        "target_audience": "",
        "topics": [],
        "style_guide": "",
        "color_palette": [],
        "updated_at": _now(),
    }
