import yt_dlp
import requests
import pytz
from datetime import datetime
import os
import glob
import time
import subprocess
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================
# SETTINGS
# ==========================================

def check_service_health():
    print("Checking GitHub system status...")
    try:
        resp = requests.get("https://www.githubstatus.com/api/v2/status.json", timeout=10)
        if resp.status_code == 200:
            indicator = resp.json().get("status", {}).get("indicator", "none")
            if indicator in ["major", "critical"]:
                print(f"CRITICAL: GitHub is currently experiencing a {indicator} outage.")
                print("Pausing bot operations until services stabilize.")
                exit(0)
    except Exception as e:
        print(f"WARNING: Could not check GitHub status: {e}")

check_service_health()

def validate_cookies(cookie_file="cookies.txt"):
    """Check if the cookie file contains the essential YouTube auth cookies and they haven't expired."""
    if not os.path.exists(cookie_file):
        return False, "Cookie file missing"

    file_size = os.path.getsize(cookie_file)
    if file_size < 100:
        return False, f"Cookie file suspiciously small ({file_size} bytes)"

    required_cookies = ["__Secure-1PSID", "LOGIN_INFO"]
    with open(cookie_file, "r", errors="replace") as f:
        content = f.read()

    missing = [c for c in required_cookies if c not in content]
    if missing:
        return False, f"Missing critical cookies: {', '.join(missing)}"

    # Check for expired cookies
    now_ts = time.time()
    for line in content.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            try:
                expiry = int(parts[4])
                cookie_name = parts[5]
                if cookie_name in required_cookies and 0 < expiry < now_ts:
                    return False, f"Cookie '{cookie_name}' has expired (expiry: {datetime.fromtimestamp(expiry).strftime('%Y-%m-%d')})"
            except (ValueError, IndexError):
                pass

    return True, "OK"

