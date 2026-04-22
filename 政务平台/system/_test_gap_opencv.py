"""Test gap detection with OpenCV template matching on saved images."""
import cv2
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bg_path = ROOT / "dashboard/data/records/slider_bg.png"
block_path = ROOT / "dashboard/data/records/slider_block.png"

bg = cv2.imdecode(np.fromfile(str(bg_path), dtype=np.uint8), cv2.IMREAD_COLOR)
block = cv2.imdecode(np.fromfile(str(block_path), dtype=np.uint8), cv2.IMREAD_COLOR)
print(f"BG: {bg.shape}, Block: {block.shape}")

# Method 1: Direct template matching on grayscale
bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
block_gray = cv2.cvtColor(block, cv2.COLOR_BGR2GRAY)

result1 = cv2.matchTemplate(bg_gray, block_gray, cv2.TM_CCOEFF_NORMED)
_, max_val1, _, max_loc1 = cv2.minMaxLoc(result1)
print(f"Method 1 (TM_CCOEFF_NORMED grayscale): x={max_loc1[0]} conf={max_val1:.4f}")

# Method 2: Canny edge matching (more robust for slider captchas)
bg_edges = cv2.Canny(bg_gray, 100, 200)
block_edges = cv2.Canny(block_gray, 100, 200)

result2 = cv2.matchTemplate(bg_edges, block_edges, cv2.TM_CCOEFF_NORMED)
_, max_val2, _, max_loc2 = cv2.minMaxLoc(result2)
print(f"Method 2 (Canny edges TM_CCOEFF_NORMED): x={max_loc2[0]} conf={max_val2:.4f}")

# Method 3: TM_CCORR_NORMED on edges
result3 = cv2.matchTemplate(bg_edges, block_edges, cv2.TM_CCORR_NORMED)
_, max_val3, _, max_loc3 = cv2.minMaxLoc(result3)
print(f"Method 3 (Canny edges TM_CCORR_NORMED): x={max_loc3[0]} conf={max_val3:.4f}")

# Method 4: Using alpha channel as mask
block_rgba = cv2.imdecode(np.fromfile(str(block_path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
if block_rgba.shape[2] == 4:
    mask = block_rgba[:, :, 3]
    print(f"Block has alpha channel, mask non-zero: {np.count_nonzero(mask)}/{mask.size}")
    # Template match with mask
    result4 = cv2.matchTemplate(bg_gray, block_gray, cv2.TM_CCORR_NORMED, mask=mask)
    _, max_val4, _, max_loc4 = cv2.minMaxLoc(result4)
    print(f"Method 4 (masked TM_CCORR_NORMED): x={max_loc4[0]} conf={max_val4:.4f}")
    
    result5 = cv2.matchTemplate(bg_gray, block_gray, cv2.TM_CCOEFF_NORMED, mask=mask)
    _, max_val5, _, max_loc5 = cv2.minMaxLoc(result5)
    print(f"Method 5 (masked TM_CCOEFF_NORMED): x={max_loc5[0]} conf={max_val5:.4f}")

# Pick best
print(f"\nBest candidate: x={max_loc2[0]} (Canny edge matching)")
print(f"In 695-wide image, x={max_loc2[0]} is at {max_loc2[0]/695*100:.1f}% from left")
print(f"With scale=585/695=0.842, display drag from bar left = {max_loc2[0]*585/695:.0f}px")
