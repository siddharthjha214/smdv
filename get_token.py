import google_auth_oauthlib.flow

# ==========================================
# PASTE YOUR KEYS HERE
# ==========================================
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
}

print("Opening web browser to generate Master Key...")

flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(
    client_config, 
    scopes=["https://www.googleapis.com/auth/youtube.upload"]
)

# This opens your web browser!
credentials = flow.run_local_server(port=0)

print("\n" + "="*60)
print("SUCCESS! KEEP THIS SECRET!")
print("Here is your Refresh Token:\n")
print(credentials.refresh_token)
print("="*60 + "\n")
