import yt_dlp
import json

ydl_opts = {
    "quiet": True,
    "extract_flat": False,
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", download=False)
    print("upload_date:", info.get("upload_date"))
    print("release_date:", info.get("release_date"))
    print("timestamp:", info.get("timestamp"))
