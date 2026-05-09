import yt_dlp
import requests
import pytz

from datetime import datetime

# ==========================================
# TELEGRAM SETTINGS
# ==========================================

BOT_TOKEN = "7936950774:AAFGpnQoPEICWNJlKnzPH33Fw-XWMel3y8s"

CHAT_ID = "765673702"

# ==========================================
# GOOGLE APPS SCRIPT URL
# ==========================================

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwzkOaWKj5HSQzdzpWkLEkssnEUbco5kq4dNjCvJJ6tVlXvKrasnQrtbfssVXcQcKw/exec"

# ==========================================
# YOUTUBE CHANNEL
# ==========================================

CHANNEL_URL = "https://www.youtube.com/@SandeepSeminars/videos"

# ==========================================
# IST TIME FORMAT
# ==========================================

IST = pytz.timezone("Asia/Kolkata")

def get_ist_time():

    now = datetime.now(IST)

    return now.strftime("%d %B %Y %I:%M %p IST")

# ==========================================
# FETCH YOUTUBE VIDEOS
# ==========================================

ydl_opts = {
    "quiet": True,
    "extract_flat": True
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:

    info = ydl.extract_info(CHANNEL_URL, download=False)

    current_video_ids = []

    # ==========================================
    # FETCH EXISTING SHEET DATA
    # ==========================================

    response = requests.get(GOOGLE_SCRIPT_URL)

    existing_data = response.text

    for video in info["entries"]:

        title = video["title"]

        video_id = video["id"]

        url = f"https://youtube.com/watch?v={video_id}"

        current_video_ids.append(video_id)

        # ==========================================
        # ONLY SEND NEW VIDEO ALERTS
        # ==========================================

        if video_id not in existing_data:

            upload_time = get_ist_time()

            # ==========================================
            # SEND TO GOOGLE SHEETS
            # ==========================================

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

            # ==========================================
            # SEND TELEGRAM ALERT
            # ==========================================

            message = f"""
NEW VIDEO UPLOADED

Title:
{title}

Upload Time:
{upload_time}

URL:
{url}
"""

            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": CHAT_ID,
                    "text": message
                }
            )

print("BOT COMPLETED SUCCESSFULLY")