import yt_dlp
import requests
import pytz
from datetime import datetime
import os
import glob
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================
# SETTINGS
# ==========================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = "765673702"
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbw81BtuAqr6NlISRUHgazF7_Q3rFXmELbmDtg5h0oKtZrU8ZWvBLstzlXqJJdKwzZUG/exec"
CHANNEL_URL = "https://www.youtube.com/@SandeepSeminars/videos"

IST = pytz.timezone("Asia/Kolkata")
DAILY_UPLOAD_QUOTA = 6
DAILY_BACKLOG_QUOTA = 5

# ==========================================
# FORMAT YOUTUBE DATE
# ==========================================

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

def get_current_time():
    return datetime.now(pytz.utc).astimezone(IST).strftime("%d %B %Y %I:%M %p IST")

def get_current_date():
    return datetime.now(pytz.utc).astimezone(IST).strftime("%d %B %Y")

# ==========================================
# UPLOAD TO YOUTUBE
# ==========================================

def upload_video_to_youtube(file_path, title, thumbnail_path=None):
    print(f"Uploading {file_path} to YouTube backup channel...")
    try:
        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            print("ERROR: YouTube API secrets are missing from environment.")
            return False

        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )

        youtube = build("youtube", "v3", credentials=credentials)

        body = {
            "snippet": {
                "title": title[:100],  # YouTube titles max 100 chars
                "description": "Automated Backup Video",
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "private"
            }
        }

        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)

        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")

        uploaded_video_id = response.get('id')
        print(f"Upload Complete! Backup Video ID: {uploaded_video_id}")
        
        if thumbnail_path and uploaded_video_id:
            print(f"Uploading thumbnail {thumbnail_path}...")
            try:
                # Convert webp to jpg if needed (YouTube API doesn't accept webp)
                if thumbnail_path.endswith(".webp"):
                    jpg_path = thumbnail_path.replace(".webp", ".jpg")
                    import subprocess
                    subprocess.run(["ffmpeg", "-y", "-i", thumbnail_path, jpg_path], check=True, capture_output=True)
                    thumbnail_path = jpg_path
                youtube.thumbnails().set(
                    videoId=uploaded_video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
                ).execute()
                print("Thumbnail uploaded successfully!")
            except Exception as thumb_err:
                print(f"Failed to upload thumbnail: {thumb_err}")

                
                
        return uploaded_video_id

    except Exception as e:
        print(f"CRITICAL ERROR during video upload: {e}")
        return None

def make_video_public(video_id):
    print(f"Making backup video {video_id} public...")
    try:
        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            print("ERROR: YouTube API secrets are missing from environment.")
            return False

        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )

        youtube = build("youtube", "v3", credentials=credentials)
        
        youtube.videos().update(
            part="status",
            body={
                "id": video_id,
                "status": {"privacyStatus": "public"}
            }
        ).execute()
        print(f"Video {video_id} is now PUBLIC!")
        return True
    except Exception as e:
        print(f"ERROR: Failed to make video {video_id} public: {e}")
        return False

def update_backup_in_sheet(video_id, today_date, backup_video_id=None, retries=3):
    """Update Google Sheets backup status with retry logic."""
    for attempt in range(retries):
        try:
            resp = requests.post(
                GOOGLE_SCRIPT_URL,
                json={
                    "type": "update_backup",
                    "video_id": video_id,
                    "backup_status": "Backed Up",
                    "backup_date": today_date,
                    "backup_video_id": backup_video_id or ""
                },
                timeout=15
            )
            if resp.status_code == 200:
                print(f"Sheet updated: {video_id} marked as Backed Up.")
                return True
            else:
                print(f"Sheet update attempt {attempt+1} failed: HTTP {resp.status_code}")
        except Exception as e:
            print(f"Sheet update attempt {attempt+1} error: {e}")
    print(f"WARNING: Failed to update sheet for {video_id} after {retries} attempts!")
    return False

def is_already_backed_up(video_id):
    """Live re-check of the sheet RIGHT before downloading. The definitive duplicate guard."""
    try:
        resp = requests.get(GOOGLE_SCRIPT_URL + "?action=get_active_videos", allow_redirects=True, timeout=15)
        live_data = resp.json()
        status = live_data.get(video_id, {}).get("backup_status", "Pending")
        if status == "Backed Up":
            print(f"LIVE SHEET CHECK: {video_id} is already 'Backed Up' — SKIPPING download to prevent duplicate.")
            return True
        return False
    except Exception as e:
        print(f"Live sheet check failed for {video_id}: {e}. Proceeding cautiously (will NOT download).")
        return True  # Fail-safe: if we can't confirm, do NOT upload

# ==========================================
# YOUTUBE OPTIONS
# ==========================================

ydl_opts_fast = {
    "quiet": True,
    "extract_flat": "in_playlist",
    "remote_components": ["ejs:npm"],
    "extractor_args": {"youtube": ["player_client=android,web"]}
}
if os.path.exists("cookies.txt"):
    ydl_opts_fast["cookiefile"] = "cookies.txt"

