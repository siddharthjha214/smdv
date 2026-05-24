import os
import google_auth_oauthlib.flow

# ==========================================
# PASTE YOUR KEYS HERE (OR LEAVE AS IS TO USE ENV VARS / TERMINAL PROMPT)
# ==========================================
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"

# Fallback to environment variables if not set
if CLIENT_ID == "YOUR_CLIENT_ID" or not CLIENT_ID:
    CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")

if CLIENT_SECRET == "YOUR_CLIENT_SECRET" or not CLIENT_SECRET:
    CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")

# If still not found, prompt the user in terminal
if not CLIENT_ID:
    CLIENT_ID = input("Enter your YouTube CLIENT_ID: ").strip()

if not CLIENT_SECRET:
    CLIENT_SECRET = input("Enter your YouTube CLIENT_SECRET: ").strip()

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: Both Client ID and Client Secret are required.")
    exit(1)

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
}

print("\nOpening web browser to generate Master Key / Refresh Token...")
try:
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(
        client_config, 
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )

    # This opens your web browser!
    credentials = flow.run_local_server(port=0)

    print("\n" + "="*60)
    print("SUCCESS! KEEP THIS SECRET!")
    print("Here is your YOUTUBE_REFRESH_TOKEN:\n")
    print(credentials.refresh_token)
    print("="*60 + "\n")
except Exception as e:
    print(f"\nAn error occurred during authentication: {e}")
    print("Please double check that your Client ID and Client Secret are correct,")
    print("and that your OAuth Consent Screen in Google Cloud Console is configured correctly.")

