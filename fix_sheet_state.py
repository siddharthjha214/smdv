import os, requests, json, time
import yt_dlp
import pytz
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyAarmgcJWsMYdHW9fhbKrTZXGsu77TFKVAQanMZmTY1xdgtq320MgiZfusuLvXlpAF/exec"
IST = pytz.timezone("Asia/Kolkata")

# Options for yt-dlp to extract precise date using Firefox cookies
ydl_opts = {
    "quiet": True,
    "cookiesfrombrowser": ("firefox",),
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
}

def format_youtube_date(upload_date):
    try:
        if isinstance(upload_date, str):
            if upload_date.isdigit() and len(upload_date) > 8:
                upload_date = float(upload_date)
            elif upload_date.isdigit() and len(upload_date) == 8:
                dt = datetime.strptime(upload_date, "%Y%m%d")
                dt_ist = IST.localize(dt)
                return dt_ist.strftime("%d %B %Y %I:%M %p IST")
            elif "-" in upload_date and len(upload_date) >= 10:
                dt = datetime.strptime(upload_date[:10], "%Y-%m-%d")
                dt_ist = IST.localize(dt)
                return dt_ist.strftime("%d %B %Y %I:%M %p IST")
                
        if isinstance(upload_date, (int, float)):
            dt_utc = datetime.fromtimestamp(upload_date, tz=pytz.utc)
            dt_ist = dt_utc.astimezone(IST)
            return dt_ist.strftime("%d %B %Y %I:%M %p IST")
            
        return "Unknown"
    except Exception as e:
        print(f"Date parse error for '{upload_date}':", e)
        return "Unknown"

def safe_post(url, json=None, retries=5):
    for attempt in range(retries):
        try:
            resp = requests.post(url, json=json, timeout=30, allow_redirects=True)
            time.sleep(1) # Rate limit protection for Google Apps Script
            return resp
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error: {e}. Retrying {attempt+1}/{retries}...")
            time.sleep(5)
        except Exception as e:
            print(f"Request error: {e}. Retrying {attempt+1}/{retries}...")
            time.sleep(5)
    raise Exception("Failed to post after maximum retries.")

def main():
    print("=" * 60)
    print("FIX SHEET STATE AND AUDIT BACKUPS")
    print("=" * 60)

    # 1. Get YouTube credentials
    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("ERROR: Missing YouTube credentials (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN).")
        print("Please export these variables or run the script in the same environment as main.py.")
        return

    creds = Credentials(
        token=None, refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id, client_secret=client_secret
    )
    youtube = build("youtube", "v3", credentials=creds)

    # 2. Fetch all backup channel videos
    print("\n[1] Fetching all uploaded videos from backup channel...")
    ch = youtube.channels().list(part="contentDetails,snippet", mine=True).execute()
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
                "id": item["snippet"]["resourceId"]["videoId"],
                "title": item["snippet"]["title"]
            })
        next_page = resp.get("nextPageToken")
        if not next_page:
            break
            
    print(f"Total videos on backup channel: {len(backup_videos)}")

    # Clean duplicates by taking the oldest
    from collections import defaultdict
    by_title = defaultdict(list)
    for v in backup_videos:
        by_title[v["title"]].append(v)
    
    clean_backup = {}
    for title, vids in by_title.items():
        clean_backup[title.strip().lower()[:100]] = vids[0]["id"]

    # 3. Fetch current sheet state
    print("\n[2] Fetching Active_Videos sheet...")
    r = requests.get(GOOGLE_SCRIPT_URL + "?action=get_active_videos", timeout=30, allow_redirects=True)
    sheet_data = r.json()
    print(f"{len(sheet_data)} videos found in sheet.")

    # 4. Iterate and fix
    print("\n[3] Auditing and fixing sheet state...")
    backup_date_now = datetime.now(IST).strftime("%d %B %Y %I:%M %p IST")
    
    for vid_id, data in sheet_data.items():
        title = data.get("title", "Unknown")
        current_status = data.get("backup_status", "Pending")
        upload_time = data.get("upload_time", "")
        
        lookup_title = title.strip().lower()[:100]
        is_on_backup_channel = lookup_title in clean_backup
        backup_vid_id = clean_backup.get(lookup_title)
        
        # --- Fix missing upload time ---
        if not upload_time or upload_time == "Unknown":
            print(f"Missing date for {vid_id} '{title[:30]}...'. Fetching via yt-dlp...")
            url = f"https://youtube.com/watch?v={vid_id}"
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    upload_date_raw = (
                        info.get("timestamp") or 
                        info.get("release_timestamp") or 
                        info.get("upload_date") or 
                        info.get("release_date")
                    )
                new_time = format_youtube_date(upload_date_raw) if upload_date_raw else "Unknown"
                if new_time != "Unknown":
                    print(f"  -> Found time: {new_time}")
                    safe_post(GOOGLE_SCRIPT_URL, json={
                        "type": "update_date",
                        "video_id": vid_id,
                        "upload_time": new_time
                    })
                else:
                    print(f"  -> Could not determine time.")
            except Exception as e:
                print(f"  -> yt-dlp failed: {e}")
        
        # --- Fix Backup Status ---
        if is_on_backup_channel:
            if current_status != "Backed Up":
                print(f"Correcting status for {vid_id}: Pending -> Backed Up (Backup ID: {backup_vid_id})")
                safe_post(GOOGLE_SCRIPT_URL, json={
                    "type": "update_backup",
                    "video_id": vid_id,
                    "backup_status": "Backed Up",
                    "backup_date": backup_date_now,
                    "backup_video_id": backup_vid_id
                })
        else:
            if current_status == "Backed Up":
                print(f"Correcting status for {vid_id}: Backed Up -> Pending (Not found on backup channel)")
                safe_post(GOOGLE_SCRIPT_URL, json={
                    "type": "force_pending",
                    "video_id": vid_id
                })
                
    # 5. Trigger sheet sorting
    print("\n[4] Triggering sheet sort (newest top, oldest bottom)...")
    safe_post(GOOGLE_SCRIPT_URL, json={
        "type": "sort_sheet"
    })
    print("Done! Sheet is now fully synced and sorted.")

if __name__ == "__main__":
    main()
