import requests
url = "https://script.google.com/macros/s/AKfycbwzkOaWKj5HSQzdzpWkLEkssnEUbco5kq4dNjCvJJ6tVlXvKrasnQrtbfssVXcQcKw/exec"
r = requests.get(url, allow_redirects=True)
print("GET STATUS:", r.status_code)
print("GET RESPONSE:", r.text[:500])

r2 = requests.post(url, json={"type": "get_videos"}, allow_redirects=True)
print("POST STATUS:", r2.status_code)
print("POST RESPONSE:", r2.text[:500])
