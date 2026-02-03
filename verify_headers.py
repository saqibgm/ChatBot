import requests
import urllib3
urllib3.disable_warnings()

url = 'https://www.createl.shop/chatbot/createl-chat-widget.js'
print(f"--- ANALYZING HEADERS FOR {url} ---")

try:
    r = requests.get(url, verify=False, timeout=10)
    print(f"Status Code: {r.status_code}")
    
    ct = r.headers.get("Content-Type", "MISSING")
    print(f"Content-Type: {ct}")
    
    csp = r.headers.get("Content-Security-Policy", "None")
    print(f"Content-Security-Policy: {csp}")
    
    xcto = r.headers.get("X-Content-Type-Options", "None")
    print(f"X-Content-Type-Options: {xcto}")

    if "javascript" not in ct:
        print("CRITICAL ERROR: Content-Type is NOT javascript. Browser will block execution.")
    else:
        print("Content-Type looks correct.")
        
except Exception as e:
    print(f"Error: {e}")
