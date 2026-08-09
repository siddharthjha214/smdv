"""
DATE FIX SCRIPT
===============
Finds all videos with "Unknown" upload_time in the sheet and fetches
their real dates from YouTube, then patches them via update_date handler.
Run after deploying updated apps_script.js (v16+).
"""

import json, time, requests, yt_dlp
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytz

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyAarmgcJWsMYdHW9fhbKrTZXGsu77TFKVAQanMZmTY1xdgtq320MgiZfusuLvXlpAF/exec"
IST = pytz.timezone("Asia/Kolkata")
DATES_CACHE = "/tmp/dates_cache.json"

def format_date(upload_date):
    try:
        if isinstance(upload_date, str) and len(upload_date) == 8 and upload_date.isdigit():
            dt = datetime.strptime(upload_date, "%Y%m%d")
            return IST.localize(dt).strftime("%d %B %Y %I:%M %p IST")
        if isinstance(upload_date, (int, float)):
            dt_utc = datetime.fromtimestamp(upload_date, tz=pytz.utc)
            return dt_utc.astimezone(IST).strftime("%d %B %Y %I:%M %p IST")
        return None
    except:
        return None

def fetch_date(video_id):
    opts = {
        "quiet": True, "skip_download": True, "no_warnings": True,
        "extractor_args": {"youtube": {"player_client": ["mweb", "web"]}},
        "cookiesfrom_browser": "firefox:~/Library/Application Support/Firefox/Profiles/qp85kdfw.default-release",
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
        ud = info.get("upload_date") or info.get("timestamp")
        return video_id, format_date(ud)
    except:
        return video_id, None

# 1. Get all videos with Unknown date
print("Fetching sheet to find Unknown dates...")
r = requests.get(GOOGLE_SCRIPT_URL + "?action=get_active_videos", timeout=30, allow_redirects=True)
sheet_data = r.json()
unknown_ids = [vid for vid, data in sheet_data.items()
               if data.get("upload_time", "Unknown") in ("Unknown", "", None)]
print(f"  Found {len(unknown_ids)} videos with Unknown dates.\n")

if not unknown_ids:
    print("All dates are already filled in! Nothing to do.")
    exit(0)

# 2. Load cached dates
import os
dates_cache = {}
if os.path.exists(DATES_CACHE):
    with open(DATES_CACHE) as f:
        dates_cache = json.load(f)

still_missing = [vid for vid in unknown_ids if vid not in dates_cache]
print(f"Fetching dates for {len(still_missing)} videos ({len(dates_cache)} cached)...")

with ThreadPoolExecutor(max_workers=5) as ex:
    futures = {ex.submit(fetch_date, vid): vid for vid in still_missing}
    done = 0
    for fut in as_completed(futures):
        vid_id, date_str = fut.result()
        if date_str:
            dates_cache[vid_id] = date_str
        done += 1
        if done % 20 == 0:
            print(f"  Fetched: {done}/{len(still_missing)}")
            with open(DATES_CACHE, "w") as f:
                json.dump(dates_cache, f)

with open(DATES_CACHE, "w") as f:
    json.dump(dates_cache, f)
print(f"  Done fetching.\n")

# 3. Patch the sheet
success, skipped = 0, 0
print(f"Patching {len(unknown_ids)} videos in sheet...\n")
for i, vid_id in enumerate(unknown_ids):
    date_str = dates_cache.get(vid_id)
    if not date_str:
        print(f"[{i+1:>3}] ✗ No date found for {vid_id}, skipping")
        skipped += 1
        continue
    for attempt in range(3):
        try:
            r = requests.post(GOOGLE_SCRIPT_URL, json={
                "type": "update_date",
                "video_id": vid_id,
                "upload_time": date_str
            }, timeout=20, allow_redirects=True)
            if r.status_code == 200:
                success += 1
                print(f"[{i+1:>3}/{len(unknown_ids)}] ✓  {vid_id}  {date_str[:20]}")
                break
            time.sleep(2)
        except Exception as e:
            time.sleep(2)
    time.sleep(0.8)

print(f"\n{'='*50}")
print(f"Done! ✓ {success} dates fixed  ✗ {skipped} not found")
print("Open your Google Sheet — all dates should now be filled in.")
