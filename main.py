import yt_dlp
import sqlite3
import pandas as pd
import requests
from datetime import datetime

# ==========================================
# YOUTUBE CHANNEL
# ==========================================

CHANNEL_URL = "https://www.youtube.com/@SandeepSeminars/videos"

# ==========================================
# TELEGRAM BOT SETTINGS
# ==========================================

BOT_TOKEN = "7936950774:AAFGpnQoPEICWNJlKnzPH33Fw-XWMel3y8s"
CHAT_ID = "765673702"

# ==========================================
# DATABASE SETUP
# ==========================================

conn = sqlite3.connect("youtube.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    title TEXT,
    url TEXT,
    upload_time TEXT,
    status TEXT,
    deleted_time TEXT
)
""")

conn.commit()

# ==========================================
# FETCH YOUTUBE VIDEOS
# ==========================================

ydl_opts = {
    'quiet': True,
    'extract_flat': True
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:

    info = ydl.extract_info(CHANNEL_URL, download=False)

    current_video_ids = []

    for video in info['entries']:

        video_id = video['id']
        title = video['title']

        url = f"https://youtube.com/watch?v={video_id}"

        current_video_ids.append(video_id)

        # CHECK IF VIDEO EXISTS
        cursor.execute(
            "SELECT * FROM videos WHERE video_id=?",
            (video_id,)
        )

        existing_video = cursor.fetchone()

        # ==========================================
        # NEW VIDEO DETECTED
        # ==========================================

        if not existing_video:

            upload_time = str(datetime.now())

            cursor.execute("""
            INSERT INTO videos (
                video_id,
                title,
                url,
                upload_time,
                status,
                deleted_time
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                video_id,
                title,
                url,
                upload_time,
                "Active",
                ""
            ))

            conn.commit()

            print(f"NEW VIDEO: {title}")

            # SEND TELEGRAM ALERT
            message = f"""
NEW VIDEO UPLOADED

Title:
{title}

URL:
{url}

Uploaded At:
{upload_time}
"""

            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": CHAT_ID,
                    "text": message
                }
            )

# ==========================================
# CHECK DELETED VIDEOS
# ==========================================

cursor.execute("""
SELECT video_id, title
FROM videos
WHERE status='Active'
""")

saved_videos = cursor.fetchall()

for saved_video in saved_videos:

    saved_video_id = saved_video[0]
    saved_title = saved_video[1]

    if saved_video_id not in current_video_ids:

        deleted_time = str(datetime.now())

        cursor.execute("""
        UPDATE videos
        SET status=?,
            deleted_time=?
        WHERE video_id=?
        """, (
            "Deleted",
            deleted_time,
            saved_video_id
        ))

        conn.commit()

        print(f"DELETED VIDEO: {saved_title}")

        # SEND TELEGRAM DELETE ALERT
        message = f"""
VIDEO DELETED

Title:
{saved_title}

Deleted At:
{deleted_time}
"""

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": message
            }
        )

# ==========================================
# EXPORT DATABASE TO EXCEL
# ==========================================

df = pd.read_sql_query(
    "SELECT * FROM videos",
    conn
)

df.to_excel("videos.xlsx", index=False)

print("BOT COMPLETED SUCCESSFULLY")

conn.close()