def download_and_backup(video_id, url, title):
    print(f"Downloading video {video_id} via yt-dlp...")
    temp_base = f"temp_video_{video_id}"
    ydl_download_opts = {
        "format": "bestvideo+bestaudio/best",   # No format restrictions — gets 4K/VP9 if available
        "merge_output_format": "mp4",            # FFmpeg merges everything into mp4
        "outtmpl": f"{temp_base}.%(ext)s",
        "quiet": True,
        "writethumbnail": True,
        "remote_components": ["ejs:npm"],
        "extractor_args": {"youtube": ["player_client=android,web"]}
    }
    if os.path.exists("cookies.txt"):
        ydl_download_opts["cookiefile"] = "cookies.txt"
    try:
        with yt_dlp.YoutubeDL(ydl_download_opts) as ydl_dl:
            ydl_dl.download([url])
        
        video_file = f"{temp_base}.mp4"
        thumbnail_file = None
        
        for file in glob.glob(f"{temp_base}.*"):
            if not file.endswith(".mp4"):
                thumbnail_file = file
                break
                
        if os.path.exists(video_file):
            backup_vid_id = upload_video_to_youtube(video_file, title, thumbnail_file)
            
            # Clean up local files
            if os.path.exists(video_file):
                os.remove(video_file)
            if thumbnail_file and os.path.exists(thumbnail_file):
                os.remove(thumbnail_file)
                
            return backup_vid_id
        else:
            print(f"Failed to find downloaded video file {video_file}")
            return None
            
    except Exception as backup_error:
        print(f"Failed to backup video: {backup_error}")
        return None

# ==========================================
# 1. FETCH STATE FROM GOOGLE SHEETS
# ==========================================
print("Fetching current active videos from Google Sheets...")
try:
    response = requests.get(GOOGLE_SCRIPT_URL + "?action=get_active_videos", allow_redirects=True)
    db_active_videos = response.json()
except Exception as e:
    print(f"CRITICAL ERROR: Failed to get active videos from Google Sheets. Error: {e}")
    db_active_videos = {}

is_first_run = len(db_active_videos) == 0
today_date = get_current_date()

# Seed backed_up_this_run from sheet so cross-run duplicates are caught immediately
backed_up_this_run = set(
    vid for vid, data in db_active_videos.items()
    if data.get("backup_status") == "Backed Up"
)

