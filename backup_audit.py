"""
BACKUP CHANNEL SYNC + DEDUP SCRIPT
====================================
1. Scans the backup YouTube channel for ALL uploaded videos
2. Finds duplicates (same title uploaded more than once)
3. Deletes the duplicate copies (keeps the OLDEST upload, removes newer ones)
4. Matches each backup video to the original in the Active_Videos sheet by title
5. Updates the sheet: marks matched videos as "Backed Up" with correct backup_video_id
6. Prints a full report of what's backed up and what's still pending

Run via GitHub Actions (backup_sync.yml) — uses stored OAuth secrets.
"""

import os, requests, json, time

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyAarmgcJWsMYdHW9fhbKrTZXGsu77TFKVAQanMZmTY1xdgtq320MgiZfusuLvXlpAF/exec"

# ── Build YouTube client ─────────────────────────────────────────────────────
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

client_id     = os.getenv("YOUTUBE_CLIENT_ID")
client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

if not all([client_id, client_secret, refresh_token]):
    print("ERROR: Set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN")
    exit(1)

creds = Credentials(
    token=None, refresh_token=refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=client_id, client_secret=client_secret
)
youtube = build("youtube", "v3", credentials=creds)

# ── Step 1: Get backup channel info ─────────────────────────────────────────
print("=" * 60)
print("STEP 1: Getting backup channel info...")
ch = youtube.channels().list(part="contentDetails,snippet", mine=True).execute()
channel_name    = ch["items"][0]["snippet"]["title"]
uploads_pl      = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
print(f"  Channel : {channel_name}")
print(f"  Playlist: {uploads_pl}")

# ── Step 2: Fetch ALL videos on backup channel ───────────────────────────────
print("\nSTEP 2: Scanning all videos on backup channel...")
backup_videos = []   # list of {id, title, published_at}
next_page = None
while True:
    resp = youtube.playlistItems().list(
        part="snippet", playlistId=uploads_pl,
        maxResults=50, pageToken=next_page
    ).execute()
    for item in resp.get("items", []):
        vid_id  = item["snippet"]["resourceId"]["videoId"]
        title   = item["snippet"]["title"]
        pub_at  = item["snippet"]["publishedAt"]   # ISO8601 string
        backup_videos.append({"id": vid_id, "title": title, "published_at": pub_at})
    next_page = resp.get("nextPageToken")
    if not next_page:
        break
    print(f"  Scanned {len(backup_videos)} videos so far...")

print(f"  Total on backup channel: {len(backup_videos)} videos")

# ── Step 3: Find duplicates (same title → keep oldest, delete newer) ─────────
print("\nSTEP 3: Checking for duplicates...")
from collections import defaultdict
by_title = defaultdict(list)
for v in backup_videos:
    by_title[v["title"]].append(v)

duplicates_deleted = 0
clean_backup = {}   # title → {id, published_at}  (the keeper for each title)

for title, vids in by_title.items():
    # Sort by published_at ascending → oldest first
    vids.sort(key=lambda x: x["published_at"])
    keeper = vids[0]
    clean_backup[title] = keeper

    if len(vids) > 1:
        # Delete all except the oldest
        for dup in vids[1:]:
            print(f"  DELETING DUPLICATE: {dup['id']} — {title[:55]}")
            try:
                youtube.videos().delete(id=dup["id"]).execute()
                duplicates_deleted += 1
                time.sleep(0.5)
            except Exception as e:
                print(f"    WARNING: Failed to delete {dup['id']}: {e}")

if duplicates_deleted == 0:
    print(f"  No duplicates found. All {len(clean_backup)} titles are unique. ✓")
else:
    print(f"  Deleted {duplicates_deleted} duplicate(s). {len(clean_backup)} unique videos remain.")

# ── Step 4: Fetch Active_Videos sheet ────────────────────────────────────────
print("\nSTEP 4: Fetching Active_Videos sheet...")
r = requests.get(GOOGLE_SCRIPT_URL + "?action=get_active_videos", timeout=30, allow_redirects=True)
sheet_data = r.json()
print(f"  {len(sheet_data)} videos in sheet")

# ── Step 5: Match backup videos to sheet entries by title ───────────────────
print("\nSTEP 5: Matching backup videos to sheet entries by title...")

# Build a case-insensitive title → original_video_id map from the sheet
sheet_by_title = {}
for orig_id, data in sheet_data.items():
    t = data.get("title", "").strip().lower()[:100]  # YouTube titles max 100 chars
    sheet_by_title[t] = {"orig_id": orig_id, "data": data}

backed_up_count   = 0
sheet_updated     = 0
not_matched       = []
already_marked    = []

backup_date_now = datetime.now(IST).strftime("%d %B %Y %I:%M %p IST")

for bkp_title, bkp_info in clean_backup.items():
    lookup = bkp_title.strip().lower()[:100]
    match  = sheet_by_title.get(lookup)

    if not match:
        not_matched.append(bkp_title)
        continue

    orig_id     = match["orig_id"]
    sheet_entry = match["data"]
    bkp_vid_id  = bkp_info["id"]

    # Already correctly marked in sheet?
    if sheet_entry.get("backup_status") == "Backed Up" and sheet_entry.get("backup_video_id") == bkp_vid_id:
        already_marked.append(orig_id)
        backed_up_count += 1
        continue

    # Update the sheet
    for attempt in range(3):
        try:
            r2 = requests.post(GOOGLE_SCRIPT_URL, json={
                "type": "update_backup",
                "video_id": orig_id,
                "backup_status": "Backed Up",
                "backup_date": backup_date_now,
                "backup_video_id": bkp_vid_id
            }, timeout=20, allow_redirects=True)
            if r2.status_code == 200:
                sheet_updated += 1
                backed_up_count += 1
                print(f"  ✓ Marked Backed Up: {orig_id} → backup {bkp_vid_id}  [{bkp_title[:45]}]")
                break
        except Exception as e:
            time.sleep(2)
    time.sleep(0.8)

# ── Step 6: Summary report ───────────────────────────────────────────────────
pending_count = len(sheet_data) - backed_up_count

print("\n" + "=" * 60)
print("BACKUP CHANNEL SYNC REPORT")
print("=" * 60)
print(f"Backup channel name   : {channel_name}")
print(f"Videos on backup ch   : {len(backup_videos)}")
print(f"Duplicates deleted    : {duplicates_deleted}")
print(f"Unique backups remain : {len(clean_backup)}")
print()
print(f"✅ Backed Up (matched + sheet updated): {backed_up_count}")
print(f"   ↳ Already correctly marked          : {len(already_marked)}")
print(f"   ↳ Newly marked in sheet             : {sheet_updated}")
print(f"⏳ Still Pending (not backed up yet)   : {pending_count}")
print()

if not_matched:
    print(f"⚠️  Backup videos with NO match in sheet ({len(not_matched)}):")
    for t in not_matched:
        print(f"    - {t[:70]}")

# Save report
report = {
    "channel_name": channel_name,
    "total_on_backup_channel": len(backup_videos),
    "duplicates_deleted": duplicates_deleted,
    "unique_backups": len(clean_backup),
    "backed_up_count": backed_up_count,
    "sheet_updated": sheet_updated,
    "pending_count": pending_count,
    "unmatched_backups": not_matched,
}
with open("backup_sync_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("\nFull report saved to backup_sync_report.json")
print("=" * 60)
