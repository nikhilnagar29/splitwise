import time
import urllib.request
import os

PING_URL = os.environ.get("PING_URL", "http://localhost:8000/health")
INTERVAL = int(os.environ.get("PING_INTERVAL", "900"))  # 15 mins default

def ping():
    try:
        req = urllib.request.urlopen(PING_URL, timeout=10)
        print(f"Ping OK — {PING_URL} → {req.status}")
    except Exception as e:
        print(f"Ping FAILED — {e}")

if __name__ == "__main__":
    print(f"Keep-alive started. Pinging {PING_URL} every {INTERVAL}s")
    while True:
        ping()
        time.sleep(INTERVAL)