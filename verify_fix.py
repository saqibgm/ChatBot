import requests
import urllib3
urllib3.disable_warnings()

print("--- VERIFYING JS FILE CONTENT ---")
try:
    with open(r'c:\inetpub\wwwroot\Chatbot\client ui\dist-widget\createl-chat-widget.js', 'r', encoding='utf-8') as f:
        js = f.read()
    
    p1 = '/chatbot/webhooks' in js
    p2 = '/chatbot/admin/themes' in js
    p3 = 'const ADMIN_API_URL = "/chatbot"' in js
    
    print(f"Patch 1 (Webhooks URL): {'PASS' if p1 else 'FAIL'}")
    print(f"Patch 2 (Themes URL):   {'PASS' if p2 else 'FAIL'}")
    print(f"Patch 3 (Base URL):     {'PASS' if p3 else 'FAIL'}")
except Exception as e:
    print(f"Error reading file: {e}")

print("\n--- VERIFYING IIS PROXY CONNECTIVITY ---")
url = 'https://www.createl.shop/chatbot/admin/themes/6'
print(f"Probing: {url}")
try:
    r = requests.get(url, verify=False, timeout=10)
    print(f"Status Code: {r.status_code}")
    print(f"Response Preview: {r.text[:200]}")
    if r.status_code == 200 and "success" in r.text:
        print("RESULT: PROXY WORKING")
    else:
        print("RESULT: PROXY FAILED")
except Exception as e:
    print(f"Request Error: {e}")
