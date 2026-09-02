import os
import yt_dlp
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# 1. Get live videos
print("Getting live channel videos...")
ydl_opts = {
    "quiet": True, "extract_flat": "in_playlist",
    "extractor_args": {"youtube": {"player_client": ["mweb", "web"]}},
}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info("https://www.youtube.com/@SandeepSeminars/videos", download=False)
live_titles = {v["title"].lower().strip(): v["id"] for v in info.get("entries", []) if v.get("id")}
print(f"Live channel has {len(live_titles)} videos.")

# 2. Get backup videos
print("Getting backup channel videos...")
creds = Credentials(
    token=None, refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN"),
    token_uri="https://oauth2.googleapis.com/token",
    client_id=os.getenv("YOUTUBE_CLIENT_ID"), client_secret=os.getenv("YOUTUBE_CLIENT_SECRET")
)
youtube = build("youtube", "v3", credentials=creds)

ch = youtube.channels().list(part="contentDetails", mine=True).execute()
uploads_pl = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

backup_videos = []
next_page = None
while True:
    resp = youtube.playlistItems().list(
        part="snippet", playlistId=uploads_pl,
        maxResults=50, pageToken=next_page
    ).execute()
    for item in resp.get("items", []):
        backup_videos.append({
            "title": item["snippet"]["title"],
            "id": item["snippet"]["resourceId"]["videoId"]
        })
    next_page = resp.get("nextPageToken")
    if not next_page:
        break

print(f"Backup channel has {len(backup_videos)} videos.")

# 3. Find missing
print("\n--- DELETED VIDEOS DETECTED ---")
found_any = False
for b_vid in backup_videos:
    b_title_lower = b_vid["title"].lower().strip()
    if b_title_lower not in live_titles:
        print(f"Title: {b_vid['title']}")
        print(f"Backup Video URL: https://youtube.com/watch?v={b_vid['id']}")
        print("-------------------------------")
        found_any = True

if not found_any:
    print("Could not find any deleted videos that were already backed up.")
