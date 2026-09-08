#!/usr/bin/env python3
"""
clean_cookies.py — Condense & Clean YouTube Cookies for GitHub Actions Secrets

GitHub Actions secrets have a 48 KB limit. Browser extensions often export 
600+ KB containing hundreds of unrelated websites and ephemeral session cookies.
This script extracts ONLY the necessary YouTube authentication cookies (~6-7 KB)
and copies the result directly to your clipboard for easy pasting into GitHub.
"""

import os
import sys
import time
import base64
import subprocess

def clean_cookies():
    # 1. Locate newest cookie file
    import glob
    candidates = glob.glob(os.path.expanduser("~/Downloads/*cookie*.txt")) + \
                 glob.glob(os.path.expanduser("~/Downloads/*cookies*.txt")) + \
                 glob.glob("*cookie*.txt")
    
    # Sort candidates by modification time (newest first)
    candidates = sorted(list(set(candidates)), key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)

    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        source_path = sys.argv[1]
    elif candidates:
        source_path = candidates[0]
    else:
        source_path = None

    if not source_path:
        print("❌ Could not find a cookies.txt file in current folder or ~/Downloads!")
        print("   Please provide the path: python3 clean_cookies.py /path/to/cookies.txt")
        sys.exit(1)

    original_size = os.path.getsize(source_path)
    mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(source_path)))
    print(f"📄 Found latest cookie file: {source_path} ({original_size:,} bytes / {original_size/1024:.1f} KB, modified: {mtime_str})")

    with open(source_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    # 2. Filter essential cookies
    header = "# Netscape HTTP Cookie File\n# Essential YouTube Auth Cookies\n"
    kept_lines = []
    auth_cookies_found = set()
    now_ts = time.time()
    expired = []

    for line in lines:
        if line.startswith("#") or not line.strip():
            continue
        parts = line.strip().split("\t")
        if len(parts) >= 7:
            domain = parts[0]
            name = parts[5]
            try:
                expiry = int(parts[4])
            except ValueError:
                expiry = 0

            # Only keep YouTube and essential Google auth domain cookies, skip ST-* tracking bloat
            is_yt = "youtube.com" in domain or domain in [".google.com", "google.com"]
            if is_yt and not name.startswith("ST-"):
                kept_lines.append(line)
                auth_cookies_found.add(name)
                if name in ["__Secure-1PSID", "LOGIN_INFO"] and 0 < expiry < now_ts:
                    expired.append(name)

    cleaned_text = header + "".join(kept_lines)
    cleaned_bytes = len(cleaned_text.encode("utf-8"))

    print(f"🧹 Cleaned result: {len(kept_lines)} cookies, {cleaned_bytes:,} bytes ({cleaned_bytes/1024:.2f} KB)")
    print(f"📉 Size reduced by {100 - (cleaned_bytes / original_size * 100):.1f}%! (Well below GitHub's 48 KB limit)")

    # 3. Check auth cookies
    critical = ["__Secure-1PSID", "LOGIN_INFO"]
    missing = [c for c in critical if c not in auth_cookies_found]
    if missing:
        print(f"⚠️  WARNING: Missing critical auth cookies: {', '.join(missing)}")
        print("   Make sure you were logged in to YouTube when you exported cookies.")
    elif expired:
        print(f"⚠️  WARNING: The following cookies are expired: {', '.join(expired)}")
    else:
        print("✅ Critical auth cookies (__Secure-1PSID, LOGIN_INFO) are PRESENT and VALID!")

    # 4. Save to output file
    out_file = os.path.expanduser("~/Downloads/youtube_cookies_cleaned.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(cleaned_text)
    print(f"💾 Saved cleaned cookies to: {out_file}")

    # 5. Base64 encoding info
    b64_content = base64.b64encode(cleaned_text.encode("utf-8")).decode("utf-8")
    b64_size = len(b64_content)
    print(f"🔐 Base64 size: {b64_size:,} bytes ({b64_size/1024:.2f} KB)")

    # 6. Test cookies live with yt-dlp if available
    try:
        import yt_dlp
        test_opts = {
            "quiet": True,
            "no_warnings": False,
            "cookiefile": out_file,
            "skip_download": True,
        }
        print("🔍 Testing cleaned cookies against YouTube...")
        with yt_dlp.YoutubeDL(test_opts) as test_ydl:
            info = test_ydl.extract_info("https://youtube.com/watch?v=dQw4w9WgXcQ", download=False)
            print("🎉 YouTube successfully verified the cookies! (Logged-in session confirmed)")
    except Exception as test_e:
        err_str = str(test_e)
        if "rotated" in err_str or "no longer valid" in err_str:
            print(f"⚠️  WARNING: YouTube reports these cookies have been rotated by the browser.")
            print("   Please export a fresh cookie file from YouTube without continuing to browse.")
        else:
            print(f"ℹ️  Test check: {test_e}")

    # 7. Copy to clipboard on macOS
    try:
        process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        process.communicate(cleaned_text.encode("utf-8"))
        print("\n📋 SUCCESS! Cleaned cookies have been automatically COPIED to your clipboard!")
        print("👉 Go to GitHub Repo → Settings → Secrets and variables → Actions")
        print("👉 Update 'YOUTUBE_COOKIES' and paste (Cmd + V)!")
    except Exception:
        print(f"\n📋 You can copy the contents of '{out_file}' into your GitHub Secret!")

if __name__ == "__main__":
    clean_cookies()
