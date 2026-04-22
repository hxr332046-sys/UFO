"""Debug slider gap detection: save images + try multiple ddddocr methods."""
import json, sys, time, base64, io, requests, websocket
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEBUG_DIR = ROOT / "dashboard" / "data" / "records"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

port = 9225
pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=5).json()
target = [p for p in pages if p.get("type") == "page"][0]
ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=20)
_id = [0]
def ev(expr):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": "Runtime.evaluate",
                         "params": {"expression": expr, "returnByValue": True, "timeout": 20000}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == _id[0]:
            return msg.get("result", {}).get("result", {}).get("value")

# First navigate to tyrz if not there
href = ev("location.href")
print(f"Current: {href[:100]}")
if "tyrz" not in str(href):
    print("Navigating to enterprise-zone to trigger SSO...")
    ev('window.location.replace("https://zhjg.scjdglj.gxzf.gov.cn:9087/icpsp-web-pc/portal.html#/index/enterprise/enterprise-zone")')
    for i in range(8):
        time.sleep(3)
        href = ev("location.href")
        print(f"  [{i+1}] {href[:80]}")
        if "tyrz" in str(href):
            break
    time.sleep(2)

# Find visible slider move-block
move = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    if (!bar) return null;
    var parent = bar.parentElement;
    while (parent && !parent.querySelector('.verify-move-block')) {
        parent = parent.parentElement;
        if (!parent || parent === document.body) return null;
    }
    var mb = parent.querySelector('.verify-move-block');
    var r = mb.getBoundingClientRect();
    return {x: r.x, y: r.y, w: r.width, h: r.height};
})()""")

if not move:
    print("No visible slider found!")
    ws.close()
    sys.exit(1)

print(f"Slider button: {move}")
cx = move["x"] + move["w"] / 2
cy = move["y"] + move["h"] / 2

# Mouse down to reveal images
def mouse(method, x, y, btn="left", count=1):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": "Input.dispatchMouseEvent",
                         "params": {"type": method, "x": x, "y": y, "button": btn, "clickCount": count}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == _id[0]:
            return

print(f"Mouse down at ({cx:.0f}, {cy:.0f})...")
mouse("mouseMoved", cx, cy)
time.sleep(0.3)
mouse("mousePressed", cx, cy)
time.sleep(1.0)

# Read images while mouse is pressed
imgs = ev("""(function(){
    var bars = document.querySelectorAll('.verify-bar-area');
    var bar = null;
    bars.forEach(function(el){ if(el.offsetParent !== null && el.getBoundingClientRect().width > 100) bar = el; });
    if (!bar) return {error: 'no bar'};
    var parent = bar.parentElement;
    while (parent && !parent.querySelector('img.backImg')) {
        parent = parent.parentElement;
        if (!parent || parent === document.body) return {error: 'no parent'};
    }
    var bg = parent.querySelector('img.backImg');
    var block = parent.querySelector('img.bock-backImg');
    var bgR = bg ? bg.getBoundingClientRect() : {};
    var blockR = block ? block.getBoundingClientRect() : {};
    return {
        bgSrc: bg ? bg.src : null,
        blockSrc: block ? block.src : null,
        bgNatW: bg ? bg.naturalWidth : 0,
        bgNatH: bg ? bg.naturalHeight : 0,
        bgDispW: bgR.width || 0,
        bgDispH: bgR.height || 0,
        bgDispX: bgR.x || 0,
        bgDispY: bgR.y || 0,
        blockNatW: block ? block.naturalWidth : 0,
        blockNatH: block ? block.naturalHeight : 0,
        blockDispW: blockR.width || 0,
        blockDispH: blockR.height || 0,
        blockDispX: blockR.x || 0,
        blockDispY: blockR.y || 0,
    };
})()""")

# Release mouse
mouse("mouseReleased", cx, cy)

print(f"Image info: bg={imgs.get('bgNatW')}x{imgs.get('bgNatH')} disp={imgs.get('bgDispW'):.0f}x{imgs.get('bgDispH'):.0f}")
print(f"Block info: {imgs.get('blockNatW')}x{imgs.get('blockNatH')} disp={imgs.get('blockDispW'):.0f}x{imgs.get('blockDispH'):.0f}")
print(f"Block pos: ({imgs.get('blockDispX'):.0f}, {imgs.get('blockDispY'):.0f})")

ws.close()

# Save images
def save_data_url(data_url, filename):
    if not data_url or not data_url.startswith("data:"):
        print(f"  {filename}: no valid data URL (type={type(data_url)}, len={len(str(data_url or '')[:20])})")
        return None
    _, encoded = data_url.split(",", 1)
    data = base64.b64decode(encoded)
    path = DEBUG_DIR / filename
    path.write_bytes(data)
    print(f"  {filename}: saved {len(data)} bytes → {path}")
    return data

print("\nSaving images...")
bg_bytes = save_data_url(imgs.get("bgSrc"), "slider_bg.png")
block_bytes = save_data_url(imgs.get("blockSrc"), "slider_block.png")

if not bg_bytes or not block_bytes:
    print("Cannot proceed without both images!")
    sys.exit(1)

# Try multiple ddddocr methods
print("\n=== ddddocr gap detection ===")
import ddddocr

# Method 1: slide_match with simple_target
try:
    det1 = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)
    result1 = det1.slide_match(block_bytes, bg_bytes, simple_target=True)
    print(f"Method 1 (slide_match simple_target=True): {result1}")
except Exception as e:
    print(f"Method 1 error: {e}")

# Method 2: slide_match without simple_target
try:
    det2 = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)
    result2 = det2.slide_match(block_bytes, bg_bytes, simple_target=False)
    print(f"Method 2 (slide_match simple_target=False): {result2}")
except Exception as e:
    print(f"Method 2 error: {e}")

# Method 3: slide_comparison (compares two bg images)
# This needs the original bg (without gap) which we don't have

# Method 4: Use PIL to detect the gap by image processing
print("\n=== PIL-based gap detection ===")
from PIL import Image, ImageFilter
import numpy as np

bg_img = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
block_img = Image.open(io.BytesIO(block_bytes)).convert("RGBA")
print(f"BG: {bg_img.size}, Block: {block_img.size}")

# Convert to grayscale for edge detection
bg_gray = bg_img.convert("L")
block_gray = block_img.convert("L")

# Detect gap by looking for the dark rectangular hole in the bg
bg_arr = np.array(bg_gray)
# The gap area is typically darker/different from surroundings
# Look for columns with significant brightness changes
col_var = np.var(bg_arr, axis=0)
print(f"Column variance: min={col_var.min():.0f} max={col_var.max():.0f} mean={col_var.mean():.0f}")

# Edge detection
bg_edges = bg_img.convert("L").filter(ImageFilter.FIND_EDGES)
edge_arr = np.array(bg_edges)
col_edge_sum = np.sum(edge_arr, axis=0)
# The gap boundaries should have strong vertical edges
# Find peaks in edge sum
threshold = col_edge_sum.mean() + col_edge_sum.std() * 2
peaks = np.where(col_edge_sum > threshold)[0]
if len(peaks) > 0:
    # Find clusters of peaks (gap left and right boundaries)
    clusters = []
    current_cluster = [peaks[0]]
    for i in range(1, len(peaks)):
        if peaks[i] - peaks[i-1] <= 5:
            current_cluster.append(peaks[i])
        else:
            clusters.append(current_cluster)
            current_cluster = [peaks[i]]
    clusters.append(current_cluster)
    
    print(f"Edge clusters ({len(clusters)}):")
    for i, c in enumerate(clusters):
        print(f"  cluster {i}: x={c[0]}-{c[-1]} (width={c[-1]-c[0]+1})")
    
    # The gap is typically 50-100px wide, look for a cluster gap matching block width
    block_w = block_img.size[0]
    for i in range(len(clusters)-1):
        gap_start = clusters[i][-1]
        gap_end = clusters[i+1][0]
        gap_w = gap_end - gap_start
        if abs(gap_w - block_w) < 30:
            gap_center = (gap_start + gap_end) // 2
            print(f"  >>> Likely gap: x={gap_start}-{gap_end} (w={gap_w}, block_w={block_w}), center={gap_center}")
else:
    print("No significant edge peaks found")

# Method 5: Template matching via numpy correlation
print("\n=== Template matching ===")
# Simple approach: slide block across bg and find best match position
bg_arr = np.array(bg_img.convert("RGB")).astype(float)
block_arr = np.array(block_img.convert("RGB")).astype(float)
# Use alpha channel of block as mask
block_alpha = np.array(block_img)[:,:,3] > 128 if block_img.mode == "RGBA" else np.ones(block_arr.shape[:2], bool)

bh, bw = block_arr.shape[:2]
best_x = 0
best_score = float('inf')
scores = []
for x in range(0, bg_arr.shape[1] - bw):
    region = bg_arr[:bh, x:x+bw]
    diff = np.abs(region - block_arr[:,:,:3])
    masked_diff = diff[block_alpha]
    score = np.mean(masked_diff)
    scores.append(score)
    if score < best_score:
        best_score = score
        best_x = x

print(f"Template match best: x={best_x} score={best_score:.1f}")
# Also find local minima
scores_arr = np.array(scores)
# Top-5 matches
top5 = np.argsort(scores_arr)[:5]
print(f"Top-5 x positions: {list(top5)} scores: {[f'{scores_arr[x]:.1f}' for x in top5]}")
