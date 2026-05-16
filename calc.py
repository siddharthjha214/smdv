import yt_dlp
import statistics

CHANNEL_URL = "https://www.youtube.com/@SandeepSeminars/videos"

ydl_opts_fast = {
    "quiet": True,
    "extract_flat": "in_playlist",
    "remote_components": ["ejs:github"]
}

print("Fetching channel info...")
with yt_dlp.YoutubeDL(ydl_opts_fast) as ydl:
    info = ydl.extract_info(CHANNEL_URL, download=False)
    
    durations = []
    total_videos = 0
    
    for video in info.get("entries", []):
        duration = video.get("duration")
        if duration:
            durations.append(duration)
        total_videos += 1

if durations:
    avg_sec = statistics.mean(durations)
    total_sec = sum(durations)
    
    print(f"Total Videos Processed: {total_videos}")
    print(f"Videos with Duration info: {len(durations)}")
    
    avg_min = avg_sec / 60
    print(f"Average Duration: {avg_min:.2f} minutes")
    
    print(f"Total Duration (all videos): {total_sec / 3600:.2f} hours")
else:
    print("Could not fetch durations")
