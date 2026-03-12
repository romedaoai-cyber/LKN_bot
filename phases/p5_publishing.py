"""
Phase 5: 發布 & 互動
- 一鍵發布到 LinkedIn
- 顯示最新貼文狀態
- 手動記錄 Q&A，存入 Q&A 資料庫
"""
import streamlit as st
from datetime import datetime

import config
from db.local_store import LocalStore
from db.firebase_db import firebase
from db.models import new_qa_record
from linkedin.publisher import publish_post, check_token

posts_store = LocalStore(config.POSTS_FILE)
qa_store = LocalStore(config.QA_RECORDS_FILE)


def render():
    st.header("🚀 Phase 5｜發布 & 互動")

    tabs = st.tabs(["📤 發布貼文", "🤖 自動發布狀態", "💬 記錄 Q&A"])

    all_posts = posts_store.all()

    # ── Tab 1: Publish ──
    with tabs[0]:
        st.subheader("發布到 LinkedIn")

        token = check_token()
        if not token:
            st.warning("⚠️ LinkedIn Token 未設定或已過期。請先在 .env 設定 LINKEDIN_ACCESS_TOKEN。")

        scheduled_posts = [p for p in all_posts if p["status"] == "scheduled" and p.get("content")]
        if not scheduled_posts:
            st.info("沒有已排程的貼文。請先在 Phase 4 完成排程。")
        else:
            options = {p["title"]: p for p in scheduled_posts}
            selected_label = st.selectbox("選擇要發布的貼文", list(options.keys()))
            post = options[selected_label]

            with st.container(border=True):
                st.markdown("**預覽：**")
                st.write(post.get("content", ""))
                if post.get("image_path"):
                    st.image(post["image_path"])

            col1, col2, col3 = st.columns(3)
            with col1:
                dry_run = st.checkbox("🧪 Dry Run（不實際發布）", value=True)

            with col2:
                if st.button("🚀 發布", type="primary", disabled=(not token and not dry_run)):
                    with st.spinner("發布中..."):
                        urn = publish_post(post, dry_run=dry_run)
                    if urn:
                        if not dry_run:
                            post["status"] = "published"
                            post["published_at"] = datetime.utcnow().isoformat()
                            post["linkedin_urn"] = urn
                            posts_store.save(post)
                        st.success(f"{'[DRY RUN] ' if dry_run else ''}發布成功！URN: {urn}")
                        st.balloons()
                    else:
                        st.error("發布失敗，請檢查 LinkedIn Token 和設定。")

        st.divider()
        st.subheader("已發布記錄")
        published = [p for p in all_posts if p["status"] == "published"]
        if not published:
            st.info("尚無已發布貼文")
        else:
            for p in reversed(published[-10:]):
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{p['title']}**")
                        st.caption(f"發布時間：{p.get('published_at', '')[:16] if p.get('published_at') else '未知'}")
                    with col2:
                        if p.get("linkedin_urn"):
                            st.caption(f"URN: ...{p['linkedin_urn'][-8:]}")

    # ── Tab 2: Auto-Publish Status ──
    with tabs[1]:
        st.subheader("🤖 Firebase 自動發布狀態")
        st.caption("發文時間：每天 6:00 AM – 3:00 PM（溫哥華時間 PT）")

        if not firebase.active:
            st.warning("⚠️ Firebase 未連線，自動發布功能未啟用。")
        else:
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("🔄 重新整理"):
                    st.rerun()

            # Pending auto-publish
            scheduled_fb = firebase.all("scheduled_posts")
            pending = [p for p in scheduled_fb if p.get("status") == "scheduled"]
            auto_done = [p for p in scheduled_fb if p.get("status") == "published" and p.get("auto_published")]

            st.markdown(f"**待自動發布：{len(pending)} 篇**")
            if pending:
                for p in sorted(pending, key=lambda x: x.get("scheduled_at", "")):
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{p.get('title', '未命名')}**")
                        with col2:
                            dt = p.get("scheduled_at", "")[:16].replace("T", " ")
                            st.caption(f"📅 {dt}")

            st.divider()
            st.markdown(f"**已自動發布：{len(auto_done)} 篇**")
            if auto_done:
                for p in reversed(auto_done[-5:]):
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"✅ **{p.get('title', '未命名')}**")
                            st.caption(f"發布時間：{p.get('published_at', '')[:16].replace('T', ' ')}")
                        with col2:
                            if p.get("linkedin_urn"):
                                st.caption(f"URN: ...{p['linkedin_urn'][-8:]}")

    # ── Tab 3: Q&A Capture ──
    with tabs[2]:
        st.subheader("記錄互動 Q&A")
        st.caption("從留言中找到有價值的問題，存入 Q&A 資料庫，再流回 Phase 1 成為靈感")

        published_posts = [p for p in all_posts if p["status"] == "published"]
        post_options = {"(手動輸入，不關聯貼文)": None}
        for p in published_posts:
            post_options[p["title"]] = p["id"]

        linked_post_label = st.selectbox("關聯到哪篇貼文？", list(post_options.keys()))
        linked_post_id = post_options[linked_post_label]

        question = st.text_area("留言問題", placeholder="讀者問了什麼？", height=80)
        answer = st.text_area("你的回答（選填）", height=80)
        qa_tags = st.text_input("標籤", placeholder="AI, 職涯")

        if st.button("💾 存入 Q&A 資料庫", type="primary", disabled=not question):
            tags = [t.strip() for t in qa_tags.split(",") if t.strip()]
            rec = new_qa_record(
                question=question,
                answer=answer,
                source="linkedin_comment" if linked_post_id else "manual",
                post_id=linked_post_id,
                tags=tags,
            )
            qa_store.save(rec)
            st.success("✅ 已存入 Q&A 資料庫！可到 Phase 1 → 粉絲 Q&A 查看並轉為靈感。")

        # Recent Q&A
        recent_qa = qa_store.all()[-5:]
        if recent_qa:
            st.divider()
            st.caption("最近記錄的 Q&A：")
            for qa in reversed(recent_qa):
                st.markdown(f"• **{qa['question'][:60]}**")