def send_cookie_alert(reason):
    """Send a Telegram alert when cookies are invalid so the user knows to re-export."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return
    message = (
        "⚠️ COOKIE ALERT ⚠️\n\n"
        f"YouTube cookies are invalid:\n{reason}\n\n"
        "The bot will attempt downloads using fallback strategies, "
        "but you should re-export fresh cookies ASAP.\n\n"
        "Remember: export cookies then CLOSE the browser — DO NOT log out!"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message},
            timeout=10
        )
    except Exception:
        pass

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = "765673702"

# Validate cookies at startup
if os.path.exists("cookies.txt"):
    cookies_valid, cookie_reason = validate_cookies()
    if cookies_valid:
        print("Cookie validation: OK — auth cookies present and not expired.")
    else:
        print(f"WARNING: Cookie validation FAILED — {cookie_reason}")
        send_cookie_alert(cookie_reason)
else:
    print("WARNING: No cookies.txt found! Downloads will likely fail on datacenter IPs.")
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyAarmgcJWsMYdHW9fhbKrTZXGsu77TFKVAQanMZmTY1xdgtq320MgiZfusuLvXlpAF/exec"
CHANNEL_URL = "https://www.youtube.com/@SandeepSeminars/videos"
CHANNEL_ID = "UCBqFKDipsnzvJdt6UT0lMIg"
UPLOADS_PLAYLIST_ID = "UU" + CHANNEL_ID[2:]  # Uploads playlist = Channel ID with UC→UU

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
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", thumbnail_path, "-q:v", "1", jpg_path],
                        check=True, capture_output=True
                    )
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

def get_youtube_client():
    """Build and return an authenticated YouTube client using the backup channel credentials."""
    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        return None
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    return build("youtube", "v3", credentials=credentials)

def scan_channel_via_api():
    """Scan all videos from the channel using YouTube Data API (no cookies/scraping needed)."""
    print("Scanning channel via YouTube Data API...")
    youtube = get_youtube_client()
    if not youtube:
        print("ERROR: YouTube API credentials missing — cannot scan via API.")
        return None

    all_videos = []
    next_page_token = None

    while True:
        try:
            request = youtube.playlistItems().list(
                part="snippet",
                playlistId=UPLOADS_PLAYLIST_ID,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()

            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                video_id = snippet.get("resourceId", {}).get("videoId", "")
                if video_id:
                    all_videos.append({
                        "id": video_id,
                        "title": snippet.get("title", "Unknown Title"),
                        "publishedAt": snippet.get("publishedAt", ""),
                    })

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        except Exception as e:
            print(f"ERROR during API channel scan: {e}")
            return None

    print(f"API scan complete: found {len(all_videos)} videos.")
    return all_videos

def check_and_reset_deleted_backups(db_active_videos, today_date, quota_used, backed_up_this_run):
    """
    Checks if every backup video marked 'Backed Up' in the sheet still
    exists on the backup YouTube channel. If YouTube deleted any of them
    (copyright strike, enforcement, etc.), this immediately re-uploads them
    in the same run. Returns the updated quota_used count.
    """
    print("Verifying backup videos still exist on YouTube...")
    youtube = get_youtube_client()
    if not youtube:
        print("WARNING: YouTube credentials missing — skipping backup verification.")
        return quota_used

    # Collect all backup video IDs that we think are 'Backed Up'
    to_check = {
        vid: data["backup_video_id"]
        for vid, data in db_active_videos.items()
        if data.get("backup_status") == "Backed Up" and data.get("backup_video_id")
    }

    if not to_check:
        print("No backed-up videos to verify.")
        return quota_used

    # YouTube API allows checking up to 50 video IDs at once
    backup_ids = list(to_check.values())
    existing_backup_ids = set()
    for i in range(0, len(backup_ids), 50):
        chunk = backup_ids[i:i+50]
        try:
            resp = youtube.videos().list(part="id", id=",".join(chunk)).execute()
            for item in resp.get("items", []):
                existing_backup_ids.add(item["id"])
        except Exception as e:
            print(f"ERROR checking backup video existence: {e}")
            return quota_used  # If API fails, skip to be safe

    # Find which backup videos were deleted by YouTube and re-upload them
    for source_vid, backup_vid in to_check.items():
        if backup_vid not in existing_backup_ids:
            current_attempts = db_active_videos[source_vid].get("reupload_attempts", 0)
            new_attempts = current_attempts + 1

            print(f"Backup video {backup_vid} was DELETED by YouTube (attempt {new_attempts}/3).")

            # Reset in Google Sheets first (sheet will mark as YouTube Removed if attempts >= 3)
            try:
                requests.post(
                    GOOGLE_SCRIPT_URL,
                    json={"type": "reset_backup", "video_id": source_vid},
                    timeout=15
                )
            except Exception as e:
                print(f"ERROR resetting sheet for {source_vid}: {e}")

            # Update local cache
            db_active_videos[source_vid]["reupload_attempts"] = new_attempts
            db_active_videos[source_vid]["backup_video_id"] = ""
            db_active_videos[source_vid]["backup_date"] = ""
            backed_up_this_run.discard(source_vid)

            if new_attempts >= 3:
                # YouTube keeps removing it (copyright enforcement) — stop trying
                print(f"PERMANENTLY SKIPPING {source_vid} — YouTube has removed it {new_attempts} times. Marked as 'YouTube Removed'.")
                db_active_videos[source_vid]["backup_status"] = "YouTube Removed"
                continue  # Do NOT re-upload

            # Reset local status to Pending and re-upload if quota allows
            db_active_videos[source_vid]["backup_status"] = "Pending"

            if quota_used < DAILY_UPLOAD_QUOTA:
                vid_data = db_active_videos.get(source_vid, {})
                title = vid_data.get("title", "Unknown Title")
                url = vid_data.get("url", f"https://youtube.com/watch?v={source_vid}")
                print(f"Re-uploading: {title}")
                new_backup_id = download_and_backup(source_vid, url, title)
                if new_backup_id:
                    update_backup_in_sheet(source_vid, today_date, new_backup_id)
                    db_active_videos[source_vid]["backup_status"] = "Backed Up"
                    db_active_videos[source_vid]["backup_video_id"] = new_backup_id
                    db_active_videos[source_vid]["backup_date"] = today_date
                    backed_up_this_run.add(source_vid)
                    quota_used += 1
                    print(f"Successfully re-uploaded {source_vid} as backup {new_backup_id}")
                else:
                    print(f"Re-upload failed for {source_vid}. Will retry on next run.")
            else:
                print(f"Daily quota reached — {source_vid} will be re-uploaded on the next run.")

    print("Backup verification complete.")
    return quota_used

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
    """Live re-check of the sheet RIGHT before downloading. Falls back to verified in-memory state on timeout."""
    # First check in-memory state
    try:
        if db_active_videos and db_active_videos.get(video_id, {}).get("backup_status") == "Backed Up":
            print(f"IN-MEMORY CHECK: {video_id} is already 'Backed Up' — SKIPPING.")
            return True
    except Exception:
        pass

    try:
        resp = requests.get(GOOGLE_SCRIPT_URL + "?action=get_active_videos", allow_redirects=True, timeout=30)
        if resp.status_code == 200:
            live_data = resp.json()
            if isinstance(live_data, dict):
                status = live_data.get(video_id, {}).get("backup_status", "Pending")
                if status == "Backed Up":
                    print(f"LIVE SHEET CHECK: {video_id} is already 'Backed Up' — SKIPPING download to prevent duplicate.")
                    return True
                return False
    except Exception as e:
        print(f"Live sheet check network warning for {video_id}: {e}. Falling back to in-memory sheet state.")

    # Fallback to in-memory state fetched at startup rather than aborting download
    if db_active_videos and db_active_videos.get(video_id, {}).get("backup_status") == "Backed Up":
        return True
    return False

# ==========================================
# YOUTUBE OPTIONS
# ==========================================

ydl_opts_fast = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": "in_playlist",
    "retries": 5,
    "sleep_interval": 3,
    "max_sleep_interval": 8,
    "remote_components": ["ejs:github"],
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
}
if os.path.exists("cookies.txt"):
    ydl_opts_fast["cookiefile"] = "cookies.txt"

def log_video_quality(video_file):
    """Log the actual video/audio quality using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_file],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return
        probe = json.loads(result.stdout)
        for stream in probe.get("streams", []):
            codec_type = stream.get("codec_type", "")
            if codec_type == "video":
                width = stream.get("width", "?")
                height = stream.get("height", "?")
                codec = stream.get("codec_name", "?")
                fps = stream.get("r_frame_rate", "?")
                bitrate = stream.get("bit_rate", "")
                br_str = f" @ {int(bitrate)//1000}kbps" if bitrate else ""
                print(f"  🎥 Video: {width}x{height} {codec}{br_str} ({fps} fps)")
            elif codec_type == "audio":
                codec = stream.get("codec_name", "?")
                sample_rate = stream.get("sample_rate", "?")
                bitrate = stream.get("bit_rate", "")
                br_str = f" @ {int(bitrate)//1000}kbps" if bitrate else ""
                channels = stream.get("channels", "?")
                print(f"  🎧 Audio: {codec}{br_str} ({sample_rate}Hz, {channels}ch)")
    except Exception as e:
        print(f"  (Could not probe quality: {e})")

