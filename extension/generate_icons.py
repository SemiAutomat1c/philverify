"""
Generate PhilVerify extension icons (16×16, 32×32, 48×48, 128×128 PNG).
Requires Pillow: pip install Pillow
Run from the extension/ directory: python generate_icons.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

SIZES = [16, 32, 48, 128]
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'icons')
os.makedirs(OUTPUT_DIR, exist_ok=True)

BG_COLOR   = (13, 13, 13, 255)       # --bg-base
RED_COLOR  = (220, 38, 38, 255)      # --accent-red
TEXT_COLOR = (245, 240, 232, 255)    # --text-primary


def make_icon(size: int) -> Image.Image:
    img  = Image.new('RGBA', (size, size), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Red left-edge accent bar (3px scaled)
    bar_width = max(2, size // 10)
    draw.rectangle([0, 0, bar_width - 1, size - 1], fill=RED_COLOR)

    # 'PV' text label — only draw text on larger icons where it looks clean
    font_size = max(6, int(size * 0.38))
    font = None
    for path in [
        '/System/Library/Fonts/Helvetica.ttc',
        '/System/Library/Fonts/SFNSDisplay.ttf',
        '/System/Library/Fonts/ArialHB.ttc',
    ]:
        try:
            font = ImageFont.truetype(path, font_size)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    if size >= 32:
        text = 'PV'
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            tx = bar_width + (size - bar_width - tw) // 2
            ty = (size - th) // 2 - bbox[1]
            draw.text((tx, ty), text, fill=TEXT_COLOR, font=font)
        except Exception:
            pass  # Skip text on render error — icon still has the red bar

    return img


for sz in SIZES:
    icon_path = os.path.join(OUTPUT_DIR, f'icon{sz}.png')
    make_icon(sz).save(icon_path, 'PNG')
    print(f'✓ icons/icon{sz}.png')

print('Icons generated in extension/icons/')
