import yt_dlp

ydl_opts = {
    "quiet": True,
    "extract_flat": "in_playlist",
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info("https://www.youtube.com/@SandeepSeminars/videos", download=False)
    for video in info.get("entries", [])[:10]:
        print("id:", video.get("id"))
        print("title:", video.get("title"))
        print("upload_date:", video.get("upload_date"))
        print("timestamp:", video.get("timestamp"))
        print("-" * 20)