def download_and_backup(video_id, url, title):
    print(f"Downloading video {video_id} via yt-dlp...")
    temp_base = f"temp_video_{video_id}"

    # Log cookie state so we can diagnose auth failures from the logs
    if os.path.exists("cookies.txt"):
        cookie_size = os.path.getsize("cookies.txt")
        print(f"cookies.txt found ({cookie_size} bytes)")
        if cookie_size < 100:
            print("WARNING: cookies.txt is suspiciously small — may be empty or corrupt!")
    else:
        print("WARNING: No cookies.txt found! Download will likely fail on datacenter IPs.")

    # Base options shared by all strategies
    base_opts = {
        "format": "bestvideo+bestaudio/best",   # Highest quality video + audio streams
        "format_sort": ["res", "vbr", "abr"],    # Explicitly sort: resolution first, then video bitrate, then audio bitrate
        "merge_output_format": "mp4",            # FFmpeg merges everything into mp4
        "outtmpl": f"{temp_base}.%(ext)s",
        "quiet": False,
        "no_warnings": True,                    # Clean terminal output: silence cosmetic cookie rotation warnings
        "writethumbnail": True,
        "remote_components": ["ejs:github"],      # Download JS challenge solver from GitHub (required for n-param)
        "postprocessors": [
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg"},  # Auto-convert thumbnails to max quality jpg
        ],
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }
    }
    if os.path.exists("cookies.txt"):
        base_opts["cookiefile"] = "cookies.txt"

    # Multi-strategy fallback chain — each strategy targets full 1080p/4K HD resolution
    # while bypassing bot challenges on cloud runners.
    strategies = [
        {
            "name": "tv_embedded client (1080p Full HD + high bitrate audio)",
            "overrides": {"extractor_args": {"youtube": {"player_client": ["tv_embedded"]}}},
        },
        {
            "name": "all clients adaptive (1080p multi-stream)",
            "overrides": {"extractor_args": {"youtube": {"player_client": ["all"]}}},
        },
        {
            "name": "android_creator client (1080p HD)",
            "overrides": {"extractor_args": {"youtube": {"player_client": ["android_creator", "android_testsuite"]}}},
        },
        {
            "name": "standard web client (1080p with Deno JS challenge solver)",
            "overrides": {},
        },
        {
            "name": "fallback mobile client",
            "overrides": {"extractor_args": {"youtube": {"player_client": ["mweb", "android"]}}},
        },
    ]

    total = len(strategies)
    last_error = None
    bot_detected = False

    for attempt, strategy in enumerate(strategies):
        opts = {**base_opts, **strategy["overrides"]}
        print(f"Download attempt {attempt + 1}/{total}: {strategy['name']}...")
        try:
            with yt_dlp.YoutubeDL(opts) as ydl_dl:
                ydl_dl.download([url])
            last_error = None
            break  # success
        except Exception as dl_err:
            last_error = dl_err
            err_msg = f"[{type(dl_err).__name__}] {dl_err}"
            print(f"Download attempt {attempt + 1}/{total} failed: {err_msg}")
            # Only remove cookiefile if there is an actual syntax / cookiejar file-reading error,
            # NOT when yt-dlp prints its help text containing the word '--cookies'.
            err_lower = str(dl_err).lower()
            if any(term in err_lower for term in ["cookiejar", "could not load cookie", "netscape format error", "malformed cookie", "cookie parsing error"]):
                print("Corrupted/unparseable cookiefile detected — removing cookiefile for remaining attempts.")
                base_opts.pop("cookiefile", None)
            if "Sign in to confirm" in str(dl_err) or "not a bot" in str(dl_err):
                bot_detected = True
            # Clean up partial files before next attempt
            for partial in glob.glob(f"{temp_base}.part*"):
                try: os.remove(partial)
                except: pass

    if last_error is not None:
        # All strategies failed — clean up and alert
        for partial in glob.glob(f"{temp_base}.*"):
            try: os.remove(partial)
            except: pass
        print(f"Failed to backup video after {total} attempts: [{type(last_error).__name__}] {last_error}")

        # Send Telegram alert if bot detection was the cause
        if bot_detected:
            send_cookie_alert(
                f"All {total} download strategies failed for video {video_id} "
                f"with bot detection. Cookies are likely expired — please re-export!"
            )
        return None

    # Download succeeded — locate files and upload
    video_file = f"{temp_base}.mp4"
    thumbnail_file = None

    # Log the quality of the downloaded video
    if os.path.exists(video_file):
        print(f"Download complete — Quality report for {video_id}:")
        log_video_quality(video_file)

    for file in glob.glob(f"{temp_base}.*"):
        if not file.endswith(".mp4"):
            thumbnail_file = file
            break

    # Log thumbnail info
    if thumbnail_file and os.path.exists(thumbnail_file):
        thumb_size = os.path.getsize(thumbnail_file)
        print(f"  🖼️  Thumbnail: {thumbnail_file} ({thumb_size:,} bytes)")

    try:
        if os.path.exists(video_file):
            backup_vid_id = upload_video_to_youtube(video_file, title, thumbnail_file)
            return backup_vid_id
        else:
            print(f"Failed to find downloaded video file {video_file}")
            return None
    finally:
        # Always clean up local files, even if upload fails
        if os.path.exists(video_file):
            os.remove(video_file)
        if thumbnail_file and os.path.exists(thumbnail_file):
            os.remove(thumbnail_file)
        # Clean up any other leftover temp files (e.g. .part, .webp converted .jpg)
        for leftover in glob.glob(f"{temp_base}*"):
            try: os.remove(leftover)
            except: pass

