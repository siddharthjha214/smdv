"""
FETCH & SEED SPIRITUALITY CHANNEL VIDEOS INTO GOOGLE SHEETS
===========================================================
Target Channel: https://www.youtube.com/@Sandeepmaheshwarispirituality
Target Tabs: Sprituality_Active_Videos / Sprituality_Deleted_Videos

Columns:
1. Title
2. Upload Time
3. Status ("Active")
4. Video ID
5. URL
6. Backup Status ("Pending")
7. Backup Date ("")
8. Backup Video ID ("")
9. Reupload Attempts (0)
"""

import os
import time
import requests
import pytz
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyAarmgcJWsMYdHW9fhbKrTZXGsu77TFKVAQanMZmTY1xdgtq320MgiZfusuLvXlpAF/exec"
CHANNEL_URL = "https://www.youtube.com/@Sandeepmaheshwarispirituality/videos"
CHANNEL_ID = "UCaEtAfisWDXL3eG8u_M2brA"
UPLOADS_PLAYLIST_ID = "UUaEtAfisWDXL3eG8u_M2brA"
CHANNEL_KEY = "spirituality"
IST = pytz.timezone("Asia/Kolkata")

# YouTube API credentials
CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN")

def format_iso_date(dt_str):
    try:
        if dt_str and len(dt_str) >= 19:
            dt_utc = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
            return dt_utc.astimezone(IST).strftime("%d %B %Y %I:%M %p IST")
    except Exception:
        pass
    return "Unknown"

def fetch_videos_via_api():
    print("Scanning Spirituality channel via YouTube Data API...")
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        youtube = build("youtube", "v3", credentials=creds)
        
        all_videos = []
        next_token = None
        while True:
            res = youtube.playlistItems().list(
                part="snippet",
                playlistId=UPLOADS_PLAYLIST_ID,
                maxResults=50,
                pageToken=next_token
            ).execute()
            
            for item in res.get("items", []):
                snippet = item.get("snippet", {})
                vid_id = snippet.get("resourceId", {}).get("videoId")
                if vid_id:
                    all_videos.append({
                        "video_id": vid_id,
                        "title": snippet.get("title", "Untitled Video"),
                        "url": f"https://youtube.com/watch?v={vid_id}",
                        "upload_time": format_iso_date(snippet.get("publishedAt", ""))
                    })
            next_token = res.get("nextPageToken")
            if not next_token:
                break
        print(f"API Scan Complete: {len(all_videos)} videos found.")
        return all_videos
    except Exception as e:
        print(f"API Scan Error ({e}). Falling back to yt-dlp...")
        return None

def fetch_videos_via_ytdlp():
    import yt_dlp
    ydl_opts = {"quiet": True, "extract_flat": "in_playlist", "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(CHANNEL_URL, download=False)
        entries = info.get("entries", [])
    
    videos = []
    for entry in entries:
        if not entry:
            continue
        vid_id = entry.get("id")
        if vid_id:
            videos.append({
                "video_id": vid_id,
                "title": entry.get("title") or "Untitled Video",
                "url": f"https://youtube.com/watch?v={vid_id}",
                "upload_time": "Unknown"
            })
    return videos

def main():
    print("=" * 60)
    print("STEP 1: Checking current videos in Sprituality_Active_Videos sheet...")
    existing_ids = set()
    try:
        r = requests.get(f"{GOOGLE_SCRIPT_URL}?action=get_active_videos&channel={CHANNEL_KEY}", timeout=30)
        if r.status_code == 200:
            data = r.json()
            # If the web app still routes to main channel, warn the user
            if "World's #1 Life Changing Video By Sandeep Maheshwari | Hindi" in [v.get("title") for v in data.values()]:
                print("\n⚠️ WARNING: Google Apps Script Web App is still returning Main Channel videos!")
                print("Please update and re-deploy apps_script.js as a 'New Version' in Apps Script before proceeding.")
                return
            existing_ids = set(data.keys())
            print(f"  Found {len(existing_ids)} existing videos already in Spirituality sheet.")
    except Exception as e:
        print(f"  Notice: Could not fetch existing sheet ({e}). Assuming clean sheet.")

    print("\nSTEP 2: Scanning channel for all videos...")
    videos = fetch_videos_via_api()
    if not videos:
        videos = fetch_videos_via_ytdlp()

    print(f"  Discovered {len(videos)} videos on @Sandeepmaheshwarispirituality!")

    to_insert = [v for v in videos if v["video_id"] not in existing_ids]
    print(f"\nSTEP 3: Inserting {len(to_insert)} new videos into Sprituality_Active_Videos...")
    if to_insert:
        chunk_size = 50
        for i in range(0, len(to_insert), chunk_size):
            chunk = to_insert[i:i + chunk_size]
            payload = {
                "type": "bulk_restore",
                "channel": CHANNEL_KEY,
                "videos": chunk
            }
            try:
                res = requests.post(GOOGLE_SCRIPT_URL, json=payload, timeout=30)
                print(f"  Inserted batch {i+1} to {min(i+chunk_size, len(to_insert))} (Response: {res.text.strip()})")
            except Exception as e:
                print(f"  Batch insert error: {e}")
            time.sleep(1)

        print("\nTriggering sheet sort...")
        try:
            requests.post(GOOGLE_SCRIPT_URL, json={"type": "sort_sheet", "channel": CHANNEL_KEY}, timeout=15)
        except Exception:
            pass

    print("\n✅ SEEDING COMPLETE! All videos registered in Sprituality_Active_Videos with 'Pending' status.")

if __name__ == "__main__":
    main()
