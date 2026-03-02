"""
LinkedIn Content Manager v2
六階段內容飛輪工作流程

Run: streamlit run streamlit_app.py
"""
import streamlit as st

st.set_page_config(
    page_title="LinkedIn Content Manager",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _render_brand_settings():
    st.header("⚙️ 品牌設定")
    st.caption("定義你的品牌聲音，AI 產文時會自動套用")

    import config
    from db.local_store import LocalStore
    from db.models import default_brand_profile
    from datetime import datetime

    brand_store = LocalStore(config.BRAND_PROFILE_FILE)
    profile = brand_store.get_single() or default_brand_profile()

    name = st.text_input("品牌/個人名稱", value=profile.get("name", ""))
    tone = st.text_area("語氣描述", value=profile.get("tone", ""), height=80,
                        placeholder="例：專業但親切，像在和聰明朋友對話")
    target_audience = st.text_area("目標受眾", value=profile.get("target_audience", ""), height=80,
                                   placeholder="例：B2B SaaS 行銷主管、新創創辦人")
    topics_raw = st.text_input("擅長話題（逗號分隔）",
                                value=", ".join(profile.get("topics", [])),
                                placeholder="AI, 行銷, 職涯發展")
    style_guide = st.text_area("詳細風格指南", value=profile.get("style_guide", ""), height=150,
                                placeholder="描述你的寫作風格、用詞習慣、要避免的表達...")

    if st.button("💾 儲存品牌設定", type="primary"):
        profile.update({
            "name": name,
            "tone": tone,
            "target_audience": target_audience,
            "topics": [t.strip() for t in topics_raw.split(",") if t.strip()],
            "style_guide": style_guide,
            "updated_at": datetime.utcnow().isoformat(),
        })
        brand_store.save_single(profile)
        st.success("品牌設定已儲存！")


# ── Sidebar navigation ──
PHASES = {
    "💡 Phase 1｜靈感輸入": "p1",
    "🔍 Phase 2｜前置審核": "p2",
    "🤖 Phase 3｜內容生產": "p3",
    "📅 Phase 4｜排程管理": "p4",
    "🚀 Phase 5｜發布 & 互動": "p5",
    "📊 Phase 6｜數據追蹤": "p6",
    "⚙️ 品牌設定": "brand",
}

with st.sidebar:
    st.markdown("## 💼 LinkedIn Manager")
    st.markdown("---")
    selected = st.radio("工作流程", list(PHASES.keys()), label_visibility="collapsed")
    st.markdown("---")

    # Quick stats
    try:
        import config
        from db.local_store import LocalStore
        posts_store = LocalStore(config.POSTS_FILE)
        inspirations_store = LocalStore(config.INSPIRATIONS_FILE)
        all_posts = posts_store.all()
        all_inspirations = inspirations_store.all()

        st.caption("📊 快速統計")
        st.caption(f"靈感：{len(all_inspirations)} 個")
        st.caption(f"草稿：{len([p for p in all_posts if p['status'] == 'draft'])} 篇")
        st.caption(f"已排程：{len([p for p in all_posts if p['status'] == 'scheduled'])} 篇")
        st.caption(f"已發布：{len([p for p in all_posts if p['status'] == 'published'])} 篇")
    except Exception:
        pass

# ── Route to phase ──
phase_key = PHASES[selected]

if phase_key == "p1":
    from phases.p1_inspiration import render
    render()

elif phase_key == "p2":
    from phases.p2_review import render
    render()

elif phase_key == "p3":
    from phases.p3_production import render
    render()

elif phase_key == "p4":
    from phases.p4_scheduling import render
    render()

elif phase_key == "p5":
    from phases.p5_publishing import render
    render()

elif phase_key == "p6":
    from phases.p6_analytics import render
    render()

elif phase_key == "brand":
    _render_brand_settings()