# ==========================================
# 1. FETCH STATE FROM GOOGLE SHEETS
# ==========================================
print("Fetching current active videos from Google Sheets...")
db_active_videos = None
for attempt in range(5):
    try:
        response = requests.get(GOOGLE_SCRIPT_URL + "?action=get_active_videos", allow_redirects=True, timeout=45)
        response.raise_for_status()
        db_active_videos = response.json()
        if not isinstance(db_active_videos, dict):
            raise ValueError("Response is not a valid JSON dictionary")
        break
    except Exception as e:
        print(f"Failed to get active videos (Attempt {attempt+1}/5). Error: {e}")
        if attempt < 4:
            import time
            time.sleep(15)  # Let Google's servers cool down to avoid 404 anti-abuse triggers

if db_active_videos is None:
    print("CRITICAL ERROR: Failed to get active videos from Google Sheets after multiple attempts.")
    print("Aborting run to prevent data corruption (e.g. treating sheet as empty).")
    exit(1)

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

# Check if it's past 10:30 PM (22:30) IST. If so, raise the backlog quota to 6 to use the reserved slot.
now_ist = datetime.now(pytz.utc).astimezone(IST)
if now_ist.hour > 22 or (now_ist.hour == 22 and now_ist.minute >= 30):
    DAILY_BACKLOG_QUOTA = 6
    print("Time is past 10:30 PM IST. Raising DAILY_BACKLOG_QUOTA to 6 to utilize the reserved slot.")

