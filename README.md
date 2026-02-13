# DaoAI LinkedIn Post Manager

AI-powered LinkedIn content management system with a Streamlit dashboard.

## Features
- 📝 AI-generated LinkedIn posts (Gemini)
- 📊 Analytics tracking (likes, comments, impressions)
- 🤖 AI feedback agent for automatic content revision
- 🔥 Firebase cloud sync
- 📅 Content calendar with scheduling

## Quick Start

### Local
```bash
pip install -r requirements.txt
streamlit run linkedin_dashboard.py
```

### Streamlit Cloud
1. Fork this repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Deploy with main file: `linkedin_dashboard.py`
4. Add your secrets in **Settings → Secrets**

## Secrets Format (`.streamlit/secrets.toml`)
```toml
LINKEDIN_CLIENT_ID = "..."
LINKEDIN_CLIENT_SECRET = "..."
LINKEDIN_ORG_ID = "..."
LINKEDIN_ACCESS_TOKEN = "..."
GEMINI_API_KEY = "..."
FIREBASE_SERVICE_ACCOUNT = '{ ... serviceAccountKey.json content ... }'
```

## Architecture
| File | Purpose |
|------|---------|
| `linkedin_dashboard.py` | Streamlit UI |
| `linkedin_publisher.py` | LinkedIn API publishing |
| `linkedin_analytics.py` | Performance tracking |
| `linkedin_feedback_agent.py` | AI revision agent |
| `linkedin_planner.py` | Content planning |
| `firebase_manager.py` | Cloud data sync |
