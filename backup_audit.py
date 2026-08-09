"""
BACKUP CHANNEL AUDIT SCRIPT
============================
Scans the backup YouTube channel using the same OAuth credentials
as the bot, then cross-checks against Active_Videos sheet to find:
  - Which videos are backed up (exist on backup channel)
  - Which videos are NOT yet backed up (Pending)
  - Which backup videos YouTube may have deleted

Run locally (requires YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN).
"""

import os, requests, json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyAarmgcJWsMYdHW9fhbKrTZXGsu77TFKVAQanMZmTY1xdgtq320MgiZfusuLvXlpAF/exec"

client_id     = os.getenv("YOUTUBE_CLIENT_ID")
client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

if not all([client_id, client_secret, refresh_token]):
    print("ERROR: Set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN env vars first.")
    exit(1)

creds = Credentials(
    token=None,
    refresh_token=refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=client_id,
    client_secret=client_secret
)
youtube = build("youtube", "v3", credentials=creds)

# 1. Get the backup channel's uploads playlist ID
print("Getting backup channel info...")
ch = youtube.channels().list(part="contentDetails,snippet", mine=True).execute()
channel_name = ch["items"][0]["snippet"]["title"]
uploads_playlist = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
print(f"  Backup channel: {channel_name}")
print(f"  Uploads playlist: {uploads_playlist}\n")

# 2. Fetch ALL videos from the backup channel
print("Scanning backup channel for all uploaded videos...")
backup_videos = {}  # backup_video_id → title
next_page = None
while True:
    resp = youtube.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist,
        maxResults=50,
        pageToken=next_page
    ).execute()
    for item in resp.get("items", []):
        vid_id = item["snippet"]["resourceId"]["videoId"]
        title  = item["snippet"]["title"]
        backup_videos[vid_id] = title
    next_page = resp.get("nextPageToken")
    if not next_page:
        break
    print(f"  Fetched {len(backup_videos)} backup videos so far...")

print(f"  Total on backup channel: {len(backup_videos)} videos\n")

# 3. Fetch active videos from sheet
print("Fetching Active_Videos sheet...")
r = requests.get(GOOGLE_SCRIPT_URL + "?action=get_active_videos", timeout=30, allow_redirects=True)
sheet_data = r.json()
print(f"  Total in sheet: {len(sheet_data)} videos\n")

# 4. Cross-check
backed_up_ids = set(backup_videos.keys())
pending       = []
backed_up     = []
backup_missing = []  # Sheet says "Backed Up" but video not found on channel

for orig_id, data in sheet_data.items():
    backup_vid_id = data.get("backup_video_id", "")
    backup_status = data.get("backup_status", "Pending")
    title         = data.get("title", "Unknown")

    if backup_status == "Backed Up" and backup_vid_id:
        if backup_vid_id in backed_up_ids:
            backed_up.append((orig_id, backup_vid_id, title))
        else:
            backup_missing.append((orig_id, backup_vid_id, title))
    else:
        pending.append((orig_id, title))

print("=" * 60)
print(f"BACKUP CHANNEL AUDIT RESULTS")
print("=" * 60)
print(f"✅ Backed Up (confirmed on channel): {len(backed_up)}")
print(f"⏳ Pending (not yet backed up)      : {len(pending)}")
print(f"❌ Missing (sheet says Backed Up, but YouTube removed it): {len(backup_missing)}")
print()

if backup_missing:
    print("MISSING BACKUPS (YouTube removed these):")
    for orig_id, bkp_id, title in backup_missing:
        print(f"  {orig_id} → backup {bkp_id}: {title[:60]}")
    print()

# Save full report
report = {
    "backup_channel": channel_name,
    "total_on_backup_channel": len(backup_videos),
    "total_in_sheet": len(sheet_data),
    "backed_up_count": len(backed_up),
    "pending_count": len(pending),
    "missing_from_channel": len(backup_missing),
    "pending_videos": [{"video_id": v[0], "title": v[1]} for v in pending],
    "missing_videos": [{"orig_id": v[0], "backup_id": v[1], "title": v[2]} for v in backup_missing],
}
with open("/tmp/backup_audit.json", "w") as f:
    json.dump(report, f, indent=2)
print(f"Full report saved to /tmp/backup_audit.json")