print(f"Daily Quota Used: {quota_used}/{DAILY_UPLOAD_QUOTA}")
print(f"Already backed up (all time): {len(backed_up_this_run)} videos — will not re-upload these.")

# ==========================================
# CHECK: Did YouTube silently delete any of our backup videos?
# ==========================================
if not is_first_run:
    quota_used = check_and_reset_deleted_backups(db_active_videos, today_date, quota_used, backed_up_this_run)


# ==========================================
# 2. FETCH YOUTUBE DATA
# ==========================================
print("Scanning channel...")
channel_entries = []

# Primary method: YouTube Data API (reliable, no cookies/IP issues)
api_videos = scan_channel_via_api()
if api_videos is not None and len(api_videos) > 0:
    channel_entries = api_videos
    print(f"Channel scan successful via API: {len(channel_entries)} videos found.")
else:
    # Fallback: yt-dlp scraping (may fail due to cookies/IP, but worth trying)
    print("API scan failed or returned empty. Falling back to yt-dlp scraping...")
    info = None
    for _attempt in range(3):
        try:
            with yt_dlp.YoutubeDL(ydl_opts_fast) as ydl:
                info = ydl.extract_info(CHANNEL_URL, download=False)
            break  # success — exit retry loop
        except Exception as scan_err:
            err_str = str(scan_err).lower()
            print(f"Channel scan attempt {_attempt + 1}/3 failed: {scan_err}")
            
            # If the error is about cookies being invalid or badly formatted, retry without cookies
            if "cookie" in err_str or "netscape format" in err_str:
                print("Cookie error detected! Retrying without cookies...")
                if os.path.exists("cookies.txt"):
                    try: os.remove("cookies.txt")
                    except: pass
                if "cookiefile" in ydl_opts_fast:
                    del ydl_opts_fast["cookiefile"]
                if "cookiesfrombrowser" in ydl_opts_fast:
                    del ydl_opts_fast["cookiesfrombrowser"]
            
            if _attempt < 2:
                import time; time.sleep(10)
    
    if info is not None and info.get("entries"):
        channel_entries = [
            {"id": v.get("id", ""), "title": v.get("title", "Unknown Title")}
            for v in info["entries"]
            if v.get("id")
        ]

if not channel_entries:
    print("CRITICAL: Could not scan channel via API or yt-dlp. Exiting.")
    exit(1)

current_channel_ids = []
new_video_processed = False

# ==========================================
# SCAN SANITY CHECK — prevent mass false-deletion
# ==========================================
# How many videos does the sheet currently know about?
db_known_count = len(db_active_videos)
# We set this flag AFTER populating current_channel_ids (see after the loop below).
# It controls whether the deleted-video section is allowed to run.
scan_looks_valid = True  # will be re-evaluated after the scan loop

