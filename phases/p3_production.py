"""
Phase 3: 內容生產
- 從待產文佇列選題
- 多選 AI Skills
- 一鍵產文 (SkillEngine)
- 顯示各 skill 洞察 + 完整貼文
- 可編輯、重新產生
"""
import streamlit as st

import config
from db.local_store import LocalStore
from db.models import new_post
from ai.skill_engine import OPTIONAL_SKILLS, run_skills, rewrite_with_feedback

posts_store = LocalStore(config.POSTS_FILE)
brand_store = LocalStore(config.BRAND_PROFILE_FILE)
inspirations_store = LocalStore(config.INSPIRATIONS_FILE)


def render():
    st.header("🤖 Phase 3｜內容生產")
    st.caption("選題 + AI Skills 組合，一鍵產出 LinkedIn 貼文")

    # Get posts in review status
    queue = [p for p in posts_store.all() if p["status"] in ("review", "draft")]
    if not queue:
        st.info("佇列是空的！請先在 Phase 2 核准主題。")
        _manual_create()
        return

    options = {f"[{p['type'].upper()}] {p['title']}": p for p in reversed(queue)}
    selected_label = st.selectbox("選擇主題", list(options.keys()))
    post = options[selected_label]

    # Show inspiration context
    if post.get("inspiration_ids"):
        insp_id = post["inspiration_ids"][0]
        insp = inspirations_store.get(insp_id)
        if insp and insp.get("ai_summary"):
            with st.expander("查看靈感摘要"):
                st.write(insp["ai_summary"])

    st.divider()

    # ── Skill selection ──
    st.subheader("選擇 AI Skills")
    st.caption("Crisis Director 和 Writing Style 永遠啟用。選擇輔助 Skills：")

    col1, col2 = st.columns(2)
    selected_keys = []
    items = list(OPTIONAL_SKILLS.items())
    for i, (key, skill) in enumerate(items):
        col = col1 if i % 2 == 0 else col2
        with col:
            if st.checkbox(f"{skill.emoji} {skill.name}", value=True, key=f"skill_{key}"):
                selected_keys.append(key)

    # ── Brand profile ──
    brand_profile = brand_store.get_single()

    st.divider()

    # ── Generate button ──
    if st.button("🚀 一鍵產文", type="primary"):
        progress_placeholder = st.empty()
        results_log = []

        def on_progress(step: str, msg: str):
            results_log.append(f"▶ {msg}")
            progress_placeholder.markdown("\n".join(results_log))

        # Get inspiration content
        inspiration_text = ""
        if post.get("inspiration_ids"):
            insp = inspirations_store.get(post["inspiration_ids"][0])
            if insp:
                inspiration_text = insp.get("ai_summary") or insp.get("content", "")

        with st.spinner("AI 正在產文..."):
            result = run_skills(
                topic=post["title"],
                selected_skill_keys=selected_keys,
                brand_profile=brand_profile,
                inspiration=inspiration_text,
                on_progress=on_progress,
            )

        progress_placeholder.empty()
        st.session_state["p3_result"] = result
        st.session_state["p3_post_id"] = post["id"]

    # ── Display results ──
    if "p3_result" in st.session_state and st.session_state.get("p3_post_id") == post["id"]:
        result = st.session_state["p3_result"]

        # Risk badge
        risk_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        risk_badge = risk_colors.get(result["risk_level"], "🟢")
        st.markdown(f"**風險等級：{risk_badge}**")

        with st.expander("查看各 Skill 洞察", expanded=False):
            for skill_name, output in result["skill_results"].items():
                st.markdown(f"**{skill_name}**")
                st.write(output)
                st.divider()

        st.subheader("產出貼文")
        edited_content = st.text_area(
            "編輯貼文內容",
            value=result["post"],
            height=400,
            key="p3_edited_content",
        )

        # ── Image Upload ──
        st.divider()
        st.subheader("🖼️ 附加圖片")
        uploaded_file = st.file_uploader(
            "上傳圖片（選填）",
            type=["jpg", "jpeg", "png", "gif"],
            key="p3_image_upload",
        )
        if uploaded_file:
            image_bytes = uploaded_file.read()
            image_url = None

            # Try Firebase Storage first
            try:
                from firebase_admin import storage as fb_storage
                from db.firebase_db import firebase
                if firebase.active:
                    bucket = fb_storage.bucket()
                    blob = bucket.blob(f"post_images/{post['id']}_{uploaded_file.name}")
                    blob.upload_from_string(image_bytes, content_type=uploaded_file.type)
                    blob.make_public()
                    image_url = blob.public_url
                    post["image_url"] = image_url
                    post["image_path"] = None
            except Exception as e:
                st.warning(f"Firebase Storage 上傳失敗，改存本地：{e}")

            # Fallback: local save
            if not image_url:
                import config as _cfg
                image_path = _cfg.IMAGES_DIR / f"{post['id']}_{uploaded_file.name}"
                image_path.write_bytes(image_bytes)
                post["image_path"] = str(image_path)
                post["image_url"] = None

            posts_store.save(post)
            st.image(image_bytes, caption=uploaded_file.name, width=300)
            st.success("圖片已儲存，發布時會一起上傳到 LinkedIn。")

        elif post.get("image_url") or post.get("image_path"):
            import os
            img_src = post.get("image_url") or post.get("image_path")
            if img_src and (img_src.startswith("http") or os.path.exists(img_src)):
                st.image(img_src, caption="目前圖片", width=300)
                if st.button("🗑️ 移除圖片"):
                    post["image_path"] = None
                    post["image_url"] = None
                    posts_store.save(post)
                    st.rerun()

        # ── Feedback & Rewrite ──
        st.divider()
        st.subheader("💬 反饋給 AI")
        feedback_text = st.text_area(
            "告訴 AI 哪裡需要改（英文或中文都可以）",
            placeholder="e.g. Make the hook more provocative / 語氣太正式，改輕鬆一點 / Add more specific data in the middle",
            height=100,
            key="p3_feedback",
        )
        if st.button("✨ 根據反饋重寫", disabled=not feedback_text.strip()):
            with st.spinner("AI 根據反饋重寫中..."):
                new_post_content = rewrite_with_feedback(
                    current_post=edited_content,
                    feedback=feedback_text,
                    brand_profile=brand_profile,
                )
            st.session_state["p3_result"]["post"] = new_post_content
            st.session_state.pop("p3_feedback", None)
            st.rerun()

        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("💾 存為草稿"):
                post["content"] = edited_content
                post["status"] = "draft"
                post["skills_used"] = list(st.session_state.get("p3_result", {}).get("skill_results", {}).keys())
                posts_store.save(post)
                st.success("已存為草稿！")

        with col2:
            if st.button("✅ 送審 (Approved)", type="primary"):
                post["content"] = edited_content
                post["status"] = "approved"
                post["skills_used"] = list(result["skill_results"].keys())
                posts_store.save(post)
                st.success("已送審！前往 Phase 4 安排排程。")

        with col3:
            if st.button("🔄 重新產文"):
                st.session_state.pop("p3_result", None)
                st.rerun()


def _manual_create():
    """Allow creating a post from scratch even without Phase 2 queue."""
    with st.expander("或從頭手動建立"):
        title = st.text_input("主題標題")
        type_ = st.selectbox("類型", ["opinion", "tutorial", "trend"])
        if st.button("建立新主題") and title:
            post = new_post(title=title, type_=type_)
            post["status"] = "review"
            posts_store.save(post)
            st.rerun()
