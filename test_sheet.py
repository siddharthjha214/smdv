import requests

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwzkOaWKj5HSQzdzpWkLEkssnEUbco5kq4dNjCvJJ6tVlXvKrasnQrtbfssVXcQcKw/exec"

response = requests.get(GOOGLE_SCRIPT_URL)
print(response.text[:1000])
