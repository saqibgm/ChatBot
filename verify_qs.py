import requests
import urllib3
urllib3.disable_warnings()

url = 'https://www.createl.shop/chatbot/createl-chat-widget.js?v=test12345'
print(f"--- TESTING URL WITH QUERY STRING: {url} ---")

try:
    r = requests.get(url, verify=False, timeout=10)
    print(f"Status Code: {r.status_code}")
    print(f"Content-Type: {r.headers.get('Content-Type')}")
    print(f"Content Length: {len(r.content)}")
    
    if r.status_code == 200:
        print("PASS: Query strings are handled correctly.")
    else:
        print("FAIL: Server rejected the query string.")
        
except Exception as e:
    print(f"Error: {e}")
