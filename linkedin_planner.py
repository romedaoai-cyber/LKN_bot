import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Configuration
ANALYTICS_FILE = Path("linkedin_analytics_data.json")
PLAN_FILE = Path("linkedin_posts/plan.md")

def main():
    print("🧠 Starting Content Planner...")
    
    # 1. Load Analytics
    if not ANALYTICS_FILE.exists():
        print("⚠️ No analytics data found. Run 'python linkedin_analytics.py' first.")
        # Create dummy plan
        try:
            PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
            PLAN_FILE.write_text("# Auto-Generated Content Plan\n\nNo data yet. Waiting for posts stats.", encoding="utf-8")
        except Exception as e:
            print(f"Error writing plan: {e}")
        return

    try:
        with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading analytics: {e}")
        return
    
    if not data:
        print("⚠️ Analytics data is empty.")
        return

    # 2. Analyze Top Performers
    # Sort by engagement rate (if impressions exist) or likes
    def get_score(p):
        likes = p.get("likes", 0)
        comments = p.get("comments", 0)
        impressions = p.get("impressions", 0)
        
        interactions = likes + comments
        if impressions > 0:
            return interactions / impressions
        return interactions

    top_posts = sorted(data, key=get_score, reverse=True)
    top_3 = top_posts[:3]
    
    print(f"📊 Analyzed {len(data)} posts. Top 3:")
    for p in top_3:
        likes = p.get("likes", 0)
        impressions = p.get("impressions", 0)
        print(f"   - {p['name']} ({likes} likes, {impressions} views)")

    # 3. Generate Plan
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    plan_content = f"""# 🧠 AI-Generated Content Plan ({current_date})

Based on your top performing content (Analyzed {len(data)} posts), here is your strategy:

## 🏆 Top Performing Content
"""
    for p in top_3:
        title = p.get('name', 'Untitled')
        likes = p.get('likes', 0)
        comments = p.get('comments', 0)
        impressions = p.get('impressions', 0)
        clicks = p.get('clicks', 0)
        
        er = 0
        if impressions > 0:
            er = ((likes + comments) / impressions) * 100
            
        plan_content += f"### {title}\n"
        plan_content += f"- **Stats**: {likes} Likes, {comments} Comments, {impressions} Views\n"
        plan_content += f"- **Engagement Rate**: {er:.2f}%\n"
        plan_content += f"- **Clicks**: {clicks}\n\n"

    plan_content += "\n## 💡 Next Steps / Suggestions\n\n"
    
    for i, p in enumerate(top_3, 1):
        title = p.get('name', 'Untitled')
        plan_content += f"### Idea {i}: Expand on '{title}'\n"
        plan_content += f"**Concept**: The audience engaged well with this topic. Create a deep-dive or a follow-up post focusing on a specific detail mentioned in '{title}'.\n"
        plan_content += f"**Format**: Carousel (PDF) or Short Video for higher engagement.\n\n"

    try:
        PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
        PLAN_FILE.write_text(plan_content, encoding="utf-8")
        print(f"\n✅ Plan generated successfully: {PLAN_FILE}")
        print("   Open Dashboard -> Analytics tab to view.")
    except Exception as e:
        print(f"Error saving plan: {e}")

if __name__ == "__main__":
    main()
