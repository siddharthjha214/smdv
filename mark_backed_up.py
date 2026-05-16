import requests
import yt_dlp
import pytz
from datetime import datetime

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzxPrjREbE3fl6sgnPihrqLUCWKGzFs6Uv1LD9ph0ITPqy9GtMwgukNiLA00ew96Luj/exec"
IST = pytz.timezone("Asia/Kolkata")

VIDEO_IDS_TO_MARK = [
    "ZGmu-hizM1E",
    "vRe-eWNhk8M",
]

today_date = datetime.now(pytz.utc).astimezone(IST).strftime("%d %B %Y")

# Step 1: Fetch what's already in the sheet
print("Fetching current sheet state...")
try:
    resp = requests.get(GOOGLE_SCRIPT_URL + "?action=get_active_videos", allow_redirects=True, timeout=15)
    existing_videos = resp.json()
    print(f"  Found {len(existing_videos)} videos already in sheet.")
except Exception as e:
    print(f"  Could not fetch sheet: {e}")
    existing_videos = {}

for video_id in VIDEO_IDS_TO_MARK:
    url = f"https://youtube.com/watch?v={video_id}"
    print(f"\nProcessing {video_id}...")

    # Step 2: If video is NOT in sheet, add it first
    if video_id not in existing_videos:
        print(f"  Not in sheet yet — fetching info from YouTube...")
        try:
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown Title")
                upload_date_raw = (
                    info.get("timestamp") or
                    info.get("release_timestamp") or
                    info.get("upload_date") or
                    "Unknown"
                )
                # Format date
                if isinstance(upload_date_raw, (int, float)):
                    dt_utc = datetime.fromtimestamp(upload_date_raw, tz=pytz.utc)
                    upload_time = dt_utc.astimezone(IST).strftime("%d %B %Y %I:%M %p IST")
                elif isinstance(upload_date_raw, str) and len(upload_date_raw) == 8 and upload_date_raw.isdigit():
                    dt = datetime.strptime(upload_date_raw, "%Y%m%d")
                    upload_time = IST.localize(dt).strftime("%d %B %Y %I:%M %p IST")
                else:
                    upload_time = "Unknown"

            print(f"  Title: {title}")
            # Add to sheet as new_video
            r = requests.post(GOOGLE_SCRIPT_URL, json={
                "type": "new_video",
                "title": title,
                "upload_time": upload_time,
                "video_id": video_id,
                "url": url
            }, timeout=15)
            print(f"  Added to sheet: HTTP {r.status_code}")
        except Exception as e:
            print(f"  ERROR fetching YouTube info: {e}")
            print(f"  Skipping {video_id}")
            continue
    else:
        print(f"  Already exists in sheet — skipping add.")

    # Step 3: Mark as Backed Up
    try:
        r = requests.post(GOOGLE_SCRIPT_URL, json={
            "type": "update_backup",
            "video_id": video_id,
            "backup_status": "Backed Up",
            "backup_date": today_date
        }, timeout=15)
        if r.status_code == 200:
            print(f"  ✅ {video_id} → Backed Up on {today_date}")
        else:
            print(f"  ❌ update_backup failed: HTTP {r.status_code}")
    except Exception as e:
        print(f"  ❌ update_backup error: {e}")

print("\nDone.")
