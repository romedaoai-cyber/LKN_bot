
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
import google.generativeai as genai

# Configuration
BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "linkedin_posts"
ANALYTICS_FILE = BASE_DIR / "linkedin_analytics_data.json"
BRAINSTORM_FILE = BASE_DIR / "brainstorm_topics.json"

def load_analytics():
    if not ANALYTICS_FILE.exists():
        return []
    try:
        return json.loads(ANALYTICS_FILE.read_text(encoding="utf-8"))
    except:
        return []

def get_top_performing_topics(data):
    if not data:
        return ["General Industry Trends", "AOI Technology", "Manufacturing Efficiency"]
    sorted_data = sorted(data, key=lambda x: x.get("likes", 0) + x.get("comments", 0), reverse=True)
    return [p.get("name", "") or p.get("filename", "") for p in sorted_data[:5]]

def get_rolling_calendar():
    """Generate a 2-week calendar starting from the next scheduled slot."""
    # Find next Monday (or current if today is small)
    now = datetime.now()
    # If today is Friday/Sat/Sun, start next Monday.
    # We assume typical M-F posting.
    days_to_monday = (7 - now.weekday()) % 7
    if days_to_monday == 0 and now.weekday() >= 4: # If it's Friday or later and somehow we are here
        days_to_monday = 7
    
    start_date = now + timedelta(days=days_to_monday)
    calendar = []
    
    current = start_date
    count = 0
    while count < 10:
        if current.weekday() < 5: # Monday-Friday
            calendar.append(current.strftime("%Y-%m-%d"))
            count += 1
        current += timedelta(days=1)
    return calendar

def get_api_key():
    import os
    api_key = os.environ.get("GEMINI_API_KEY", "")
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
    except ImportError:
        pass
    if not api_key:
        api_key = "AIzaSyBqQF9-ivsvkAjbGhb-OIvDv6dbtBmK38M"
    return api_key

def generate_brainstorm_topics(user_feedback=""):
    """Generate exactly 10 topic suggestions based on analytics."""
    api_key = get_api_key()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    data = load_analytics()
    top_topics = get_top_performing_topics(data)
    
    prompt = f"""
    You are a LinkedIn Content Strategist for DaoAI (AOI machines for PCBA).
    WINNING TOPICS: {json.dumps(top_topics, indent=2)}
    USER FEEDBACK: {user_feedback}

    Generate 10 specific LinkedIn post topics for a 2-week calendar.
    Focus on high-value industry insights, ROI, and technical authority.
    
    Return ONLY a JSON array of strings (the topic titles).
    Example: ["Topic 1", "Topic 2", ...]
    """
    
    try:
        response = model.generate_content(prompt)
        # Handle potential markdown formatting in response
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif raw_text.startswith("["):
            pass # Already looks like JSON
            
        topics = json.loads(raw_text)
        if isinstance(topics, list):
            # Save for dashboard access
            dates = get_rolling_calendar()
            brainstorm_data = []
            for i, topic in enumerate(topics[:10]):
                brainstorm_data.append({
                    "id": i,
                    "date": dates[i] if i < len(dates) else "",
                    "topic": topic,
                    "status": "suggested"
                })
            BRAINSTORM_FILE.write_text(json.dumps(brainstorm_data, indent=2), encoding="utf-8")
            return brainstorm_data
    except Exception as e:
        print(f"Error generating topics: {e}")
    return []

def regenerate_single_topic(index, user_feedback=""):
    """Replace one topic in the existing brainstorm list."""
    if not BRAINSTORM_FILE.exists():
        return [], False, "brainstorm file not found"
    
    topics_data = json.loads(BRAINSTORM_FILE.read_text(encoding="utf-8"))
    if index < 0 or index >= len(topics_data):
        return topics_data, False, "index out of range"

    old_topic = (topics_data[index].get("topic") or "").strip()

    api_key = get_api_key()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash") # Use faster model for single topic

    prompt = f"""
    Suggest ONE new LinkedIn post topic for DaoAI (AOI manufacturing).
    Avoid these existing topics: {[t['topic'] for t in topics_data if t['id'] != index]}
    FEEDBACK: {user_feedback}
    Return ONLY the string for the topic title.
    """
    
    new_topic = ""
    err = None
    try:
        response = model.generate_content(prompt)
        new_topic = (response.text or "").strip().strip('"').replace("\n", " ")
        if new_topic.startswith("```"):
            new_topic = new_topic.replace("```", "").replace("json", "").strip()
    except Exception as e:
        err = str(e)
        print(f"Error regenerating topic: {e}")

    # Guaranteed fallback so the button always changes something.
    if not new_topic or len(new_topic) < 8 or new_topic.lower() == old_topic.lower():
        suffix = user_feedback.strip() if user_feedback.strip() else "new angle"
        suffix = suffix[:40]
        seed = int(datetime.now().timestamp()) % 1000
        base = old_topic if old_topic else "AOI manufacturing insight"
        new_topic = f"{base} ({suffix} #{seed})"

    topics_data[index]["topic"] = new_topic
    BRAINSTORM_FILE.write_text(json.dumps(topics_data, indent=2), encoding="utf-8")
    return topics_data, True, err

def generate_post_content(topic, user_feedback=""):
    """Generate a full LinkedIn post body from a topic."""
    api_key = get_api_key()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""
You are a senior LinkedIn writer for DaoAI (AI-powered AOI for PCBA manufacturing).

Write ONE complete LinkedIn post based on this topic:
TOPIC: {topic}
OPTIONAL STRATEGY FEEDBACK: {user_feedback}

Rules:
- English only
- 140-280 words
- Clear hook in first 1-2 lines
- Practical insight and concrete manufacturing relevance
- End with a short CTA question
- Plain text only (no markdown syntax)
"""
    try:
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        if len(text) >= 80:
            return text
    except Exception as e:
        print(f"Error generating full post content: {e}")
    return f"{topic}\n\nWhat changes would this unlock in your production workflow?"


def build_post_markdown(date, topic, body):
    return f"""<!-- date: {date} -->
<!-- status: pending -->
<!-- subject: {topic} -->
<!-- image: -->
<!-- feedback: -->
<!-- revisions: 0 -->
<!-- time: 09:00 -->
---CONTENT---
{body}
---END---
"""


def convert_to_planning(topics_to_save, user_feedback=""):
    """Save topics as pending .md files in the planning tab with full content."""
    created = 0
    for t in topics_to_save:
        filename = f"plan_{t['date']}_{t['id']}.md"
        filepath = POSTS_DIR / filename
        full_body = generate_post_content(t["topic"], user_feedback=user_feedback)
        content = build_post_markdown(t["date"], t["topic"], full_body)
        filepath.write_text(content, encoding="utf-8")
        created += 1

    # Clear brainstorm file only when all current topics were promoted.
    if BRAINSTORM_FILE.exists():
        try:
            existing = json.loads(BRAINSTORM_FILE.read_text(encoding="utf-8"))
            promoted_ids = {t.get("id") for t in topics_to_save}
            remaining = [t for t in existing if t.get("id") not in promoted_ids]
            if remaining:
                BRAINSTORM_FILE.write_text(json.dumps(remaining, indent=2), encoding="utf-8")
            else:
                BRAINSTORM_FILE.unlink()
        except Exception:
            if BRAINSTORM_FILE.exists():
                BRAINSTORM_FILE.unlink()
    return created

if __name__ == "__main__":
    # Test
    print(generate_brainstorm_topics())
