import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

paths = [
    '/api/token', 
    '/api/frontend/token', 
    '/api/misc/webapi/frontend/token',
    '/api/nop/token', 
    '/token', 
    '/swagger/index.html', 
    '/swagger/v1/swagger.json',
    '/api/docs',
    '/api/backend/token'
]

base_url = "https://createl.shop"

print(f"Probing {base_url}...")

for p in paths:
    try:
        url = base_url + p
        r = requests.get(url, verify=False, timeout=5)
        print(f"GET {p}: {r.status_code}")
    except Exception as e:
        print(f"GET {p}: Error {str(e)}")
