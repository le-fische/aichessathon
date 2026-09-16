# ruff: noqa
import os
import re
import urllib.request

url = "http://tablebase.sesse.net/syzygy/3-4-5/"

try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urllib.request.urlopen(req)
    html = response.read().decode('utf-8')
    
    files = set(re.findall(r'href="([^"]+\.rtbw)"', html))
    
    valid_files = []
    for f in files:
        if f.endswith('.rtbw'):
            name = f[:-5]
            parts = name.split('v')
            if len(parts) == 2:
                num_pieces = len(parts[0]) + len(parts[1])
                if num_pieces <= 4:
                    valid_files.append(f)
                    
    print(f"Found {len(valid_files)} files to download.")
    
    os.makedirs("weights", exist_ok=True)
    
    for f in valid_files:
        path = os.path.join("weights", f)
        if not os.path.exists(path):
            print(f"Downloading {f}...")
            urllib.request.urlretrieve(url + f, path)
            
    print("Download complete.")
except Exception as e:
    print(f"Error: {e}")
