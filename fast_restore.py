import json, requests, time

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyAarmgcJWsMYdHW9fhbKrTZXGsu77TFKVAQanMZmTY1xdgtq320MgiZfusuLvXlpAF/exec"

print("Loading backup from /tmp/current_sheet.json...")
try:
    with open('/tmp/current_sheet.json', 'r') as f:
        data = json.load(f)
except Exception as e:
    print("Failed to load backup:", e)
    exit(1)

videos = []
for vid, info in data.items():
    videos.append({
        "video_id": vid,
        "title": info.get("title", ""),
        "upload_time": info.get("upload_time", "Unknown"),
        "url": info.get("url", f"https://youtube.com/watch?v={vid}")
    })

from datetime import datetime

print(f"Found {len(videos)} videos in backup. Sorting newest first...")

def parse_date(date_str):
    if not date_str or date_str == "Unknown":
        return datetime.min
    try:
        clean_str = date_str.replace(" IST", "").strip()
        return datetime.strptime(clean_str, "%d %B %Y %I:%M %p")
    except Exception as e:
        return datetime.min

videos.sort(key=lambda x: parse_date(x["upload_time"]), reverse=True)

print(f"Sending ALL {len(videos)} videos in ONE request to prevent Google Sheets from wiping...")
try:
    r = requests.post(GOOGLE_SCRIPT_URL, json={
        "type": "bulk_restore",
        "videos": videos
    }, timeout=60, allow_redirects=True)
    
    if r.status_code == 200:
        print(f"✅ Success! Google Sheets Response: {r.text[:50]}")
    else:
        print(f"❌ Error {r.status_code}: {r.text[:100]}")
except Exception as e:
    print(f"❌ Connection error: {e}")

print("Restore complete! Check your Google Sheet.")
