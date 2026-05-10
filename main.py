import yt_dlp
import requests
import pytz
from datetime import datetime
import os

# ==========================================
# SETTINGS
# ==========================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = "765673702"
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzKtlIvMXCLQQV0LvAbeNKfhoW8LzTfbwSjcn7MhQQHXUHXhcBWAhY5Cu06ujJDPe7T/exec"
CHANNEL_URL = "https://www.youtube.com/@SandeepSeminars/videos"

IST = pytz.timezone("Asia/Kolkata")

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

# ==========================================
# YOUTUBE OPTIONS
# ==========================================

ydl_opts_fast = {
    "quiet": True,
    "extract_flat": "in_playlist",
    "remote_components": ["ejs:github"]
}

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

# ==========================================
# 2. FETCH YOUTUBE DATA
# ==========================================
print("Scanning channel...")
with yt_dlp.YoutubeDL(ydl_opts_fast) as ydl:
    info = ydl.extract_info(CHANNEL_URL, download=False)
    
    current_channel_ids = []
    
    for video in info["entries"]:
        try:
            video_id = video.get("id", "")
            if not video_id:
                continue
                
            current_channel_ids.append(video_id)
            title = video.get("title", "Unknown Title")
            url = f"https://youtube.com/watch?v={video_id}"

            # ==========================================
            # NEW VIDEO DETECTED
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

                # Send to Google Sheets
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

                # Telegram Notification (prevent spam on initial GitHub Action run)
                if not is_first_run:
                    message = f"🚨 NEW VIDEO UPLOADED 🚨\n\nTitle:\n{title}\n\nUpload Date:\n{upload_time}\n\nURL:\n{url}"
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        data={"chat_id": CHAT_ID, "text": message}
                    )
                else:
                    print("(Skipped Telegram notification because this is the first initial setup run)")

        except Exception as e:
            print("ERROR on video parsing:", e)

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
                        "url": video_url
                    }
                )

                # Telegram Notification
                message = f"❌ VIDEO DELETED OR MADE PRIVATE ❌\n\nOriginal Title:\n{original_title}\n\nOriginal Upload Date:\n{original_upload_time}\n\nDeleted Time:\n{deleted_time}\n\nURL:\n{video_url}"
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    data={"chat_id": CHAT_ID, "text": message}
                )

print("BOT COMPLETED SUCCESSFULLY")