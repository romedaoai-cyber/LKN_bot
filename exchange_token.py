import os
import requests
from pathlib import Path

# Configuration
DOTENV_PATH = Path(__file__).parent.parent / ".env"
# Must match the one in LinkedIn App Settings exactly
REDIRECT_URI = "http://localhost:8585/callback" 
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

def load_env():
    """Load environment variables from .env file."""
    env = {}
    if DOTENV_PATH.exists():
        with open(DOTENV_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip().strip('"').strip("'")
    return env

def save_env_var(key, value):
    """Save or update a variable in .env file."""
    lines = []
    found = False
    if DOTENV_PATH.exists():
        with open(DOTENV_PATH, "r") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f'{key}="{value}"\n')
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f'{key}="{value}"\n')

    with open(DOTENV_PATH, "w") as f:
        f.writelines(new_lines)

def main():
    print("🔐 Manual Token Exchange Tool")
    
    env = load_env()
    client_id = env.get("LINKEDIN_CLIENT_ID")
    client_secret = env.get("LINKEDIN_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("❌ Missing LINKEDIN_CLIENT_ID or LINKEDIN_CLIENT_SECRET in .env")
        return

    print("\n👇 Paste the 'code' parameter from the redirected URL:")
    print("(Example: If URL is http://localhost:8585/callback?code=AQxxx..., paste AQxxx...)")
    
    auth_code = input("> ").strip()
    
    if not auth_code:
        print("❌ Code cannot be empty.")
        return

    print("\n🔄 Exchanging code for access token...")
    
    try:
        resp = requests.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        })
        
        if resp.status_code == 200:
            data = resp.json()
            access_token = data.get("access_token")
            expires_in = data.get("expires_in")
            
            save_env_var("LINKEDIN_ACCESS_TOKEN", access_token)
            print(f"\n✅ Success! Access Token saved to .env")
            print(f"   Expires in: {expires_in} seconds")
            
            # Try to get Org ID automatically if not set
            if not env.get("LINKEDIN_ORG_ID"):
                print("\n🔍 Checking for Organization ID...")
                # ... simple check logic or prompt ...
                # For now, let user run the main sync script which checks it
        else:
            print(f"\n❌ Failed to get token: {resp.status_code}")
            print(f"   Response: {resp.text}")
            
    except Exception as e:
        print(f"\n❌ Error during request: {e}")

if __name__ == "__main__":
    main()
