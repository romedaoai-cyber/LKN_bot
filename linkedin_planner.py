
import os
import json
import random
from pathlib import Path
from datetime import datetime
import google.generativeai as genai

# Configuration
BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "linkedin_posts"
ANALYTICS_FILE = BASE_DIR / "linkedin_analytics_data.json"
PLAN_FILE = POSTS_DIR / "plan.md"

def load_analytics():
    if not ANALYTICS_FILE.exists():
        return []
    try:
        return json.loads(ANALYTICS_FILE.read_text(encoding="utf-8"))
    except:
        return []

def get_top_performing_topics(data):
    """Analyze high-performing posts to extract topics/themes."""
    if not data:
        return ["General Industry Trends", "AOI Technology", "Manufacturing Efficiency"]
    
    # Sort by engagement (likes + comments)
    sorted_data = sorted(data, key=lambda x: x.get("likes", 0) + x.get("comments", 0), reverse=True)
    top_posts = sorted_data[:5]
    
    # In a real scenario, we'd use LLM to extract themes, but here we'll use titles
    topics = [p.get("filename", "").replace(".md", "").replace("_", " ") for p in top_posts]
    return topics

def generate_strategic_plan():
    """Generate a content plan and draft new posts."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "❌ Missing GEMINI_API_KEY"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    data = load_analytics()
    top_topics = get_top_performing_topics(data)
    
    # 1. Strategy Generation
    strategy_prompt = f"""
    You are a LinkedIn Content Strategist for DaoAI (AOI machines for PCBA).
    
    Based on our top-performing past posts:
    {json.dumps(top_topics[:5], indent=2)}
    
    1. Identify the WINNING THEME (why did these work?)
    2. Suggest 3 NEW ANGLES or "Remixes" to double down on this success.
    3. Write 3 NEW LinkedIn posts (Drafts) based on these angles.
    
    Output Format:
    # Strategy Report
    (Analysis...)

    # New Drafts
    
    ## Draft 1: [Title]
    (Content...)
    
    ## Draft 2: [Title]
    (Content...)
    
    ## Draft 3: [Title]
    (Content...)
    """
    
    response = model.generate_content(strategy_prompt)
    plan_content = response.text
    
    # Save the plan
    PLAN_FILE.write_text(plan_content, encoding="utf-8")
    
    # 2. Extract and Save Drafts (Simple parsing)
    # We'll just save the whole plan for now, but in a full "Autopilot", we'd parse and save individual .md files.
    # Let's do a simple parse to save individual drafts to populate the dashboard.
    
    drafts = plan_content.split("## Draft")
    created_count = 0
    
    for i, draft in enumerate(drafts[1:], 1):
        lines = draft.strip().split("\n")
        title = lines[0].strip().replace(":", "").strip()
        body = "\n".join(lines[1:]).strip()
        
        filename = f"auto_draft_{datetime.now().strftime('%Y%m%d')}_{i}.md"
        filepath = POSTS_DIR / filename
        
        file_content = f"""<!-- date: {datetime.now().strftime('%Y-%m-%d')} -->
<!-- status: pending -->
<!-- subject: {title} -->
<!-- image: -->

{body}
"""
        filepath.write_text(file_content, encoding="utf-8")
        created_count += 1
        
    return f"✅ Generated Strategy Plan & {created_count} New Drafts based on data!"

if __name__ == "__main__":
    print(generate_strategic_plan())
