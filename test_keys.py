import yt_dlp
import json

ydl_opts = {
    "quiet": True,
    "extract_flat": "in_playlist"
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info("https://www.youtube.com/@SandeepSeminars/videos", download=False)
    for video in info.get("entries", [])[:5]:
        print("id:", video.get("id"))
        print("keys:", video.keys())
        print("upload_date:", video.get("upload_date"))
        print("timestamp:", video.get("timestamp"))
        print("-" * 20)