# Deep extraction options (with cookies + anti-bot settings, matching ydl_opts_fast)
ydl_opts_deep = {
    "quiet": True,
    "no_warnings": True,
    "retries": 3,
    "sleep_interval": 3,
    "max_sleep_interval": 8,
    "remote_components": ["ejs:github"],      # Download JS challenge solver from GitHub (required for n-param)
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
}
if os.path.exists("cookies.txt"):
    ydl_opts_deep["cookiefile"] = "cookies.txt"

for video in channel_entries:
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
            
            # Deep extraction for exact upload time.
            # IMPORTANT: uses ydl_opts_deep (with cookies + anti-bot headers) to avoid bot-detection.
            # Falls back to flat-scan date if deep extraction fails — video is still registered.
            upload_date_raw = None
            try:
                with yt_dlp.YoutubeDL(ydl_opts_deep) as ydl_deep:
                    deep_info = ydl_deep.extract_info(url, download=False)
                    upload_date_raw = (
                        deep_info.get("timestamp") or 
                        deep_info.get("release_timestamp") or 
                        deep_info.get("upload_date") or 
                        deep_info.get("release_date")
                    )
            except Exception as deep_err:
                # Deep extraction failed (e.g. bot detection). Use the flat-scan date if present.
                print(f"WARNING: Deep extraction failed for {video_id} ({deep_err}). Using flat-scan metadata.")
                upload_date_raw = (
                    video.get("timestamp") or
                    video.get("release_timestamp") or
                    video.get("upload_date") or
                    video.get("publishedAt")
                )

            upload_time = format_youtube_date(upload_date_raw) if upload_date_raw else "Unknown"

            # Register video in Google Sheets — happens even if deep extraction failed.
            # This prevents the bot from treating the same video as "new" on every subsequent run.
            try:
                requests.post(
                    GOOGLE_SCRIPT_URL,
                    json={
                        "type": "new_video",
                        "title": title,
                        "upload_time": upload_time,
                        "video_id": video_id,
                        "url": url
                    },
                    timeout=15
                )
            except Exception as sheet_err:
                print(f"WARNING: Could not post new video {video_id} to sheet: {sheet_err}")

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
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                            data={"chat_id": CHAT_ID, "text": message},
                            timeout=10
                        )
                    except Exception as tg_err:
                        print(f"WARNING: Telegram notification failed: {tg_err}")
                
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
        status = vid_data.get("backup_status", "Pending")
        if status in ("Backed Up", "YouTube Removed"):
            continue  # Skip already backed up or permanently removed videos
        if video_id not in backed_up_this_run:
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
# SAFETY GUARD: Only run deleted-video detection if the channel scan looks complete.
# If the scan returned far fewer videos than we know exist (e.g. yt-dlp was blocked
# mid-scan and returned partial results), running this section would incorrectly mark
# hundreds of videos as deleted — which is exactly what wiped the sheet.
if db_known_count > 0 and len(current_channel_ids) < db_known_count * 0.5:
    scan_looks_valid = False
    print(
        f"WARNING: Channel scan returned only {len(current_channel_ids)} videos but the sheet "
        f"has {db_known_count}. This looks like a partial/failed scan — "
        f"SKIPPING deleted-video detection to prevent false mass-deletion."
    )

if not is_first_run and scan_looks_valid:
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
            try:
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
                    },
                    timeout=15
                )
            except Exception as del_err:
                print(f"WARNING: Failed to post deleted-video to sheet for {db_video_id}: {del_err}")

            # Telegram Notification
            message = f"❌ VIDEO DELETED OR MADE PRIVATE ❌\n\nOriginal Title:\n{original_title}\n\nOriginal Upload Date:\n{original_upload_time}\n\nDeleted Time:\n{deleted_time}\n\nURL:\n{video_url}"
            if BOT_TOKEN:
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        data={"chat_id": CHAT_ID, "text": message},
                        timeout=10
                    )
                except Exception as tg_err:
                    print(f"WARNING: Telegram notification failed for {db_video_id}: {tg_err}")

# Trigger sheet sorting to ensure newest videos are always at the top
try:
    requests.post(GOOGLE_SCRIPT_URL, json={"type": "sort_sheet"}, timeout=15)
    print("Triggered final sheet sort.")
except Exception as e:
    print(f"WARNING: Failed to trigger sheet sort: {e}")

print("BOT COMPLETED SUCCESSFULLY")