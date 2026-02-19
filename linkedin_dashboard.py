import streamlit as st
import os
import json
import time
from pathlib import Path
from datetime import datetime
import subprocess
import requests
import urllib.parse
import pandas as pd
from firebase_manager import fm

# Initialize Firebase
fm.initialize()

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "linkedin_posts"
PUBLISHER_SCRIPT = "linkedin_publisher.py" # Assumes in same dir
FEEDBACK_LOG = POSTS_DIR / "feedback_log.json"
DEPRECATED_SAMPLE_FILES = {
    "w1_day1_20260211_npi_paradox.md",
    "w1_day2_20260212_false_calls.md",
    "w1_day3_20260213_five_signs.md",
    "w2_day1_20260216_setup_speed.md",
    "w2_day2_20260217_auto_bom.md",
    "w2_day3_20260218_semantic_filter.md",
    "w2_day4_20260219_spc_dashboard.md",
    "w2_day5_20260220_product_lineup.md",
}

st.set_page_config(
    page_title="DaoAI Content Studio",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ──────────────────────────────────────────────
# Premium CSS Theme (Midnight Editorial)
# ──────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

    :root {
        --ink-900: #0f172a;
        --ink-700: #334155;
        --ink-500: #64748b;
        --paper-100: #f8fafc;
        --accent-1: #f97316;
        --accent-2: #2563eb;
        --card-bg: rgba(255, 255, 255, 0.92);
    }

    html, body, [class*="css"] {
        font-family: 'Manrope', sans-serif !important;
        color: var(--ink-900) !important;
    }

    .stDeployButton { display: none !important; }
    [data-testid="stDecoration"] { display: none; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }

    .stApp {
        background:
            radial-gradient(900px 500px at 95% 5%, rgba(37, 99, 235, 0.16), transparent 60%),
            radial-gradient(700px 380px at 0% 90%, rgba(249, 115, 22, 0.14), transparent 55%),
            linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.96) 0%, rgba(30, 41, 59, 0.96) 100%) !important;
        border-right: 1px solid rgba(148, 163, 184, 0.2);
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown span,
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] div {
        color: #e2e8f0 !important;
    }

    .sidebar-stat {
        background: rgba(30, 41, 59, 0.55);
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-radius: 14px;
        padding: 12px;
        text-align: center;
        margin-bottom: 8px;
        backdrop-filter: blur(8px);
    }
    .sidebar-stat-value {
        font-size: 1.45rem;
        font-weight: 800;
        color: #f8fafc;
    }
    .sidebar-stat-label {
        font-size: 0.67rem;
        color: #cbd5e1;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        font-weight: 700;
    }

    .top-header {
        background: linear-gradient(120deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.96));
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 24px;
        padding: 28px 32px;
        margin-bottom: 28px;
        box-shadow: 0 20px 45px rgba(15, 23, 42, 0.18);
    }
    .top-header h1 {
        margin: 0;
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 2rem;
        color: #f8fafc !important;
        letter-spacing: -0.04em;
    }
    .top-header p {
        margin: 10px 0 0 0;
        color: #cbd5e1;
        font-size: 0.96rem;
        font-weight: 500;
    }
    .top-header .header-pill {
        margin-top: 14px;
        display: inline-flex;
        padding: 7px 12px;
        border-radius: 999px;
        background: rgba(248, 250, 252, 0.12);
        border: 1px solid rgba(248, 250, 252, 0.24);
        color: #f8fafc;
        font-size: 0.78rem;
        letter-spacing: 0.4px;
    }

    .section-title {
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 1.35rem;
        font-weight: 700;
        color: var(--ink-900);
        margin: 30px 0 14px 0;
    }

    .status-badge {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.45px;
    }
    .status-approved  { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
    .status-rejected  { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
    .status-pending   { background: #ffedd5; color: #9a3412; border: 1px solid #fdba74; }
    .status-published { background: #dbeafe; color: #1d4ed8; border: 1px solid #93c5fd; }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid rgba(148, 163, 184, 0.22) !important;
        border-radius: 18px !important;
        background: var(--card-bg) !important;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 18px 34px rgba(15, 23, 42, 0.12) !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        padding: 8px;
        border-radius: 16px;
        background: rgba(15, 23, 42, 0.06);
        border: 1px solid rgba(148, 163, 184, 0.2);
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 700;
        color: var(--ink-700);
        border-radius: 12px;
        padding: 8px 15px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--accent-1), #ea580c) !important;
        color: #fff !important;
        box-shadow: 0 8px 18px rgba(249, 115, 22, 0.28);
    }

    button {
        min-height: 42px !important;
        padding-top: 8px !important;
        padding-bottom: 8px !important;
    }
    .stButton > button,
    div[data-testid="stPopover"] > button {
        width: 100%;
        border-radius: 12px !important;
        border: 1px solid rgba(148, 163, 184, 0.36) !important;
        background: #fff !important;
        color: var(--ink-900) !important;
        font-weight: 700 !important;
        box-shadow: 0 6px 15px rgba(15, 23, 42, 0.05) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        border-color: rgba(15, 23, 42, 0.26) !important;
    }
    .stButton > button[kind="primary"] {
        border: 0 !important;
        background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
        color: #fff !important;
    }

    input, textarea, select {
        color: var(--ink-900) !important;
        caret-color: var(--accent-2);
    }
    div[data-baseweb="input"], div[data-baseweb="base-input"],
    div[data-baseweb="select"], div[data-baseweb="textarea"] {
        background-color: #fff !important;
        border: 1px solid rgba(148, 163, 184, 0.5) !important;
        border-radius: 12px !important;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
    }

    section[data-testid="stFileUploader"] {
        background-color: #f8fafc !important;
        border: 1px dashed rgba(37, 99, 235, 0.4) !important;
        border-radius: 12px !important;
    }
    .stImage > img {
        border-radius: 12px;
        box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12);
    }
</style>
""", unsafe_allow_html=True)

# Auto-refresh every 30 seconds
st.markdown("""
<script>
    setTimeout(function(){ window.location.reload(); }, 30000);
</script>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def load_posts():
    local_posts = []
    if POSTS_DIR.exists():
        for f in sorted(POSTS_DIR.glob("*.md")):
            if f.name in DEPRECATED_SAMPLE_FILES:
                continue
            content = f.read_text(encoding="utf-8")
            meta = {"file": f, "filename": f.name}
            lines = content.split("\n")
            text_lines = []
            in_content = False
            for line in lines:
                if line.startswith("<!-- date:"):
                    meta["date"] = line.replace("<!-- date:", "").replace("-->", "").strip()
                elif line.startswith("<!-- image:"):
                    meta["image"] = line.replace("<!-- image:", "").replace("-->", "").strip()
                elif line.startswith("<!-- status:"):
                    meta["status"] = line.replace("<!-- status:", "").replace("-->", "").strip()
                elif line.startswith("<!-- feedback:"):
                    meta["feedback"] = line.replace("<!-- feedback:", "").replace("-->", "").strip()
                elif line.startswith("<!-- revisions:"):
                    meta["revisions"] = line.replace("<!-- revisions:", "").replace("-->", "").strip()
                elif line.startswith("<!-- subject:"):
                    meta["subject"] = line.replace("<!-- subject:", "").replace("-->", "").strip()
                elif line.startswith("<!-- time:"):
                    meta["time"] = line.replace("<!-- time:", "").replace("-->", "").strip()
                elif line.strip() == "---CONTENT---":
                    in_content = True
                elif line.strip() == "---END---":
                    in_content = False
                elif in_content:
                    text_lines.append(line)
            
            full_text = "\n".join(text_lines).strip()
            meta["text"] = full_text
            if "subject" not in meta and full_text:
                 meta["subject"] = full_text.split("\n")[0].strip()[:50]
            local_posts.append(meta)

    # 2. Get Cloud Posts from Firebase
    cloud_posts = fm.get_all_posts() if fm.is_active() else []
    
    # 3. Merge: LOCAL file is always the source of truth for content
    merged = {}
    
    # First, fill with local
    for p in local_posts:
        merged[p["filename"]] = p
        
    # Then, supplement with cloud metadata (but NEVER overwrite local text/status)
    for cp in cloud_posts:
        fname = cp.get("filename")
        if not fname: continue
        if fname in DEPRECATED_SAMPLE_FILES:
            continue
        
        if fname in merged:
            # Local file exists — keep local text, status, and file path
            # Only add cloud-only fields (e.g., analytics) that local doesn't have
            for key, val in cp.items():
                if key not in merged[fname] or merged[fname][key] is None:
                    merged[fname][key] = val
        else:
            # Cloud-only post (no local file) — use cloud data as-is
            merged[fname] = cp

    return sorted(merged.values(), key=lambda x: x.get("date", "9999-99-99"))


def update_post_metadata(filepath, status=None, feedback=None, image=None, subject=None, date=None, time=None):
    path = Path(filepath)
    lines = path.read_text(encoding="utf-8").split("\n")
    new_lines = []
    
    # Track which fields we found to update
    found = {
        "status": False, "feedback": False, "image": False,
        "subject": False, "date": False, "time": False
    }

    # Helper to check if we should update a line
    for line in lines:
        updated_line = line
        
        if line.startswith("<!-- status:") and status is not None:
            updated_line = f"<!-- status: {status} -->"
            found["status"] = True
        elif line.startswith("<!-- feedback:") and feedback is not None:
            updated_line = f"<!-- feedback: {feedback} -->"
            found["feedback"] = True
        elif line.startswith("<!-- image:") and image is not None:
            updated_line = f"<!-- image: {image} -->"
            found["image"] = True
        elif line.startswith("<!-- subject:") and subject is not None:
            updated_line = f"<!-- subject: {subject} -->"
            found["subject"] = True
        elif line.startswith("<!-- date:") and date is not None:
            updated_line = f"<!-- date: {date} -->"
            found["date"] = True
        elif line.startswith("<!-- time:") and time is not None:
            updated_line = f"<!-- time: {time} -->"
            found["time"] = True
            
        new_lines.append(updated_line)

    # If new fields weren't found, insert them at the top
    insert_idx = 0
    if subject is not None and not found["subject"]:
        new_lines.insert(insert_idx, f"<!-- subject: {subject} -->")
    if date is not None and not found["date"]:
        new_lines.insert(insert_idx, f"<!-- date: {date} -->")
    if time is not None and not found["time"]:
        new_lines.insert(insert_idx, f"<!-- time: {time} -->")
    
    # Append feedback if it's new
    if feedback is not None and not found["feedback"]:
        # Find where to append feedback (try to keep it near status)
        inserted_fb = False
        final = []
        for line in new_lines:
            final.append(line)
            if line.startswith("<!-- status:"):
                final.append(f"<!-- feedback: {feedback} -->")
                inserted_fb = True
        if not inserted_fb:
            final.insert(0, f"<!-- feedback: {feedback} -->")
        new_lines = final

    # Final write to local file
    path.write_text("\n".join(new_lines), encoding="utf-8")

    # 🔥 Sync to Firebase
    if fm.is_active():
        # Reload metadata to get the full object for syncing
        updated_posts = load_posts()
        for p in updated_posts:
            if p["filename"] == path.name:
                # Remove Path object before syncing
                sync_p = p.copy()
                if "file" in sync_p: sync_p["file"] = str(sync_p["file"])
                fm.sync_post(sync_p)
                break


def update_post_content(filepath, new_text):
    path = Path(filepath)
    lines = path.read_text(encoding="utf-8").split("\n")
    try:
        si, ei = -1, -1
        for i, line in enumerate(lines):
            if line.strip() == "---CONTENT---":
                si = i
            elif line.strip() == "---END---":
                ei = i
        if si != -1 and ei != -1:
            path.write_text("\n".join(lines[:si+1] + [new_text.strip()] + lines[ei:]), encoding="utf-8")
            
            # 🔥 Sync to Firebase
            if fm.is_active():
                updated_posts = load_posts()
                for p in updated_posts:
                    if p["filename"] == path.name:
                        sync_p = p.copy()
                        if "file" in sync_p: sync_p["file"] = str(sync_p["file"])
                        fm.sync_post(sync_p)
                        break
            return True
    except Exception as e:
        st.error(f"Error: {e}")
    return False


def log_feedback(filename, feedback_text, action):
    log = []
    if FEEDBACK_LOG.exists():
        try:
            log = json.loads(FEEDBACK_LOG.read_text(encoding="utf-8"))
        except:
            log = []
    log.append({
        "file": filename,
        "feedback": feedback_text,
        "action": action,
        "timestamp": datetime.now().isoformat(),
        "resolved": False
    })
    FEEDBACK_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # 🔥 Sync to Firebase
    if fm.is_active():
        fm.log_event("feedback", f"Action: {action} on {filename}", {
            "file": filename,
            "feedback": feedback_text,
            "action": action
        })



def trigger_publish():
    try:
        result = subprocess.run(
            ["python3", PUBLISHER_SCRIPT, "publish-all-pending"],
            capture_output=True, text=True
        )
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)


