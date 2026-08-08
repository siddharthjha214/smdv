"""
FAST BULK RECOVERY SCRIPT
=========================
Uses the new bulk_restore endpoint to restore all 658 videos in batches of 50.
MUCH faster than 1-per-second — completes in under 2 minutes.
Requires the updated apps_script.js to be deployed first.
"""

import json, time, requests, os, yt_dlp
from datetime import datetime
import pytz

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbx4mICDCIPFqU8pINja2A7OZdmZczmeUsSsYgx3Ru1G8f0JoAzfO1lrtRlwmwi6n33U/exec"
CACHE_FILE = "/tmp/channel_videos.json"
IST = pytz.timezone("Asia/Kolkata")
BATCH_SIZE = 50

def format_date(upload_date):
    try:
        if isinstance(upload_date, str):
            if upload_date.isdigit() and len(upload_date) == 8:
                dt = datetime.strptime(upload_date, "%Y%m%d")
                return IST.localize(dt).strftime("%d %B %Y %I:%M %p IST")
        if isinstance(upload_date, (int, float)):
            dt_utc = datetime.fromtimestamp(upload_date, tz=pytz.utc)
            return dt_utc.astimezone(IST).strftime("%d %B %Y %I:%M %p IST")
        return "Unknown"
    except:
        return "Unknown"

# 1. Scan channel (or use cache)
if os.path.exists(CACHE_FILE):
    print("Loading cached channel scan...")
    with open(CACHE_FILE) as f:
        entries = json.load(f)
else:
    print("Scanning channel (60s)...")
    ydl_opts = {
        "quiet": True, "extract_flat": "in_playlist",
        "extractor_args": {"youtube": {"player_client": ["mweb", "web"]}},
        "retries": 3,
        "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info("https://www.youtube.com/@SandeepSeminars/videos", download=False)
    entries = info.get("entries", [])
    with open(CACHE_FILE, "w") as f:
        json.dump(entries, f)

print(f"Channel has {len(entries)} videos.\n")

# 2. Build the video list (oldest first)
all_videos = []
for v in reversed(entries):
    vid_id = v.get("id", "")
    if not vid_id:
        continue
    raw_date = v.get("timestamp") or v.get("release_timestamp") or v.get("upload_date")
    all_videos.append({
        "video_id": vid_id,
        "title": (v.get("title") or "Unknown Title").strip(),
        "upload_time": format_date(raw_date) if raw_date else "Unknown",
        "url": f"https://youtube.com/watch?v={vid_id}"
    })

# 3. Send in batches of 50
total_inserted = 0
total_failed = 0
batches = [all_videos[i:i+BATCH_SIZE] for i in range(0, len(all_videos), BATCH_SIZE)]
print(f"Sending {len(all_videos)} videos in {len(batches)} batches of {BATCH_SIZE}...\n")

for i, batch in enumerate(batches):
    for attempt in range(3):
        try:
            r = requests.post(
                GOOGLE_SCRIPT_URL,
                json={"type": "bulk_restore", "videos": batch},
                timeout=60
            )
            if r.status_code == 200:
                try:
                    result = r.json()
                    inserted = result.get("inserted", len(batch))
                except:
                    inserted = "?"
                total_inserted += len(batch)
                print(f"  Batch {i+1}/{len(batches)} ✓  ({inserted} new rows inserted)")
                break
            else:
                print(f"  Batch {i+1} HTTP {r.status_code}, retrying...")
                time.sleep(5)
        except Exception as e:
            print(f"  Batch {i+1} error attempt {attempt+1}: {e}")
            time.sleep(5)
    else:
        total_failed += len(batch)
        print(f"  Batch {i+1} ✗ FAILED")
    time.sleep(3)  # brief pause between batches

print(f"\n{'='*50}")
print(f"Recovery done!")
print(f"  Batches sent : {len(batches)}")
print(f"  Total videos : {len(all_videos)}")
print(f"  Failed       : {total_failed}")
print(f"\nCheck your Google Sheet — Active_Videos should now have ~{len(all_videos)} rows.")
