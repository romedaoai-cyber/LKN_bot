import os
import requests
from pathlib import Path

# Configuration
DOTENV_PATH = Path(__file__).parent / ".env"

def load_env():
    env = {}
    if DOTENV_PATH.exists():
        with open(DOTENV_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip().strip('"').strip("'")
    return env

def get_headers(access_token):
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202411",
    }

def main():
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN") or load_env().get("LINKEDIN_ACCESS_TOKEN")
    current_org_id = os.environ.get("LINKEDIN_ORG_ID") or load_env().get("LINKEDIN_ORG_ID")
    
    if not token:
        print("❌ No Access Token found.")
        return

    headers = get_headers(token)
    
    print("\n--- 🕵️‍♂️ Current Configuration ---")
    print(f"Token (First 10 chars): {token[:10]}...")
    print(f"Configured Org ID: {current_org_id}")

    # 1. Fetch info for the current Org ID
    if current_org_id:
        org_urn = current_org_id if current_org_id.startswith("urn:") else f"urn:li:organization:{current_org_id}"
        org_id_only = org_urn.split(":")[-1]
        
        # Try to get organization name
        url = f"https://api.linkedin.com/rest/organizations/{org_id_only}"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            name = data.get("localizedName", "Unknown")
            print(f"✅ Current ID Name: {name}")
        else:
            print(f"⚠️ Could not fetch details for {org_urn}: {resp.status_code} {resp.text}")

    # 2. List all Organizations the user can admin
    print("\n--- 📋 Organizations You Admin ---")
    url = "https://api.linkedin.com/rest/organizationAcls?q=roleAssignee"
    resp = requests.get(url, headers=headers)
    
    if resp.status_code == 200:
        elements = resp.json().get("elements", [])
        if not elements:
            print("📭 No organizations found where you are an admin.")
        
        for el in elements:
            org_urn = el.get("organization")
            role = el.get("role")
            state = el.get("state")
            
            # Fetch name for each
            org_id_only = org_urn.split(":")[-1]
            name_resp = requests.get(f"https://api.linkedin.com/rest/organizations/{org_id_only}", headers=headers)
            name = name_resp.json().get("localizedName", "Unknown") if name_resp.status_code == 200 else "Unknown"
            
            print(f"- Name: {name}")
            print(f"  URN:  {org_urn}")
            print(f"  Role: {role} ({state})")
            print("-" * 30)
    else:
        print(f"❌ Failed to list admin roles: {resp.status_code} {resp.text}")

    # 3. Check Personal Profile just in case
    print("\n--- 👤 Personal Profile ---")
    resp = requests.get("https://api.linkedin.com/v2/me", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code == 200:
        data = resp.json()
        print(f"Name: {data.get('localizedFirstName')} {data.get('localizedLastName')}")
        print(f"URN:  urn:li:person:{data.get('id')}")
    else:
        print(f"⚠️ Could not fetch profile: {resp.status_code}")

if __name__ == "__main__":
    main()
