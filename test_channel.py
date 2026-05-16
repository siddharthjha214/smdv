import yt_dlp
import json

ydl_opts = {
    "quiet": True,
    "extract_flat": False,
    "playlistend": 2
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info("https://www.youtube.com/@SandeepSeminars/videos", download=False)
    for video in info.get("entries", []):
        print("id:", video.get("id"))
        print("upload_date:", video.get("upload_date"))
        print("release_date:", video.get("release_date"))
        print("timestamp:", video.get("timestamp"))