# Count quota used today
quota_used = 0
for vid, data in db_active_videos.items():
    if data.get("backup_status") == "Backed Up":
        bd = str(data.get("backup_date", "")).lstrip("'")
        if bd == today_date:
            quota_used += 1
        elif "T" in bd and bd.endswith("Z"):
            try:
                dt_utc = datetime.strptime(bd[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
                if dt_utc.astimezone(IST).strftime("%d %B %Y") == today_date:
                    quota_used += 1
            except Exception:
                pass

print(f"Daily Quota Used: {quota_used}/{DAILY_UPLOAD_QUOTA}")
print(f"Already backed up (all time): {len(backed_up_this_run)} videos — will not re-upload these.")

# ==========================================
# 2. FETCH YOUTUBE DATA
# ==========================================
print("Scanning channel...")
with yt_dlp.YoutubeDL(ydl_opts_fast) as ydl:
    info = ydl.extract_info(CHANNEL_URL, download=False)
    
    current_channel_ids = []
    new_video_processed = False
    
    for video in info["entries"]:
        try:
            video_id = video.get("id", "")
            if not video_id:
                continue
                
            current_channel_ids.append(video_id)
            title = video.get("title", "Unknown Title")
            url = f"https://youtube.com/watch?v={video_id}"

            # ==========================================
            # PRIORITY #1: NEW VIDEO DETECTED
            # ==========================================
            if video_id not in db_active_videos:
                print(f"New video found: {video_id}")
                
                # Deep extraction for exact time
                with yt_dlp.YoutubeDL({"quiet": True}) as ydl_deep:
                    deep_info = ydl_deep.extract_info(url, download=False)
                    upload_date_raw = (
                        deep_info.get("timestamp") or 
                        deep_info.get("release_timestamp") or 
                        deep_info.get("upload_date") or 
                        deep_info.get("release_date")
                    )

                upload_time = format_youtube_date(upload_date_raw)

                # Send new video info to Google Sheets
                requests.post(
                    GOOGLE_SCRIPT_URL,
                    json={
                        "type": "new_video",
                        "title": title,
                        "upload_time": upload_time,
                        "video_id": video_id,
                        "url": url
                    }
                )

                # Add to local cache so we don't treat it as missing later
                db_active_videos[video_id] = {
                    "title": title,
                    "upload_time": upload_time,
                    "status": "Active",
                    "url": url,
                    "backup_status": "Pending",
                    "backup_date": ""
                }

                if not is_first_run:
                    message = f"🚨 NEW VIDEO UPLOADED 🚨\n\nTitle:\n{title}\n\nUpload Date:\n{upload_time}\n\nURL:\n{url}"
                    if BOT_TOKEN:
                        requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                            data={"chat_id": CHAT_ID, "text": message}
                        )
                    
                    # ⚠️ DUPLICATE GUARD: Check in-memory state + live sheet re-check before downloading
                    if quota_used < DAILY_UPLOAD_QUOTA and video_id not in backed_up_this_run:
                        if is_already_backed_up(video_id):  # Live re-check right before download
                            backed_up_this_run.add(video_id)  # Sync in-memory state
                        else:
                            print("Prioritizing new video for backup...")
                            backup_vid_id = download_and_backup(video_id, url, title)
                            if backup_vid_id:
                                sheet_updated = update_backup_in_sheet(video_id, today_date, backup_vid_id)
                                if not sheet_updated:
                                    print(f"WARNING: Upload succeeded but sheet update FAILED for {video_id}. Retrying once more...")
                                    update_backup_in_sheet(video_id, today_date, backup_vid_id)  # One extra retry
                                db_active_videos[video_id]["backup_status"] = "Backed Up"
                                db_active_videos[video_id]["backup_date"] = today_date
                                db_active_videos[video_id]["backup_video_id"] = backup_vid_id
                                backed_up_this_run.add(video_id)
                                quota_used += 1
                                new_video_processed = True
                            else:
                                print(f"Download/upload failed for {video_id}. Will retry next run.")
                    elif video_id in backed_up_this_run:
                        print(f"SKIPPED: {video_id} is already marked as Backed Up — preventing duplicate upload.")
                    else:
                        print(f"Daily quota reached ({DAILY_UPLOAD_QUOTA}). Will backup new video tomorrow.")
                else:
                    print("(Skipped Telegram notification & Backup because this is the first initial setup run)")

        except Exception as e:
            print("ERROR on video parsing:", e)

    # ==========================================
    # PRIORITY #2: BACKLOG DOWNLOADS (oldest first — 2012 → present)
    # ==========================================
    if not is_first_run and not new_video_processed and quota_used < DAILY_BACKLOG_QUOTA:
        print("Checking for backlog videos to backup (oldest first)...")
        
        # Go through ALL videos oldest→newest (YouTube returns newest first, so we reverse)
        pending_video_to_backup = None
        for video_id in reversed(current_channel_ids):
            vid_data = db_active_videos.get(video_id, {})
            if vid_data.get("backup_status") != "Backed Up" and video_id not in backed_up_this_run:
                print(f"Found oldest pending video for backup: {video_id} — {vid_data.get('title', '')}")
                pending_video_to_backup = video_id
                break
        
        if pending_video_to_backup:
            video_id = pending_video_to_backup
            db_info = db_active_videos.get(video_id, {})
            title = db_info.get("title", "Unknown Title")
            url = db_info.get("url", f"https://youtube.com/watch?v={video_id}")
            
            if is_already_backed_up(video_id):  # Live re-check before backlog download too
                backed_up_this_run.add(video_id)
            else:
                backup_vid_id = download_and_backup(video_id, url, title)
                if backup_vid_id:
                    update_backup_in_sheet(video_id, today_date, backup_vid_id)
                    backed_up_this_run.add(video_id)
                    quota_used += 1
        else:
            print("No pending backlog videos found.")
            
        # We only process ONE backlog video per run to prevent GitHub Actions timeout!
    elif quota_used >= DAILY_BACKLOG_QUOTA:
        print(f"Daily backlog quota of {DAILY_BACKLOG_QUOTA} reached. Reserved 1 slot for new videos today.")

    # ==========================================
    # 3. CHECK FOR DELETED OR PRIVATE VIDEOS
    # ==========================================
    if not is_first_run:
        print("Checking for deleted videos...")
        for db_video_id, db_video_data in db_active_videos.items():
            if db_video_id not in current_channel_ids:
                print(f"Deleted/Private video found: {db_video_id}")
                
                original_title = db_video_data.get("title", "Unknown")
                original_upload_time = db_video_data.get("upload_time", "Unknown")
                video_url = db_video_data.get("url", f"https://youtube.com/watch?v={db_video_id}")
                deleted_time = get_current_time()
                status = "Deleted/Private"
                backup_video_id = db_video_data.get("backup_video_id", "")
                
                # Automatically make the backup video public!
                if backup_video_id:
                    make_video_public(backup_video_id)
                
                # Send to Google Sheets
                requests.post(
                    GOOGLE_SCRIPT_URL,
                    json={
                        "type": "deleted_video",
                        "title": original_title,
                        "original_upload_time": original_upload_time,
                        "deleted_time": deleted_time,
                        "status": status,
                        "video_id": db_video_id,
                        "url": video_url,
                        "backup_video_id": backup_video_id
                    }
                )

                # Telegram Notification
                message = f"❌ VIDEO DELETED OR MADE PRIVATE ❌\n\nOriginal Title:\n{original_title}\n\nOriginal Upload Date:\n{original_upload_time}\n\nDeleted Time:\n{deleted_time}\n\nURL:\n{video_url}"
                if BOT_TOKEN:
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        data={"chat_id": CHAT_ID, "text": message}
                    )

print("BOT COMPLETED SUCCESSFULLY")