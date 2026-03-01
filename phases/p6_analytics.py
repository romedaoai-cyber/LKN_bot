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
from linkedin.analytics_fetcher import fetch_metrics

posts_store = LocalStore(config.POSTS_FILE)
analytics_store = LocalStore(config.ANALYTICS_FILE)


def _fetch_all_analytics():
    """Sync analytics for all published posts."""
    posts = [p for p in posts_store.all() if p["status"] == "published" and p.get("linkedin_urn")]
    updated = 0
    for post in posts:
        metrics = fetch_metrics(post["linkedin_urn"])
        if metrics:
            record = analytics_store.get(post["id"]) or {"post_id": post["id"]}
            record.update({
                "post_id": post["id"],
                "linkedin_urn": post["linkedin_urn"],
                "type": post.get("type", "unknown"),
                "title": post.get("title", ""),
                **metrics,
            })
            if "id" not in record:
                record["id"] = post["id"]
            analytics_store.save(record)
            updated += 1
    return updated


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

    # ── Fetch analytics ──
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 同步 LinkedIn 數據"):
            with st.spinner("抓取數據中..."):
                count = _fetch_all_analytics()
            st.success(f"已更新 {count} 篇貼文數據")
            st.rerun()

    all_analytics = analytics_store.all()
    all_posts = posts_store.all()
    published_posts = [p for p in all_posts if p["status"] == "published"]

    if not all_analytics:
        st.info("尚無數據。請先發布貼文並點擊「同步 LinkedIn 數據」。")
        if published_posts:
            st.caption(f"已有 {len(published_posts)} 篇已發布貼文，點擊右上角按鈕同步數據。")
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
        type_e = {"opinion": "🔴", "tutorial": "🟡", "trend": "🟢"}.get(a.get("type", ""), "")
        st.markdown(
            f"{i}. {type_e} **{a.get('title', a.get('post_id', '')[:20])}** — "
            f"觀看 {a.get('impressions', 0):,} | 互動率 {a.get('engagement_rate', 0):.2f}%"
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
