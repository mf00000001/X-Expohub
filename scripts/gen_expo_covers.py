#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_expo_covers.py — 为演示用展会批量生成「虚拟封面图」（本地生成, 离线可用）

设计
====
纯几何抽象风格：深色渐变底 + 大面积柔光斑 + 细斜线纹理 + 主题几何母题
（圆环/节点网络/齿轮/射线/脉冲线）。不含任何文字 —— 页面卡片与详情页头图
都会在图片上叠加标题文字，图中若再带字会冲突。

产出
====
- expo-hub-frontend/public/covers/<slug>.png  8 张主题封面 (1600x660)
- expo-hub-frontend/public/placeholder-expo.jpg  通用占位图（无封面展会兜底）
- docs/evidence/covers-preview.png  拼版预览（人工/机器审阅用, --sheet 生成）

用法
====
    python scripts/gen_expo_covers.py        # 生成图片并更新库中 cover_image
    python scripts/gen_expo_covers.py --sheet  # 额外输出拼版预览图
    python scripts/gen_expo_covers.py --no-db  # 只生成图片, 不动数据库
"""
import argparse
import math
import random
import sqlite3
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parents[1]
PUBLIC = REPO / "expo-hub-frontend" / "public"
COVERS = PUBLIC / "covers"
DEFAULT_DB = REPO / "expohub-backend" / "expohub.db"
EVIDENCE = REPO / "docs" / "evidence"

W, H = 1600, 660

# slug -> (标题关键词, 色组: 顶部色/底部色/主题强调色, 母题)
THEMES = {
    "expo-ai-2026": ("人工智能产业交流会", (0x0F, 0x17, 0x2A), (0x4C, 0x1D, 0x95), (0x8B, 0x5C, 0xF6), "nodes"),
    "expo-manufacturing-2026": ("智能制造与工业互联网", (0x0B, 0x1B, 0x3A), (0x1E, 0x3A, 0x8A), (0x3B, 0x82, 0xF6), "gear"),
    "expo-energy-2026": ("新能源与碳中和", (0x05, 0x2E, 0x2B), (0x04, 0x78, 0x57), (0x34, 0xD3, 0x99), "rays"),
    "expo-medical-2026": ("智慧医疗与健康", (0x04, 0x33, 0x3F), (0x0E, 0x74, 0x90), (0x22, 0xD3, 0xEE), "pulse"),
    "expo-electronics-2026": ("消费电子与智能生活", (0x2A, 0x0A, 0x33), (0x6B, 0x21, 0xA8), (0xC0, 0x84, 0xFC), "rings"),
    "expo-aidigital-2027": ("AI与数字经济", (0x10, 0x17, 0x33), (0x37, 0x30, 0xA3), (0x81, 0x8C, 0xF8), "nodes"),
    "expo-medical-2025": ("医疗器械与康复健康", (0x08, 0x33, 0x44), (0x15, 0x5E, 0x75), (0x67, 0xE8, 0xF9), "cross"),
    "expo-food-2026": ("食品加工与消费品", (0x3A, 0x1D, 0x07), (0xB4, 0x53, 0x09), (0xFB, 0xBF, 0x24), "waves"),
}


def _rgb(c):
    return (c[0], c[1], c[2])


def vertical_gradient(top, bottom):
    """1px 竖条渐变再横向拉伸, 比逐像素快得多"""
    strip = Image.new("RGB", (1, H))
    d = ImageDraw.Draw(strip)
    for y in range(H):
        t = y / (H - 1)
        d.point((0, y), fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return strip.resize((W, H))


def add_glow(img, cx, cy, r, color, alpha):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_rgb(color) + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=r * 0.55))
    img.alpha_composite(layer)


def add_diagonal_lines(img, color=(255, 255, 255), alpha=10, spacing=46):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x in range(-H, W + H, spacing):
        d.line([(x, H), (x + H, 0)], fill=color + (alpha,), width=1)
    img.alpha_composite(layer)


def add_dot_grid(img, x0, y0, cols, rows, step, radius=3, color=(255, 255, 255), alpha=26):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(cols):
        for j in range(rows):
            cx, cy = x0 + i * step, y0 + j * step
            d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=color + (alpha,))
    img.alpha_composite(layer)


def motif_rings(img, accent):
    d = ImageDraw.Draw(img)
    cx, cy = 1280, 300
    for i, r in enumerate((230, 170, 112, 62)):
        a = 34 + i * 16
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=accent + (a,), width=4)
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=accent + (235,))


def motif_nodes(img, accent, seed=7):
    rng = random.Random(seed)
    d = ImageDraw.Draw(img)
    pts = []
    for i in range(9):
        ang = -0.55 + i * 0.40
        rad = 100 + (i % 3) * 92
        pts.append((1315 + math.cos(ang) * rad * 1.2, 320 + math.sin(ang) * rad * 0.78))
    # 每个节点最多连最近的 2 条线，避免交叉过密成一团
    for i, a in enumerate(pts):
        dists = sorted(
            ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2, j)
            for j, b in enumerate(pts) if j != i
        )
        for dist, j in dists[:2]:
            if dist < 200 ** 2 and j > i:
                d.line([a, pts[j]], fill=accent + (58,), width=2)
    for i, p in enumerate(pts):
        r = 15 if i % 3 else 25
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=accent + (215,))


def motif_gear(img, accent):
    d = ImageDraw.Draw(img)
    cx, cy, r = 1290, 320, 185
    half = 17  # 轮齿半宽
    # 厚轮体
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=accent + (185,), width=36)
    # 轮齿：从轮体外缘向外伸出的粗短线（不悬空）
    for k in range(12):
        ang = k * math.pi / 6
        ca, sa = math.cos(ang), math.sin(ang)
        x1, y1 = cx + ca * (r + 12), cy + sa * (r + 12)
        x2, y2 = cx + ca * (r + 46), cy + sa * (r + 46)
        d.line([(x1, y1), (x2, y2)], fill=accent + (185,), width=24)
    # 内圈 + 轮毂
    d.ellipse([cx - 92, cy - 92, cx + 92, cy + 92], outline=accent + (110,), width=7)
    d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=accent + (225,))


def motif_rays(img, accent):
    """日出/阳光：低悬的太阳圆盘 + 以其为中心的扇形光束"""
    d = ImageDraw.Draw(img)
    cx, cy = 1330, 630
    # 背后大弧增加层次
    d.arc([cx - 300, cy - 300, cx + 300, cy + 300], 200, 340, fill=accent + (62,), width=5)
    # 光束：围绕太阳向上的扇形（近太阳起笔, 中部更长）
    for i in range(11):
        ang = math.radians(192 + i * 15.6)
        ca, sa = math.cos(ang), math.sin(ang)
        r1 = 96
        r2 = 96 + (58 if 3 <= i <= 7 else 38)
        d.line([(cx + ca * r1, cy + sa * r1), (cx + ca * r2, cy + sa * r2)],
               fill=accent + (140,), width=8)
    # 太阳圆盘（略低于画面底边, 呈半升之势）
    d.ellipse([cx - 72, cy - 72, cx + 72, cy + 72], fill=accent + (230,))


def motif_pulse(img, accent):
    d = ImageDraw.Draw(img)
    y0 = 330
    pts = [(980, y0)]
    seq = [(60, 0), (34, -58), (30, 116), (46, -176), (34, 118), (52, -40), (46, 40), (110, 0)]
    x, y = 980, y0
    for dx, dy in seq:
        x += dx
        y = y0 + dy
        pts.append((x, y))
    pts.append((1620, y0))
    d.line(pts, fill=accent + (210,), width=9, joint="curve")
    d.ellipse([968, y0 - 12, 992, y0 + 12], fill=accent + (240,))


def motif_cross(img, accent):
    d = ImageDraw.Draw(img)
    cx, cy, L, w = 1290, 320, 150, 52
    d.rectangle([cx - w / 2, cy - L, cx + w / 2, cy + L], fill=accent + (215,))
    d.rectangle([cx - L, cy - w / 2, cx + L, cy + w / 2], fill=accent + (215,))
    for i, r in enumerate((250, 300)):
        d.arc([cx - r, cy - r, cx + r, cy + r], 200 + i * 25, 340 - i * 25, fill=accent + (80,), width=5)


def motif_waves(img, accent):
    d = ImageDraw.Draw(img)
    cx, cy = 1310, 560
    for i in range(5):
        r = 130 + i * 95
        d.arc([cx - r, cy - r, cx + r, cy + r], 190, 350, fill=accent + (95 - i * 12,), width=8)
    d.ellipse([cx - 46, cy - 46, cx + 46, cy + 46], fill=accent + (225,))


MOTIFS = {
    "rings": motif_rings, "nodes": motif_nodes, "gear": motif_gear,
    "rays": motif_rays, "pulse": motif_pulse, "cross": motif_cross, "waves": motif_waves,
}


def gen_cover(slug, meta):
    _title_kw, top, bottom, accent, motif = meta
    img = vertical_gradient(top, bottom).convert("RGBA")
    add_glow(img, 240, 120, 330, (255, 255, 255), 14)
    add_glow(img, 1330, 520, 430, accent, 46)
    add_glow(img, 1080, 90, 250, accent, 30)
    add_diagonal_lines(img, alpha=9)
    add_dot_grid(img, 120, 430, 7, 5, 34, radius=3, alpha=30)
    # 底部轻微压暗，给页面标题叠字留层次
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(H - 200, H):
        t = (y - (H - 200)) / 200
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, int(70 * t)))
    img.alpha_composite(shade)
    MOTIFS[motif](img, accent)
    out = COVERS / f"{slug}.png"
    img.convert("RGB").save(out, quality=95)
    return out


def gen_placeholder():
    img = vertical_gradient((0x1F, 0x29, 0x37), (0x37, 0x41, 0x51)).convert("RGBA")
    add_glow(img, 800, 330, 420, (0xFF, 0xFF, 0xFF), 12)
    add_diagonal_lines(img, alpha=8)
    add_dot_grid(img, 140, 420, 6, 4, 36, alpha=24)
    d = ImageDraw.Draw(img)
    cx, cy = 800, 300
    d.ellipse([cx - 120, cy - 120, cx + 120, cy + 120], outline=(255, 255, 255, 90), width=8)
    d.ellipse([cx - 58, cy - 58, cx + 58, cy + 58], outline=(255, 255, 255, 60), width=6)
    d.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=(255, 255, 255, 150))
    out = PUBLIC / "placeholder-expo.jpg"
    img.convert("RGB").save(out, quality=90)
    return out


def make_sheet(paths):
    cols, rows = 2, 4
    tw, th = 640, 264
    pad = 18
    sheet = Image.new("RGB", (cols * tw + pad * (cols + 1), rows * th + pad * (rows + 1)), (24, 26, 32))
    for i, p in enumerate(paths):
        im = Image.open(p).resize((tw, th))
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (th + pad)
        sheet.paste(im, (x, y))
    out = EVIDENCE / "covers-preview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def update_db(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    n = 0
    for slug, (kw, *_rest) in THEMES.items():
        rows = conn.execute("SELECT id FROM exhibitions WHERE title LIKE ?", (f"%{kw}%",)).fetchall()
        for (eid,) in rows:
            conn.execute("UPDATE exhibitions SET cover_image = ? WHERE id = ?", (f"/covers/{slug}.png", eid))
            print(f"  #{eid} <- /covers/{slug}.png")
            n += 1
    conn.commit()
    conn.close()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true", help="输出拼版预览到 docs/evidence/")
    ap.add_argument("--no-db", action="store_true", help="不更新数据库")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()

    COVERS.mkdir(parents=True, exist_ok=True)
    paths = []
    for slug, meta in THEMES.items():
        p = gen_cover(slug, meta)
        paths.append(p)
        print(f"封面 {p.relative_to(REPO)}")
    ph = gen_placeholder()
    print(f"占位 {ph.relative_to(REPO)}")
    if args.sheet:
        print(f"拼版 {make_sheet(paths).relative_to(REPO)}")
    if not args.no_db:
        n = update_db(args.db)
        print(f"数据库更新 {n} 行")


if __name__ == "__main__":
    main()
