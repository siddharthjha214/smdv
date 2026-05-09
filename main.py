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
# IST TIMEZONE
# ==========================================

IST = pytz.timezone("Asia/Kolkata")

# ==========================================
# FORMAT YOUTUBE DATE
# ==========================================

def format_youtube_date(upload_date):

    try:

        dt = datetime.strptime(upload_date, "%Y%m%d")

        dt_ist = IST.localize(dt)

        return dt_ist.strftime("%d %B %Y %I:%M %p IST")

    except:

        return "Unknown"

# ==========================================
# YOUTUBE OPTIONS
# ==========================================

ydl_opts = {
    "quiet": True,
    "extract_flat": True
}

# ==========================================
# FETCH YOUTUBE DATA
# ==========================================

with yt_dlp.YoutubeDL(ydl_opts) as ydl:

    info = ydl.extract_info(CHANNEL_URL, download=False)

    current_video_ids = []

    # ==========================================
    # FETCH EXISTING SHEET DATA
    # ==========================================

    response = requests.get(GOOGLE_SCRIPT_URL)

    existing_data = response.text

    # ==========================================
    # LOOP THROUGH VIDEOS
    # ==========================================

    for video in info["entries"]:

        try:

            title = video.get("title", "Unknown Title")

            video_id = video.get("id", "")

            upload_date_raw = video.get("release_date")

            upload_time = format_youtube_date(upload_date_raw)

            url = f"https://youtube.com/watch?v={video_id}"

            current_video_ids.append(video_id)

            # ==========================================
            # ONLY NEW VIDEOS
            # ==========================================

            if video_id not in existing_data:

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
                # TELEGRAM MESSAGE
                # ==========================================

                message = f"""
NEW VIDEO UPLOADED

Title:
{title}

Original Upload Date:
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

        except Exception as e:

            print("ERROR:", e)

print("BOT COMPLETED SUCCESSFULLY")