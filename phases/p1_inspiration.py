"""
Phase 1: 靈感輸入
- Trend Radar (手動貼文 + Gemini 萃取)
- 個人觀察
- 粉絲 Q&A
- 靈感庫
"""
import streamlit as st
from datetime import datetime
import os

import config
from db.local_store import LocalStore
from db.models import new_inspiration, new_qa_record

inspirations_store = LocalStore(config.INSPIRATIONS_FILE)
qa_store = LocalStore(config.QA_RECORDS_FILE)


def _extract_with_gemini(text: str) -> str:
    try:
        import google.generativeai as genai
        api_key = os.environ.get("GEMINI_API_KEY") or config.GEMINI_API_KEY
        if not api_key:
            return text[:500]
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        resp = model.generate_content(
            f"請萃取以下內容的核心重點，用繁體中文條列出 3-5 個適合作為 LinkedIn 貼文靈感的觀點或洞察：\n\n{text[:3000]}"
        )
        return resp.text.strip()
    except Exception as e:
        return f"AI 萃取失敗：{e}"


def render():
    st.header("💡 Phase 1｜靈感輸入")

    tabs = st.tabs(["📡 趨勢雷達", "👁️ 個人觀察", "💬 粉絲 Q&A", "📚 靈感庫"])

    # ── Tab 1: Trend Radar ──
    with tabs[0]:
        st.subheader("趨勢雷達")
        st.caption("貼上文章、新聞或 URL 內容，AI 自動萃取靈感重點")

        input_text = st.text_area("貼上文章內容或摘要", height=200, placeholder="貼上任何文章、新聞、LinkedIn 貼文...")
        col1, col2 = st.columns([1, 3])
        with col1:
            tag_input = st.text_input("標籤（逗號分隔）", placeholder="AI, 行銷, 職涯")

        if st.button("🤖 AI 萃取並存入靈感庫", type="primary", disabled=not input_text):
            with st.spinner("AI 萃取中..."):
                summary = _extract_with_gemini(input_text)
            tags = [t.strip() for t in tag_input.split(",") if t.strip()]
            rec = new_inspiration(
                type_="trend",
                title=input_text[:60] + "..." if len(input_text) > 60 else input_text,
                content=input_text,
                source="manual",
                tags=tags,
                ai_summary=summary,
            )
            inspirations_store.save(rec)
            st.success("已存入靈感庫！")
            st.markdown("**AI 萃取重點：**")
            st.markdown(summary)

    # ── Tab 2: Personal Observation ──
    with tabs[1]:
        st.subheader("個人觀察")
        st.caption("記錄日常觸發點、靈感瞬間")

        title = st.text_input("標題 / 一句話摘要")
        content = st.text_area("詳細想法", height=150)
        tags_raw = st.text_input("標籤", placeholder="職場, 觀察, 趨勢")

        if st.button("💾 存入靈感庫", type="primary", disabled=not (title and content)):
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            rec = new_inspiration(
                type_="personal",
                title=title,
                content=content,
                source="manual",
                tags=tags,
            )
            inspirations_store.save(rec)
            st.success("個人觀察已存入！")

    # ── Tab 3: Fan Q&A ──
    with tabs[2]:
        st.subheader("粉絲 Q&A")
        st.caption("記錄有價值的問題，一鍵轉為靈感")

        with st.expander("➕ 新增 Q&A 記錄", expanded=False):
            q = st.text_input("問題")
            a = st.text_area("回答（可留空）", height=100)
            src = st.selectbox("來源", ["manual", "linkedin_comment"])
            qa_tags = st.text_input("標籤", key="qa_tags")

            if st.button("新增 Q&A"):
                if q:
                    tags = [t.strip() for t in qa_tags.split(",") if t.strip()]
                    rec = new_qa_record(question=q, answer=a, source=src, tags=tags)
                    qa_store.save(rec)
                    st.success("Q&A 已記錄！")
                    st.rerun()

        qa_records = qa_store.all()
        if not qa_records:
            st.info("還沒有 Q&A 記錄。")
        else:
            for qa in reversed(qa_records[-20:]):
                with st.container(border=True):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown(f"**Q:** {qa['question']}")
                        if qa.get("answer"):
                            st.caption(f"A: {qa['answer'][:100]}...")
                    with col2:
                        if not qa.get("converted"):
                            if st.button("→ 靈感庫", key=f"qa_conv_{qa['id']}"):
                                insp = new_inspiration(
                                    type_="qa",
                                    title=qa["question"],
                                    content=f"問：{qa['question']}\n答：{qa.get('answer', '')}",
                                    source="linkedin_comment",
                                    tags=qa.get("tags", []),
                                )
                                inspirations_store.save(insp)
                                qa["converted"] = True
                                qa["inspiration_id"] = insp["id"]
                                qa_store.save(qa)
                                st.rerun()
                        else:
                            st.caption("✅ 已轉換")

    # ── Tab 4: Inspiration Library ──
    with tabs[3]:
        st.subheader("靈感庫")

        all_inspirations = inspirations_store.all()

        col1, col2 = st.columns([2, 1])
        with col1:
            search = st.text_input("搜尋靈感", placeholder="輸入關鍵字...")
        with col2:
            type_filter = st.selectbox("類型篩選", ["全部", "trend", "personal", "qa", "idea"])

        if search:
            all_inspirations = [i for i in all_inspirations
                                 if search.lower() in i.get("title", "").lower()
                                 or search.lower() in i.get("content", "").lower()]
        if type_filter != "全部":
            all_inspirations = [i for i in all_inspirations if i.get("type") == type_filter]

        if not all_inspirations:
            st.info("暫無靈感，先在趨勢雷達或個人觀察記錄吧！")
        else:
            type_emoji = {"trend": "📡", "personal": "👁️", "qa": "💬", "idea": "💡"}
            for insp in reversed(all_inspirations[-30:]):
                emoji = type_emoji.get(insp.get("type", ""), "💡")
                with st.container(border=True):
                    st.markdown(f"{emoji} **{insp['title']}**")
                    if insp.get("ai_summary"):
                        st.caption(insp["ai_summary"][:200])
                    if insp.get("tags"):
                        st.caption("🏷️ " + " · ".join(insp["tags"]))
                    if insp.get("used_in_posts"):
                        st.caption(f"✅ 已用於 {len(insp['used_in_posts'])} 篇貼文")
