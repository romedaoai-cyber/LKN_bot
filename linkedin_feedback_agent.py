#!/usr/bin/env python3
"""
DaoAI LinkedIn Feedback Agent
Autonomously watches for rejected posts with feedback and uses Gemini AI to revise them.

Runs as a background daemon or via cron.
When it finds a rejected post with feedback, it:
1. Reads the original content + feedback
2. Calls Gemini to revise
3. Updates the post file with new content
4. Sets status back to "pending" for re-review
5. Marks feedback as resolved
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
POSTS_DIR = Path(__file__).parent / "linkedin_posts"
FEEDBACK_LOG = POSTS_DIR / "feedback_log.json"
AGENT_LOG = POSTS_DIR / "feedback_agent.log"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBqQF9-ivsvkAjbGhb-OIvDv6dbtBmK38M")

# How often to check (seconds) — daemon mode
CHECK_INTERVAL = 30

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(AGENT_LOG),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("feedback_agent")

# ──────────────────────────────────────────────
# Gemini API
# ──────────────────────────────────────────────
def revise_with_gemini(original_text, feedback, post_context):
    """Use Gemini to revise LinkedIn post based on user feedback."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        prompt = f"""You are a LinkedIn content writer for DaoAI, a company that makes AI-powered AOI (Automated Optical Inspection) machines for PCBA manufacturing.

The user REJECTED the following LinkedIn post and provided feedback. 
Revise the post according to their feedback. Keep the same general topic and intent.

