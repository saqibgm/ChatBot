import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base_url = "https://createl.shop"
endpoints = [
    "/chatbot/createl-chat-widget.js",
    "/chatbot/admin/config",
    "/chatbot/admin.html",
    "/chatbot/socket.io/",
    "/socket.io/"
]

print(f"Probing {base_url}...")

for ep in endpoints:
    try:
        url = base_url + ep
        print(f"Checking {url}...")
        r = requests.get(url, verify=False, timeout=5)
        print(f"GET {ep}: {r.status_code} - len: {len(r.content)}")
    except Exception as e:
        print(f"GET {ep}: Error {str(e)}")
