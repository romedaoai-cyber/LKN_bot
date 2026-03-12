"""
Phase 6: 數據追蹤 & 內容回饋
- 各類型 ROI 比較
- AI 自動生成週報洞察
- 主題聚類提示（3+ 同主題 → 延伸方向）
"""
import streamlit as st
from datetime import datetime
import os

import config
from db.local_store import LocalStore
from linkedin.analytics_fetcher import sync_all_analytics

posts_store = LocalStore(config.POSTS_FILE)
analytics_store = LocalStore(config.ANALYTICS_FILE)

# Legacy paths
LEGACY_POSTS_DIR = config.BASE_DIR / "linkedin_posts"
# Try seed file first (committed to git, works on Streamlit Cloud)
# Fall back to local legacy file
_SEED_FILE = config.BASE_DIR / "data" / "seed_analytics.json"
_LEGACY_FILE = config.BASE_DIR / "linkedin_analytics_data.json"
LEGACY_ANALYTICS_FILE = _SEED_FILE if _SEED_FILE.exists() else _LEGACY_FILE


def _import_legacy_analytics():
    """
    One-time import: convert old linkedin_analytics_data.json → new analytics store.
    Old format: {name, urn, likes, comments, impressions, clicks, fetched_at}
    New format: {id, linkedin_urn, title, type, impressions, likes, comments, engagement_rate, ...}
    """
    import json
    if not LEGACY_ANALYTICS_FILE.exists():
        return 0

    try:
        old_data = json.loads(LEGACY_ANALYTICS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return 0

    existing_urns = {a.get("linkedin_urn") for a in analytics_store.all()}
    imported = 0

    for row in old_data:
        urn = row.get("urn", "")
        if not urn or urn in existing_urns:
            continue

        impressions = row.get("impressions", 0)
        likes = row.get("likes", 0)
        comments = row.get("comments", 0)
        total = likes + comments
        engagement_rate = round(total / impressions * 100, 2) if impressions else 0.0

        new_row = {
            "id": urn,
            "linkedin_urn": urn,
            "title": row.get("name", ""),
            "type": "unknown",
            "impressions": impressions,
            "likes": likes,
            "comments": comments,
            "shares": 0,
            "clicks": row.get("clicks", 0),
            "engagement_rate": engagement_rate,
            "fetched_at": row.get("fetched_at", datetime.utcnow().isoformat()),
            "post_id": urn,
        }
        analytics_store.save(new_row)
        existing_urns.add(urn)
        imported += 1

    return imported


def _fetch_all_analytics() -> int:
    """Sync analytics: API posts + legacy .md URNs, merge with local post types."""
    rows = sync_all_analytics(posts_dir=LEGACY_POSTS_DIR if LEGACY_POSTS_DIR.exists() else None)
    if not rows:
        return 0

    # Enrich with content type from local posts store (match by URN)
    posts_by_urn = {p["linkedin_urn"]: p for p in posts_store.all() if p.get("linkedin_urn")}

    for row in rows:
        urn = row.get("linkedin_urn", "")
        matched_post = posts_by_urn.get(urn)
        if matched_post:
            row["type"] = matched_post.get("type", "unknown")
            row["post_id"] = matched_post.get("id", urn)
        else:
            row.setdefault("type", "unknown")
            row.setdefault("post_id", urn)
        analytics_store.save(row)

    return len(rows)


def _generate_ai_insights(data: list) -> str:
    try:
        import google.generativeai as genai
        api_key = os.environ.get("GEMINI_API_KEY") or config.GEMINI_API_KEY
        if not api_key or not data:
            return ""
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        summary = "\n".join([
            f"- [{d.get('type')}] {d.get('title', '')}: 觀看 {d.get('impressions',0)}, 互動率 {d.get('engagement_rate',0)}%"
            for d in data
        ])
        resp = model.generate_content(
            f"""根據以下 LinkedIn 貼文數據，用繁體中文產出一份 200 字以內的數據洞察報告，
包含：表現最佳的內容類型、建議加強的方向、下一步內容策略建議：

{summary}"""
        )
        return resp.text.strip()
    except Exception:
        return ""


def _find_topic_clusters(posts: list) -> dict:
    """Simple keyword clustering — group posts with common title words."""
    from collections import Counter
    word_to_posts = {}
    stop_words = {"的", "是", "在", "與", "和", "如何", "了解", "為什麼", "這", "那"}

    for post in posts:
        words = [w for w in post.get("title", "").split() if len(w) > 1 and w not in stop_words]
        for word in words:
            word_to_posts.setdefault(word, []).append(post)

    clusters = {word: ps for word, ps in word_to_posts.items() if len(ps) >= 3}
    return clusters


def render():
    st.header("📊 Phase 6｜數據追蹤 & 回饋")

    # ── Auto-import legacy data on first load ──
    if not analytics_store.all():
        _import_legacy_analytics()

    # ── Fetch analytics ──
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 同步 LinkedIn 數據"):
            with st.spinner("抓取數據中..."):
                count = _fetch_all_analytics()
            st.success(f"已更新 {count} 篇貼文數據")
            st.rerun()

    # Read from store, fall back directly to seed file if store is still empty
    all_analytics = analytics_store.all()
    if not all_analytics and LEGACY_ANALYTICS_FILE.exists():
        import json as _json
        raw = _json.loads(LEGACY_ANALYTICS_FILE.read_text(encoding="utf-8"))
        all_analytics = [
            {
                "id": r.get("urn", ""),
                "linkedin_urn": r.get("urn", ""),
                "title": r.get("name", ""),
                "type": "unknown",
                "impressions": r.get("impressions", 0),
                "likes": r.get("likes", 0),
                "comments": r.get("comments", 0),
                "engagement_rate": round(
                    (r.get("likes", 0) + r.get("comments", 0)) / r.get("impressions", 1) * 100, 2
                ) if r.get("impressions") else 0.0,
            }
            for r in raw if r.get("urn")
        ]

    all_posts = posts_store.all()
    published_posts = [p for p in all_posts if p["status"] == "published"]

    if not all_analytics:
        st.info("尚無數據。請先發布貼文並點擊「同步 LinkedIn 數據」。")
        return

    # ── Overview metrics ──
    total_impressions = sum(a.get("impressions", 0) for a in all_analytics)
    total_likes = sum(a.get("likes", 0) for a in all_analytics)
    total_comments = sum(a.get("comments", 0) for a in all_analytics)
    avg_engagement = (
        sum(a.get("engagement_rate", 0) for a in all_analytics) / len(all_analytics)
        if all_analytics else 0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總觀看數", f"{total_impressions:,}")
    c2.metric("總按讚數", f"{total_likes:,}")
    c3.metric("總留言數", f"{total_comments:,}")
    c4.metric("平均互動率", f"{avg_engagement:.2f}%")

    st.divider()

    # ── By content type ──
    st.subheader("各類型表現比較")
    type_labels = {"opinion": "🔴 觀點文", "tutorial": "🟡 教學文", "trend": "🟢 趨勢文"}
    for type_key, type_label in type_labels.items():
        type_data = [a for a in all_analytics if a.get("type") == type_key]
        if not type_data:
            continue
        avg_imp = sum(a.get("impressions", 0) for a in type_data) / len(type_data)
        avg_eng = sum(a.get("engagement_rate", 0) for a in type_data) / len(type_data)
        count = len(type_data)

        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            col1.metric(f"{type_label}", f"{count} 篇")
            col2.metric("平均觀看", f"{avg_imp:,.0f}")
            col3.metric("平均互動率", f"{avg_eng:.2f}%")

    st.divider()

    # ── Top posts ──
    st.subheader("Top 貼文")
    sorted_by_imp = sorted(all_analytics, key=lambda x: x.get("impressions", 0), reverse=True)[:5]
    for i, a in enumerate(sorted_by_imp, 1):
        type_e = {"opinion": "🔴", "tutorial": "🟡", "trend": "🟢"}.get(a.get("type", ""), "📄")
        display_title = a.get("title") or a.get("name") or a.get("linkedin_urn", "")[:30]
        st.markdown(
            f"{i}. {type_e} **{display_title[:60]}** — "
            f"觀看 {a.get('impressions', 0):,} | "
            f"👍 {a.get('likes', 0)} | "
            f"💬 {a.get('comments', 0)} | "
            f"互動率 {a.get('engagement_rate', 0):.2f}%"
        )

    st.divider()

    # ── AI Insights ──
    st.subheader("🤖 AI 數據洞察報告")
    if st.button("生成本週洞察"):
        with st.spinner("AI 分析中..."):
            insight = _generate_ai_insights(all_analytics)
        if insight:
            st.markdown(insight)
            st.session_state["p6_insight"] = insight
        else:
            st.warning("無法生成洞察，請確認 GEMINI_API_KEY 設定。")

    if "p6_insight" in st.session_state:
        st.markdown(st.session_state["p6_insight"])

    st.divider()

    # ── Topic clusters ──
    st.subheader("🔍 主題聚類（延伸建議）")
    clusters = _find_topic_clusters(published_posts)
    if not clusters:
        st.info("發布 3+ 篇同主題貼文後，這裡會出現延伸內容建議。")
    else:
        for keyword, posts in clusters.items():
            with st.container(border=True):
                st.markdown(f"**「{keyword}」** 系列 — {len(posts)} 篇")
                for p in posts:
                    st.caption(f"• {p['title']}")
                if st.button(f"🤖 建議延伸方向", key=f"cluster_{keyword}"):
                    with st.spinner("Claude 分析延伸方向..."):
                        try:
                            import anthropic
                            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
                            post_titles = "\n".join([f"- {p['title']}" for p in posts])
                            resp = client.messages.create(
                                model="claude-sonnet-4-6",
                                max_tokens=512,
                                messages=[{
                                    "role": "user",
                                    "content": f"我已經發了以下幾篇關於「{keyword}」的 LinkedIn 貼文：\n{post_titles}\n\n請建議 3-5 個可以延伸的新角度，用繁體中文回應。"
                                }],
                            )
                            st.markdown(resp.content[0].text)
                        except Exception as e:
                            st.error(f"Claude 分析失敗：{e}")
