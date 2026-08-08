"""
DATE FIX + FULL RECOVERY SCRIPT
================================
1. Scans all 658 channel videos to get proper upload dates (parallel, 10 at a time)
2. Inserts/updates videos in the sheet with correct dates
3. Skips videos already in the sheet WITH a proper date
"""

import json, time, requests, os, yt_dlp
from datetime import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbx4mICDCIPFqU8pINja2A7OZdmZczmeUsSsYgx3Ru1G8f0JoAzfO1lrtRlwmwi6n33U/exec"
CACHE_FILE = "/tmp/channel_videos.json"
DATES_CACHE = "/tmp/video_dates_full.json"
IST = pytz.timezone("Asia/Kolkata")
COOKIES_FROM_BROWSER = "firefox:~/Library/Application Support/Firefox/Profiles/qp85kdfw.default-release"

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

def get_video_date(video_id):
    """Get upload date for a single video using yt-dlp."""
    opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": False,
        "extractor_args": {"youtube": {"player_client": ["mweb", "web"]}},
        "no_warnings": True,
        "cookiesfrom_browser": COOKIES_FROM_BROWSER,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
        ud = info.get("upload_date") or info.get("timestamp")
        return video_id, format_date(ud)
    except Exception as e:
        return video_id, None

# ── Step 1: Get flat channel scan ──────────────────────────────────────────
if os.path.exists(CACHE_FILE):
    print("Loading flat channel scan from cache...")
    with open(CACHE_FILE) as f:
        entries = json.load(f)
else:
    print("Scanning channel (flat, fast)...")
    ydl_opts = {
        "quiet": True, "extract_flat": "in_playlist",
        "extractor_args": {"youtube": {"player_client": ["mweb", "web"]}},
        "no_warnings": True,
        "cookiesfrom_browser": COOKIES_FROM_BROWSER,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info("https://www.youtube.com/@SandeepSeminars/videos", download=False)
    entries = info.get("entries", [])
    with open(CACHE_FILE, "w") as f:
        json.dump(entries, f)

all_ids = [v["id"] for v in entries if v.get("id")]
print(f"  {len(all_ids)} videos found.\n")

# ── Step 2: Get dates (parallel, 5 workers) ────────────────────────────────
if os.path.exists(DATES_CACHE):
    print("Loading cached dates...")
    with open(DATES_CACHE) as f:
        dates_map = json.load(f)
    missing = [vid for vid in all_ids if vid not in dates_map]
    print(f"  {len(dates_map)} cached, {len(missing)} missing.\n")
else:
    dates_map = {}
    missing = all_ids

if missing:
    print(f"Fetching dates for {len(missing)} videos (5 parallel workers)...")
    done = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(get_video_date, vid): vid for vid in missing}
        for fut in as_completed(futures):
            vid_id, date_str = fut.result()
            dates_map[vid_id] = date_str
            done += 1
            if done % 10 == 0:
                print(f"  Dates fetched: {done}/{len(missing)}")
            with open(DATES_CACHE, "w") as f:
                json.dump(dates_map, f)
    print(f"  Done fetching all dates.\n")

# ── Step 3: Get current sheet state ───────────────────────────────────────
print("Fetching current sheet state...")
existing = {}
try:
    r = requests.get(GOOGLE_SCRIPT_URL + "?action=get_active_videos", timeout=30, allow_redirects=True)
    existing = r.json()
    print(f"  {len(existing)} videos already in sheet.\n")
except Exception as e:
    print(f"  Warning: {e}\n")

# ── Step 4: Insert missing videos ─────────────────────────────────────────
to_insert = []
for v in reversed(entries):  # oldest first
    vid_id = v.get("id", "")
    if not vid_id:
        continue
    # Skip only if already in sheet WITH a real date (not Unknown)
    if vid_id in existing and existing[vid_id].get("upload_time", "Unknown") != "Unknown":
        continue
    title = (v.get("title") or "Unknown Title").strip()
    date_str = dates_map.get(vid_id) or "Unknown"
    to_insert.append({
        "type": "new_video",
        "title": title,
        "upload_time": date_str,
        "video_id": vid_id,
        "url": f"https://youtube.com/watch?v={vid_id}"
    })

print(f"{len(to_insert)} videos to insert/update.\n")

success, failed = 0, []
for i, payload in enumerate(to_insert):
    for attempt in range(3):
        try:
            r = requests.post(GOOGLE_SCRIPT_URL, json=payload, timeout=20, allow_redirects=True)
            if r.status_code == 200 and "Error" not in r.text[:50]:
                success += 1
                date_display = payload['upload_time'][:12] if payload['upload_time'] != 'Unknown' else 'Unknown'
                print(f"[{i+1:>3}/{len(to_insert)}] ✓  {payload['video_id']}  [{date_display}]  {payload['title'][:45]}")
                break
            else:
                time.sleep(3)
        except Exception as e:
            time.sleep(3)
    else:
        failed.append(payload['video_id'])
        print(f"[{i+1:>3}] ✗ FAILED: {payload['video_id']}")
    time.sleep(0.8)

print(f"\n{'='*55}")
print(f"Done! ✓ {success} inserted  ✗ {len(failed)} failed")
print(f"Open your Google Sheet — Active_Videos should have ~{len(all_ids)} rows with proper dates.")
