import urllib.request
import json
import re

def test_page_assets(page_url):
    print(f"\n--- Testing Assets on {page_url} ---")
    try:
        with urllib.request.urlopen(page_url) as r:
            html = r.read().decode("utf-8")
    except Exception as e:
        print(f"Error opening page {page_url}: {e}")
        return

    # Find static assets
    assets = re.findall(r'(?:src|href)=["\'](/static/[^"\']+)["\']', html)
    for asset in set(assets):
        url = f"http://127.0.0.1:8000{asset}"
        try:
            with urllib.request.urlopen(url) as resp:
                print(f"  [OK {resp.getcode()}] {asset} ({len(resp.read())} bytes)")
        except Exception as e:
            print(f"  [FAIL] {asset}: {e}")

test_page_assets("http://127.0.0.1:8000/static/index.html")
test_page_assets("http://127.0.0.1:8000/")
test_page_assets("http://127.0.0.1:8000/login")
test_page_assets("http://127.0.0.1:8000/admin/login")
test_page_assets("http://127.0.0.1:8000/dashboard")