RULES:
- Write in English only
- Keep it professional and engaging for LinkedIn
- Include relevant hashtags at the end
- Keep roughly the same length (slightly shorter is OK)
- Include the APEX Expo CTA if the original had one (Booth #2747, March 17-19, Anaheim CA)
- Do NOT include any markdown formatting — plain text only
- Use emojis sparingly and naturally

ORIGINAL POST:
{original_text}

USER FEEDBACK:
{feedback}

POST DATE: {post_context.get('date', 'unknown')}

Write ONLY the revised post text. No explanations, no headers, just the post content ready to publish."""

        response = model.generate_content(prompt)
        revised = response.text.strip()
        
        # Sanity check
        if len(revised) < 50:
            log.warning(f"Gemini response too short ({len(revised)} chars), skipping")
            return None
        
        return revised
        
    except Exception as e:
        log.error(f"Gemini API error: {e}")
        return None


# ──────────────────────────────────────────────
# Post File Operations
# ──────────────────────────────────────────────
def parse_post_file(filepath):
    """Parse post file metadata and content."""
    path = Path(filepath)
    if not path.exists():
        return None
    
    content = path.read_text(encoding="utf-8")
    post = {"file": path, "filename": path.name}
    lines = content.split("\n")
    text_lines = []
    in_content = False
    
    for line in lines:
        if line.startswith("<!-- date:"):
            post["date"] = line.replace("<!-- date:", "").replace("-->", "").strip()
        elif line.startswith("<!-- image:"):
            post["image"] = line.replace("<!-- image:", "").replace("-->", "").strip()
        elif line.startswith("<!-- status:"):
            post["status"] = line.replace("<!-- status:", "").replace("-->", "").strip()
        elif line.startswith("<!-- feedback:"):
            post["feedback"] = line.replace("<!-- feedback:", "").replace("-->", "").strip()
        elif line.strip() == "---CONTENT---":
            in_content = True
        elif line.strip() == "---END---":
            in_content = False
        elif in_content:
            text_lines.append(line)
    
    post["text"] = "\n".join(text_lines).strip()
    return post


def update_post_file(filepath, new_text, new_status="pending", clear_feedback=True):
    """Update post content, status, timestamp, and revision count."""
    path = Path(filepath)
    lines = path.read_text(encoding="utf-8").split("\n")
    
    # Track metadata
    new_lines = []
    seen_revision = False
    current_revisions = 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # First pass: find current revision count
    for line in lines:
        if line.startswith("<!-- revisions:"):
            try:
                current_revisions = int(line.replace("<!-- revisions:", "").replace("-->", "").strip())
            except:
                pass

    new_revisions = current_revisions + 1

    for line in lines:
        if line.startswith("<!-- status:"):
            new_lines.append(f"<!-- status: {new_status} -->")
        elif clear_feedback and line.startswith("<!-- feedback:"):
            new_lines.append("<!-- feedback:  -->")
        elif line.startswith("<!-- revisions:"):
            new_lines.append(f"<!-- revisions: {new_revisions} -->")
            seen_revision = True
        elif line.startswith("<!-- revised_at:"):
            new_lines.append(f"<!-- revised_at: {now_str} -->")
        else:
            new_lines.append(line)
    
    # If revised metadata missing, add it after status
    if not seen_revision:
        final_lines = []
        for line in new_lines:
            final_lines.append(line)
            if line.startswith("<!-- status:"):
                final_lines.append(f"<!-- revisions: {new_revisions} -->")
                final_lines.append(f"<!-- revised_at: {now_str} -->")
        new_lines = final_lines
    
    # Update content block
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(new_lines):
        if line.strip() == "---CONTENT---":
            start_idx = i
        elif line.strip() == "---END---":
            end_idx = i
    
    if start_idx != -1 and end_idx != -1:
        final_lines = new_lines[:start_idx+1] + [new_text.strip()] + new_lines[end_idx:]
        path.write_text("\n".join(final_lines), encoding="utf-8")
        return True
    
    return False


# ──────────────────────────────────────────────
# Feedback Processing
# ──────────────────────────────────────────────
def load_feedback_log():
    """Load unresolved feedback items."""
    if not FEEDBACK_LOG.exists():
        return []
    try:
        return json.loads(FEEDBACK_LOG.read_text(encoding="utf-8"))
    except:
        return []


def save_feedback_log(log_entries):
    """Save feedback log."""
    FEEDBACK_LOG.write_text(
        json.dumps(log_entries, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def generate_image_from_feedback(feedback, post_context):
    """Image generation temporarily disabled by user request."""
    log.info("🖼️ Image generation is currently DISABLED (User request: No Pollinations)")
    return None


def update_post_image(filepath, new_image_path):
    """Update the image path in a post file."""
    path = Path(filepath)
    lines = path.read_text(encoding="utf-8").split("\n")
    new_lines = []
    for line in lines:
        if line.startswith("<!-- image:"):
            new_lines.append(f"<!-- image: {new_image_path} -->")
        else:
            new_lines.append(line)
    path.write_text("\n".join(new_lines), encoding="utf-8")


def process_feedback():
    """Main loop: find rejected posts with feedback, revise them."""
    feedback_entries = load_feedback_log()
    unresolved = [f for f in feedback_entries if not f.get("resolved")]
    
    if not unresolved:
        return 0
    
    processed = 0
    
    for entry in unresolved:
        filename = entry.get("file")
        feedback_text = entry.get("feedback", "").strip()
        action = entry.get("action", "rejected")
        
        if not filename or not feedback_text:
            entry["resolved"] = True
            entry["resolved_at"] = datetime.now().isoformat()
            entry["resolution"] = "skipped — no feedback text"
            continue
        
        filepath = POSTS_DIR / filename
        if not filepath.exists():
            log.warning(f"Post file not found: {filename}")
            entry["resolved"] = True
            entry["resolution"] = "file not found"
            continue
        
        post = parse_post_file(filepath)
        if not post:
            continue
        
        # ── IMAGE FEEDBACK ──
        if action == "image_feedback" or feedback_text.startswith("[IMAGE]"):
            clean_fb = feedback_text.replace("[IMAGE]", "").strip()
            log.info(f"🖼️ Regenerating image for {filename}: {clean_fb[:80]}...")
            
            new_image = generate_image_from_feedback(clean_fb, post)
            if new_image:
                update_post_image(filepath, new_image)
                log.info(f"✅ Image updated for {filename}")
                entry["resolved"] = True
                entry["resolved_at"] = datetime.now().isoformat()
                entry["resolution"] = "image regenerated"
                processed += 1
            else:
                log.error(f"❌ Failed to regenerate image for {filename}")
                entry["resolved"] = True
                entry["resolution"] = "image generation failed"
            continue
        
        # ── TEXT FEEDBACK ──
        # Only process if still rejected
        if post.get("status") != "rejected":
            log.info(f"Skipping {filename} — status is '{post.get('status')}', not 'rejected'")
            entry["resolved"] = True
            entry["resolution"] = "status changed by user"
            continue
        
        log.info(f"🔄 Revising {filename} based on feedback: {feedback_text[:80]}...")
        
        # Call Gemini
        revised_text = revise_with_gemini(post["text"], feedback_text, post)
        
        if revised_text:
            # Update post file
            success = update_post_file(filepath, revised_text, new_status="pending", clear_feedback=False)
            
            if success:
                log.info(f"✅ Revised {filename} — set back to 'pending' for re-review")
                entry["resolved"] = True
                entry["resolved_at"] = datetime.now().isoformat()
                entry["resolution"] = "revised by AI"
                processed += 1
            else:
                log.error(f"❌ Failed to update {filename}")
        else:
            log.error(f"❌ Gemini failed to revise {filename}")
    
    # Save updated log
    save_feedback_log(feedback_entries)
    return processed


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "once"
    
    if mode == "daemon":
        log.info("🤖 Feedback Agent starting in daemon mode...")
        log.info(f"   Watching: {FEEDBACK_LOG}")
        log.info(f"   Check interval: {CHECK_INTERVAL}s")
        
        while True:
            try:
                count = process_feedback()
                if count > 0:
                    log.info(f"Processed {count} feedback items")
            except Exception as e:
                log.error(f"Error in feedback loop: {e}")
            
            time.sleep(CHECK_INTERVAL)
    
    elif mode == "once":
        log.info("🤖 Feedback Agent — single run")
        count = process_feedback()
        if count > 0:
            log.info(f"✅ Processed {count} feedback items")
        else:
            log.info("✨ No unresolved feedback to process")
    
    else:
        print(f"""
DaoAI LinkedIn Feedback Agent

Usage:
    python3 linkedin_feedback_agent.py once     # Process once and exit
    python3 linkedin_feedback_agent.py daemon   # Run continuously (every {CHECK_INTERVAL}s)
""")


if __name__ == "__main__":
    main()
