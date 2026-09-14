import os
import time
import requests
from PIL import Image
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyAarmgcJWsMYdHW9fhbKrTZXGsu77TFKVAQanMZmTY1xdgtq320MgiZfusuLvXlpAF/exec"

def get_youtube_client():
    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("ERROR: YouTube API credentials missing from environment.")
        return None

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    return build("youtube", "v3", credentials=credentials)

def fetch_all_backed_up_videos():
    """Fetch all videos with backup_video_id from Google Sheets."""
    print("Fetching active and deleted videos from Google Sheets...")
    pairs = []
    
    # 1. Active Videos
    try:
        res = requests.get(f"{GOOGLE_SCRIPT_URL}?action=get_active_videos", timeout=15)
        if res.status_code == 200:
            data = res.json()
            for orig_id, item in data.items():
                b_id = item.get("backup_video_id", "").strip()
                status = item.get("backup_status", "")
                title = item.get("title", "Unknown Title")
                if b_id and status == "Backed Up":
                    pairs.append({"orig_id": orig_id, "backup_id": b_id, "title": title, "type": "Active"})
    except Exception as e:
        print(f"Error fetching active videos: {e}")

    # 2. Deleted Videos
    try:
        res = requests.get(f"{GOOGLE_SCRIPT_URL}?action=get_deleted_videos", timeout=15)
        if res.status_code == 200:
            data = res.json()
            for item in data:
                orig_id = item.get("video_id", "").strip()
                b_id = item.get("backup_video_id", "").strip()
                title = item.get("title", "Unknown Title")
                if orig_id and b_id:
                    pairs.append({"orig_id": orig_id, "backup_id": b_id, "title": title, "type": "Deleted"})
    except Exception as e:
        print(f"Error fetching deleted videos: {e}")

    print(f"Total backed-up videos found in sheet: {len(pairs)}")
    return pairs

def find_videos_missing_custom_thumbnails(youtube, video_pairs):
    """
    Check backup videos in batches of 50 via YouTube API.
    Videos with custom thumbnails have 'maxres' or 'standard' resolutions.
    Auto-generated default frame thumbnails only have 'default' or 'hqdefault'.
    """
    print("Checking backup videos on YouTube to identify missing custom thumbnails...")
    needs_thumbnail = []
    backup_to_pair = {p["backup_id"]: p for p in video_pairs}
    all_backup_ids = list(backup_to_pair.keys())

    for i in range(0, len(all_backup_ids), 50):
        chunk = all_backup_ids[i:i + 50]
        try:
            resp = youtube.videos().list(part="snippet", id=",".join(chunk)).execute()
            for item in resp.get("items", []):
                b_id = item.get("id")
                snippet = item.get("snippet", {})
                thumbnails = snippet.get("thumbnails", {})

                # If standard or maxres is missing, it is using default auto-generated frames
                has_custom = "maxres" in thumbnails or "standard" in thumbnails
                if not has_custom and b_id in backup_to_pair:
                    needs_thumbnail.append(backup_to_pair[b_id])
        except Exception as e:
            print(f"Error checking chunk {i}-{i+50}: {e}")

    print(f"Videos identified needing custom thumbnail: {len(needs_thumbnail)} / {len(video_pairs)}")
    return needs_thumbnail

def download_original_thumbnail(orig_id):
    """Download highest resolution thumbnail from original YouTube video CDN."""
    cdn_urls = [
        f"https://i.ytimg.com/vi/{orig_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{orig_id}/sddefault.jpg",
        f"https://i.ytimg.com/vi/{orig_id}/hqdefault.jpg"
    ]

    temp_path = f"temp_thumb_{orig_id}.jpg"
    for url in cdn_urls:
        try:
            resp = requests.get(url, timeout=10)
            # YouTube returns a 120x90 blank image (~1000 bytes) on 404 placeholder
            if resp.status_code == 200 and len(resp.content) > 1500:
                with open(temp_path, "wb") as f:
                    f.write(resp.content)
                
                # Verify and convert to standard RGB JPEG via Pillow
                try:
                    with Image.open(temp_path) as im:
                        im.convert("RGB").save(temp_path, "JPEG", quality=95)
                    return temp_path
                except Exception:
                    return temp_path
        except Exception:
            continue

    return None

def sync_thumbnails():
    youtube = get_youtube_client()
    if not youtube:
        print("CRITICAL: Cannot authenticate with YouTube API.")
        return

    video_pairs = fetch_all_backed_up_videos()
    if not video_pairs:
        print("No backed-up videos found in Google Sheet.")
        return

    missing_list = find_videos_missing_custom_thumbnails(youtube, video_pairs)
    if not missing_list:
        print("🎉 All backup videos already have custom high-resolution thumbnails!")
        return

    print(f"\n--- Starting Thumbnail Sync for {len(missing_list)} videos ---")
    success_count = 0
    skipped_count = 0

    for idx, item in enumerate(missing_list, 1):
        orig_id = item["orig_id"]
        backup_id = item["backup_id"]
        title = item["title"]

        print(f"[{idx}/{len(missing_list)}] Processing: {orig_id} → Backup: {backup_id} ({title[:45]}...)")
        
        thumb_path = download_original_thumbnail(orig_id)
        if not thumb_path or not os.path.exists(thumb_path):
            print(f"  ⚠️ Could not fetch original thumbnail for {orig_id}. Skipping.")
            skipped_count += 1
            continue

        # Upload thumbnail to backup video
        try:
            youtube.thumbnails().set(
                videoId=backup_id,
                media_body=MediaFileUpload(thumb_path, mimetype="image/jpeg")
            ).execute()
            print("  ✅ Custom thumbnail uploaded successfully!")
            success_count += 1
            time.sleep(1)  # Gentle delay between uploads
        except Exception as e:
            err_str = str(e)
            if "uploadRateLimitExceeded" in err_str or "too many thumbnails" in err_str.lower():
                print("\n⚠️ YouTube 24-hour custom thumbnail rate limit reached.")
                print(f"Uploaded {success_count} thumbnails before reaching daily channel limit.")
                print("You can run this workflow again tomorrow to resume the remaining videos.")
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
                break
            else:
                print(f"  ❌ Failed to upload thumbnail: {e}")
                skipped_count += 1

        if os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass

    print("\n==========================================")
    print("THUMBNAIL SYNC SUMMARY:")
    print(f"  • Successfully Updated: {success_count}")
    print(f"  • Skipped / Failed:     {skipped_count}")
    print(f"  • Total Processed:      {success_count + skipped_count} / {len(missing_list)}")
    print("==========================================")

if __name__ == "__main__":
    sync_thumbnails()
