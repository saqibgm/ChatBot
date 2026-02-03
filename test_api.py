import requests
import time

url = "https://createl.shop/api/token"
print(f"Testing connection to {url}...")
start = time.time()
try:
    # Mimic the nopcommerce_service.py logic (verify=False)
    resp = requests.post(url, verify=False, timeout=10)
    end = time.time()
    print(f"Status Code: {resp.status_code}")
    print(f"Time Taken: {end - start:.4f} seconds")
    print(f"Response: {resp.text[:100]}")
except Exception as e:
    end = time.time()
    print(f"Error: {e}")
    print(f"Time Taken: {end - start:.4f} seconds")
