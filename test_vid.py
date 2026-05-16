import requests
r = requests.get("https://www.youtube.com/watch?v=ZGmu-hizM1E")
print(r.status_code)
