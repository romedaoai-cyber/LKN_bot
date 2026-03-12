"""
Phase 2: 前置審核
- 從靈感庫選題
- 三道濾網 (風向/品牌/類型)
- Crisis Director 風險預判
- 核准後進入「待產文」佇列
"""
import streamlit as st

import config
from db.local_store import LocalStore
from db.models import new_post

inspirations_store = LocalStore(config.INSPIRATIONS_FILE)
posts_store = LocalStore(config.POSTS_FILE)


def render():
    st.header("🔍 Phase 2｜前置審核")
    st.caption("選擇靈感、通過三道濾網，核准進入產文佇列")

    all_inspirations = inspirations_store.all()
    if not all_inspirations:
        st.warning("靈感庫是空的！請先到 Phase 1 新增靈感。")
        return

    # ── Select inspiration ──
    options = {f"[{i.get('type','').upper()}] {i['title'][:60]}": i for i in reversed(all_inspirations)}
    selected_label = st.selectbox("選擇靈感主題", list(options.keys()))
    selected_insp = options[selected_label]

    with st.expander("查看靈感內容", expanded=False):
        st.write(selected_insp.get("content", ""))
        if selected_insp.get("ai_summary"):
            st.markdown("**AI 摘要：**")
            st.write(selected_insp["ai_summary"])

    st.divider()

    # ── Three filters ──
    st.subheader("三道濾網")

    col1, col2 = st.columns(2)
    with col1:
        trend_check = st.radio(
            "🌊 風向判斷 — 這個話題現在適合發嗎？",
            ["是，時機正好", "還可以，但需要角度", "否，先跳過"],
            index=0,
        )
    with col2:
        brand_aligned = st.radio(
            "🎯 定位吻合 — 符合品牌人設嗎？",
            ["完全符合", "部分符合，需調整", "不符合，跳過"],
            index=0,
        )

    content_type = st.radio(
        "📋 類型判斷 — 這篇是什麼類型？",
        ["🔴 觀點文 (opinion)", "🟡 教學文 (tutorial)", "🟢 趨勢文 (trend)"],
        horizontal=True,
    )
    type_key = content_type.split("(")[1].replace(")", "").strip()

    # ── Risk pre-check ──
    topic_title = st.text_input("發文主題標題（可修改）", value=selected_insp["title"])

    run_risk = st.button("🛡️ 執行風險預判 (Crisis Director)")
    if run_risk and topic_title:
        with st.spinner("Claude 分析風險中..."):
            from ai.skills.crisis_director import CrisisDirectorSkill
            skill = CrisisDirectorSkill()
            risk_result = skill.generate(topic_title, {})
        st.session_state["p2_risk_result"] = risk_result
        st.session_state["p2_topic"] = topic_title

    if "p2_risk_result" in st.session_state:
        with st.container(border=True):
            st.markdown("**🛡️ 風險評估結果：**")
            st.write(st.session_state["p2_risk_result"])

    # ── Approve ──
    st.divider()
    can_approve = ("否" not in trend_check and "不符合" not in brand_aligned)

    if not can_approve:
        st.warning("此主題未通過濾網，建議先跳過或修改方向。")

    if st.button("✅ 核准，進入產文佇列", type="primary", disabled=not (can_approve and topic_title)):
        post = new_post(
            title=topic_title,
            type_=type_key,
            inspiration_ids=[selected_insp["id"]],
        )
        post["status"] = "review"
        post["pre_review"] = {
            "trend_check": trend_check,
            "brand_aligned": brand_aligned,
            "content_type": type_key,
            "risk_level": None,
            "risk_note": st.session_state.get("p2_risk_result", ""),
        }
        posts_store.save(post)

        # Mark inspiration as used
        selected_insp.setdefault("used_in_posts", []).append(post["id"])
        inspirations_store.save(selected_insp)

        st.success(f"「{topic_title}」已進入產文佇列！前往 Phase 3 開始產文。")
        st.session_state.pop("p2_risk_result", None)
