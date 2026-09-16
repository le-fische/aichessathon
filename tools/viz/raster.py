import glob, re, os
from playwright.sync_api import sync_playwright

exe = None
for c in glob.glob("/opt/pw-browsers/chromium*/chrome-linux/chrome") + glob.glob("/opt/pw-browsers/chromium*/chrome-linux/headless_shell"):
    exe = c; break

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
    pg = b.new_page(device_scale_factor=2)
    for f in sorted(glob.glob("out/*.svg")):
        svg = open(f).read()
        m = re.search(r'width="(\d+)" height="(\d+)"', svg)
        w, h = int(m.group(1)), int(m.group(2))
        pg.set_viewport_size({"width": w, "height": h})
        pg.set_content(f'<body style="margin:0">{svg}</body>')
        pg.wait_for_timeout(150)
        out = f.replace(".svg", ".png")
        pg.screenshot(path=out)
        print(os.path.basename(out), f"{w}x{h}")
    b.close()
