import requests
url = "https://script.google.com/macros/s/AKfycbxytfYZ4K6hMuuXjkTZaT21xtnQra8u0J6lVCBIgJFRYnScYcC5ZIIqosv1x-jEhikQ/exec"
r = requests.get(url + "?action=get_active_videos", allow_redirects=True)
print("STATUS:", r.status_code)
print("RESPONSE:", r.text[:500])