def is_draft(post):
    return post.get("status", "pending") == "pending"


def is_protected_post(post):
    return False


def delete_post_everywhere(post):
    filename = post.get("filename", "")

    deleted_local = False
    file_path = post.get("file")
    if file_path:
        try:
            local_path = Path(file_path)
            if local_path.exists():
                local_path.unlink()
                deleted_local = True
        except Exception as e:
            return False, f"Local delete failed: {e}"

    if fm.is_active() and filename:
        try:
            fm.db.collection("posts").document(filename).delete()
        except Exception as e:
            if not deleted_local:
                return False, f"Cloud delete failed: {e}"

    if deleted_local or (fm.is_active() and filename):
        return True, "Deleted"
    return False, "No deletable source found"


# ──────────────────────────────────────────────
# Load Data
# ──────────────────────────────────────────────
posts = load_posts()
total = len(posts)
approved = sum(1 for p in posts if p.get("status") == "approved")
rejected = sum(1 for p in posts if p.get("status") == "rejected")
pending = sum(1 for p in posts if p.get("status", "pending") == "pending")
published = sum(1 for p in posts if p.get("status") == "published")


# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────
with st.sidebar:
    # Logo / Brand
    st.markdown("""
    <div style="padding: 18px 0 12px 0;">
        <div style="font-size: 0.7rem; letter-spacing: 1.8px; text-transform: uppercase; color: #94a3b8;">DaoAI Workflow</div>
        <div style="font-size: 1.55rem; font-weight: 800; margin-top: 4px; color: #f8fafc;">
            LinkedIn Studio
        </div>
        <div style="font-size: 0.78rem; color: #cbd5e1; margin-top: 4px; line-height: 1.5;">
            Content pipeline control center
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Progress
    if total > 0:
        progress = (approved + published) / total
        st.progress(progress)
        st.caption(f"Pipeline Ready: {int(progress*100)}%")
    
    st.markdown("---")
    
    # Stats Grid
    st.markdown(f"""
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
        <div class="sidebar-stat">
            <div class="sidebar-stat-value">{total}</div>
            <div class="sidebar-stat-label">Total</div>
        </div>
        <div class="sidebar-stat">
            <div class="sidebar-stat-value" style="color: #fbbf24;">{pending}</div>
            <div class="sidebar-stat-label">Pending</div>
        </div>
        <div class="sidebar-stat">
            <div class="sidebar-stat-value" style="color: #4ade80;">{approved}</div>
            <div class="sidebar-stat-label">Approved</div>
        </div>
        <div class="sidebar-stat">
            <div class="sidebar-stat-value" style="color: #60a5fa;">{published}</div>
            <div class="sidebar-stat-label">Published</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if rejected > 0:
        st.markdown(f"""
        <div style="margin-top: 12px; padding: 10px 14px; background: rgba(239,68,68,0.1);
             border: 1px solid rgba(239,68,68,0.2); border-radius: 10px; text-align: center;">
            <span style="color: #f87171; font-weight: 600;">Rejected: {rejected}</span>
            <div style="color: #94a3b8; font-size: 0.7rem; margin-top: 2px;">AI revising...</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Check for recently revised posts
    revised_posts = [p for p in posts if p.get("revisions") and int(p.get("revisions", 0)) > 0 and p.get("status") == "pending"]
    if revised_posts:
        st.success(f"{len(revised_posts)} revised — please review!")
    
    # Check for recently regenerated images
    try:
        if FEEDBACK_LOG.exists():
            fb_log = json.loads(FEEDBACK_LOG.read_text(encoding="utf-8"))
            now = datetime.now()
            recent_imgs = []
            for entry in fb_log:
                if entry.get("resolution") == "image regenerated" and entry.get("resolved_at"):
                    resolved_time = datetime.fromisoformat(entry["resolved_at"])
                    if (now - resolved_time).total_seconds() < 300:
                        recent_imgs.append(entry.get("file", ""))
            if recent_imgs:
                st.balloons()
                st.success(f"{len(recent_imgs)} images updated!")
    except:
        pass
    
    st.markdown("---")
    if st.button("Refresh Dashboard", use_container_width=True):
        st.rerun()


# ──────────────────────────────────────────────
# Post Card Renderer
# ──────────────────────────────────────────────
def render_post_card(post, prefix="", allow_delete=False, draft_delete_only=False):
    status = post.get("status", "pending")
    k = f"{prefix}_{post['filename']}"
    can_delete = allow_delete and (not draft_delete_only or is_draft(post)) and not is_protected_post(post)
    with st.container(border=True):
        col_img, col_content, col_del = st.columns([1, 2, 0.2], gap="large")

        with col_del:
            if can_delete and st.button("🗑️", key=f"del_post_{k}", help="Delete this post"):
                ok, msg = delete_post_everywhere(post)
                if ok:
                    st.toast(f"Deleted: {post['filename']}")
                    time.sleep(0.6)
                    st.rerun()
                else:
                    st.error(msg)

        with col_img:
            img_path = post.get("image", "")
            if img_path and os.path.exists(img_path):
                st.image(img_path, use_container_width=True)
                if st.button("Delete Image", key=f"del_img_{k}"):
                    update_post_metadata(post["file"], image="NONE")
                    st.rerun()
            else:
                st.markdown("""
                <div style="background: rgba(99,102,241,0.08); border: 1px dashed rgba(99,102,241,0.3);
                     border-radius: 12px; padding: 40px 16px; text-align: center; color: #64748b;">
                    <div style="font-size: 0.8rem;">No image attached</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Metadata Display
            st.markdown(f"""
            <div style="margin-top: 12px; display: flex; flex-direction: column; gap: 4px;">
                <div style="display: flex; align-items: center; gap: 6px; color: #64748b; font-size: 0.85rem;">
                    <strong>Date:</strong> <strong>{post.get('date', 'TBD')}</strong>
                </div>
                <div style="display: flex; align-items: center; gap: 6px; color: #64748b; font-size: 0.85rem;">
                    <strong>Time:</strong> <span>{post.get('time', '09:00 AM')}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            badge = f"status-{status}"
            st.markdown(f'<div style="margin-top: 8px;"><span class="status-badge {badge}">{status.upper()}</span></div>', unsafe_allow_html=True)
            st.caption(f"File: {post.get('filename', 'unknown')}")

            # Image Upload
            uploaded = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg", "webp"], key=f"img_{k}", label_visibility="collapsed")
            if uploaded:
                save_dir = POSTS_DIR / "images"
                save_dir.mkdir(exist_ok=True)
                save_path = save_dir / f"{post['filename'].replace('.md', '')}_{uploaded.name}"
                save_path.write_bytes(uploaded.read())
                update_post_metadata(post["file"], image=str(save_path.resolve()))
                st.toast("✅ Image updated!")
                st.rerun()
            
            if img_path and os.path.exists(img_path):
                img_pop = st.popover("Image Feedback", use_container_width=True)
                with img_pop:
                    img_fb = st.text_area("Tell AI how to change the image", key=f"imgfb_{k}", height=80,
                                          placeholder="e.g. use real product photo, background too dark...")
                    if st.button("Submit Feedback", key=f"imgsub_{k}"):
                        log_feedback(post["filename"], f"[IMAGE] {img_fb}", "image_feedback")
                        st.toast("📨 Feedback sent!")

        with col_content:
            # Editable Subject
            subject_val = st.text_input("Subject", value=post.get("subject", "Untitled"), key=f"subj_{k}")
            if subject_val != post.get("subject", "Untitled"):
                 update_post_metadata(post["file"], subject=subject_val)
                 st.rerun()

            # Metadata Row (Date & Time)
            md1, md2 = st.columns(2)
            with md1:
                date_str = post.get("date", datetime.now().strftime("%Y-%m-%d"))
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                except:
                    date_obj = datetime.now().date()
                
                new_date = st.date_input("Date", value=date_obj, key=f"date_{k}")
                if str(new_date) != date_str:
                    update_post_metadata(post["file"], date=str(new_date))
                    st.rerun()
            
            with md2:
                time_str = post.get("time", "09:00")
                try:
                    time_obj = datetime.strptime(time_str, "%H:%M").time()
                except:
                    try:
                        time_obj = datetime.strptime(time_str.split(" ")[0], "%H:%M").time()
                    except:
                        time_obj = datetime.strptime("09:00", "%H:%M").time()

                new_time = st.time_input("Time", value=time_obj, key=f"time_{k}")
                new_time_str = new_time.strftime("%H:%M")
                if new_time_str != time_str:
                    update_post_metadata(post["file"], time=new_time_str)
                    st.rerun()

            revisions = post.get("revisions")
            revised_at = post.get("revised_at")
            if revisions and int(revisions) > 0:
                st.success(f"AI Revised (v{int(revisions)+1}) • {revised_at}")

            text_val = st.text_area(
                "Content", value=post.get("text", ""),
                height=180, key=f"txt_{k}",
                label_visibility="collapsed"
            )

            ac1, ac2, ac3, ac4 = st.columns(4)
            with ac1:
                if status == "approved":
                    if st.button("Publish Now", key=f"pub_{k}", type="primary", use_container_width=True):
                        with st.spinner("Publishing..."):
                            try:
                                res = subprocess.run(
                                    ["python3", "linkedin_publisher.py", "publish", post["file"]],
                                    capture_output=True, text=True
                                )
                                if "Published!" in res.stdout:
                                    st.success("Published!")
                                    st.balloons()
                                    update_post_metadata(post["file"], status="published")
                                    time.sleep(1.5)
                                    st.rerun()
                                else:
                                    st.error(f"Failed: {res.stdout}")
                            except Exception as e:
                                st.error(f"Error: {e}")
                
                elif status != "published":
                    if st.button("Approve", key=f"app_{k}", type="primary", use_container_width=True):
                        update_post_metadata(post["file"], status="approved", feedback="")
                        st.rerun()
            with ac2:
                if st.button("💾 Save", key=f"save_{k}", use_container_width=True):
                    if update_post_content(post["file"], text_val):
                        # Subject is verified by change detection above, but we save text here
                        st.toast("Saved!")
                        st.rerun()
            with ac3:
                popover = st.popover("Reject", use_container_width=True)
                with popover:
                    fb = st.text_area("Rejection feedback for AI", key=f"fb_{k}", height=100,
                                      placeholder="e.g. too salesy, make it more technical...")
                    if st.button("Submit", key=f"sub_{k}"):
                        update_post_metadata(post["file"], status="rejected", feedback=fb)
                        log_feedback(post["filename"], fb, "rejected")
                        
                        # ── Call Gemini DIRECTLY (bypass agent for reliability) ──
                        with st.spinner("AI is revising based on your feedback..."):
                            try:
                                import google.generativeai as genai
                                api_key = os.environ.get("GEMINI_API_KEY", "")
                                if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
                                    api_key = st.secrets["GEMINI_API_KEY"]
                                if not api_key:
                                    api_key = "AIzaSyBqQF9-ivsvkAjbGhb-OIvDv6dbtBmK38M"
                                
                                genai.configure(api_key=api_key)
                                model = genai.GenerativeModel("gemini-2.0-flash")
                                
                                original_text = post.get("text", "")
                                prompt = f"""You are a LinkedIn content writer for DaoAI, a company that makes AI-powered AOI (Automated Optical Inspection) machines for PCBA manufacturing.

The user REJECTED the following LinkedIn post and provided feedback. 
Revise the post according to their feedback. Keep the same general topic and intent.

RULES:
- Write in English only
- Keep it professional and engaging for LinkedIn
- Keep roughly the same length (slightly shorter is OK)
- Do NOT include any markdown formatting — plain text only
- STRICTLY follow the user's feedback instructions

ORIGINAL POST:
{original_text}

USER FEEDBACK:
{fb}

Write ONLY the revised post text. No explanations, no headers, just the post content ready to publish."""

                                response = model.generate_content(prompt)
                                revised = response.text.strip()
                                
                                if len(revised) > 50:
                                    # Write revised content back to the file
                                    if update_post_content(post["file"], revised):
                                        update_post_metadata(post["file"], status="pending", feedback=fb)
                                        st.success(f"AI has revised the post! ({len(revised)} chars)")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error("Failed to save revised content.")
                                else:
                                    st.error(f"AI returned a response too short ({len(revised)} chars). Please try again.")
                            except Exception as e:
                                st.error(f"AI revision error: {e}")

            if post.get("feedback"):
                st.info(f"{post['feedback']}")


# ──────────────────────────────────────────────
# Brainstorming Entry
# ──────────────────────────────────────────────
if st.button("Brainstorming Room", type="primary", use_container_width=True):
    st.session_state.show_brainstorm = True

if st.session_state.get("show_brainstorm", False):
    # Render Brainstorming Room Overlay / View
    st.markdown("---")
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("### Brainstorming Room")
    with c2:
        if st.button("Close Room", use_container_width=True):
            st.session_state.show_brainstorm = False
            st.rerun()

    # Integrated Content Placeholder
    import linkedin_planner
    
    # 1. Discussion & Strategy
    with st.container(border=True):
        st.markdown("**AI Content Strategist**")
        feedback = st.text_input("Refine Strategy (e.g., 'Focus more on technical ROI')", key="brain_feedback")
        if st.button("Generate 10 New Topics", use_container_width=True):
            with st.spinner("Analyzing data & generating topics..."):
                linkedin_planner.generate_brainstorm_topics(feedback)
                st.rerun()

    # 2. Topic List & 2-Week Calendar
    if Path(linkedin_planner.BRAINSTORM_FILE).exists():
        topics = json.loads(Path(linkedin_planner.BRAINSTORM_FILE).read_text(encoding="utf-8"))
        
        st.markdown("#### 2-Week Strategy Plan")
        for i, t in enumerate(topics):
            col1, col2, col3 = st.columns([1, 4, 1])
            with col1: st.write(f"`{t['date']}`")
            with col2: st.write(f"**{t['topic']}**")
            with col3: 
                if st.button("Rethink", key=f"rethink_{i}"):
                    linkedin_planner.regenerate_single_topic(i, feedback)
                    st.rerun()
        
        if st.button("Finalize & Move to Planning", type="primary", use_container_width=True):
            count = linkedin_planner.convert_to_planning(topics)
            st.success(f"Moved {count} posts to Planning tab!")
            st.session_state.show_brainstorm = False
            time.sleep(2)
            st.rerun()
    else:
        st.info("No active brainstorming session. Click above to start.")

    st.markdown("---")


# ──────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────
tab_all, tab_planning, tab_approved, tab_rejected, tab_analytics, tab_lab, tab_growth = st.tabs([
    f"All ({total})", f"Planning ({pending})",
    f"Approved ({approved})", f"Rejected ({rejected})",
    "Strategic Analytics", "Image Lab", "Growth & Engagement"
])


# ──────────────────────────────────────────────
# Tab: All Posts
# ──────────────────────────────────────────────
with tab_all:
    draft_posts = [p for p in posts if is_draft(p)]
    c_pub, c_del = st.columns([4, 1])
    with c_pub:
        if st.button("Publish All Approved", type="primary", use_container_width=True):
            with st.spinner("Publishing..."):
                log = trigger_publish()
                st.code(log)
                time.sleep(2)
                st.rerun()
    with c_del:
        clear_label = f"🗑️ 清除全部 Draft ({len(draft_posts)})"
        if st.button(clear_label, type="primary", help="One-click delete all drafts", disabled=len(draft_posts) == 0):
            deleted = 0
            failed = 0
            for p in draft_posts:
                ok, _ = delete_post_everywhere(p)
                if ok:
                    deleted += 1
                else:
                    failed += 1
            if deleted:
                st.toast(f"Deleted {deleted} drafts")
            if failed:
                st.warning(f"{failed} drafts could not be deleted.")
            time.sleep(0.8)
            st.rerun()

    st.caption("One-by-one delete is available on every tab. Bulk clear only removes drafts.")
    for p in posts:
        render_post_card(p, prefix="all", allow_delete=True, draft_delete_only=False)

with tab_planning:
    plist = [p for p in posts if p.get("status", "pending") == "pending"]
    if not plist:
        st.info("No planned posts.")
    for p in plist:
        render_post_card(p, prefix="pnd", allow_delete=True)

with tab_approved:
    alist = [p for p in posts if p.get("status") == "approved"]
    if not alist:
        st.info("No approved posts.")
    for p in alist:
        render_post_card(p, prefix="apr", allow_delete=True)

with tab_rejected:
    rlist = [p for p in posts if p.get("status") == "rejected"]
    if not rlist:
        st.info("No rejected posts.")
    for p in rlist:
        render_post_card(p, prefix="rej", allow_delete=True)


# ──────────────────────────────────────────────
# Tab: Analytics & Plan
# ──────────────────────────────────────────────
with tab_analytics:
    
    # Header Row
    h_col1, h_col2 = st.columns([4, 1])
    with h_col1:
        st.markdown('<div class="section-title">Channel Performance</div>', unsafe_allow_html=True)
    with h_col2:
        if st.button("Check Access & Org Name", use_container_width=True):
            with st.spinner("Checking permissions..."):
                try:
                    if hasattr(st, "secrets"):
                        for key, value in st.secrets.items():
                            os.environ[str(key)] = str(value)
                    
                    import io
                    import sys
                    captured_output = io.StringIO()
                    sys.stdout = captured_output
                    
                    import check_linkedin_access
                    import importlib
                    importlib.reload(check_linkedin_access)
                    check_linkedin_access.main()
                    
                    sys.stdout = sys.__stdout__
                    debug_log = captured_output.getvalue()
                    
                    st.info("LinkedIn Access Report")
                    st.code(debug_log)
                except Exception as e:
                    st.error(f"Failed: {e}")

        if st.button("Sync Data (Debug Mode)", use_container_width=True):
            with st.spinner("Fetching (Debug Mode)..."):
                try:
                    # Inject secrets
                    if hasattr(st, "secrets"):
                        for key, value in st.secrets.items():
                            os.environ[str(key)] = str(value)
                    
                    # Capture stdout to show on UI
                    import io
                    import sys
                    captured_output = io.StringIO()
                    sys.stdout = captured_output
                    
                    import linkedin_analytics
                    import importlib
                    importlib.reload(linkedin_analytics)
                    linkedin_analytics.main()
                    
                    # Restore stdout
                    sys.stdout = sys.__stdout__
                    debug_log = captured_output.getvalue()
                    
                    st.success("Sync Finished!")
                    st.expander("Show Debug Logs", expanded=True).code(debug_log)
                    
                    time.sleep(5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    # Load Data
    analytics_file = Path("linkedin_analytics_data.json")
    if analytics_file.exists():
        with open(analytics_file, "r") as f:
            data = json.load(f)
        
        if data:
            df = pd.DataFrame(data)
            df["Engagement"] = df["likes"] + df["comments"]
            
            if "impressions" not in df.columns:
                df["impressions"] = 0
            if "clicks" not in df.columns:
                df["clicks"] = 0
            
            # Fix: Handle NaNs explicitly
            df["impressions"] = df["impressions"].fillna(0).astype(int)
            df["clicks"] = df["clicks"].fillna(0).astype(int)
            
            df["ER"] = df.apply(
                lambda x: (x["Engagement"] / x["impressions"] * 100) if x["impressions"] > 0 else 0, 
                axis=1
            )
            df["CTR"] = df.apply(
                lambda x: (x["clicks"] / x["impressions"] * 100) if x["impressions"] > 0 else 0, 
                axis=1
            )

            total_posts_count = len(df)
            total_impressions = int(df["impressions"].sum())
            total_engagement = int(df["Engagement"].sum())
            avg_er = df["ER"].mean()
            
            # ── KPI Cards (HTML) ──
            st.markdown(f"""
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 16px 0 28px 0;">
                <div class="kpi-card">
                    <div class="kpi-label" style="font-size: 0.7rem;">CONTENT</div>
                    <div class="kpi-value">{total_posts_count}</div>
                    <div class="kpi-label">Total Posts</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label" style="font-size: 0.7rem;">REACH</div>
                    <div class="kpi-value blue">{total_impressions:,}</div>
                    <div class="kpi-label">Total Impressions</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label" style="font-size: 0.7rem;">ENGAGE</div>
                    <div class="kpi-value green">{total_engagement}</div>
                    <div class="kpi-label">Total Engagement</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label" style="font-size: 0.7rem;">GROWTH</div>
                    <div class="kpi-value amber">{avg_er:.2f}%</div>
                    <div class="kpi-label">Avg Engagement Rate</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # ── Charts ──
            col_chart, col_top = st.columns([3, 2], gap="large")
            
            with col_chart:
                st.markdown('<div class="section-title" style="font-size:1.1rem; margin-top:0;">Engagement by Post</div>', unsafe_allow_html=True)
                
                # Shorten names for chart
                chart_df = df.copy()
                chart_df["short_name"] = chart_df["name"].apply(lambda x: x[:50] + "..." if len(x) > 50 else x)
                chart_df = chart_df.sort_values("ER", ascending=False).head(8)
                
                st.bar_chart(
                    chart_df.set_index("short_name")[["likes", "comments"]],
                    height=320,
                    color=["#818cf8", "#34d399"]
                )
            
            with col_top:
                st.markdown('<div class="section-title" style="font-size:1.1rem; margin-top:0;">Top Performers</div>', unsafe_allow_html=True)
                
                top_df = df.sort_values("ER", ascending=False).head(3)
                medals = ["1st", "2nd", "3rd"]
                for idx, (_, row) in enumerate(top_df.iterrows()):
                    short_title = row['name'][:60] + "..." if len(row['name']) > 60 else row['name']
                    er_val = row['ER']
                    imp_val = int(row['impressions'])
                    
                    st.markdown(f"""
                    <div style="background: rgba(255,255,255,0.6); border: 1px solid rgba(255,255,255,0.8);
                         border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                            <span style="font-size: 1.2rem;">{medals[idx]}</span>
                            <span style="color: #334155; font-weight: 600; font-size: 0.82rem; line-height: 1.3;">{short_title}</span>
                        </div>
                        <div style="display: flex; gap: 16px; font-size: 0.75rem; color: #64748b;">
                            <span>👁️ {imp_val:,} views</span>
                            <span>❤️ {int(row['likes'])} likes</span>
                            <span>📊 {er_val:.1f}% ER</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            # ── Data Table ──
            st.markdown('<div class="section-title" style="font-size:1.1rem;">📋 Detailed Performance</div>', unsafe_allow_html=True)
            
            display_df = df[["name", "impressions", "clicks", "likes", "comments", "ER", "fetched_at"]].sort_values("ER", ascending=False).copy()
            display_df["impressions"] = display_df["impressions"].astype(int)
            display_df["clicks"] = display_df["clicks"].astype(int)
            
            st.dataframe(
                display_df,
                column_config={
                    "name": st.column_config.TextColumn("Post Title", width="large"),
                    "impressions": st.column_config.NumberColumn("👁️ Impressions", format="%d"),
                    "clicks": st.column_config.NumberColumn("🔗 Clicks", format="%d"),
                    "likes": st.column_config.NumberColumn("❤️ Likes", format="%d"),
                    "comments": st.column_config.NumberColumn("💬 Comments", format="%d"),
                    "ER": st.column_config.ProgressColumn(
                        "📊 ER %", 
                        format="%.1f%%", 
                        min_value=0, 
                        max_value=max(df["ER"].max() * 1.2, 5)
                    ),
                    "fetched_at": st.column_config.TextColumn("Updated", width="small")
                },
                hide_index=True,
                use_container_width=True,
                height=400
            )
            
            # ── AI Content Strategist ──
            st.markdown("---")
            st.markdown('<div class="section-title" style="font-size:1.1rem;">🤖 AI Content Strategist</div>', unsafe_allow_html=True)
            
            with st.container(border=True):
                cs1, cs2 = st.columns([1, 5])
                with cs1:
                    if st.button("✨ Auto-Generate", type="primary", use_container_width=True, key="btn_autopilot"):
                        with st.spinner("Analyzing trends & drafting new content..."):
                            try:
                                # Inject secrets directly
                                if hasattr(st, "secrets"):
                                    for key, value in st.secrets.items():
                                        os.environ[str(key)] = str(value)
                                
                                import linkedin_planner
                                import importlib
                                importlib.reload(linkedin_planner)
                                result = linkedin_planner.generate_strategic_plan()
                                
                                if result and result.startswith("✅"):
                                    st.success(result)
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error(f"Failed: {result}")
                            except Exception as e:
                                st.error(f"Error: {e}")

                with cs2:
                    st.markdown("""
                    <div style="color: #64748b; font-size: 0.85rem; padding-top: 6px;">
                        Analyze top-performing content (views/likes) and automatically write 3 new drafts based on winning themes.
                    </div>
                    """, unsafe_allow_html=True)
            
            plan_file = POSTS_DIR / "plan.md"
            if plan_file.exists():
                with st.expander("📄 View Strategy Report", expanded=False):
                    st.markdown(plan_file.read_text(encoding="utf-8"))
        else:
            st.info("No analytics data found. Click 'Sync Data' to fetch.")
    else:
        st.info("No analytics data yet. Click 'Sync Data' to start tracking.")


# ──────────────────────────────────────────────
# Image Lab Tab
# ──────────────────────────────────────────────
with tab_lab:
    st.markdown('<div class="section-title">🎨 AI Image Lab</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="color: #94a3b8; font-size: 0.85rem; margin-bottom: 16px;">
        Generate AI images for your LinkedIn posts. Choose a provider below.
    </div>
    """, unsafe_allow_html=True)
    
    provider = st.radio("Provider", ["Off", "OpenAI (DALL-E 3)", "Pollinations AI (Free)", "Lorem Picsum (Random)"], horizontal=True)
    
    if "lab_img_url" not in st.session_state:
        st.session_state.lab_img_url = None
    if "lab_img_bytes" not in st.session_state:
        st.session_state.lab_img_bytes = None
    
    openai_key = ""
    if provider == "OpenAI (DALL-E 3)":
        openai_key = st.text_input("OpenAI API Key", type="password", key="openai_key_input")
        if not openai_key:
            st.info("Enter your API Key to enable DALL-E 3")
    
    st.markdown("---")
    
    c1, c2 = st.columns([3, 1])
    with c1:
        prompt = st.text_input("Prompt (English)", "Futuristic PCBA manufacturing factory, 4k, cinematic lighting")
    with c2:
        generate_btn = st.button("✨ Generate", type="primary", use_container_width=True, disabled=(provider=="Off"), key="lab_gen")
    
    if generate_btn and prompt and provider != "Off":
        with st.spinner("Generating..."):
            try:
                resp_content = None
                img_url = None
                
                if provider == "Pollinations AI (Free)":
                    encoded = urllib.parse.quote(prompt)
                    img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=600&model=flux&seed={int(time.time())}"
                    resp = requests.get(img_url, timeout=30)
                    if resp.status_code == 200:
                        resp_content = resp.content
                    else:
                        st.error(f"Pollinations Error: {resp.status_code}")

                elif provider == "Lorem Picsum (Random)":
                    img_url = f"https://picsum.photos/1024/600?random={int(time.time())}"
                    resp = requests.get(img_url, timeout=10, allow_redirects=True)
                    if resp.status_code == 200:
                        resp_content = resp.content
                        img_url = resp.url
                
                elif provider == "OpenAI (DALL-E 3)":
                    if not openai_key:
                        st.error("Missing OpenAI API Key")
                    else:
                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {openai_key}"
                        }
                        api_data = {
                            "model": "dall-e-3",
                            "prompt": prompt,
                            "n": 1,
                            "size": "1024x1024"
                        }
                        res = requests.post("https://api.openai.com/v1/images/generations", headers=headers, json=api_data, timeout=60)
                        if res.status_code == 200:
                            img_url = res.json()["data"][0]["url"]
                            img_resp = requests.get(img_url)
                            resp_content = img_resp.content
                        else:
                            st.error(f"OpenAI Error: {res.text}")

                if resp_content:
                    st.session_state.lab_img_url = img_url
                    st.session_state.lab_img_bytes = resp_content
                
            except Exception as e:
                st.error(f"Error: {e}")

    if st.session_state.lab_img_bytes:
        st.image(st.session_state.lab_img_bytes, caption="Generated Image", use_container_width=True)
        
        st.markdown("#### Save Image")
        c_sel, c_btn = st.columns([3, 1])
        with c_sel:
            selected_post = st.selectbox("Apply to post", [p['filename'] for p in posts], key="lab_sel")
        with c_btn:
            if st.button("Apply", key="lab_save", use_container_width=True):
                save_dir = POSTS_DIR / "images"
                save_dir.mkdir(exist_ok=True)
                save_path = save_dir / f"lab_{int(time.time())}.jpg"
                save_path.write_bytes(st.session_state.lab_img_bytes)
                
                target_file = POSTS_DIR / selected_post
                update_post_metadata(target_file, image=str(save_path.resolve()))
                st.success(f"Applied to {selected_post}!")
                time.sleep(2)
                st.rerun()
# ──────────────────────────────────────────────
# Growth & Engagement Tab
# ──────────────────────────────────────────────
with tab_growth:
    st.markdown('<div class="section-title">Growth & Engagement Center</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="color: #64748b; font-size: 0.9rem; margin-bottom: 24px;">
        Integrate human-like automation to boost your LinkedIn reach and authority.
    </div>
    """, unsafe_allow_html=True)

    # ── KPI Row ──
    st.markdown(f"""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px;">
        <div class="kpi-card">
            <div class="kpi-label" style="font-size: 0.7rem;">ACTION</div>
            <div class="kpi-value">1,248</div>
            <div class="kpi-label">Actions Taken</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label" style="font-size: 0.7rem;">REACH</div>
            <div class="kpi-value green">852</div>
            <div class="kpi-label">Accounts Reached</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label" style="font-size: 0.7rem;">HOT</div>
            <div class="kpi-value amber">12.4%</div>
            <div class="kpi-label">Engagement Rate</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label" style="font-size: 0.7rem;">SAFE</div>
            <div class="kpi-value">98/100</div>
            <div class="kpi-label">Safety Score</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_stream, col_settings = st.columns([2, 1], gap="large")

    with col_stream:
        st.markdown('<div class="section-title" style="font-size:1.2rem; margin-top:0;">Live Engage Stream</div>', unsafe_allow_html=True)
        
        # Bot Status Badge
        st.markdown("""
        <div style="background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 12px; padding: 12px 16px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between;">
            <div style="color: #0369a1; font-weight: 600; font-size: 0.9rem;">
                <span style="display: inline-block; width: 8px; height: 8px; background: #10b981; border-radius: 50%; margin-right: 8px; box-shadow: 0 0 8px #10b981;"></span>
                Bot Status: ACTIVE
            </div>
            <div style="color: #64748b; font-size: 0.8rem;">Session duration: 1h 24m</div>
        </div>
        """, unsafe_allow_html=True)

        # Mock Logs
        logs = [
            {"msg": "Post summarized: 'The future of PCBA manufacturing...'", "action": "COMMENTED (Insightful tone) • 2m ago", "type": "success"},
            {"msg": "Post summarized: 'New AI chips from NVIDIA...'", "action": "LIKED & REPOSTED (Professional tone) • 15m ago", "type": "success"},
            {"msg": "ENGAGE_SKIP: Already interacted with this URN.", "action": "SKIPPED • 45m ago", "type": "info"},
            {"msg": "Searching for new relevant posts in 'PCBA Assembly' niche...", "action": "SCROLLING • 1h ago", "type": "neutral"},
        ]

        for log in logs:
            bg = "#f8fafc" if log["type"] != "info" else "#f1f5f9"
            border = "#e2e8f0"
            text_color = "#334155" if log["type"] != "info" else "#94a3b8"
            
            st.markdown(f"""
            <div style="background: {bg}; border: 1px solid {border}; border-radius: 12px; padding: 16px; margin-bottom: 12px;">
                <div style="font-weight: 600; font-size: 0.9rem; color: {text_color}; margin-bottom: 4px;">{log['msg']}</div>
                <div style="font-size: 0.75rem; color: #64748b;">{log['action']}</div>
            </div>
            """, unsafe_allow_html=True)

    with col_settings:
        st.markdown('<div class="section-title" style="font-size:1.2rem; margin-top:0;">Framework Settings</div>', unsafe_allow_html=True)
        
        with st.container(border=True):
            st.write("**Engagement Pacing**")
            p1, p2 = st.columns(2)
            with p1: st.number_input("Min Delay (s)", value=30, step=10)
            with p2: st.number_input("Max Delay (s)", value=120, step=10)
            
            st.divider()
            
            st.write("**Growth Strategy**")
            st.selectbox("Mode", ["Auto-Engage Stream (Like + Comment)", "Like Only", "Comment Only", "Strategic Reposting"])
            st.multiselect("Niches to Target", ["PCBA Manufacturing", "SMT Technology", "AI in Hardware", "Industrial Automation"], default=["PCBA Manufacturing", "AI in Hardware"])
            
            st.divider()
            
            st.write("**Safety Filters**")
            st.toggle("Skip Promoted Posts", value=True)
            st.toggle("Avoid Duplicate Interactons", value=True)
            st.toggle("Respect Human Hours (9 AM - 6 PM)", value=True)
            
            st.divider()
            
            if st.button("Run Growth Bot Once", type="primary", use_container_width=True):
                st.toast("Starting growth sequence...")
                time.sleep(1)
                st.success("Sequence initiated in background.")

    # ── Content Calendar Section ──
    st.markdown("---")
    cal_col1, cal_col2 = st.columns([4, 1])
    with cal_col1:
        st.markdown('<div class="section-title">AI Content Calendar (30 Days)</div>', unsafe_allow_html=True)
    with cal_col2:
        if st.button("Regenerate Plan", use_container_width=True):
            st.toast("Drafting new 30-day strategy...")

    # Placeholder for Calendar Visualization
    st.info("The 30-day content calendar is being generated based on your niche 'AI-Powered PCBA Manufacturing'.")
    
    # Simple list view for calendar
    days = [
        {"day": "Day 1", "topic": "Introduction to AI in PCBA", "type": "Educational"},
        {"day": "Day 2", "topic": "Case Study: Efficiency Gains", "type": "ROI Focus"},
        {"day": "Day 3", "topic": "The future of SMT lines", "type": "Thought Leadership"},
    ]
    
    for d in days:
        with st.expander(f"{d['day']}: {d['topic']}"):
            st.write(f"**Format**: {d['type']}")
            st.write("Suggested Keywords: #AOI #PCBA #AI #SmartFactory")
            st.button("Draft Post", key=f"draft_{d['day']}")
