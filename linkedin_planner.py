
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

def generate_brainstorm_topics(user_feedback=""):
    """Generate exactly 10 topic suggestions based on analytics."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return []

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
    if not BRAINSTORM_FILE.exists(): return generate_brainstorm_topics()
    
    topics_data = json.loads(BRAINSTORM_FILE.read_text(encoding="utf-8"))
    if index < 0 or index >= len(topics_data): return topics_data

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return topics_data

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash") # Use faster model for single topic

    prompt = f"""
    Suggest ONE new LinkedIn post topic for DaoAI (AOI manufacturing).
    Avoid these existing topics: {[t['topic'] for t in topics_data if t['id'] != index]}
    FEEDBACK: {user_feedback}
    Return ONLY the string for the topic title.
    """
    
    try:
        response = model.generate_content(prompt)
        new_topic = response.text.strip().strip('"')
        topics_data[index]["topic"] = new_topic
        BRAINSTORM_FILE.write_text(json.dumps(topics_data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Error regenerating topic: {e}")
    
    return topics_data

def convert_to_planning(topics_to_save):
    """Save topics as pending .md files in the planning tab."""
    created = 0
    for t in topics_to_save:
        filename = f"plan_{t['date']}_{t['id']}.md"
        filepath = POSTS_DIR / filename
        
        content = f"""<!-- date: {t['date']} -->
<!-- status: pending -->
<!-- subject: {t['topic']} -->
<!-- image: -->

Draft for: {t['topic']}
(AI will expand this into a full post in the planning phase)
"""
        filepath.write_text(content, encoding="utf-8")
        created += 1
    
    # Clear brainstorm file after promotion
    if BRAINSTORM_FILE.exists(): BRAINSTORM_FILE.unlink()
    return created

if __name__ == "__main__":
    # Test
    print(generate_brainstorm_topics())

