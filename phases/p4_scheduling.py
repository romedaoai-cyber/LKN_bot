"""
Phase 4: 排程管理
- Kanban 視圖 (status board)
- 月曆排程
- 人工終審區（微調內容）
"""
import streamlit as st
from datetime import datetime, timedelta, date

import config
from db.local_store import LocalStore

posts_store = LocalStore(config.POSTS_FILE)

STATUS_LABELS = {
    "draft": ("📝 草稿", "#94a3b8"),
    "review": ("🔍 待審", "#f59e0b"),
    "approved": ("✅ 已核准", "#22c55e"),
    "scheduled": ("📅 已排程", "#3b82f6"),
    "published": ("🚀 已發布", "#8b5cf6"),
}

TYPE_EMOJI = {
    "opinion": "🔴",
    "tutorial": "🟡",
    "trend": "🟢",
}


def render():
    st.header("📅 Phase 4｜排程管理")

    tabs = st.tabs(["📋 Kanban 看板", "📅 排程設定", "✏️ 人工終審"])

    all_posts = posts_store.all()

    # ── Tab 1: Kanban ──
    with tabs[0]:
        st.subheader("貼文狀態看板")
        cols = st.columns(5)
        for i, (status, (label, color)) in enumerate(STATUS_LABELS.items()):
            with cols[i]:
                st.markdown(f"**{label}**")
                status_posts = [p for p in all_posts if p["status"] == status]
                if not status_posts:
                    st.caption("空")
                for post in status_posts:
                    type_e = TYPE_EMOJI.get(post.get("type", ""), "")
                    with st.container(border=True):
                        st.caption(f"{type_e} {post['title'][:30]}")
                        if post.get("scheduled_at"):
                            st.caption(f"📅 {post['scheduled_at'][:10]}")

    # ── Tab 2: Scheduling ──
    with tabs[1]:
        st.subheader("安排發文時間")

        approved_posts = [p for p in all_posts if p["status"] in ("approved", "draft")]
        if not approved_posts:
            st.info("目前沒有已核准的貼文可排程。")
        else:
            options = {f"{TYPE_EMOJI.get(p.get('type',''),'')} {p['title']}": p for p in approved_posts}
            selected_label = st.selectbox("選擇貼文", list(options.keys()))
            selected_post = options[selected_label]

            col1, col2 = st.columns(2)
            with col1:
                schedule_date = st.date_input("發文日期", value=date.today() + timedelta(days=1))
            with col2:
                schedule_time = st.time_input("發文時間", value=datetime.strptime("09:00", "%H:%M").time())

            if st.button("📅 確認排程", type="primary"):
                scheduled_at = datetime.combine(schedule_date, schedule_time).isoformat()
                selected_post["scheduled_at"] = scheduled_at
                selected_post["status"] = "scheduled"
                posts_store.save(selected_post)
                st.success(f"已排程於 {schedule_date} {schedule_time}")
                st.rerun()

        # Calendar view
        st.divider()
        st.subheader("本月排程一覽")
        scheduled = sorted(
            [p for p in all_posts if p.get("scheduled_at")],
            key=lambda x: x["scheduled_at"],
        )
        if not scheduled:
            st.info("尚無排程貼文")
        else:
            for post in scheduled:
                type_e = TYPE_EMOJI.get(post.get("type", ""), "")
                dt = post["scheduled_at"][:16].replace("T", " ")
                status_label = STATUS_LABELS.get(post["status"], ("", ""))[0]
                st.markdown(f"- `{dt}` {type_e} **{post['title']}** — {status_label}")

    # ── Tab 3: Human Review ──
    with tabs[2]:
        st.subheader("人工終審區")
        st.caption("最終微調語氣、標點，確保每篇都是你的風格")

        review_posts = [p for p in all_posts if p["status"] in ("scheduled", "approved") and p.get("content")]
        if not review_posts:
            st.info("沒有待審稿件。")
        else:
            options = {p["title"]: p for p in review_posts}
            selected_label = st.selectbox("選擇稿件", list(options.keys()), key="review_select")
            post = options[selected_label]

            type_e = TYPE_EMOJI.get(post.get("type", ""), "")
            st.caption(f"{type_e} 類型：{post.get('type', '')} ｜ 排程：{post.get('scheduled_at', '未設定')[:16] if post.get('scheduled_at') else '未設定'}")

            edited = st.text_area("貼文內容（可直接編輯）", value=post.get("content", ""), height=350)
            word_count = len(edited)
            st.caption(f"字數：{word_count}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 儲存修改", type="primary"):
                    post["content"] = edited
                    posts_store.save(post)
                    st.success("已儲存！")
            with col2:
                if post["status"] == "approved" and st.button("📅 標記為已排程"):
                    post["status"] = "scheduled"
                    posts_store.save(post)
                    st.rerun()
