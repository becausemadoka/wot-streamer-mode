# -*- coding: utf-8 -*-
"""Generate the Streamer Mode cover image.

Everything drawn here is original artwork -- no game assets, no client files.
The scene is an abstract "player list" with names masked, which is exactly what
the mod does.
"""
import io
import math

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1208, 680          # 4x of the 302x170 minimum requirement
import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cover.png')

FONT_DIR = 'C:/Windows/Fonts/'

def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)

# typefaces -- 圆角黑体 (simhei) 比雅黑粗更稳，视觉体积小一档
F_CN_TITLE   = font('simhei.ttf', 118)
F_EN_TITLE   = font('arialbd.ttf', 40)
F_TAGLINE_CN = font('msyh.ttc', 27)
F_TAGLINE_EN = font('arial.ttf', 19)
F_MONO       = font('consolab.ttf', 28)     # 伪等宽：昵称
F_MONO_SMALL = font('consolab.ttf', 17)
F_MONO_XS    = font('consolab.ttf', 17)
F_MASK       = font('consolab.ttf', 28)

def hex_rgb(s):
    s = s.lstrip('#')
    return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))

# palette: deep navy + a single signal amber
BG_TOP    = hex_rgb('#0D1420')
BG_BOTTOM = hex_rgb('#060A12')
PANEL     = hex_rgb('#141E2E')
PANEL_EDGE= hex_rgb('#243349')
TEXT_HI   = hex_rgb('#E8EDF5')
TEXT_MID  = hex_rgb('#8A9BB4')
TEXT_LOW  = hex_rgb('#4E5F7A')
AMBER     = hex_rgb('#F5B53F')
AMBER_DIM = hex_rgb('#7A5A1E')
GREEN     = hex_rgb('#63C07A')
RED       = hex_rgb('#E0604E')

def vgradient(size, top, bottom):
    """Vertical gradient background."""
    w, h = size
    img = Image.new('RGB', (w, h))
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return img

def soft_glow(img, cx, cy, radius, color, strength):
    """Radial glow, composited additively."""
    glow = Image.new('L', img.size, 0)
    d = ImageDraw.Draw(glow)
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=strength)
    glow = glow.filter(ImageFilter.GaussianBlur(radius * 0.75))
    layer = Image.new('RGB', img.size, color)
    return Image.composite(layer, img, glow.point(lambda v: int(v * 0.32)))

def rounded(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill,
                           outline=outline, width=width)

def text_size(d, text, fnt):
    bbox = d.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

img = vgradient((W, H), BG_TOP, BG_BOTTOM)
qx = ImageDraw.Draw(img, 'RGBA')

# faint diagonal scanlines for a "screen" feel
for y in range(0, H, 6):
    qx.line([(0, y), (W, y)], fill=(255, 255, 255, 7), width=1)
# vignette
qx.rectangle([0, 0, W, H], outline=(0, 0, 0, 120), width=34)

img = soft_glow(img, int(W * 0.30), int(H * 0.30), 340, hex_rgb('#12233A'), 200)
qx = ImageDraw.Draw(img, 'RGBA')

# ---------------------------------------------------------------- layout --
# left: title block.  right: the mock "battle player list"
pad = 54
left_w = 470

# ---- left: kicker + title + tagline + badges
qx.text((pad, 96), 'TANK MODS', font=F_TAGLINE_EN, fill=AMBER)
qx.text((pad, 116), '主播模式', font=F_CN_TITLE, fill=TEXT_HI)
qx.text((pad, 244), 'Streamer Mode', font=F_EN_TITLE, fill=TEXT_HI)
qx.text((pad, 300), '直播时，路人昵称不上屏', font=F_TAGLINE_CN, fill=TEXT_MID)
qx.text((pad, 336), 'The stream hides everyone but you.',
        font=F_TAGLINE_EN, fill=TEXT_LOW)

# small chips
chip_y = 426
chips = [('Player_001', AMBER), ('MIT', TEXT_MID), ('2.4.1', TEXT_MID)]
cx = pad
for label, color in chips:
    w, h = text_size(qx, label, F_MONO_XS)
    rounded(qx, [cx, chip_y, cx + w + 30, chip_y + h + 18],
            12, fill=(255, 255, 255, 10), outline=PANEL_EDGE, width=1)
    qx.text((cx + 15, chip_y + 8), label, font=F_MONO_XS, fill=color)
    cx += w + 30 + 18

# ---- right: mock scoreboard panel
px = left_w + pad
pw = W - px - pad
ph = 470
py = 118

rounded(qx, [px, py, px + pw, py + ph], 18, fill=PANEL, outline=PANEL_EDGE, width=2)
# header strip
qx.rectangle([px, py + 44, px + pw, py + 46], fill=PANEL_EDGE)
qx.text((px + 26, py + 14), 'BATTLE', font=F_MONO_XS, fill=TEXT_MID)
# fake window dots
for i, c in enumerate((RED, AMBER, GREEN)):
    qx.ellipse([px + pw - 26 - i * 26, py + 15,
                px + pw - 12 - i * 26, py + 29], fill=c)

# rows -- use pure placeholders so no font coverage issue
rows = [
    ('Player_001', 'T-34-85',    82, TEXT_MID, False),
    ('Player_002', 'IS-3',        96, TEXT_MID, False),
    ('Bot_001',    'T-54',        64, TEXT_LOW, False),
    ('You',        'Object 277', 100, TEXT_HI,  True),
]
ry = py + 72
bar_h = 15
for name, tank, hp, color, is_self in rows:
    if is_self:
        rounded(qx, [px + 18, ry - 6, px + pw - 18, ry + 64], 10,
                fill=(245, 181, 63, 26))

    qx.text((px + 30, ry), name, font=F_MONO, fill=color)
    bar_y = ry + 34
    bx = px + 30
    bw = pw - 60
    qx.text((px + 30, bar_y), tank, font=F_MONO_XS, fill=TEXT_LOW)
    rounded(qx, [bx, bar_y + 20, bx + bw, bar_y + 20 + bar_h], bar_h // 2,
            fill=(255, 255, 255, 14))
    rounded(qx, [bx, bar_y + 20, bx + int(bw * hp / 100), bar_y + 20 + bar_h],
            bar_h // 2, fill=(AMBER if is_self else GREEN))
    ry += 82

# callout: masked-stranger callout
qx.text((px + 26, py + ph - 28), 'Player_001  =  masked',
        font=F_MONO_XS, fill=AMBER)

# ---- footer strip
qx.rectangle([0, H - 46, W, H], fill=(6, 9, 16))
qx.line([(0, H - 46), (W, H - 46)], fill=PANEL_EDGE, width=1)
qx.text((pad, H - 34), 'AKEMI.STREAMERMODE', font=F_MONO_XS, fill=TEXT_MID)
right_note = 'ONLY YOU SEE THE REAL NAMES'
w, _ = text_size(qx, right_note, F_MONO_XS)
qx.text((W - pad - w, H - 34), right_note, font=F_MONO_XS, fill=AMBER)

img.save(OUT, 'PNG', optimize=True)

# report
buf = io.BytesIO()
img.save(buf, 'PNG')
print('saved', OUT)
print('size  %dx%d  bytes=%d' % (img.width, img.height, len(buf.getvalue())))
